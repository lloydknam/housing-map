#!/usr/bin/env python3
"""KOSIS 통합검색·메타 API로 주택 관련 통계표(orgId/tblId, 항목·분류 코드)를 찾아 data/_discovery.json 에 저장한다.

한 번 쓰고 버리는 탐색용 스크립트. 키는 결과 파일에 남기지 않는다.
"""
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

KEY = os.environ.get("KOSIS_API_KEY", "").strip()
OUT = Path(__file__).resolve().parent.parent / "data" / "_discovery.json"
SEARCH = "https://kosis.kr/openapi/statisticsSearch.do"
DATA = "https://kosis.kr/openapi/statisticsData.do"
KEYWORDS = ["주택건설실적", "주택건설 인허가", "주택 착공", "주택 준공", "주택 분양", "미분양"]
MUST = ("주택", "미분양", "인허가", "착공", "준공", "분양")


def call(base, params):
    shown = {k: v for k, v in params.items() if k != "apiKey"}
    url = base + "?" + urllib.parse.urlencode({**params, "apiKey": KEY})
    rec = {"base": base, "params": shown}
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "housing-map/1.0"})
        with urllib.request.urlopen(req, timeout=60) as r:
            body = r.read().decode("utf-8")
        try:
            rec["result"] = json.loads(body)
        except json.JSONDecodeError:
            fixed = re.sub(r"([{,])\s*([A-Za-z_][A-Za-z0-9_]*)\s*:", r'\1"\2":', body)
            rec["result"] = json.loads(fixed)
    except Exception as e:  # noqa: BLE001 — 탐색용이라 모든 실패를 기록만 한다
        rec["error"] = f"{type(e).__name__}: {e}"[:300]
    return rec


def trim(obj, n=300):
    if isinstance(obj, dict):
        return {k: trim(v, n) for k, v in obj.items()}
    if isinstance(obj, list):
        return [trim(v, n) for v in obj]
    return obj[:n] if isinstance(obj, str) else obj


def main():
    out = {"search": {}, "meta": {}}
    if not KEY:
        out["error"] = "KOSIS_API_KEY 없음"
        OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        return 0

    cands = {}
    for kw in KEYWORDS:
        for org in ("116", None):
            params = {"method": "getList", "searchNm": kw, "startCount": 1, "resultCount": 40,
                      "sort": "RANK", "format": "json", "jsonVD": "Y"}
            if org:
                params["orgId"] = org
            rec = call(SEARCH, params)
            out["search"][f"{kw}|{org or 'all'}"] = trim(rec)
            res = rec.get("result")
            if isinstance(res, list):
                for it in res:
                    tid, oid = it.get("TBL_ID"), it.get("ORG_ID")
                    text = json.dumps(it, ensure_ascii=False)
                    if tid and oid == "116" and any(m in text for m in MUST):
                        cands[(oid, tid)] = it.get("TBL_NM", "")

    cands[("116", "DT_MLTM_2082")] = cands.get(("116", "DT_MLTM_2082"), "시군구별 미분양현황(문서 기재)")
    cands[("116", "DT_MLTM_2086")] = cands.get(("116", "DT_MLTM_2086"), "미분양현황_종합(문서 기재)")
    out["candidates"] = [{"orgId": o, "tblId": t, "name": n} for (o, t), n in sorted(cands.items())]

    for (oid, tid) in list(sorted(cands))[:40]:
        entry = {}
        for typ in ("ITM", "OBJ"):
            rec = call(DATA, {"method": "getMeta", "type": typ, "format": "json", "jsonVD": "Y",
                              "orgId": oid, "tblId": tid})
            entry[typ] = trim(rec)
        out["meta"][f"{oid}/{tid}"] = entry

    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"후보 {len(cands)}개, 메타 {len(out['meta'])}개 저장")
    return 0


if __name__ == "__main__":
    sys.exit(main())
