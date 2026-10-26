# Phase 9 보완: 대시보드 기록 집중 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 2026-10-26 대시보드 디자인 평가(`/impeccable critique`, 26/40, 기록은 `.impeccable/critique/`)의 P1 두 개와 접근성 문제를 고친다.
1. 위계: 가장 큰 요소가 "이번 주 공수" 숫자이고 타이머는 차트 아래(1280 폭에서 y≈900)에 있다. 기록과 타이머를 위쪽 한 패널로 모은다.
2. 문구: 프로젝트 선택 상자의 빈 값 "자동 (태스크 또는 common)"이 1280·1920 폭 모두에서 잘린다.
3. 접근성: 어두운 테마에서 입력 칸 안내 글자 대비가 3.5:1이다(`::placeholder` 규칙 없음, 브라우저 기본 `#757575`). 모든 화면에 `<h1>`이 없다. 타이머 영역에 제목이 없다.

**범위 밖(평가의 P2):** 최근 기록을 날짜 순으로 바꾸기(방향은 날짜 순으로 정함), 차트 접기와 정리, 단축키.

**기준:** develop 68f9117(PR #24 병합)에서 갈라진 브랜치 `feat/dashboard-focus`

**진행:**
1. 이 계획서를 사용자가 승인하면 Task 순서대로 구현한다.
2. 변경이 작아서 구현은 메인 세션이 직접 한다. Task마다 테스트를 먼저 고치거나 써서 실패를 확인(RED)하고 구현한다.
3. Task마다 전후 스크린샷(1280·375·320px × 밝은·어두운)을 보여 사용자 승인을 받은 뒤 다음 Task로 넘어간다.
4. 끝에 문서 → 전체 검증(pytest·ruff·mypy) → 브랜치 최종 리뷰 1회(`final-reviewer`, Sonnet high) → PR(develop 대상) → 사용자 Windows·macOS 확인

**Tech Stack:** 기존과 같다. 새 의존성은 없다. JS 변경도 없다.

---

## 결정 (2026-10-26 결정 게이트, 사용자 확정)

| ID | 결정 |
|---|---|
| D1 | 빠른 기록과 타이머를 위쪽 **"작업 기록" 패널 하나**에 두 줄로 넣는다. 화면 순서는 작업 기록 → 최근 기록 → 주간 요약(숫자·차트)이다. |
| D2 | 빈 값 문구를 **"프로젝트 자동"·"카테고리 자동"·"태스크 없음"**으로 줄이고, 자동 규칙 전체 설명은 선택 상자의 말풍선(`title`)에 둔다. 타이머 폼도 같다. |
| D3 | `base.html`에서 **모든 화면**에 화면 이름을 화면 낭독기용 숨김 `<h1>`으로 넣는다. 보이는 화면은 바뀌지 않는다. |
| D4 | develop 최신(68f9117)에서 새 브랜치 `feat/dashboard-focus`. |
| D5 | 작업 기록 패널은 **위에 붙지 않는다**(`position: sticky` 제거). 기록·타이머가 이미 맨 위에 있다. |

함께 정한 방향(평가 질문 답): 대시보드의 주인공은 기록·타이머다.

---

## Task 1: 작업 기록 패널과 화면 순서 (D1, D5)

**파일:** `templates/dashboard.html`, `templates/partials/quick_form.html`, `templates/partials/timer.html`, `static/css/app.css`, `static/css/components.css`, `static/css/dashboard.css`, `static/css/responsive.css`, 테스트 `tests/web/test_dashboard.py`, `tests/web/test_css_layout.py`, `tests/web/test_timer_actions.py`(필요하면)

**구조:**
```html
<section id="work" class="panel work" aria-labelledby="work-title">
  <div class="panel__head"><h2 id="work-title" class="panel__title">작업 기록</h2></div>
  <form id="quick-form" class="quick" ...>…</form>        <!-- 그대로, 카드 모양만 뺌 -->
  <section id="timer" class="timer ..." aria-labelledby="timer-title">
    <h3 id="timer-title" class="visually-hidden">타이머</h3>
    …                                                    <!-- 내용·HTMX 속성 그대로 -->
  </section>
</section>
{% include "partials/recent.html" %}
{% include "partials/summary.html" %}
```
- `#quick-form`과 `#timer`의 id, HTMX 속성(`hx-target`, `hx-swap="outerHTML"`, OOB)은 바꾸지 않는다. 바깥에 패널만 씌운다. 그래서 저장·시작·정지·취소 응답 조각은 그대로 동작한다.
- `#timer`에서 `panel` 클래스를 뺀다(작업 기록 패널 안의 한 줄이 된다). 빠른 기록 줄과 타이머 줄 사이에는 얇은 괘선(`border-top: 1px solid var(--rule)`)을 둔다.
- `aria-label="타이머"`를 숨김 `<h3>`과 `aria-labelledby`로 바꾼다(평가: 타이머 영역 제목 없음).

**CSS:**
- `.quick`에서 `position: sticky`, `top`, `z-index`, 테두리·모서리·`--shadow-raised`를 뺀다. 패널 안 줄 간격만 남긴다. 겉모양은 `.panel`이 맡는다.
- 큰 숫자를 줄인다(평가: 약 30%).
  - `--text-stat-lead`: 최대 4.25rem → 3rem.
  - `--text-stat`: 최대 3.25rem → 2.5rem. 비율은 유지한다.
  - 이 토큰은 대시보드 요약에서만 쓴다(`dashboard.css:67,75`).
- 인쇄: `responsive.css`의 `@media print`에서 `.quick` 대신 `.work`(작업 기록 패널 전체)를 숨긴다.

**테스트 먼저(RED):**
- 순서: `#work`(안에 `#quick-form`, `#timer`) → `#recent` → `#summary`. `test_dashboard_page_skeleton`과 `test_dashboard_sections_are_in_reading_order`를 이 순서로 고친다.
- `#timer`의 태그와 `aria-labelledby="timer-title"`, 숨김 h3 "타이머"를 검사한다.
- `.quick`에 `position: sticky`가 없고, `.panel` 그림자 규칙을 따른다. `test_quick_bar_has_no_heavy_top_rule_but_keeps_raised_shadow`와 모서리 검사(`test_css_layout.py:263`)를 새 구조에 맞게 바꾼다.
- 숫자 토큰 최대값을 검사한다.
- 타이머 응답(시작·정지·취소)의 OOB 조각에도 같은 마크업이 나오는지 검사한다. 기존 테스트가 이미 보는 부분은 그대로 둔다.

**확인:**
- 전후 스크린샷 1280·375·320 × 밝은·어두운.
- 진행 중 타이머 상태도 찍는다.
- 1280×720에서 타이머 시작 버튼이 첫 화면 안에 보이는지 잰다(평가 기준: 보이는지).

## Task 2: 선택 상자 빈 값 문구 (D2)

**파일:** `templates/partials/choose_macro.html`, `quick_form.html`, `timer.html`, 테스트 `tests/web/test_quick_add.py:118,122`, `tests/web/test_timer_actions.py:300`

- `choose` 매크로에 선택 인자 `hint`를 더한다. 값이 있으면 `<select title="{{ hint }}">`.
- 문구:

| 칸 | 빈 값 | 말풍선(`title`) |
|---|---|---|
| 프로젝트 | 프로젝트 자동 | 비우면 태스크의 프로젝트, 태스크가 없으면 {기본 프로젝트}에 기록합니다. |
| 카테고리 | 카테고리 자동 | 비우면 태스크의 카테고리를 씁니다. |
| 태스크 | 태스크 없음 | (없음) |

- 숨긴 `<label>`(프로젝트·카테고리·태스크)은 그대로 둔다. 화면 낭독기는 레이블 + 선택값 + 설명을 읽는다.
- 타이머 폼도 같은 말풍선을 쓴다. 타이머는 정지할 때 기록되므로 "기록합니다"가 그대로 맞다.

**테스트 먼저(RED):** 두 폼의 첫 option 문구와 프로젝트·카테고리 `title`을 검사한다. 기본 프로젝트 이름이 말풍선에 들어가는지도 본다.

**확인:** 1280·1920 폭에서 문구가 잘리지 않는지 잰다(`scrollWidth`가 `clientWidth` 이하). 375·320 스크린샷도 찍는다.

## Task 3: 접근성 — h1과 안내 글자 대비 (D3)

**파일:** `templates/base.html`, `static/css/app.css`, 테스트(새 테스트 또는 화면별 기존 테스트)

- `base.html`의 `<main>` 첫 줄에 `<h1 class="visually-hidden">{{ self.title() }}</h1>`을 넣는다(대시보드·기록·태스크·새 태스크·태스크 수정·보고서·설정).
- 오류 페이지(`web/errors.py`가 따로 만든다)는 이번 범위에서 빼고 결과에 적는다.
- `app.css`에 `::placeholder { color: var(--ink-muted); opacity: 1; }`를 넣는다.
  - `--ink-muted`의 대비는 밝은 테마 `#615d59` on `#ffffff`가 6.53:1, 어두운 테마 `#a3a09b` on `#222221`이 6.11:1이다(WCAG 상대 휘도 계산, 2026-10-26). 둘 다 4.5:1을 넘고, 테스트에 숫자로 남긴다.
  - `opacity: 1`은 Firefox가 placeholder를 흐리게 하는 기본값을 막는다.
  - 모든 화면의 입력 칸에 적용된다(기록 필터, 태스크 폼, 보고서 특이사항 포함).

**테스트 먼저(RED):**
- 화면 7개 각각에 h1이 하나이고 글자가 화면 이름과 같은지 검사한다.
- `::placeholder` 규칙과 두 테마의 대비 숫자를 검사한다(기존 대비 계산 도우미가 있으면 그것을 쓴다).

**확인:**
- 어두운 테마 CDP 검사(`impeccable detect --cdp`)로 low-contrast 0건을 확인한다.
- 보이는 화면이 바뀌지 않았는지 화면별 전후 스크린샷을 비교한다.

## Task 4: 문서와 마무리

- `docs/SPEC.md`:
  - 대시보드 화면 설명(431행 근처)을 작업 기록 패널, 순서, 위에 붙지 않음으로 고친다.
  - 빠른 기록 문단(366행)에 빈 값 문구와 말풍선을 적는다.
  - 접근성(화면 h1, 안내 글자 대비)을 적는다.
- `README.md`: 대시보드 설명이 있으면 맞춘다.
- `docs/ROADMAP.md`: 항목 체크.
- 사용자에게 알릴 것: 저장소 밖으로 옮긴 `docs/SCREENS.md`에서 바뀌어야 할 곳이 있다. "1. 대시보드" 구성 순서, 1-1 빠른 기록의 빈 값 문구, 타이머 폼 문구다.
- 전체 검증: `uv run pytest`(timeout 600000으로 1회), `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy src/logbook/core`.
- `final-reviewer` 1회 → 지적 반영 → PR(develop 대상, 확인 절차 포함) → 사용자 Windows·macOS 확인.

## 위험과 대응

| 위험 | 대응 |
|---|---|
| 타이머 응답 조각(OOB)이 바뀐 바깥 구조와 어긋남 | id·HTMX 속성은 그대로 두고 바깥 패널만 씌운다. 시작·정지·취소 응답 테스트를 돌린다. |
| 위에 붙는 동작이 사라져 아래에서 기록하려면 위로 올라가야 함 | D5에서 받아들였다. 확인 절차에 적는다. |
| `title` 말풍선은 터치 화면에서 안 보임 | 데스크톱 전용 도구라 받아들인다. 짧은 문구만으로도 뜻이 통하게 했다. |
| 큰 숫자 축소로 요약의 위계가 약해짐 | 이번 주 공수(lead)는 다른 숫자보다 여전히 크다(3rem 대 2.5rem). 스크린샷으로 확인한다. |
