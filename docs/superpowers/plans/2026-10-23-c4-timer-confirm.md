# Issue #21 C4·타이머 취소 확인 창 수정 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Issue #21에 남은 두 가지를 고친다.
- C4: 기본 `common` 프로젝트와 `dev` 카테고리가 같은 파랑이다. 어두운 테마에서 짙은 프로젝트 색 점의 대비가 낮다.
- 타이머 취소 확인 창의 경과가 처음 값에 머문다.

그리고 Issue #21 B2·B11 결과를 문서에 반영한다(ROADMAP 체크, SPEC의 한글 입력기 동작).

**기준:** develop 41cfc8f(PR #22 병합)에서 갈라진 브랜치 `fix/c4-timer-confirm`

**진행:**
1. 이 계획서를 사용자가 승인하면 구현한다. 구현 1명 + 검토 1명(Sonnet medium)이다.
2. 색(Task 1·2)은 화면이 바뀐다. 메인 세션이 전후 스크린샷과 비교 페이지를 만들어 사용자 승인을 받는다.
3. 전체 검증 → PR(develop 대상, `Refs #21`) → #21 댓글 → 사용자 macOS 확인

**Tech Stack:** 기존과 같다. 새 의존성은 없다.

**승인:** 사용자가 이 계획서를 승인했다(2026-10-23, 76292c6).

---

## 결정 (2026-10-23 결정 게이트, 사용자 확정)

| # | 결정할 것 | 결정 |
|---|---|---|
| G1 | common·dev가 같은 파랑 | 프로젝트 자동 색의 순서를 카테고리와 따로 둔다. 카테고리는 지금 색 그대로다 |
| G2 | 어두운 테마의 짙은 색 점 | 어두운 테마에서만 점 둘레에 옅은 테두리를 그린다. 색은 그대로라 차트 색과 같다 |
| G3 | 취소 확인 창의 경과 | 60초마다 경과를 갱신할 때 확인 문구도 갱신한다 |

**메인 세션이 정한 세부(승인 대상):**
- G1의 순서: 프로젝트 자동 색은 팔레트를 **끝에서부터 거꾸로** 쓴다(`CHART_PALETTE[(n - 1 - (id - 1)) % n]`, n = 10).
  - 기본 카테고리 9개가 팔레트 0~8번을 쓴다. 그래서 common(ID 1)은 어떤 기본 카테고리와도 겹치지 않는 회색 `#495057`이 된다.
  - 다음 프로젝트들(ID 2, 3, …)은 `#a61e4d`, `#5c940d`, `#e67700`, … 순서다. 덜 쓰는 카테고리(admin, study, support) 색부터 받는다.
  - 10색뿐이라 프로젝트가 많아지면 어떤 카테고리와는 겹친다. 겹침이 싫으면 설정 화면에서 색을 고르면 된다(지금과 같다).
- G3의 방식: 버튼을 통째로 바꾸지(OOB) 않는다. 키보드 포커스가 취소 버튼에 있을 때 사라지기 때문이다.
  - 경과 갱신 응답(`#timer-elapsed`)에 새 확인 문구를 `data-cancel-confirm`으로 싣는다.
  - `app.js`가 그 교체 뒤에 취소 버튼의 `hx-confirm` 속성만 바꾼다. htmx는 요청을 보낼 때 속성을 읽으므로 새 문구가 쓰인다.

---

## 사실 (메인 세션 확인)

- `web/pages/views.py`의 `project_color`는 지정 색이 없으면 `CHART_PALETTE[(id - 1) % 10]`이다. `category_color_map`은 설정 순서 위치의 팔레트 색이다. 그래서 common(ID 1)과 dev(첫 카테고리)가 둘 다 0번 `#2f6fde`다.
- `project_color`를 쓰는 곳: 기록 행·태스크 카드·설정 표의 색 점, 대시보드 프로젝트 차트(`summary.py`), 설정의 색 고르기 칸 값(`settings.py` 193·285행). 한 함수만 바꾸면 모두 같은 색이 된다.
  - `ProjectAddValues.color`(새 프로젝트 폼의 색 고르기 기본값 `CHART_PALETTE[0]`)는 자동 색이 아니라 고르기 칸의 시작값이라 그대로 둔다.
- 색 점은 `partials/marks.html` `project_mark`의 SVG 원(`fill`)이다(`.dot`, 8px).
- 어두운 바탕 `#222221` 대비: `#2f6fde` 3.37, `#e8590c` 4.45, `#2b8a3e` 3.65, `#c2255c` 2.82, `#7048e8` 2.87, `#0b7285` 2.85, `#e67700` 5.31, `#5c940d` 4.32, `#a61e4d` 2.21, `#495057` 1.95. 밝은 바탕에서는 모두 3:1 이상이다.
- 타이머 확인 문구 `CANCEL_CONFIRM`은 `timer_view`가 만들어 취소 버튼 `hx-confirm`에 넣는다. `/timer/elapsed`는 `partials/timer_elapsed.html`(`<span id="timer-elapsed" … hx-swap="outerHTML">`)만 돌려준다.

---

## Task 1: 프로젝트 자동 색 순서(G1)

**Files:** `src/logbook/web/pages/views.py`(`project_color`), 테스트(`tests/web/test_views*.py` 또는 색 관련 테스트), 프로젝트 색을 단정하는 기존 테스트

- 지정 색이 없으면 팔레트를 끝에서부터 거꾸로 쓴다. 지정 색이 있으면 지금처럼 그 색이다.
- 카테고리 색(`category_color_map`)은 바꾸지 않는다.

| 대상 | 케이스 | 기대 |
|---|---|---|
| `project_color` | ID 1(색 없음) | `#495057` |
| `project_color` | ID 2·3·10·11 | `#a61e4d`·`#5c940d`·`#2f6fde`·`#495057`(10개마다 반복) |
| `project_color` | 지정 색 있음 | 그 색 |
| 기본 설정 | common(ID 1)과 dev | 색이 다르다. common 색은 기본 카테고리 9개의 색 어디에도 없다 |
| 차트·점 | 대시보드 프로젝트 차트와 기록 행 색 점 | 같은 프로젝트는 같은 색 |

- 이미 자동 색을 쓰던 프로젝트는 점·차트 색이 바뀐다(데이터는 그대로). SPEC·README에 적는다.
- [x] RED → GREEN → 커밋 `fix: 프로젝트 자동 색을 팔레트 끝에서부터 써서 기본 카테고리 색과 겹치지 않게`

---

## Task 2: 어두운 테마 색 점 테두리(G2)

**Files:** `src/logbook/web/static/css/app.css`(토큰 `--dot-ring` 두 블록), `components.css`(`.dot`), `tests/web/test_theme.py`, `tests/web/test_css_layout.py`

- 새 토큰 `--dot-ring`을 둔다. 밝은 테마는 `transparent`(지금 모양 그대로), 어두운 테마는 옅은 회색이다. 값은 `--surface`·`--bg`와 비글자 대비 3:1 이상이 되게 고른다(출발점 `--ink-muted`의 어두운 값 `#a3a09b`).
- `.dot`에 `border-radius: 50%`와 `box-shadow: 0 0 0 1px var(--dot-ring)`을 준다. 점 크기와 색은 그대로다. CSP 때문에 인라인 style은 쓰지 않는다.
- 색 값은 Phase 8 규칙대로 `app.css`의 `:root` 두 블록에만 둔다.

| 대상 | 케이스 | 기대 |
|---|---|---|
| 토큰 | `--dot-ring` 두 테마 | 둘 다 있다. 밝은 테마는 `transparent` |
| 대비 | 어두운 `--dot-ring` 대 `--surface`·`--bg` | 3:1 이상 |
| CSS | `.dot` | `box-shadow`가 `var(--dot-ring)`을 쓴다 |

- [x] RED → GREEN → 커밋 `fix: 어두운 테마에서 프로젝트 색 점에 옅은 테두리`
- [x] 메인 세션: Task 1·2 전후 스크린샷(대시보드·기록·태스크·설정 × 1280·375·320px × 밝은·어두운)과 비교 페이지 → 사용자 승인

---

## Task 3: 취소 확인 창의 경과 갱신(G3)

**Files:** `src/logbook/web/pages/timer.py`(`/timer/elapsed`), `templates/partials/timer_elapsed.html`, `static/js/app.js`, `tests/web/test_timer_panel.py`, `tests/web/test_static.py`(app.js 문자열)

- `timer_elapsed.html`의 span에 `data-cancel-confirm="{{ timer.cancel_confirm }}"`을 둔다. 패널을 처음 그릴 때와 경과 갱신 때 모두 같은 조각이라 값이 늘 최신이다.
- `app.js`: `htmx:afterSettle`에서 대상이 `#timer-elapsed`면, 그 값을 `#timer` 안 취소 버튼(`[hx-post="/timer/cancel"]`)의 `hx-confirm`에 넣는다. 인라인 코드는 쓰지 않는다.
- 타이머가 없으면(경과 갱신이 빈 응답 등) 아무것도 하지 않는다. 지금 동작을 확인하고 맞춘다.

| 대상 | 케이스 | 기대 |
|---|---|---|
| `/timer/elapsed` | 시작 뒤 시계를 61초 옮김 | 응답 span의 `data-cancel-confirm`에 `경과 1m` |
| 패널 | `GET /timer` | 취소 버튼 `hx-confirm`과 span `data-cancel-confirm`이 같은 문구 |
| `app.js` | 문자열 | `timer-elapsed`, `data-cancel-confirm`, `hx-confirm`을 다룬다 |

- [x] RED → GREEN → 커밋 `fix: 타이머 경과를 갱신할 때 취소 확인 창 문구도 갱신`
- [x] 메인 세션·QA 세션 화면 확인: 61초 뒤 취소 확인 창 문구가 `경과 1m`, 취소 버튼에 포커스가 있을 때 갱신돼도 포커스 유지

---

## Task 4: 문서

- [x] **SPEC.md**
  - 프로젝트 색 규칙: 자동 색은 팔레트를 끝에서부터 쓴다(카테고리는 앞에서부터). 어두운 테마의 점 테두리.
  - 타이머: 경과를 갱신할 때 취소 확인 문구도 갱신한다. 후속 항목의 "타이머 취소 확인 창의 경과"를 지운다.
  - 한글 입력기(Issue #21 B2): Enter 한 번에 조합 확정과 저장, Esc는 조합 중이어도 곧 취소(입력기가 Esc를 조합에 쓰지 않음, 사용자 결정 2026-10-19).
- [x] **README.md:** 프로젝트 색이 바뀔 수 있다는 업그레이드 안내(자동 색을 쓰던 프로젝트)
- [x] **ROADMAP.md:** "남은 확인"의 B2·B11 체크(2026-10-19 사용자 확인), Phase 9 보완 항목 아래에 이번 수정 항목
- [x] 커밋 `docs: 프로젝트 자동 색·점 테두리·취소 확인 문구와 #21 B2·B11 결과 반영`

---

## 구현 기록

- 구현 a2578a1(Task 1), 74635ee(Task 2, `--dot-ring` 어두운 값 #a3a09b, `--surface` 6.11·`--bg` 6.75), 1684e22(Task 3). 각 RED 확인, 전체 pytest 3109 passed. 검토(Sonnet medium) approved, minor M1(app.js 테스트는 문자열만)은 Edge 헤드리스 확인으로 보완: 경과 갱신 뒤 hx-confirm `경과 0m`→`경과 5m`, 같은 버튼, 포커스 유지.
- 색 비교 페이지(compare-c4.html) 사용자 승인(2026-10-23).

## Task 5: 검증, PR, 기록

- [ ] 전체 검증: ruff, format, mypy(core strict, 전체), pytest
- [ ] PR: develop 대상, `Refs #21`, CI
- [ ] #21 댓글: C4·취소 확인 창 수정 결과(Windows), 본문 C4 항목 갱신은 사용자 macOS 확인 뒤
- [ ] 사용자 macOS 확인: 색(common 회색, dev 파랑), 어두운 테마 점 테두리, 61초 뒤 취소 확인 문구

---

## 범위 밖

- 팔레트 자체(10색)를 바꾸거나 늘리기
- 카테고리 색 순서
- 차트 색의 어두운 테마 보정
