#!/usr/bin/env python3
"""KOSIS(국가통계포털) OpenAPI에서 시도별 월간 주택통계를 받아 data/housing.json에 병합한다.

- config/sources.json 의 url_template 이 채워진 지표만 처리한다.
- API 키는 환경변수 KOSIS_API_KEY 로 받는다 (GitHub Secret).
- 이미 저장된 과거 월은 유지하고, 새로 받은 월은 덮어쓴다.
- "cumulative": true 인 지표(월별 누계 표)는 전월 누계를 빼서 월 값으로 환산한다.
- 광주·전남은 2026년 중반부터 '전남광주' 한 행으로 공표된다. 지도·시계열이 끊기지 않도록
  세 이름을 모두 코드 2436(전남광주)으로 합친다. 같은 월에 '전남광주'가 있으면 그것만 쓰고,
  없으면 광주+전남을 더한다.
- 실행 결과 요약은 data/_fetch_log.json 에 남긴다 (키는 기록하지 않는다).
"""
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "sources.json"
OUT = ROOT / "data" / "housing.json"
LOG = ROOT / "data" / "_fetch_log.json"

# 시도 표준코드(행정구역 앞 2자리) — 지도 GeoJSON의 code와 동일. 광주·전남은 아래 MERGED 로 처리.
ALIASES = {
    "11": ["서울", "서울특별시"],
    "21": ["부산", "부산광역시"],
    "22": ["대구", "대구광역시"],
    "23": ["인천", "인천광역시"],
    "25": ["대전", "대전광역시"],
    "26": ["울산", "울산광역시"],
    "29": ["세종", "세종시", "세종특별자치시"],
    "31": ["경기", "경기도"],
    "32": ["강원", "강원도", "강원특별자치도"],
    "33": ["충북", "충청북도"],
    "34": ["충남", "충청남도"],
    "35": ["전북", "전라북도", "전북특별자치도"],
    "37": ["경북", "경상북도"],
    "38": ["경남", "경상남도"],
    "39": ["제주", "제주도", "제주특별자치도"],
}
NAME_TO_CODE = {n: c for c, names in ALIASES.items() for n in names}
MERGED_CODE = "2436"
PART = {  # 이름 → 구성요소
    "광주": "GJ", "광주광역시": "GJ",
    "전남": "JN", "전라남도": "JN",
    "전남광주": "JG", "전남광주특별시": "JG", "전남광주통합특별시": "JG",
}


def to_month(prd):
    m = re.fullmatch(r"(\d{4})(\d{2})", str(prd).strip())
    return f"{m.group(1)}-{m.group(2)}" if m else None


def to_number(raw):
    s = str(raw).replace(",", "").strip()
    if s in ("", "-", "…", "X"):
        return None
    try:
        v = float(s)
    except ValueError:
        return None
    return int(v) if v.is_integer() else v


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "housing-map/1.0"})
    with urllib.request.urlopen(req, timeout=90) as resp:
        body = resp.read().decode("utf-8")
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        fixed = re.sub(r"([{,])\s*([A-Za-z_][A-Za-z0-9_]*)\s*:", r'\1"\2":', body)
        return json.loads(fixed)


def to_monthly(series):
    """월별 누계 → 월 값. 1월은 누계 그대로, 그 외는 전월 누계와의 차.

    누계는 줄어들 수 없으므로, 앞선 달보다 작아진 값(예: 일부 달이 0으로 비어 온 경우)은 결측으로 본다.
    결측 달과 그 다음 달(전월 누계가 없어 월 값을 만들 수 없음)은 건너뛴다.
    """
    valid, last = {}, 0
    for m in sorted(series):
        y, mm = m.split("-")
        if mm == "01":
            last = 0
        v = series[m]
        if v < last:  # 누계가 줄었다 = 결측
            continue
        valid[m] = v
        last = v
    out = {}
    for m in sorted(valid):
        y, mm = m.split("-")
        if mm == "01":
            out[m] = valid[m]
            continue
        prev = f"{y}-{int(mm) - 1:02d}"
        if prev in valid:
            out[m] = valid[m] - valid[prev]
    return out


