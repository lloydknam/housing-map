#!/usr/bin/env python3
"""KOSIS(국가통계포털) OpenAPI에서 시도별 월간 주택통계를 받아 data/housing.json에 병합한다.

- config/sources.json 의 url_template 이 채워진 지표만 처리한다.
- API 키는 환경변수 KOSIS_API_KEY 로 받는다 (GitHub Secret).
- 이미 저장된 과거 월은 유지하고, 새로 받은 월은 덮어쓴다.
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

# 시도 표준코드(행정구역 앞 2자리) — 지도 GeoJSON의 code와 동일
ALIASES = {
    "11": ["서울", "서울특별시"],
    "21": ["부산", "부산광역시"],
    "22": ["대구", "대구광역시"],
    "23": ["인천", "인천광역시"],
    "24": ["광주", "광주광역시"],
    "25": ["대전", "대전광역시"],
    "26": ["울산", "울산광역시"],
    "29": ["세종", "세종시", "세종특별자치시"],
    "31": ["경기", "경기도"],
    "32": ["강원", "강원도", "강원특별자치도"],
    "33": ["충북", "충청북도"],
    "34": ["충남", "충청남도"],
    "35": ["전북", "전라북도", "전북특별자치도"],
    "36": ["전남", "전라남도"],
    "37": ["경북", "경상북도"],
    "38": ["경남", "경상남도"],
    "39": ["제주", "제주도", "제주특별자치도"],
}
NAME_TO_CODE = {n: c for c, names in ALIASES.items() for n in names}


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
    with urllib.request.urlopen(req, timeout=60) as resp:
        body = resp.read().decode("utf-8")
    # KOSIS 는 키를 `{...}` 형태의 비표준 JSON 으로 주기도 해서 느슨하게 보정한다.
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        fixed = re.sub(r"([{,])\s*([A-Za-z_][A-Za-z0-9_]*)\s*:", r'\1"\2":', body)
        return json.loads(fixed)


def collect(metric, api_key):
    url = metric["url_template"].replace("{API_KEY}", api_key)
    rows = fetch(url)
    if isinstance(rows, dict):
        raise RuntimeError(f"KOSIS 오류 응답: {rows.get('err')} {rows.get('errMsg', '')}".strip())
    rf, pf, vf = metric["region_field"], metric["period_field"], metric["value_field"]
    filters = metric.get("filters", {})
    out, seen = {}, {}
    for row in rows:
        if any(str(row.get(k)) != str(v) for k, v in filters.items()):
            continue
        code = NAME_TO_CODE.get(str(row.get(rf, "")).strip())
        month = to_month(row.get(pf, ""))
        value = to_number(row.get(vf))
        if code is None or month is None or value is None:
            continue
        key = (code, month)
        seen[key] = seen.get(key, 0) + 1
        out.setdefault(code, {})[month] = value
    dups = [k for k, n in seen.items() if n > 1]
    if dups:
        raise RuntimeError(
            f"(시도, 월) 중복 {len(dups)}건 — config의 filters로 분류를 하나로 좁혀주세요. 예: {dups[0]}"
        )
    return out


def main():
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    store = json.loads(OUT.read_text(encoding="utf-8"))
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
            print(f"[{mid}] 실패: {e}", file=sys.stderr)
            failed += 1
            continue
        cur = store.setdefault("data", {}).setdefault(mid, {})
        for code, months in fresh.items():
            cur.setdefault(code, {}).update(months)
        print(f"[{mid}] {sum(len(v) for v in fresh.values())}개 값 병합")

    # 정렬해서 diff 를 안정적으로 유지
    for mid, regions in store.get("data", {}).items():
        store["data"][mid] = {c: dict(sorted(regions[c].items())) for c in sorted(regions)}
    all_months = sorted({m for regions in store.get("data", {}).values() for ms in regions.values() for m in ms})
    store["latest"] = all_months[-1] if all_months else None
    store["updated"] = datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d")

    OUT.write_text(json.dumps(store, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
