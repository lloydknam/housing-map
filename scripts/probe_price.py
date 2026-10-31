#!/usr/bin/env python3
"""가격 통계표의 항목·분류 코드를 요약해 data/_probe_price.json 에 저장하는 탐색용 스크립트(일회용)."""
import json, os, re, sys, urllib.parse, urllib.request
from pathlib import Path

KEY = os.environ.get("KOSIS_API_KEY", "").strip()
OUT = Path(__file__).resolve().parent.parent / "data" / "_probe_price.json"
TABLES = ["DT_KAB_11672_S1", "DT_40803_N0001", "DT_30404_C012", "DT_30404_C013", "DT_40803_N0002", "DT_KAB_11672_S15"]


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "housing-map/1.0"})
    with urllib.request.urlopen(req, timeout=90) as r:
        body = r.read().decode("utf-8")
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return json.loads(re.sub(r"([{,])\s*([A-Za-z_][A-Za-z0-9_]*)\s*:", r'\1"\2":', body))


def main():
    out = {}
    for t in TABLES:
        e = {}
        for typ in ("ITM", "OBJ"):
            q = urllib.parse.urlencode({"method": "getMeta", "type": typ, "format": "json", "jsonVD": "Y",
                                        "orgId": "408", "tblId": t, "apiKey": KEY})
            try:
                res = get("https://kosis.kr/openapi/statisticsData.do?" + q)
            except Exception as ex:  # noqa: BLE001
                e[typ] = f"ERR {type(ex).__name__}: {ex}"[:200]
                continue
            comp = {}
            if isinstance(res, list):
                for it in res:
                    comp.setdefault(f"{it.get('OBJ_ID')}:{it.get('OBJ_NM')}:{it.get('OBJ_ID_SN','')}", []).append(
                        f"{it.get('ITM_ID')}={it.get('ITM_NM')}" + (f"({it.get('UNIT_NM')})" if it.get("UNIT_NM") else ""))
            else:
                comp = res
            e[typ] = comp
        out[t] = e
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