def collect(metric, api_key, rows=None):
    if rows is None:
        url = metric["url_template"].replace("{API_KEY}", api_key)
        rows = fetch(url)
    if isinstance(rows, dict):
        raise RuntimeError(f"KOSIS 오류 응답: {rows.get('err')} {rows.get('errMsg', '')}".strip())
    rf, pf, vf = metric["region_field"], metric["period_field"], metric["value_field"]
    filters = metric.get("filters", {})
    if metric.get("code_map"):  # 지수 계열: 분류코드로 시도를 지정한다(합산·이름 매칭 없음). 00 은 전국.
        cf, cmap, out = metric["code_field"], metric["code_map"], {}
        for row in rows:
            if any(str(row.get(k)) != str(v) for k, v in filters.items()):
                continue
            code, month, value = cmap.get(str(row.get(cf, "")).strip()), to_month(row.get(pf, "")), to_number(row.get(vf))
            if code is None or month is None or value is None:
                continue
            if month in out.get(code, {}):
                raise RuntimeError(f"(시도, 월) 중복: {code} {month}")
            out.setdefault(code, {})[month] = value
        # 광주·전남 지수는 합산할 수 없다. 전남광주 통합 지수가 시작되기 전(기준월=100)에는 두 지수를
        # 기준월 대비로 환산해 단순평균한 값으로 이어 붙인다(근사치).
        gj, jn, jg = out.pop("GJ", None), out.pop("JN", None), out.get(MERGED_CODE, {})
        if gj and jn and jg:
            base = min(jg)
            if base in gj and base in jn:
                for m in sorted(set(gj) & set(jn)):
                    if m not in jg:
                        jg[m] = round(jg[base] * ((gj[m] / gj[base] + jn[m] / jn[base]) / 2), 4)
                out[MERGED_CODE] = dict(sorted(jg.items()))
        return out
    by_key, seen = {}, {}
    for row in rows:
        if any(str(row.get(k)) != str(v) for k, v in filters.items()):
            continue
        name = str(row.get(rf, "")).strip()
        code = NAME_TO_CODE.get(name) or PART.get(name)
        month = to_month(row.get(pf, ""))
        value = to_number(row.get(vf))
        if code is None or month is None or value is None:
            continue
        key = (code, month)
        seen[key] = seen.get(key, 0) + 1
        by_key[key] = value
    dups = [k for k, n in seen.items() if n > 1]
    if dups:
        raise RuntimeError(
            f"(시도, 월) 중복 {len(dups)}건 — config의 filters로 분류를 하나로 좁혀주세요. 예: {dups[0]}"
        )

    out = {}
    for (code, month), v in by_key.items():
        if code in PART.values():
            continue
        out.setdefault(code, {})[month] = v
    months = {m for (c, m) in by_key if c in PART.values()}
    for m in months:
        jg, gj, jn = by_key.get(("JG", m)), by_key.get(("GJ", m)), by_key.get(("JN", m))
        if jg is not None:
            v = jg
        elif gj is not None or jn is not None:
            v = (gj or 0) + (jn or 0)
        else:
            continue
        out.setdefault(MERGED_CODE, {})[m] = v

    if metric.get("cumulative"):
        out = {c: to_monthly(s) for c, s in out.items()}
    return out


def main():
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    store = json.loads(OUT.read_text(encoding="utf-8"))
    log = {"run": datetime.now(timezone(timedelta(hours=9))).isoformat(timespec="seconds"), "metrics": {}}
    todo = [m for m in cfg["metrics"] if m.get("url_template", "").strip()]
    if not todo:
        print("url_template 이 설정된 지표가 없어 건너뜁니다. config/sources.json 을 채워주세요.")
        return 0
    api_key = os.environ.get("KOSIS_API_KEY", "").strip()
    if not api_key:
        print("KOSIS_API_KEY 환경변수가 없습니다.", file=sys.stderr)
        return 1

    failed = 0
    for metric in todo:
        mid = metric["id"]
        try:
            fresh = collect(metric, api_key)
        except (urllib.error.URLError, RuntimeError, json.JSONDecodeError) as e:
            msg = str(e).replace(api_key, "***")[:300]
            print(f"[{mid}] 실패: {msg}", file=sys.stderr)
            log["metrics"][mid] = {"status": "error", "error": msg}
            failed += 1
            continue
        if metric.get("cumulative"):  # 환산 규칙이 바뀌면 과거 값도 다시 계산해야 하므로 통째로 교체한다
            store.setdefault("data", {})[mid] = {}
        cur = store.setdefault("data", {}).setdefault(mid, {})
        for code, months in fresh.items():
            cur.setdefault(code, {}).update(months)
        all_m = sorted({m for s in fresh.values() for m in s})
        sums = ({m: fresh.get("00", {}).get(m) for m in all_m[-4:]} if metric.get("code_map")
                else {m: sum(s.get(m, 0) for s in fresh.values()) for m in all_m[-4:]})
        log["metrics"][mid] = {"status": "ok", "regions": len(fresh), "months": [all_m[0], all_m[-1]] if all_m else [],
                               "latest_sums": sums}
        print(f"[{mid}] {sum(len(v) for v in fresh.values())}개 값 병합")

    for mid, regions in store.get("data", {}).items():
        store["data"][mid] = {c: dict(sorted(regions[c].items())) for c in sorted(regions)}
    all_months = sorted({m for regions in store.get("data", {}).values() for ms in regions.values() for m in ms})
    store["latest"] = all_months[-1] if all_months else None
    store["updated"] = datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d")

    OUT.write_text(json.dumps(store, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    LOG.write_text(json.dumps(log, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
