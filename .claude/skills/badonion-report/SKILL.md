---
name: badonion-report
description: 나쁜양파(Bad Onion) 회사 리포트 양식으로 HTML 보고서·차트·그래프·도표를 만들 때 사용. 어두운 남색 바탕 + 청록 강조, Plotly 인터랙티브 차트(꺾은선·막대·묶음 막대·순위 막대·사분면 산점도·캔들+거래량+조건부 경로), 흐름도·조건 카드·기업 분석 카드, 개조식 문체와 출처·데이터 등급 표기. 사용자가 "회사 양식", "나쁜양파 양식", "Meta Muse 보고서처럼", "이 스타일로 보고서/차트 만들어줘", 주식·기업 분석 자료를 HTML로 정리해 달라고 할 때 트리거.
---

# 나쁜양파 리포트 양식

회사 직원이 만든 `Meta Muse 파급효과` 보고서의 디자인·차트·글쓰기 방식을 그대로 재현하는 스킬.

- `template.html` — 모든 부품과 차트가 실제로 동작하는 완성 양식(예시 데이터). **항상 여기서 시작함.**
- `style-guide.md` — 색·부품·차트·문체·데이터 정직성 규칙. 판단이 필요할 때 읽음.
- `make_offline.py` — 차트 라이브러리를 파일 안에 넣어 인터넷 없이 열리는 단일 파일로 만듦.

## 만드는 순서

1. **`template.html`을 복사**해 새 파일을 만듦 (예: `reports/<주제>_<YYYYMMDD>.html`). 처음부터 새로 쓰지 않음.
2. **그대로 두는 부분**: `<style>` 전체, “차트 도구” `<script>` 전체(`C`, `plotLayout`, `draw`, `lineChart`, `barChart`, `groupedBar`, `rankBar`, `quadrantScatter`, `candleChart`, `saveCSV` …). 색·여백·글자 크기 값을 바꾸지 않음. 새 부품이 필요하면 기존 토큰(`var(--cyan)` 등)만으로 추가함.
3. **바꾸는 부분**:
   - `REPORT` 데이터 블록 → 실제 데이터. `sampleCloud` 함수와 `...sampleCloud(90)` 줄은 삭제.
   - 머리글(브랜드 줄·제목 2줄·dek·hero-grid·meta-note), nav 링크, 섹션 HTML, 출처 목록, 바닥글.
   - “그리기” `<script>`에서 차트 id와 함수 연결. 쓰지 않는 부품·차트는 HTML과 호출을 **둘 다** 지움.
4. **차트 고르기** (`style-guide.md` 5절): 점 몇 개 변화 → `lineChart` / 2~6개 비교 → `barChart` / 두 그룹 → `groupedBar` / 순위 → `rankBar` / 두 지표 관계+분류 → `quadrantScatter` / 주가 → `candleChart`. 차트가 필요 없는 숫자는 `.kpis`·`.wide-stats`로.
5. **모든 차트 카드**: 제목=결론 문장, `.sub`=무엇·단위·기간·등급, figcaption 첫 문장 굵게=핵심 숫자 → 해석 → 한계, `.source`=출처 · 등급.
6. **문체**: 개조식 명사형(“~함/~임/~아님”). 사실·추정·회사 주장·해석을 구분. 전문용어는 처음에 괄호 풀이. 본문 출처는 `<a class="ref-link" href="#src-N">[이름]</a>`.
7. **검증** (아래) 후 결과를 사용자에게 보여줌.

## 색 규칙 (요약)

청록=주인공 1개, 호박=비교·기준선·주의, 초록/빨강=좋음/나쁨(부호가 아니라 의미), 회색=배경·미검토. 청록↔초록, 초록↔호박은 색각이상자에게 헷갈리므로 **같은 차트에서 다른 분류를 뜻하면 마커 모양도 다르게**(`GROUP_STYLE`: 원·빈 원·네모·마름모) + 이름표. 두 분류에 같은 색+같은 모양을 주지 않음.

## 데이터 정직성 (반드시)

- 없는 값은 `—`, 0이나 임의 추정으로 채우지 않음. 가짜/예시 숫자를 실제 보고서에 남기지 않음.
- 캔들 x축은 실제 거래일 번호(주말·휴장일 빈 봉 없음). 조건부 경로 첫 점 = 마지막 실제 종가.
- 공급자가 다른 분자·분모를 섞지 않음. 작성일과 시세 기준일을 따로 표기.
- 사용자가 준 수치의 출처를 모르면 출처 줄에 “사용자 제공”이라고 적고 등급을 추측하지 않음.

## 검증

Playwright(Chromium: `/opt/pw-browsers/chromium`)로 1280px, 390px 두 폭에서 열어 확인함.

- `window.REPORT_READY === true`, `window.REPORT_ERROR` 없음, 콘솔 에러 없음.
- `document.documentElement.scrollWidth - innerWidth === 0` (가로 스크롤 없음).
- 스크린샷을 직접 보고: 이름표 겹침(산점도는 종목별 `pos:'bottom left'` 등으로 조정), 막대 위 글씨 잘림, 범례와 주석 겹침 확인.
- 샌드박스에서 CDN 인증서 오류로 Plotly가 안 뜨면 TLS 검증을 끄지 말고, `curl`로 받은 `plotly.min.js`를 `page.route('**/plotly.min.js', r => r.fulfill({path: ...}))`로 연결해 테스트함.

## 공유

- 기본은 CDN(`cdn.jsdelivr.net/npm/plotly.js-dist-min@3.3.1`)으로 불러오는 가벼운 파일.
- 텔레그램 등으로 파일 하나만 보내야 하면: `python make_offline.py <보고서.html>` → `<보고서>_offline.html`.
