#!/usr/bin/env python3
"""서울 아파트 가격 결정요인 분석용 거시·시장 변수를 KOSIS에서 월별로 받아 data/macro.json 에 저장(분석용 일회성)."""
import json, os, re, sys, urllib.parse, urllib.request
from pathlib import Path
KEY = os.environ.get("KOSIS_API_KEY", "").strip()
ROOT = Path(__file__).resolve().parent.parent / "data"
BASE = "https://kosis.kr/openapi/Param/statisticsParameterData.do"

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "housing-map/1.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        body = r.read().decode("utf-8")
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return json.loads(re.sub(r"([{,])\s*([A-Za-z_][A-Za-z0-9_]*)\s*:", r'\1"\2":', body))

def fetch(org, tbl, itm="ALL", objs=(), prd="M", start="200601", end="202612"):
    p = {"method": "getList", "apiKey": KEY, "itmId": itm + "+" if itm != "ALL" else "ALL", "format": "json", "jsonVD": "Y",
         "prdSe": prd, "startPrdDe": start, "endPrdDe": end, "orgId": org, "tblId": tbl}
    for i, o in enumerate(objs, 1):
        p[f"objL{i}"] = o + "+" if o != "ALL" else "ALL"
    return get(BASE + "?" + urllib.parse.urlencode(p, safe="+"))

JOBS = {
  "mortgage_rate_new": ("301", "DT_121Y006", "13103134553999", ["13102134553ACC_ITEM.BECBLA0302"]),
  "loan_rate_household_new": ("301", "DT_121Y006", "13103134553999", ["13102134553ACC_ITEM.BECBLA03"]),
  "m2": ("301", "DT_161Y008", "13103844599999", ["13102844599ACC_ITEM.BBGA00"]),
  "cpi_seoul": ("101", "DT_1J22003", "T", ["T11"]),
  "cpi_nat": ("101", "DT_1J22003", "T", ["T10"]),
  "jeonse_idx_seoul": ("408", "DT_KAB_11672_S23", "T1", ["40001"]),
  "jeonse_idx_seoul2": ("408", "DT_KAB_11672_S23", "T1", ["ALL"]),
  "jeonse_idx_nat": ("408", "DT_KAB_11672_S23", "T1", ["10"]),
  "apt_trade_seoul_sale": ("408", "DT_408_2006_S0053", "13103114437T1", ["13102114437A.0002", "13102114437B.00010001"]),
  "policy_rate_kr": ("101", "DT_2OEEO032", "T1", ["1005"]),
  "kospi": ("343", "DT_343_2010_S0027", "ALL", []),
  "households_seoul": ("101", "DT_1B040B3", "ALL", ["11"]),
}
out, log = {}, {}
for name, (org, tbl, itm, objs) in JOBS.items():
    res, used = None, None
    for prd, st in (("M", "200601"), ("Y", "2006")):
        for objset in (objs, [o for o in objs] + (["ALL"] if not objs else [])):
            try:
                r = fetch(org, tbl, itm, objset, prd, st, "202612" if prd == "M" else "2026")
                if isinstance(r, list) and r:
                    res, used = r, (prd, objset); break
                log.setdefault(name, []).append(f"{prd}:{str(r)[:120]}")
            except Exception as e:
                log.setdefault(name, []).append(f"{prd}:ERR {e}"[:200])
        if res: break
    if not res:
        continue
    rows = []
    for it in res:
        rows.append([it.get("PRD_DE"), it.get("C1"), it.get("C2"), it.get("C3"), it.get("ITM_ID"), it.get("DT"), it.get("C1_NM"), it.get("C2_NM"), it.get("ITM_NM")])
    # 같은 키가 여러 개면 일부만 보존
    out[name] = {"period": used[0], "n": len(rows), "rows": rows[:3000], "sample": rows[:2]}
    log[name] = log.get(name, []) + [f"ok {used[0]} n={len(rows)} first={rows[0][:6]} last={rows[-1][:6]}"]
(ROOT / "macro.json").write_text(json.dumps(out, ensure_ascii=False) + "\n", encoding="utf-8")
(ROOT / "_macro_log.json").write_text(json.dumps(log, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print("ok", {k: v["n"] for k, v in out.items()})
