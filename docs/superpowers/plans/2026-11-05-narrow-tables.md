# 평가 P2: 좁은 폭에서 표 내용이 말없이 화면 밖에 있는 문제 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 375px 같은 좁은 폭에서 기록의 메모가 가로 스크롤 밖으로 밀리지 않게 하고, 그래도 넘치는 표는 밀 수 있다는 신호를 보인다.

2026-11-04 재평가(28/40)의 P2 "좁은 폭에서 표 내용이 말없이 화면 밖에 있다"를 다룬다. 2026-11-05 develop 5ab4a9c를 CDP로 375px에서 찍어 확인한 지금 모습:

- 대시보드 최근 기록: ID·날짜·프로젝트/카테고리 다음 `시간`이 오른쪽에서 잘리고, 메모·태스크 열은 상자 밖에 있다.
- 기록 화면: 메모 첫 글자만 보이고 나머지·태스크·⋮ 메뉴가 상자 밖에 있다.
- 보고서: 1절 공수 요약은 `운영/배포/장애` 열부터, 4절 다음 주 계획은 `예상` 열이 잘린다. 2절은 `실적·예상` 열이 밖에 있다.
- Windows는 스크롤 막대가 보이지만 macOS는 스크롤 막대가 숨어 있어 아무 신호가 없다. 페이지 자체 가로 넘침은 0건.

