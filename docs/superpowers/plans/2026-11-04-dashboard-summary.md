# 평가 P2: 대시보드 주간 요약 다듬기 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 대시보드 맨 아래 주간 요약을 그 자리에 둔 채 장부답게 줄인다. 작은 숫자 칸 둘을 한 줄 보조 문구로 낮추고, 도넛 둘을 값이 글자로 보이는 비율 막대로 바꾼다.

2026-11-04 재평가(28/40)의 P2 "대시보드 하단 요약이 범용 대시보드 공식이다"를 다룬다. 지금은 큰 숫자 칸 3개(이번 주 공수, `기록 7건`, `완료 태스크 1건`) 아래에 요일별 막대(왼쪽 2)와 프로젝트별·카테고리별 도넛 2개(오른쪽 1)가 있다. 작은 값 둘이 큰 칸을 차지하고, 도넛은 값을 보려면 마우스를 올리거나 `표로 보기`를 열어야 한다.

**기준:** develop 082495e(PR #38 병합)에서 갈라진 브랜치 `feat/dashboard-summary`.

**진행:** 계획서 승인 → Task 순서대로, 테스트 먼저(RED). Task마다 전후 스크린샷(1280px 밝음·어두움, 375px 밝음)을 비교 HTML 한 장으로 보여 드리고 승인을 받은 뒤 커밋한다. 끝에 문서·전체 검증·최종 리뷰 1회(`final-reviewer`, Sonnet high) → PR(develop) → "logbook QA" 세션 점검. 새 의존성 없음.

---

## 결정 (2026-11-04 결정 게이트, 사용자 확정)

| ID | 결정 |
|---|---|
| M1 | **기록·완료 수는 공수 아래 한 줄.** 큰 숫자는 `이번 주 공수` 하나만 남긴다. 그 아래 `오늘 N / 목표 N` 줄과 진행 막대 다음에 `기록 7건 · 완료 태스크 1건`을 보조 글자(--text-sm, --ink-muted)로 둔다. 숫자 칸 3개 격자와 세로 괘선은 없어진다. |
| M2 | **도넛 둘 → 비율 막대 둘 + 글줄.** 프로젝트별·카테고리별마다 가로 100% 누적 막대 한 줄과 그 아래 `● 이름 시간 비율` 행. 값이 글자로 보이므로 두 `표로 보기`는 뺀다. Chart.js 도넛 코드는 지운다. |
| M3 | **배치는 지금 2:1 그대로.** 왼쪽 요일별 막대, 오른쪽 열에 비율 막대 둘. 좁은 폭에서는 지금처럼 아래로 내려간다. |

## 설계

- **막대는 서버가 SVG로 그린다.** CSP가 인라인 style을 막으므로(`style-src 'self'`) 지금 진행 막대처럼 `<rect x=".." width=".." fill="#rrggbb">` 속성을 쓴다. `viewBox="0 0 100 N"` + `preserveAspectRatio="none"`. 막대 SVG는 `aria-hidden="true"`이고 정보는 아래 글줄이 전한다. 조각 사이의 틈은 CSS 한 줄(`.share__bar rect { stroke: var(--surface) }`)로 바탕색 테두리를 줘서 만든다.
- **글줄은 작은 표.** `<table class="share__rows">`(숨긴 caption `프로젝트별 공수`·`카테고리별 공수`), 행마다 색 점(SVG 원, `fill` 속성) + 이름(th) + 시간(td.num) + 비율(td.num). 숫자는 tabular 글자. 행 높이는 기존 `--row-height`보다 낮은 촘촘한 표.
- **비율 표기:** `round(분 × 100 / 합계)`%. 0이 되면 `<1%`. 막대 폭은 반올림하지 않은 실수(소수 둘째 자리)로 그려 끝이 100에 맞는다.
- **순서와 색:** 지금 도넛과 같다. 프로젝트는 합계 내림차순(같으면 slug 순)·프로젝트 색, 카테고리는 `stats_by` 순·카테고리 색. 이름도 지금처럼 프로젝트는 slug, 카테고리는 설정 한글명(꼬리표 영어 키 결정과 별개로 요약은 지금 표기를 유지).
- **데이터:** `pages/summary.py`에 `ShareRow(label, color, time, percent, x, width)`와 `ShareGroup(title, rows)`를 더하고 `SummaryView.shares`(프로젝트, 카테고리 순)로 넘긴다. `data-chart` JSON에서는 `projects`·`categories`를 빼고 `daily`만 남긴다(`DonutChart` 타입 삭제). JSON API(`/api/stats`)는 바뀌지 않는다.
- **JS:** `dashboard.js`에서 `doughnutConfig`와 두 캔버스 처리를 지운다. `drawCharts`는 `chart-daily`만 본다.
- **기록이 없는 주:** 지금처럼 차트 영역 대신 빈 상태 문구 하나. M1의 보조 줄은 `기록 0건 · 완료 태스크 N건`으로 그대로 보인다.
- **인쇄·어두운 테마:** 색은 이미 두 테마에서 쓰는 프로젝트·카테고리 색 그대로. 틈 색은 `--surface` 토큰이라 테마를 따른다.

## Task 1: 기록·완료 수를 공수 아래 한 줄로(M1)

**Files:** `templates/partials/summary.html`, `static/css/dashboard.css`, 테스트 `tests/web/test_dashboard.py`, `tests/web/test_css_layout.py`

- [x] RED: 테스트를 쓰고 실패를 확인한다.
  - 요약에 `.stat__value`가 하나(이번 주 공수)뿐이다.
  - 공수 칸 안에 `기록 3건 · 완료 태스크 1건` 보조 줄(`.stat__counts`)이 있다(시드 기준 값).
  - 기록 없는 주에도 `기록 0건 · 완료 태스크 N건`이 보인다.
  - CSS: `.stats` 3열 격자 선언이 없어지고, `.stat__counts`가 `--text-sm`·`--ink-muted`를 쓴다. 기존 `.stat__value` 글자 크기 테스트는 맞게 고친다.
- [x] 구현 → GREEN
- [x] 전후 스크린샷 → 비교 HTML → 사용자 승인 → 커밋 `feat: 대시보드 요약의 기록·완료 수를 공수 아래 한 줄로 낮춘다`

## Task 2: 도넛 둘을 비율 막대와 글줄로(M2, M3)

**Files:** `web/pages/summary.py`, `templates/partials/summary.html`, `static/css/dashboard.css`, `static/js/dashboard.js`, 테스트 `tests/web/test_dashboard.py`(+ 필요하면 `test_views.py`)

- [x] RED: 테스트를 쓰고 실패를 확인한다.
  - `data-chart`에는 `daily`만 있다(`EXPECTED_CHART`에서 두 키 삭제).
  - 캔버스는 `chart-daily` 하나, `표로 보기`는 하나(요일별)뿐이다.
  - 비율 묶음 둘(`프로젝트별`, `카테고리별`): 행 이름·시간·비율이 시드 값과 같다(payment 3h 86%, common 30m 14% / 개발 3h 86%, 회의 30m 14%).
  - 막대 SVG의 rect `x`·`width`·`fill`이 순서대로 맞고 폭 합이 100이다. SVG는 `aria-hidden`.
  - 아주 작은 조각은 `<1%`로 표기한다(단위 테스트: 비율 계산 함수).
  - 지정한 프로젝트 색·카테고리 한글명 테스트(기존 352·454행)는 새 구조에서 같은 것을 확인하도록 옮긴다.
- [x] 구현 → GREEN
- [x] JS 도넛 코드 삭제 뒤 브라우저 콘솔 오류 없음(CDP로 확인)
- [x] 전후 스크린샷 → 비교 HTML → 사용자 승인 → 커밋 `feat: 대시보드 도넛 차트를 값이 보이는 비율 막대로 바꾼다`

## Task 3: 문서와 PR

- [x] SPEC 대시보드 절(459·461행 카드·도넛 문구, 428행 요약 숫자 결정, 556행 차트 팔레트의 도넛 언급)과 README 화면 표(333행)를 고친다
- [x] ROADMAP Phase 9 보완 줄을 더하고 체크한다
- [x] 전체 검증: `ruff check`, `ruff format --check`, `mypy src/logbook/core`, 전체 `pytest`
- [x] 최종 리뷰 1회(`final-reviewer`) → 지적 반영
- [ ] PR(develop) 생성, "logbook QA" 세션에 점검 요청
