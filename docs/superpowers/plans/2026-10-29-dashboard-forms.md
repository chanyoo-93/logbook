# Phase 9 보완: 대시보드 기록·타이머 한 폼 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 대시보드 "작업 기록" 패널에서 하루의 기본 동작(빠른 기록)이 무엇인지 화면이 말하게 한다.

2026-10-26 웹 전 화면 평가(26/40)의 두 번째 P1이다. 지금 패널의 문제는 다음과 같다.
- 빠른 기록 폼과 타이머 시작 폼이 프로젝트·카테고리·태스크 선택 상자를 따로 갖는다. 같은 패널에서 선택 상자 세 개가 두 번 나온다.
- 주 버튼(파란색)이 `기록`과 `시작` 두 개다.
- 동시에 보이는 결정이 11개다(기록 5칸 + 버튼, 타이머 4칸 + 버튼).
- 타이머가 없을 때 `진행 중인 타이머가 없습니다.`가 한 줄을 차지한다.

**기준:** develop aeef002(PR #30 병합)에서 갈라진 브랜치 `feat/dashboard-forms`

**진행:**
- 계획서 승인 → Task 순서대로 진행한다. 테스트를 먼저 써서 실패를 확인(RED)한다.
- Task마다 전후 스크린샷을 보여 주고 사용자 승인을 받는다.
- 끝에 문서·전체 검증·최종 리뷰 1회(`final-reviewer`, Sonnet high) → PR(develop) → "logbook QA" 세션 자동 점검.
- 구현은 메인 세션이 직접 한다.

**Tech Stack:** 기존과 같다. 새 의존성은 없다. 인라인 스크립트·스타일 없이 템플릿·CSS·서버 응답만 바꾼다.

---

## 결정 (2026-10-29 결정 게이트, 사용자 확정)

| ID | 결정 |
|---|---|
| E1 | **한 폼에 버튼 둘.** 타이머 시작 폼을 없애고, 빠른 기록 폼에 `기록`(주 버튼)과 `타이머 시작`(외곽선 보조 버튼)을 둔다. 메모·프로젝트·카테고리·태스크를 함께 쓰고, 타이머 시작은 시간 칸을 무시한다. 보이는 결정이 11개에서 7개로 준다. `진행 중인 타이머가 없습니다.` 줄은 없앤다. |
| E2 | **시간 칸이 빈 채 Enter는 지금처럼 오류.** Enter는 늘 `기록`이다. 오류 문구에 타이머 안내를 덧붙인다: `시간을 입력하세요. 예: 2h, 90m, 1:30. 시간을 재려면 타이머 시작을 누르세요.` |
| E3 | **타이머가 진행 중이면 `타이머 시작` 버튼을 숨긴다.** 진행 줄의 `정지`·`취소`만 남는다. 정지·취소하면 다시 보인다. |

## 설계

- **버튼:** `<button type="button" class="btn quick__timer" hx-post="/timer/start" hx-target="#timer" hx-swap="outerHTML">`를 폼 안 `기록` 옆에 둔다.
  - htmx는 POST 요청에 감싸는 폼의 값을 넣는다. `/timer/start`가 받는 칸(note, project, category, task)은 빠른 기록 폼의 이름과 같다. `duration`은 서버가 받지 않으므로 무시된다.
  - `type="button"`이라 Enter는 첫 submit 버튼인 `기록`으로 간다(E2).
- **진행 중 숨김(E3):** 타이머 영역(`#timer`)은 진행 중이면 `timer--running` 클래스를 갖는다. CSS `.work:has(.timer--running) .quick__timer { display: none; }`로 숨긴다.
  - 시작·정지·취소 응답은 지금처럼 `#timer`만 바꾸면 되고, 폼을 다시 그릴 필요가 없다.
  - 그사이 CLI로 타이머를 시작했다면 버튼이 보일 수 있다. 눌러도 서버가 지금처럼 오류(이미 진행 중)를 알리고 진행 중 패널을 그린다. 그러면 버튼이 숨는다.
- **시작 성공:** `#timer`를 진행 중 패널로 바꾸고, 빠른 기록 폼을 OOB로 빈 값으로 다시 그린다. 입력한 메모가 남아 다음 기록에 섞이지 않게 하기 위해서다.
- **시작 실패:** 폼 값은 그대로 두고, 오류 문구는 타이머 영역(`#timer-result`)에 보인다. 서버는 더 이상 시작 폼 값을 다시 그리지 않는다. `timer_options`·`timer_values`·`TimerStartValues`의 다시 그리기 용도는 정리한다.
- **모양:** `타이머 시작`은 외곽선 버튼(`.btn`)에 재생 아이콘(`icons.html`에 `icon_play` 추가)과 글자를 쓴다. 좁은 폭에서는 두 버튼이 한 줄로 내려간다.

## Task 1: 한 폼으로 합치기 (E1, E3)

**파일:** `partials/quick_form.html`, `partials/timer.html`, `partials/icons.html`, `web/pages/timer.py`, `web/pages/panels.py`, `static/css/`(대시보드 작업 패널), 테스트(`test_dashboard.py`, `test_timer_panel.py`, `test_timer_actions.py`, `test_css_layout.py`)

**테스트 먼저(RED):**
- 대시보드에 `#timer-start` 폼과 `timer-note` 칸이 없다.
- 빠른 기록 폼 안에 `타이머 시작` 버튼이 있다(`type=button`, `hx-post=/timer/start`, `hx-target=#timer`). `기록`이 첫 submit 버튼이다.
- 타이머가 없을 때 `진행 중인 타이머가 없습니다.`가 없다.
- `POST /timer/start` 성공 응답에 진행 중 패널과 OOB 빈 빠른 기록 폼이 있다. 실패 응답에는 오류 문구가 있고 OOB 폼은 없다.
- CSS에 `.work:has(.timer--running) .quick__timer`의 `display: none`이 있다.

**확인:** 1280·375·320, 밝은·어두운 테마의 전후 스크린샷(타이머 없음, 진행 중). 헤드리스 CDP로 `타이머 시작` → 진행 줄이 생기고 버튼이 숨으며 폼이 비는지, `정지` → 버튼이 다시 보이는지 확인한다.

## Task 2: 빈 시간 Enter 안내 (E2)

**파일:** `web/pages/dashboard.py`(`DURATION_REQUIRED`), 테스트

**테스트 먼저(RED):** 시간 없이 `POST /logs`를 보내면 오류 문구가 `…시간을 재려면 타이머 시작을 누르세요.`로 끝난다.

## Task 3: 문서와 마무리

- `docs/SPEC.md`: 대시보드 "작업 기록" 패널 설명(한 폼, 버튼 둘, 진행 중 숨김, 빈 시간 오류 문구).
- `README.md`: 대시보드 설명.
- `docs/ROADMAP.md`: 체크.
- 전체 검증: `uv run pytest`(timeout 600000으로 1회, 포트 8765가 비었는지 먼저 확인), `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy src/logbook/core`.
- `final-reviewer` 1회 → 지적 반영 → PR(develop) → "logbook QA" 세션 자동 점검.

## 위험과 대응

| 위험 | 대응 |
|---|---|
| `:has()`를 지원하지 않는 브라우저 | Chrome·Edge·Safari·Firefox 121+가 지원한다. 지원하지 않으면 버튼이 보이기만 하고, 누르면 서버가 지금처럼 이미 진행 중이라고 알린다. |
| 타이머 시작 때 시간 칸에 값이 있으면 헷갈림 | 시간은 무시한다. 성공하면 폼이 비므로 남지 않는다. |
| 시작 실패 문구가 폼 아래 타이머 영역에 뜸 | 폼 바로 아래 줄이라 눈에 들어온다. 스크린샷으로 확인한다. |
