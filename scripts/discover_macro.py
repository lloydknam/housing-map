#!/usr/bin/env python3
"""거시변수(금리·통화·물가·가계대출·전세 등) KOSIS 통계표 탐색 — 일회용. 결과: data/_discovery_macro.json"""
import json, os, re, sys, urllib.parse, urllib.request
from pathlib import Path
KEY = os.environ.get("KOSIS_API_KEY", "").strip()
OUT = Path(__file__).resolve().parent.parent / "data" / "_discovery_macro.json"
KW = ["시장금리", "주택담보대출 금리", "예금은행 대출금리", "광의통화 M2", "소비자물가지수", "가계대출 주택담보대출 잔액",
      "종합주가지수 코스피", "원달러 환율", "전세가격지수 서울", "아파트 전세 실거래가격지수", "주택 매매거래량 서울", "기준금리",
      "서울 인구 이동 전입", "가구수 서울 추계", "경제활동 임금 소득 월평균 서울", "주택가격 소득 PIR", "건설공사비지수", "주택 전월세 거래량"]

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "housing-map/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        body = r.read().decode("utf-8")
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return json.loads(re.sub(r"([{,])\s*([A-Za-z_][A-Za-z0-9_]*)\s*:", r'\1"\2":', body))

out = {}
for kw in KW:
    q = urllib.parse.urlencode({"method": "getList", "searchNm": kw, "startCount": 1, "resultCount": 15, "sort": "RANK",
                                "format": "json", "jsonVD": "Y", "apiKey": KEY})
    try:
        res = get("https://kosis.kr/openapi/statisticsSearch.do?" + q)
        out[kw] = [{k: it.get(k) for k in ("ORG_ID", "ORG_NM", "TBL_ID", "TBL_NM", "STRT_PRD_DE", "END_PRD_DE", "PRD_SE")} for it in res] if isinstance(res, list) else res
    except Exception as e:
        out[kw] = f"ERR {type(e).__name__}: {e}"[:200]
OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print("ok")
