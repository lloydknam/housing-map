# 주택공급 지도

국토교통부 월간 주택통계(인허가·착공·분양·준공·미분양)를 시도별 지도 위에 보여주는 GitHub Pages 사이트입니다.

- 보기 방식: 월 수치 / 연초 누계 / 전년 동월 대비, 월 슬라이더와 재생 버튼
- 데이터: KOSIS OpenAPI → `data/housing.json` (GitHub Actions가 매일 확인해 바뀐 경우에만 커밋)
- 지도 경계: `data/provinces.geo.json` (KOSTAT 2013 시도 경계, southkorea/southkorea-maps)

## 설정

1. `config/sources.json`의 지표별 `url_template`에 KOSIS 통계자료 요청 URL을 넣습니다. API 키 자리는 `{API_KEY}`로 둡니다.
2. 저장소 Settings → Secrets and variables → Actions에 `KOSIS_API_KEY`를 등록합니다.
3. Settings → Pages에서 Source를 `Deploy from a branch`, Branch를 `main` / `(root)`로 지정합니다.
4. Actions 탭에서 `Update housing data`를 한 번 수동 실행하면 지도가 채워집니다.

## 사용한 KOSIS 통계표 (국토교통부, orgId 116)

| 지표 | tblId | 비고 |
|---|---|---|
| 인허가 | DT_MLTM_1946 | 월별 누계표 → 전월 누계를 빼 월 값으로 환산 |
| 착공 | DT_MLTM_5386 | 주택건설 착공실적(월계) |
| 분양(승인) | DT_MLTM_5557 | 주택건설 분양실적(공동주택), 순계 |
| 준공 | DT_MLTM_5372 | 주택건설 준공실적(월계, 사용검사) |
| 미분양 | DT_MLTM_2082 | 시·군·구별 미분양현황 중 시도 합계 |
| 준공 후 미분양 | DT_MLTM_5328 | 공사완료후 미분양현황, 부문·규모 '계' |

광주·전남은 국토부가 2026년 중반부터 '전남광주'로 합쳐 공표해서, 이전 월은 광주+전남을 더해 같은 지역(코드 2436)으로 맞췄습니다.
수치는 2026년 5월·7월·8월 기준 국토부 발표 전국 수치(인허가·착공·분양·준공·미분양)와 대조해 일치함을 확인했습니다.

## 로컬 확인

```bash
python3 -m http.server 8000   # http://localhost:8000
KOSIS_API_KEY=... python3 scripts/fetch_kosis.py
```
