# Phase 9 보완: 장부다운 위계 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** "어느 날 몇 시간 했나"를 눈으로 더하지 않고 읽게 하고, 화면마다 주인공 숫자와 제목이 한눈에 서게 한다.

2026-10-26 전 화면 평가 P2 "시각 위계가 평평하고, 장부다운 데이터 표현이 없다"를 다룬다.
- 기록 화면 표에 날짜 묶음이나 하루 합계가 없다. 하루 공수를 행을 보며 더해야 한다.
- 패널 제목이 모든 화면에서 17px이다. 본문 15px의 1.13배라 제목과 본문의 단계가 거의 없다.
- 주간 요약의 `기록 12건`, `완료 태스크 3건`이 주인공 `이번 주 공수`와 거의 같은 크기의 큰 숫자다.

평가의 P3(설정 화면 정리)와 대시보드 최근 기록의 날짜 묶음은 이번 범위가 아니다.

**기준:** develop 731864c(PR #32 병합)에서 갈라진 브랜치 `feat/ledger-hierarchy`.

**진행:**
- 계획서 승인 → Task 순서대로 진행한다. 테스트를 먼저 써서 실패를 확인(RED)한다.
- Task마다 전후 스크린샷을 HTML 비교 페이지 하나로 보여 주고 사용자 승인을 받는다.
- 끝에 문서·전체 검증·최종 리뷰 1회(`final-reviewer`, Sonnet high) → PR(develop) → "logbook QA" 세션 점검.
- 구현은 메인 세션이 직접 한다.

**Tech Stack:** 기존과 같다. 새 의존성은 없다.

---

## 결정 (2026-10-30 결정 게이트, 사용자 확정)

| ID | 결정 |
|---|---|
| H1 | **날짜 묶음은 기록 화면(`/logs`)만 한다.** 묶은 행에서는 날짜 칸을 빼고 날짜 머리글이 날짜를 맡는다. 대시보드 최근 기록은 몇 줄뿐이라 지금처럼 날짜 칸을 둔다. |
| H2 | **날짜 머리글에 그날 합계와 하루 목표 대비 막대를 넣는다.** `10-27 (월)`, `6h 30m / 8h`, 채움 막대. 막대는 대시보드 `오늘 / 목표` 막대와 같은 부품이고, 목표에 닿으면 같은 초록 채움이 된다. |
| H3 | **패널 제목을 20px로 키운다.** 본문 15px의 1.33배다(평가 기준 1.25배 이상). 보드 열 제목 같은 하위 제목은 지금 크기로 둔다. |
| H4 | **주간 요약의 부수 숫자를 한 단계 낮춘다.** `기록`, `완료 태스크` 칸은 자리를 그대로 두고 숫자만 24px(`--text-lg`)로 줄인다. `이번 주 공수`만 크게 남는다. |

## 설계

### 기록 표 날짜 묶음(H1·H2)

**보기 모델(`web/pages/views.py`)**
- `LogDayView`(불변)를 둔다.
  - `day: str`: `day_label`(`10-27 (월)`).
  - `total: str`: 그날 기록 합계(`format_duration`).
  - `target: str`: 하루 목표(`format_duration(cfg.daily_target_minutes)`). 필터가 있으면 빈 문자열이다(아래).
  - `percent: int`: `progress_percent(합계, 목표)`. 대시보드 `오늘 / 목표`와 같은 함수다.
  - `reached: bool`: 합계 >= 목표.
  - `rows: tuple[LogRowView, ...]`.
- `LogTableView.rows`를 `days: tuple[LogDayView, ...]`로 바꾼다. 날짜 순서는 지금 그대로다(`list_worklogs`의 날짜·ID 오름차순). 기록이 없는 날은 머리글도 없다.
- `total`과 `count`(표 아래 합계 줄)는 그대로다. 빈 상태 판단은 `days`가 비었는지로 한다.
- `log_table_view`가 하루 목표를 받아야 하므로 인자에 `daily_target_minutes: int`를 더한다. 부르는 곳은 `pages/logs.py`의 `_table_page` 한 곳이다.

**필터가 있을 때:** 하루 목표는 그날 전체 공수와 비교하는 값이다. 프로젝트나 카테고리로 거른 합계를 목표와 비교하면 덜 한 것처럼 보인다. 그래서 필터가 있으면 머리글에 합계만 보이고 `/ 8h`와 막대를 뺀다.

**템플릿(`partials/log_table.html`, `partials/log_row.html`)**
- 날마다 `<tbody class="log-day">`를 하나씩 둔다. 첫 행은 머리글 행이다.
  ```html
  <tr class="log-day__head">
    <th scope="rowgroup" colspan="7">
      <span class="log-day__date">10-27 (월)</span>
      <span class="log-day__total">6h 30m<span class="log-day__target"> / 8h</span></span>
      <svg class="progress …" aria-hidden="true">…</svg>
    </th>
  </tr>
  ```
  - `scope="rowgroup"`이라 화면 낭독기가 그날 행을 읽을 때 날짜를 함께 알린다.
  - 막대는 `aria-hidden`이다. 뜻은 `6h 30m / 8h` 글자가 전한다.
- `log_row.html`에서 날짜 칸을 뺀다. 열은 8개에서 7개가 된다(ID, 프로젝트, 카테고리, 시간, 메모, 태스크, 동작). 숨긴 `thead`의 `날짜` 열과 `tfoot` `colspan`도 맞춘다.
- 대시보드 최근 기록(`recent.html`)은 `log_row.html`을 쓰지 않으므로 바뀌지 않는다.

**편집 행(`partials/log_edit_row.html`):** 날짜를 바꿀 수 있어야 하므로 날짜 입력은 남긴다. 따로 칸을 두면 열 수가 어긋나므로 날짜 입력을 ID 칸 안에 ID 아래로 둔다. 화면은 Task 2의 스크린샷으로 확인한다.

**저장·삭제 뒤:** 수정 저장과 삭제는 지금도 표 전체를 다시 그린다(`_table_page`). 날짜를 옮기거나 시간을 바꾸면 머리글 합계와 묶음도 새로 그려진다. 편집 취소(`GET /logs/{id}/row`)는 행 하나만 바꾸는데, 합계가 바뀌지 않으므로 그대로 둔다.

**CSS(`logs.css`):**
- 머리글 행은 옅은 바탕(`--tag-bg` 계열 토큰)에 날짜는 굵게, 합계는 오른쪽 정렬 숫자로 둔다. 막대는 머리글 아래쪽 전체 폭이다.
- 둘째 날부터는 머리글 위에 간격을 두어 날과 날을 나눈다.
- 320px에서 날짜와 합계가 한 줄에 들어가지 않으면 줄바꿈한다(`flex-wrap`).

### 제목과 요약 숫자(H3·H4)

- `app.css`에 `--text-title: 1.25rem`(20px) 토큰을 더하고 `.panel__title`(`dashboard.css`)이 쓴다. `--text-md`(17px)는 다른 곳(보드 열 제목, 오류 카드 제목, 타이머 등)이 계속 쓴다.
- `dashboard.css`: `.stat__value`의 기본 크기를 `--text-lg`로 내린다. `.stat--lead .stat__value`는 지금처럼 `--text-stat-lead`다. 그러면 쓰지 않게 되는 `--text-stat` 토큰을 지운다(지금 쓰는 곳은 `.stat__value` 한 곳이다).

## Task 1: 제목과 요약 숫자 단계(H3·H4)

**Files:** `static/css/app.css`, `static/css/dashboard.css`

CSS만 바꾸므로 단위 테스트 대신 실제 화면의 계산된 글자 크기를 잰다(헤드리스 Edge CDP, `getComputedStyle`).

- [ ] 바꾸기 전 스크린샷: 대시보드·기록·태스크·보고서·설정, 1280px과 320px, 밝은·어두운 테마
- [ ] 바꾸기 전 계산값 기록: `.panel__title` 17px, 요약 부수 숫자 28~40px
- [ ] `--text-title` 토큰과 `.panel__title`, `.stat__value` 변경
- [ ] 바꾼 뒤 계산값 확인: `.panel__title` 20px, 부수 숫자 24px, 주인공 숫자는 그대로
- [ ] 320px에서 패널 제목·머리 줄이 넘치거나 겹치지 않는지 확인(가로 스크롤 없음)
- [ ] 전후 비교 HTML → 사용자 승인 → 커밋 `style: 패널 제목과 요약 부수 숫자의 크기 단계를 벌린다`

## Task 2: 기록 표 날짜 묶음(H1·H2)

**Files:** `web/pages/views.py`, `web/pages/logs.py`, `templates/partials/log_table.html`, `log_row.html`, `log_edit_row.html`, CSS, 테스트 `tests/web/test_logs_days.py`(새 파일)와 기존 기록 화면 테스트

- [ ] RED: 새 테스트를 쓰고 실패를 확인한다.
  - 같은 주 두 날에 기록이 있으면 날마다 `tbody` 하나, 머리글 `th[scope=rowgroup]`에 날짜와 그날 합계가 있다.
  - 하루 목표 8h에 6h 30m이면 `6h 30m / 8h`, 막대 채움 81%. 목표 이상이면 `progress--done`.
  - 필터가 있으면 머리글에 합계만 있고 `/ 8h`와 막대가 없다.
  - 묶은 행에는 날짜 칸이 없다(7칸). 편집 행에는 날짜 입력이 있다.
  - 기록을 다른 날로 옮겨 저장하면 두 날의 합계가 함께 바뀐다.
  - 표 아래 주 합계 줄과 빈 상태 문구는 그대로다.
- [ ] 보기 모델·템플릿·CSS 구현 → GREEN
- [ ] 기존 테스트 중 행의 칸 위치나 날짜 칸을 보는 것을 고친다(`test_logs_page.py`, `test_logs_edit.py` 등). 고친 이유를 커밋 본문에 적는다
- [ ] 전후 스크린샷: 기록 화면(필터 없음·필터 있음·편집 중), 1280px과 320px, 밝은·어두운 테마
- [ ] 전후 비교 HTML → 사용자 승인 → 커밋 `feat: 기록 화면 표를 날짜별로 묶고 하루 합계와 목표 막대를 보인다`

## Task 3: 문서와 PR

- [ ] SPEC 6장 "기록 조회·수정"에 날짜 묶음·머리글·필터 때 목표 생략을 적는다. 화면 위계(제목 20px, 요약 부수 숫자)를 디자인 시스템 절에 맞춘다
- [ ] ROADMAP Phase 9에 보완 줄을 더하고 체크한다
- [ ] 전체 검증: `ruff check`, `ruff format --check`, `mypy src/logbook/core`, 전체 `pytest`
- [ ] 최종 리뷰 1회(`final-reviewer`) → 지적 반영
- [ ] PR(develop) 생성, "logbook QA" 세션에 점검 요청
