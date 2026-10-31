#!/usr/bin/env python3
"""탐색으로 찾은 통계표에서 최근 2개월치를 실제로 받아 행 구조를 data/_probe.json 에 저장한다 (일회용)."""
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

KEY = os.environ.get("KOSIS_API_KEY", "").strip()
OUT = Path(__file__).resolve().parent.parent / "data" / "_probe.json"
PARAM = "https://kosis.kr/openapi/Param/statisticsParameterData.do"
META = "https://kosis.kr/openapi/statisticsData.do"


def call(base, params):
    shown = {k: v for k, v in params.items() if k != "apiKey"}
    url = base + "?" + urllib.parse.urlencode({**params, "apiKey": KEY}, safe="+*.")
    rec = {"params": shown}
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "housing-map/1.0"})
        with urllib.request.urlopen(req, timeout=90) as r:
            body = r.read().decode("utf-8")
        try:
            rec["result"] = json.loads(body)
        except json.JSONDecodeError:
            rec["result"] = json.loads(re.sub(r"([{,])\s*([A-Za-z_][A-Za-z0-9_]*)\s*:", r'\1"\2":', body))
    except Exception as e:  # noqa: BLE001
        rec["error"] = f"{type(e).__name__}: {e}"[:300]
    return rec


def compact(rec, limit=70):
    res = rec.get("result")
    if isinstance(res, list):
        keep = ("C1_NM", "C2_NM", "C3_NM", "C4_NM", "ITM_NM", "PRD_SE", "PRD_DE", "DT", "UNIT_NM")
        rec["count"] = len(res)
        rec["rows"] = [{k: r.get(k) for k in keep if k in r} for r in res[:limit]]
        rec["all_keys"] = sorted(res[0].keys()) if res else []
        del rec["result"]
    return rec


def p(tbl, itm, objs, extra=None):
    params = {"method": "getList", "orgId": "116", "tblId": tbl, "itmId": itm, "prdSe": "M",
              "newEstPrdCnt": 2, "format": "json", "jsonVD": "Y"}
    for i, v in enumerate(objs, 1):
        params[f"objL{i}"] = v
    params.update(extra or {})
    return params


PROBES = {
    "start_5386": p("DT_MLTM_5386", "13103766971T1", ["13102766971A.0001", "13102766971B.0001", "ALL"]),
    "complete_5372": p("DT_MLTM_5372", "13103766972T1", ["13102766972A.0001", "13102766972B.0001", "ALL"]),
    "sale_5557": p("DT_MLTM_5557", "13103133605T1", ["ALL", "ALL", "13102133605C.0001"]),
    "unsold_2082": p("DT_MLTM_2082", "13103871087T1", ["ALL", "13102871087B.0001"]),
    "unsold_post_5328_B1": p("DT_MLTM_5328", "13103871088T1", ["ALL", "13102871088B.0001"]),
    "unsold_post_5328_B2": p("DT_MLTM_5328", "13103871088T1", ["ALL", "13102871088B.0002"]),
    "permit_666_o1": p("DT_MLTM_666", "ALL", ["ALL"]),
    "permit_666_o2": p("DT_MLTM_666", "ALL", ["ALL", "ALL"]),
    "permit_666_o3": p("DT_MLTM_666", "ALL", ["ALL", "ALL", "ALL"]),
}


def main():
    out = {"meta": {}, "probe": {}}
    if not KEY:
        out["error"] = "KOSIS_API_KEY 없음"
    else:
        for tbl in ("DT_MLTM_666", "DT_MLTM_5386", "DT_MLTM_5557", "DT_MLTM_2082", "DT_MLTM_5328"):
            e = {}
            for typ in ("ITM", "OBJ", "PRD"):
                e[typ] = call(META, {"method": "getMeta", "type": typ, "format": "json", "jsonVD": "Y",
                                     "orgId": "116", "tblId": tbl})
            out["meta"][tbl] = e
        for name, params in PROBES.items():
            out["probe"][name] = compact(call(PARAM, params))
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("probe saved", len(out["probe"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
