#!/usr/bin/env python3
"""후보 거시 통계표의 항목·분류 코드와 최근 샘플을 data/_probe_macro.json 에 저장(일회용)."""
import json, os, re, sys, urllib.parse, urllib.request
from pathlib import Path
KEY = os.environ.get("KOSIS_API_KEY", "").strip()
OUT = Path(__file__).resolve().parent.parent / "data" / "_probe_macro.json"
TABLES = [("301","DT_121Y006"),("301","DT_161Y008"),("101","DT_1J22003"),("408","DT_KAB_11672_S23"),
          ("408","DT_408_2006_S0053"),("101","DT_2OEEO032"),("301","DT_181Y002"),("101","DT_1J22006")]
SEARCH = ["국고채 3년", "가계신용 주택담보대출", "한국은행 기준금리", "아파트매매거래 시도 월", "코스피지수", "서울 세대수 주민등록", "주택담보대출 가계대출 잔액 예금취급기관", "주택건설실적 서울 입주"]

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "housing-map/1.0"})
    with urllib.request.urlopen(req, timeout=90) as r:
        body = r.read().decode("utf-8")
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return json.loads(re.sub(r"([{,])\s*([A-Za-z_][A-Za-z0-9_]*)\s*:", r'\1"\2":', body))

out = {"tables": {}, "search": {}}
for org, t in TABLES:
    e = {}
    for typ in ("ITM", "OBJ"):
        q = urllib.parse.urlencode({"method": "getMeta", "type": typ, "format": "json", "jsonVD": "Y", "orgId": org, "tblId": t, "apiKey": KEY})
        try:
            res = get("https://kosis.kr/openapi/statisticsData.do?" + q)
            comp = {}
            if isinstance(res, list):
                for it in res:
                    comp.setdefault(f"{it.get('OBJ_ID')}:{it.get('OBJ_NM')}", []).append(f"{it.get('ITM_ID')}={it.get('ITM_NM')}"[:60])
                comp = {k: v[:40] for k, v in comp.items()}
            else:
                comp = res
            e[typ] = comp
        except Exception as ex:
            e[typ] = f"ERR {type(ex).__name__}: {ex}"[:200]
    out["tables"][f"{org}/{t}"] = e
for kw in SEARCH:
    q = urllib.parse.urlencode({"method": "getList", "searchNm": kw, "startCount": 1, "resultCount": 10, "sort": "RANK", "format": "json", "jsonVD": "Y", "apiKey": KEY})
    try:
        res = get("https://kosis.kr/openapi/statisticsSearch.do?" + q)
        out["search"][kw] = [{k: it.get(k) for k in ("ORG_ID", "TBL_ID", "TBL_NM", "STRT_PRD_DE", "END_PRD_DE")} for it in res] if isinstance(res, list) else res
    except Exception as ex:
        out["search"][kw] = f"ERR {ex}"[:200]
OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print("ok")