**기준:** develop 5ab4a9c(PR #39 병합)에서 갈라진 브랜치 `feat/narrow-tables`.

**진행:** 계획서 승인 → Task 순서대로, 테스트 먼저(RED). Task마다 전후 스크린샷(375px 밝음·어두움, 320px 밝음, 1280px 밝음)을 비교 HTML 한 장으로 보여 드리고 승인을 받은 뒤 커밋한다. 끝에 문서·전체 검증·최종 리뷰 1회(`final-reviewer`, Sonnet high) → PR(develop) → "logbook QA" 세션 점검. 새 의존성 없음. 서버 코드 변경 없음(템플릿·CSS만).

---

## 결정 (2026-11-05 결정 게이트, 사용자 확정)

| ID | 결정 |
|---|---|
| N1 | **기록 표 두 곳은 좁은 폭에서 메모를 둘째 줄로.** 대시보드 최근 기록과 기록 화면의 각 행을 두 줄로 쌓아 가로 스크롤 없이 들어오게 한다. |
| N2 | **그래도 넘치는 표에는 가장자리 그림자.** 보고서 표처럼 열이 많아 넘치는 가로 스크롤 상자는 가려진 내용이 있는 쪽 가장자리에 그림자를 둔다. |

## 설계

- **기준 폭은 지금 좁은 화면 경계 `max-width: 719px`.** 1280px·768px 이상은 지금 그대로다.
- **두 줄 행(N1):** 좁은 폭에서만 행(`tr`)을 CSS grid로 바꾼다.
  - 최근 기록: 1줄 `ID · 날짜 · 프로젝트 꼬리표 · 시간(오른쪽)`, 2줄 `메모 · 태스크(오른쪽)`.
  - 기록 화면: 1줄 `ID · 프로젝트 · 시간(오른쪽) · ⋮`, 2줄 `카테고리 · 메모 · 태스크(오른쪽)`. (구현 중 변경: 카테고리를 1줄에 두면 320px에서 `common`이 `commo/n`으로 끊겨 2줄로 내렸다.)
  - 메모는 둘째 줄 전체 폭을 쓰고 줄바꿈한다. 괘선은 행 아래 한 줄(지금과 같음).
  - 열 머리(`thead`): 최근 기록의 보이는 열 머리는 좁은 폭에서 숨긴다(기록 화면은 이미 숨김). 낭독기는 그대로 읽는다.
  - **표 의미 지키기:** 표 요소에 `display`를 바꾸면 일부 브라우저(Safari·Chrome)가 표 의미를 버린다. 템플릿의 `table/thead/tbody/tfoot/tr/th/td`에 `role`(table·rowgroup·row·columnheader·rowheader·cell)을 명시해 낭독기가 표로 읽게 한다.
  - **날짜 묶음 머리(기록 화면):** 표가 더는 가로로 스크롤하지 않으므로 날짜·합계 줄의 `position: sticky` 규칙은 지운다.
  - **편집 행(기록 화면 ⋮ → 수정):** 좁은 폭에서는 칸이 접혀 내려간다(날짜·프로젝트·카테고리·시간 → 메모 전체 폭 → 태스크 → 저장·취소). 입력 칸이 화면 밖으로 나가지 않는다.
  - 320px에서도 가로 스크롤이 없어야 한다. 프로젝트 slug가 32자일 때는 1줄 안에서 slug가 줄바꿈한다(시간은 한 줄).
- **가장자리 그림자(N2):** JS 없이 CSS만 쓴다. 스크롤 상자에 배경 네 겹을 둔다. 둘(바탕색 가림막)은 `background-attachment: local`로 내용과 함께 움직이고, 둘(그림자)은 `scroll`로 상자 가장자리에 붙어 있다. 내용이 끝까지 밀리면 가림막이 그림자를 덮어 그쪽 그림자가 사라진다. CSP(`style-src 'self'`)와 충돌 없음.
  - 대상: `.sheet__scroll`(보고서 표 넷)과 `.table-wrap`(대시보드·기록·설정의 표 상자). 넘치지 않으면 그림자도 보이지 않으므로 넓은 화면에는 변화가 없다.
  - 색: 그림자는 `--ink` 기반 반투명, 가림막은 카드 바탕 `--surface`. 두 테마를 따른다.
  - 표 칸에 바탕색이 있으면 그림자를 덮으므로, 보고서 표 칸이 투명한지 확인하고 아니면 맞춘다.
- **인쇄:** 인쇄에는 그림자를 넣지 않는다(`@media print`에서 배경 끔).

## Task 1: 기록 표 두 곳을 좁은 폭에서 두 줄로(N1)

**Files:** `templates/partials/recent.html`, `templates/partials/log_table.html`, `templates/partials/log_row.html`, `templates/partials/log_edit_row.html`, `static/css/dashboard.css`·`logs.css`·`responsive.css`, 테스트 `tests/web/test_css_layout.py`, `tests/web/test_dashboard.py`, `tests/web/test_logs*.py`(이름은 저장소에 맞춤)

- [x] RED: 테스트를 쓰고 실패를 확인한다.
  - 최근 기록·기록 표의 표 요소에 role이 있다(table, row, columnheader, cell 등). 편집 행도 같다.
  - CSS: `max-width: 719px` 안에 두 표의 행을 grid로 바꾸는 규칙이 있고, 메모 칸이 둘째 줄 전체 폭(`grid-column: 1 / -1` 또는 영역 이름)이다.
  - CSS: 좁은 폭의 `.log-day__line` sticky 규칙이 없다.
- [x] 구현 → GREEN
- [x] CDP 확인: 375·320px에서 두 표 상자의 `scrollWidth == clientWidth`(가로 스크롤 없음), 메모가 상자 안에 보임, 편집 행을 열어도 넘침 없음. 1280px은 변화 없음.
- [x] 전후 스크린샷 → 비교 HTML → 사용자 승인 → 커밋 `feat: 좁은 폭에서 기록 표의 메모를 둘째 줄로 내린다`

## Task 2: 넘치는 표 상자에 가장자리 그림자(N2)

**Files:** `static/css/app.css` 또는 `components.css`(공용 규칙 위치는 저장소 관례대로), `static/css/report.css`, `responsive.css`(인쇄), 테스트 `tests/web/test_css_layout.py`

- [ ] RED: 테스트를 쓰고 실패를 확인한다.
  - `.sheet__scroll`과 `.table-wrap`에 `background-attachment: local, local, scroll, scroll`과 그림자 그러데이션이 있다.
  - 인쇄 규칙에서 그 배경을 끈다.
- [ ] 구현 → GREEN
- [ ] CDP 확인: 375px 보고서 1절 표에서 처음엔 오른쪽 그림자만, 끝까지 밀면 왼쪽 그림자만 보인다(스크롤 위치별 캡처). 두 테마. 1280px은 변화 없음. 대비 검사 0건.
- [ ] 전후 스크린샷 → 비교 HTML → 사용자 승인 → 커밋 `feat: 넘치는 표 상자 가장자리에 그림자로 밀 수 있다는 신호를 둔다`

## Task 3: 문서와 PR

- [ ] SPEC을 고친다: 383행 보고서 표 보기의 `좁은 화면에서는 표가 옆으로 스크롤된다`에 가장자리 그림자를 더하고, 466행 기록 날짜 묶음의 좁은 화면 sticky 설명을 두 줄 행으로 바꾼다(대시보드 최근 기록도 함께). README 화면 표는 필요할 때만 고친다
- [ ] ROADMAP Phase 9 보완 줄을 더하고 체크한다
- [ ] 전체 검증: `ruff check`, `ruff format --check`, `mypy src/logbook/core`, 전체 `pytest`
- [ ] 최종 리뷰 1회(`final-reviewer`) → 지적 반영
- [ ] PR(develop) 생성, "logbook QA" 세션에 점검 요청

## 다음 PR (이 계획 밖)

P3 필터 줄·제목은 이 PR이 병합된 뒤 따로 계획서를 쓴다. 결정: 카드 위 공용 필터 줄, 제목은 모두 카드 머리 안, 잔손질 셋(설정 카테고리 색 빈 공간, 404 머리 이번 주, 새 태스크 폼 폭).
