# 주택공급 지도

국토교통부 월간 주택통계(인허가·착공·분양·준공·미분양)를 시도별 지도 위에 보여주는 GitHub Pages 사이트입니다.

- 보기 방식: 월별/연도별 전환, 월 수치·연초 누계·전년 대비, 최근 20년 연도별 추이 막대(전년 대비 증감, 동기간 비교)와 시도별 미니 차트
- 데이터: 최근 240개월(20년) KOSIS OpenAPI → `data/housing.json` (GitHub Actions가 매일 확인해 바뀐 경우에만 커밋)
- 지도 경계: `data/provinces.geo.json` (KOSTAT 2013 시도 경계, southkorea/southkorea-maps)

## 운영

- `KOSIS_API_KEY`를 저장소 Secret에 등록해 두면 `Update housing data` 워크플로가 매일 KOSIS를 확인해 바뀐 데이터만 커밋합니다.
- `Deploy Pages` 워크플로가 `index.html`·`data/`가 바뀌거나 데이터 갱신이 끝날 때마다 사이트를 다시 배포합니다.
- Pages가 자동으로 켜지지 않으면 Settings → Pages에서 Source를 `GitHub Actions`로 지정하세요.
- 수집 결과 요약은 `data/_fetch_log.json`에서 볼 수 있습니다.

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
