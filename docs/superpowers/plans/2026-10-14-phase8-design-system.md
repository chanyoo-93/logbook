# Phase 8 구현 계획 (웹 대시보드 — 디자인 시스템)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 웹 대시보드(`lb serve`의 다섯 화면)의 겉모양을 공통 디자인 시스템으로 다시 잡는다(ROADMAP Phase 8).
- 색·표면 토큰, 모서리·버튼 체계, 글꼴 설정(설치된 글꼴 이름), 타이포그래피(제목·큰 숫자는 고딕, 보고서는 명조), 꼬리표(pill)·프로젝트 색 점
- 기존 컨셉은 유지한다: Swiss 계열 기록 우선 업무 도구, 입력 줄 위 고정, 큰 숫자, 촘촘한 표, 색은 데이터·상태에만, 상단 내비
- 화면 구조와 조작 방식은 바꾸지 않는다. 칸반 고도화, 등록·수정 화면 분리, 끌어 놓기, 대시보드 위계는 Phase 9다.

**Architecture:**
- **CSS 토큰이 중심이다.** 색·모서리·글꼴·자간을 `app.css`의 `:root` 토큰으로 정하고, 각 화면 CSS는 토큰만 쓴다. 색 값은 지금처럼 `app.css`의 `:root` 두 블록(밝은·어두운)에만 둔다.
- **글꼴 파일은 저장소에 넣지 않는다.** PC에 설치된 글꼴을 CSS 글꼴 이름으로 쓴다. 이름은 설정 `[web]`에서 정하고, 서버가 그 값으로 작은 스타일시트(`GET /fonts.css`)를 만들어 준다. CSP(`style-src 'self'`)가 인라인 스타일을 막으므로 별도 파일로 낸다. 설치되지 않은 글꼴이면 브라우저가 기존 OS 글꼴로 넘어간다.
- **꼬리표와 색 점은 공용 부품이다.** `components.css`의 `.pill`과 템플릿 매크로(`partials/marks.html`)로 모든 화면이 같은 모양을 쓴다. 프로젝트 색 점은 CSP 때문에 `style` 속성이 아닌 SVG `fill`로 칠한다(설정 화면의 색 견본과 같은 방식).
- **프로젝트 색은 어디서나 같다.** 지정한 색이 있으면 그 색, 없으면 프로젝트 ID로 정한 팔레트 색이다. 대시보드 차트도 같은 규칙으로 바꿔 색 점과 차트 색이 맞게 한다.
- 계층 규칙은 그대로다. web은 `core.services`와 허용된 core 진입점만 쓰고, SQL·ORM 쿼리를 쓰지 않는다.

**Tech Stack:** 기존과 같다(Python 3.11+, FastAPI 0.143, Jinja2 3.1, htmx 2.0.11, Chart.js 4.5.1). 새 의존성은 없다.

**선행 조건:**
- **브랜치:** `feat/design-refresh`(develop `cd30666`에서 분기). 이미 있는 커밋:
  - `f43dab7` 색·표면 토큰(계획 없이 먼저 적용) → `62297e2`로 되돌림(사용자 결정). Task 8-1에서 이 계획대로 다시 한다.
  - `92cf3ea`, `a152d75` ROADMAP(Phase 8·9, 남은 확인)
- **uv PATH:** Git Bash `export PATH="/c/Users/User/AppData/Local/Microsoft/WinGet/Packages/astral-sh.uv_Microsoft.Winget.Source_8wekyb3d8bbwe:$PATH"`, PowerShell `$env:Path = "$env:LOCALAPPDATA\Microsoft\WinGet\Packages\astral-sh.uv_Microsoft.Winget.Source_8wekyb3d8bbwe;$env:Path"`
- **진행 규칙(사용자 결정):**
  - 이 계획서를 사용자가 승인한 뒤 구현한다.
  - Task를 하나씩 진행한다. Task마다 구현 1명 + 통합 검토 1명(Sonnet, effort medium)이 끝나면, 메인 세션이 바꾸기 전후 스크린샷(다섯 화면 × 1280·375·320px × 밝은·어두운)을 찍어 사용자에게 보여 주고 승인을 받은 뒤 다음 Task를 시작한다.
  - 사용자가 고칠 점을 말하면 그 Task 안에서 고치고 다시 승인받는다.
- **Task 공통 완료 조건:** 모두 통과한 뒤 커밋한다.
  - `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy src/logbook/core`, `uv run mypy src/logbook`
  - `uv run pytest` (커버리지: core·web 100% 유지)
- **커밋 메시지:** Conventional Commits. type만 영어, 설명·본문은 한국어. CSS만 바꾸면 `style:`, 기능이 늘면 `feat:`.
- **TDD:** 테스트로 고정할 수 있는 것(토큰 존재·대비, CSS 선언, 템플릿 마크업, 설정 검증, 라우트 응답)은 테스트를 먼저 쓰고 실패를 확인한 뒤 구현한다. 모양은 메인 세션의 스크린샷으로 확인한다.
- **사용자 문구 규칙:** 변수 값 바로 뒤에 조사를 붙이지 않는다. core 문구에 `—` 같은 기호를 넣지 않는다. 식별자는 영어.
- **서브에이전트 실행 규칙:**
  - 삭제 명령(rm, Remove-Item, rmdir, git rm, git clean)을 쓰지 않는다. 임시 파일은 새 임시 폴더에 만든다.
  - 다른 프로세스를 강제로 끝내지 않는다. `lb serve`를 터미널에서 띄우지 않는다.
  - 실제 `~/.logbook`, 실제 클립보드, 실제 브라우저를 쓰지 않는다.
  - 글꼴을 설치하거나 OS 설정을 바꾸지 않는다. 화면 모양(스크린샷)은 메인 세션이 확인한다.

---

## 파일 구조

| 파일 | 구분 | 책임 |
|---|---|---|
| `src/logbook/web/static/css/app.css` | 수정 | 색·모양·글꼴·자간 토큰(밝은·어두운), 머리, 빠른 기록 줄 |
| `src/logbook/web/static/css/components.css` | 수정 | 버튼(모서리·누름 효과), 알림, `.pill`·`.dot` |
| `dashboard.css`, `logs.css`, `tasks.css`, `report.css`, `settings.css`, `responsive.css` | 수정 | 토큰 사용(경계·그림자·모서리·글꼴), 설정 화면의 글꼴 미리보기 |
| `src/logbook/core/config.py` | 수정 | `WebConfig.heading_font`·`document_font`·`body_font`와 검증, 기본 설정 파일 |
| `src/logbook/web/fonts.py` | 생성 | `fonts_css(web: WebConfig) -> str` (설정 글꼴 → CSS 변수) |
| `src/logbook/web/pages/fonts.py` | 생성 | `GET /fonts.css` |
| `src/logbook/web/assets.py` | 수정 | `FONTS_CSS_URL = "/fonts.css"` |
| `src/logbook/web/pages/templating.py`, `web/errors.py`, `templates/base.html` | 수정 | 스타일시트 목록 뒤에 `/fonts.css` 링크(화면·오류 페이지 같게) |
| `src/logbook/web/pages/settings.py`, `templates/settings.html` | 수정 | 설정 정보에 글꼴 세 줄과 미리보기 |
| `src/logbook/web/templates/partials/marks.html` | 생성 | 매크로 `pill(text, tone)`, `project_mark(slug, color)` |
| `src/logbook/web/pages/views.py`, `task_views.py`, `summary.py`, `settings.py` | 수정 | `project_color()`(지정 색 또는 ID 팔레트), 행·카드 뷰의 `project_color`, 차트 색 규칙 |
| `templates/partials/task_card.html`, `task_plan.html`, `log_row.html`, `recent.html`, `timer.html`, `project_row.html` | 수정 | 꼬리표·색 점 적용 |
| `tests/web/test_theme.py`, `test_css_layout.py`, `test_static.py`, `test_settings_page.py`, `test_views.py`, `test_dashboard.py`, `test_tasks_page.py`, `test_logs_page.py`, `test_timer_panel.py`, `test_settings_projects.py`, 새 `test_fonts.py` | 수정·생성 | |
| `tests/core/test_config.py` | 수정 | 글꼴 설정 검증, 기본 설정 문서 |
| `docs/SPEC.md`, `README.md`, `CLAUDE.md`, `AGENTS.md`, `docs/ROADMAP.md` | 수정 | 문서 |

---

## Phase 8 공통 규칙

### 색 토큰 (Task 8-1, 8-5)

모든 색은 `app.css`의 `:root`(밝은)와 `@media screen and (prefers-color-scheme: dark)` 안의 `:root`(어두운)에만 있다. 대비는 WCAG 기준이다(글자 4.5:1, 입력칸 경계 3:1).

| 토큰 | 밝은 | 어두운 | 쓰임 |
|---|---|---|---|
| `--bg` | `#f6f5f4` | `#191918` | 바탕(따뜻한 종이색) |
| `--surface` | `#ffffff` | `#222221` | 패널·카드·입력칸 면 |
| `--ink` | `#1f1e1c` | `#ecebe9` | 글자 |
| `--ink-muted` | `#615d59` | `#a3a09b` | 보조 글자 |
| `--rule` | `#e6e5e3` | `#33322f` | 옅은 경계선 |
| `--rule-strong` | `#c9c6c2` | `#4a4844` | 표 머리·바닥 선, 버튼 테두리(새 토큰) |
| `--control-border` | `#8f8a84` | `#77736d` | 입력칸·선택 상자 테두리(새 토큰, 3:1 이상) |
| `--row-hover` | `#f3f2f0` | `#2a2a28` | 행·버튼 hover |
| `--accent` | `#0075de` | `#5ea8f0` | 링크·포커스·주 버튼(유일한 강조색) |
| `--accent-hover` | `#005bab` | `#86bff5` | |
| `--accent-ink` | `#ffffff` | `#0b1724` | 주 버튼 글자 |
| `--ok` | `#0f7a3d` | `#4fc283` | 상태: 정상 |
| `--danger` | `#b42318` | `#ff7b72` | 상태: 오류·예상 초과 |
| `--tag-bg` | `#f1f0ee` | `#2e2d2b` | 꼬리표 바탕(새 토큰, Task 8-5) |
| `--ok-soft` | `#e8f5ec` | `#1f3428` | 정상 꼬리표 바탕(새 토큰, Task 8-5) |
| `--danger-soft` | `#fdecea` | `#3a2422` | 위험 꼬리표 바탕(새 토큰, Task 8-5) |
| `--shadow-soft` | 4겹 옅은 그림자 | 2겹 | 패널·보드 열(새 토큰) |
| `--shadow-raised` | 4겹(마지막 `0 23px 52px rgba(0,0,0,.05)`) | 2겹 | 빠른 기록 줄·알림 |

그림자 값:
```css
/* 밝은 */
--shadow-soft: 0 0.2px 1px rgba(0, 0, 0, 0.01), 0 0.8px 3px rgba(0, 0, 0, 0.02),
  0 2px 8px rgba(0, 0, 0, 0.027), 0 4px 18px rgba(0, 0, 0, 0.04);
--shadow-raised: 0 1px 3px rgba(0, 0, 0, 0.02), 0 3px 9px rgba(0, 0, 0, 0.03),
  0 8px 20px rgba(0, 0, 0, 0.04), 0 23px 52px rgba(0, 0, 0, 0.05);
/* 어두운 */
--shadow-soft: 0 1px 2px rgba(0, 0, 0, 0.3), 0 4px 14px rgba(0, 0, 0, 0.25);
--shadow-raised: 0 2px 6px rgba(0, 0, 0, 0.35), 0 16px 40px rgba(0, 0, 0, 0.4);
```

미리 계산한 대비(2026-10-14):
- 밝은: ink/bg 15.3, ink/surface 16.7, ink-muted/surface 6.5, ink-muted/bg 6.0, accent/surface 4.57, accent-ink/accent 4.57, danger/surface 6.6, ok/surface 5.4, control-border/surface 3.42, control-border/bg 3.14, ink-muted/tag-bg 5.7, danger/danger-soft 5.75, ok/ok-soft 4.83
- 어두운: ink/bg 14.8, ink/surface 13.4, ink-muted/surface 6.1, ink-muted/bg 6.8, accent/surface 6.3, accent-ink/accent 7.2, danger/surface 6.3, ok/surface 7.1, control-border/surface 3.38, control-border/bg 3.73, ink-muted/tag-bg 5.3, danger/danger-soft 5.7, ok/ok-soft 5.9

### 모양 토큰 (Task 8-2)

| 토큰 | 값 | 쓰임 |
|---|---|---|
| `--radius-xs` | `4px` | 입력칸·선택 상자·textarea, 건너뛰기 링크 |
| `--radius-sm` | `8px` | 버튼, 태스크 카드 |
| `--radius-md` | `12px` | 패널(`.panel`), 빠른 기록 줄, 태스크 추가 폼, 보드 열, 알림, 설정 알림, 보고서 미리보기·요약 패널 |
| `--radius-full` | `999px` | 꼬리표(Task 8-5) |

- 기존 `--radius: 2px`는 없앤다. 남은 사용처가 없어야 한다(테스트로 확인).
- 누름 효과: `.btn:active { transform: scale(0.97); }`, `.btn { transition: transform 80ms ease-out, background-color 120ms ease-out; }`. `prefers-reduced-motion`이면 기존 전역 규칙이 transition을 끈다.

### 글꼴 토큰 (Task 8-3, 8-4)

`app.css`의 `:root`(밝은 블록)에 기본값을 둔다. `/fonts.css`가 설정 값으로 덮어쓴다.

```css
--font-sans: "Pretendard", "Apple SD Gothic Neo", "Malgun Gothic", "Noto Sans KR", system-ui, sans-serif; /* 기존 */
--font-serif: "AppleMyungjo", "Batang", "Noto Serif KR", serif; /* 새 토큰 */
--font-body: var(--font-sans);
--font-heading: var(--font-sans);
--font-document: var(--font-serif);
--tracking-title: -0.01em;
--tracking-display: -0.035em;
```

- `body`는 `font-family: var(--font-body)`로 바꾼다.
- 설정 기본값: `heading_font = "Bookk Gothic"`, `document_font = "Bookk Myungjo"`, `body_font = ""`(빈 값이면 `--font-body`를 덮어쓰지 않는다).
- 부크크 폰트의 글꼴 이름은 TTF 이름 정보에서 확인했다: `Bookk Gothic`, `Bookk Myungjo`. Light 파일이 400, Bold 파일이 700이다.

### 꼬리표·색 점 (Task 8-5, 8-6)

```html
{# partials/marks.html #}
{% macro pill(text, tone="", extra="") -%}
<span class="pill{% if tone %} pill--{{ tone }}{% endif %}{% if extra %} {{ extra }}{% endif %}">{{ text }}</span>
{%- endmacro %}
{% macro project_mark(slug, color) -%}
<span class="project-mark"><svg class="dot" width="8" height="8" viewBox="0 0 8 8" aria-hidden="true"><circle cx="4" cy="4" r="4" fill="{{ color }}"/></svg>{{ slug }}</span>
{%- endmacro %}
```
- `tone`은 `""`(중립), `"ok"`, `"danger"`만 쓴다.
- `extra`는 기존 테스트와 화면 코드가 찾는 class(예: `task-card__category`)를 남길 때 쓴다. 그 class의 CSS 규칙은 지워도 class 이름은 표지로 남긴다.
- `color`는 항상 서버가 검증한 `#rrggbb`다(`project_color()`의 결과).

---

## Task 8-0: 계획 문서 저장

- [ ] 이 계획서를 커밋한다: `docs: Phase 8 디자인 시스템 구현 계획 추가`

---

## Task 8-1: 색·표면 토큰

되돌린 `f43dab7`과 같은 방향으로 다시 하되, 입력칸 경계를 고친다. `f43dab7`은 입력칸 hover 테두리가 기본보다 옅어지고(`--rule-strong`), 옅은 테두리는 입력칸 경계 대비 3:1을 넘지 못했다.

**Files:**
- Modify: `app.css`(토큰 두 블록, 머리, 빠른 기록 줄), `components.css`(버튼·알림·타이머 입력칸), `dashboard.css`(`.panel`, 표 머리), `logs.css`(필터·편집 행 입력칸, 표 바닥), `tasks.css`(추가 폼, 보드 열, 편집 카드 입력칸), `report.css`(textarea), `settings.css`(입력칸)
- Modify tests: `tests/web/test_theme.py`(토큰 목록, 대비 쌍), `tests/web/test_css_layout.py`(`.task-edit` 테두리 기대)

**바꾸는 규칙**

| 대상 | 지금 | 바꾼 뒤 |
|---|---|---|
| 토큰 두 블록 | 기존 값 | 위 "색 토큰" 표(Task 8-5의 새 토큰 셋은 제외) |
| `.panel`, `.task-form`, `.board__col` | `border-top: 2px solid var(--ink)` | 줄을 지우고 `box-shadow: var(--shadow-soft)` |
| `.quick` | `border-top: 2px solid var(--ink)` + `--shadow-raised` | 위쪽 선만 지운다(그림자는 새 `--shadow-raised`) |
| `.masthead` | `border-bottom: 2px solid var(--ink)` | `border-bottom: 1px solid var(--rule)` |
| 모든 입력칸·선택 상자·textarea 기본 테두리 | `1px solid var(--ink-muted)` | `1px solid var(--control-border)` |
| 입력칸 hover | `border-color: var(--ink)` | `border-color: var(--ink-muted)` (기본보다 진하게) |
| 입력칸 focus | `var(--accent)` | 그대로 |
| `.btn` 테두리 | `1px solid var(--ink)` | `1px solid var(--rule-strong)`. 버튼은 글자로 알아볼 수 있어 경계 대비 기준(1.4.11) 대상이 아니다 |
| `.grid thead th`의 `border-bottom-color`(dashboard.css), `.grid tfoot td`의 `border-top`(logs.css) | `var(--ink)` | `var(--rule-strong)` |
| 그대로 둠 | 내비 현재 페이지 밑줄(`--ink`), 건너뛰기 링크 테두리, 알림 왼쪽 띠, 타이머 진행 중 띠 | |

- 입력칸 셀렉터는 `grep -rn "border: 1px solid var(--ink-muted)" src/logbook/web/static/css`로 모두 찾는다(빠른 기록, 타이머 시작, 태스크 추가·편집, 필터·편집 행, 프로젝트 폼·편집 행, 특이사항 textarea).

**테스트 케이스**

| 대상 | 케이스 | 기대 |
|---|---|---|
| 토큰 | 두 테마에 `--rule-strong`, `--control-border`, `--shadow-soft`가 있다 | `COLOR_TOKENS`에 더한다 |
| 대비 | 기존 쌍 + `(--control-border, --surface)`, `(--control-border, --bg)` | 글자 쌍 4.5 이상, 경계 쌍 3.0 이상(새 상수 `MIN_NON_TEXT_CONTRAST = 3.0`) |
| CSS | `.panel`·`.task-form`·`.board__col`에 `border-top: 2px solid var(--ink)`가 없고 `box-shadow: var(--shadow-soft)`가 있다 | `_declarations`로 확인 |
| CSS | 입력칸 규칙 어디에도 `border: 1px solid var(--ink-muted)`가 없다(전 CSS 문자열 검사), `.task-edit` 테두리는 `var(--control-border)` | `test_css_layout` 기대를 고친다 |
| CSS | 입력칸 hover 규칙이 `var(--ink-muted)`를 쓴다 | |

- [ ] RED → GREEN → 커밋 `style: 색·표면 토큰을 따뜻한 바탕과 옅은 경계·겹 그림자로 바꾸고 입력칸 경계 대비를 맞춤`
- [ ] 메인 세션: 전후 스크린샷 → 사용자 승인

---

## Task 8-2: 모서리·버튼 체계

**Files:**
- Modify: 모든 CSS(위 "모양 토큰" 표의 사용처), `responsive.css`(필요하면)
- Modify tests: `tests/web/test_css_layout.py`

- `.panel`에 `overflow: clip`을 더해 표 hover 배경·구분선이 둥근 모서리 밖으로 나오지 않게 한다. `overflow: clip`은 스크롤 상자를 만들지 않으므로 패널 안의 `.table-wrap` 가로 스크롤은 그대로 동작한다.
- 패널 가장자리 요소의 포커스 윤곽선이 잘리지 않는지는 메인 세션이 키보드 포커스 스크린샷으로 확인한다(잘리면 그 요소에 `outline-offset: -2px`).
- 태스크 카드의 왼쪽 띠(3px)는 Phase 9에서 바뀌므로 이번에는 모서리만 `--radius-sm`으로 둔다.

**테스트 케이스**

| 대상 | 케이스 | 기대 |
|---|---|---|
| 토큰 | `app.css` `:root`에 `--radius-xs`·`--radius-sm`·`--radius-md`·`--radius-full` | 값이 표와 같다 |
| CSS | 어떤 CSS에도 `var(--radius)`와 `--radius:`가 없다 | |
| CSS | `.btn`은 `border-radius: var(--radius-sm)`, `.panel`은 `var(--radius-md)`와 `overflow: clip`, 입력칸 규칙은 `var(--radius-xs)` | |
| CSS | `.btn:active`는 `transform: scale(0.97)`, `.btn`에 `transition` | |

- [ ] RED → GREEN → 커밋 `style: 모서리 단계(4·8·12px)와 버튼 누름 효과 추가`
- [ ] 메인 세션: 전후 스크린샷(키보드 포커스 1장 포함) → 사용자 승인

---

## Task 8-3: 글꼴 설정 (설치된 글꼴 이름)

**Files:**
- Modify: `src/logbook/core/config.py`, `src/logbook/web/assets.py`, `src/logbook/web/pages/templating.py`, `src/logbook/web/templates/base.html`, `src/logbook/web/errors.py`, `src/logbook/web/pages/__init__.py`, `src/logbook/web/pages/settings.py`, `src/logbook/web/templates/settings.html`, `src/logbook/web/static/css/app.css`(글꼴 토큰 기본값, `body`), `src/logbook/web/static/css/settings.css`(미리보기)
- Create: `src/logbook/web/fonts.py`, `src/logbook/web/pages/fonts.py`, `tests/web/test_fonts.py`
- Modify tests: `tests/core/test_config.py`, `tests/web/test_static.py`(링크 목록), `tests/web/test_settings_page.py`, `tests/web/test_config_reload.py`(설정 바꾼 뒤 `/fonts.css`)

```python
# core/config.py
@dataclass(frozen=True)
class WebConfig:
    host: str = "127.0.0.1"
    port: int = 8765
    heading_font: str = "Bookk Gothic"
    document_font: str = "Bookk Myungjo"
    body_font: str = ""

# 글꼴 이름: 100자 이하, 따옴표·역슬래시·세미콜론·쉼표·중괄호·꺾쇠·제어 문자 없음. 빈 값은 기본 글꼴.
_FONT_NAME = re.compile(r"[^\x00-\x1f\x7f\"'\\;,{}<>]{0,100}")
FONT_NAME_RULE = "글꼴 이름 하나(100자 이하, 따옴표·역슬래시·세미콜론·쉼표·중괄호·꺾쇠 없이) 또는 빈 값"
```
- `_Table.to_web()`이 세 키를 `self.string(...)`으로 읽고 `_FONT_NAME.fullmatch`와 `value == value.strip()`을 확인한다. 어기면 기존 `_invalid(name, value, FONT_NAME_RULE)` 문구다.
- `_default_document()`는 `asdict(defaults.web)`이라 기본 설정 파일에 세 키가 자동으로 들어간다. `test_write_default_config_document`의 `"web"` 기대를 고친다.
- `restart_keys()`는 바꾸지 않는다. 글꼴은 다시 시작하지 않아도 새로 고침으로 반영된다(설정 자동 반영 + `/fonts.css`는 `no-store`).

```python
# web/fonts.py
def fonts_css(web: WebConfig) -> str:
    """설정 글꼴을 CSS 변수로. 빈 값은 줄을 내지 않아 app.css의 기본값이 남는다."""
```
출력 예(기본 설정):
```css
/* 설정 [web]의 글꼴. PC에 설치되지 않은 글꼴이면 다음 글꼴로 넘어간다. */
:root {
  --font-heading: "Bookk Gothic", var(--font-sans);
  --font-document: "Bookk Myungjo", var(--font-serif);
}
```
- `body_font`가 있으면 `--font-body: "<이름>", var(--font-sans);` 줄을 더한다.
- 세 값이 모두 비면 주석과 빈 `:root {}`만 낸다.

```python
# web/pages/fonts.py
@router.get("/fonts.css")
def fonts_stylesheet(ctx: Ctx) -> Response:
    return Response(fonts_css(ctx.cfg.web), media_type="text/css; charset=utf-8")
```
- `/static/` 밖이라 보안 미들웨어가 `Cache-Control: no-store`를 붙인다. 설정을 고친 뒤 새로 고침만 하면 바뀐다.
- `assets.FONTS_CSS_URL = "/fonts.css"`. `STYLESHEETS`에는 넣지 않는다(`test_stylesheet_list_has_every_css_file_exactly_once`가 `static/css`의 파일 목록과 비교한다). `templating.py`가 전역으로 넘기고 `base.html`은 스타일시트 반복 다음에 `<link rel="stylesheet" href="{{ FONTS_CSS_URL }}">`을 둔다. 오류 페이지(`errors._stylesheet_links()`)도 같은 링크를 마지막에 더한다.

**설정 화면**
- `SettingsInfoView.fonts: tuple[FontRowView, ...]`(`label`, `name`, `preview_class`)
  - `("제목 글꼴", 설정 값 또는 "기본 글꼴", "font-preview--heading")`, `("문서 글꼴", …, "font-preview--document")`, `("본문 글꼴", …, "font-preview--body")`
- `settings.html`의 `<dl class="info">`에서 하루 목표 다음, 카테고리 앞에 세 줄을 둔다.
  ```html
  <dt>제목 글꼴</dt>
  <dd>Bookk Gothic <span class="font-preview font-preview--heading">가나다 ABC 123 · 8h 55m</span></dd>
  ```
- 안내 문구(상수 `FONT_NOTE`, `info__note` 아래 한 줄): `글꼴은 이 PC에 설치된 글꼴 이름으로 정합니다(설정 [web]의 heading_font·document_font·body_font). 설치되지 않은 글꼴이면 기본 글꼴로 보입니다.`
- `settings.css`: `.font-preview { margin-left: var(--space-3); font-size: var(--text-md); }`, `--heading`은 `font-family: var(--font-heading); font-weight: 700;`, `--document`는 `var(--font-document)`, `--body`는 `var(--font-body)`.

**테스트 케이스**

| 대상 | 케이스 | 기대 |
|---|---|---|
| config | `[web]` 글꼴 키 없음 | 기본값 세 개 |
| config | `heading_font = "나눔고딕"`, `"Noto Sans CJK KR"`, `""` | 그대로 |
| config | `"A\"B"`, `"A;B"`, `"A, B"`, `"{x}"`, `"<b>"`, `" A"`, 101자, 숫자 값 | 각각 `_invalid` 문구(키 이름 포함) |
| config | `write_default_config` 문서 | `"web"`에 세 키 |
| `fonts_css` | 기본 / 셋 다 빈 값 / body만 있음 | 위 출력 예와 같다 / 빈 `:root` / `--font-body` 줄만 |
| `/fonts.css` | GET | 200, `text/css; charset=utf-8`, `Cache-Control: no-store`, `X-Content-Type-Options: nosniff`, CSP 있음 |
| `/fonts.css` | 설정 파일에서 `heading_font`를 바꾸고 다시 GET | 새 이름(설정 자동 반영) |
| 링크 | 대시보드 HTML | 스타일시트 링크가 `STYLESHEETS` 순서 + 마지막 `/fonts.css`. `test_static.py`의 `test_base_template_links_every_stylesheet_in_order` 기대를 `[f"/static/css/{n}" for n in STYLESHEETS] + ["/fonts.css"]`로 바꾼다 |
| 링크 | 오류 페이지 | 대시보드와 같은 링크 목록 |
| 설정 화면 | 기본 설정 / `body_font = ""` | 세 줄과 미리보기 class, 빈 값은 `기본 글꼴`, 안내 문구 |
| CSS | `body`가 `var(--font-body)`, 글꼴 토큰 기본값이 `:root`에 있다 | |

- [ ] RED → GREEN → 커밋 `feat: 설정에서 설치된 글꼴을 지정하는 /fonts.css와 설정 화면 미리보기 추가`
- [ ] 메인 세션: 전후 스크린샷. 이 PC에 부크크가 없으면 임시 설정의 `heading_font`를 설치된 글꼴(예: `Malgun Gothic`, 문서는 `Batang`)로 바꿔 적용 경로를 확인한다 → 사용자 승인

---

## Task 8-4: 타이포그래피 (제목·큰 숫자 고딕, 보고서 명조)

**Files:**
- Modify: `app.css`(자간 토큰, `.masthead__brand`), `dashboard.css`(`.panel__title`, `.stat__value`), `tasks.css`(`.board__title`, `.board__col-title`, `.plan__title`), `report.css`(`.report__title`, `.report-notes__title`, `.report__preview`, `.report-polish__text`)
- Modify tests: `tests/web/test_css_layout.py`

| 대상 | 바꾼 뒤 |
|---|---|
| `.masthead__brand`, `.panel__title`, `.board__title`, `.board__col-title`, `.plan__title`, `.report__title`, `.report-notes__title` | `font-family: var(--font-heading); letter-spacing: var(--tracking-title);` (굵기 700 유지) |
| `.stat__value` | `font-family: var(--font-heading); letter-spacing: var(--tracking-display);` (기존 `-0.02em` 대체) |
| `.report__preview`, `.report-polish__text` | `font-family: var(--font-document);` (`.report__preview`의 `font: inherit` 뒤에 둔다) |
| 그대로 | 본문, 표, 입력칸, 버튼, 차트 글꼴 |

- `.masthead__brand`의 `letter-spacing: -0.03em`은 `var(--tracking-display)`로 바꾼다(큰 글자일수록 좁게).

**테스트 케이스**

| 대상 | 케이스 | 기대 |
|---|---|---|
| CSS | 위 표의 선언이 각 셀렉터에 있다 | `_declarations`로 확인(파라미터 표에 행 추가) |
| CSS | 자간 토큰 두 개가 `:root`에 있다 | |

- [ ] RED → GREEN → 커밋 `style: 제목·큰 숫자에 제목 글꼴과 자간, 보고서 미리보기에 문서 글꼴 적용`
- [ ] 메인 세션: 전후 스크린샷(다섯 화면, 보고서 요약 패널 포함) → 사용자 승인

---

## Task 8-5: 꼬리표(pill) 통일

**Files:**
- Modify: `app.css`(토큰 `--tag-bg`·`--ok-soft`·`--danger-soft` 두 블록), `components.css`(`.pill` 추가, `.timer__state` 규칙 삭제: `pill pill--ok`가 대신한다), `tasks.css`(`.task-card__tag`·`.task-card__over` 규칙 삭제)
- Create: `src/logbook/web/templates/partials/marks.html`(`pill` 매크로만, `project_mark`는 Task 8-6)
- Modify templates: `task_card.html`, `task_plan.html`, `log_row.html`, `recent.html`, `timer.html`, `project_row.html`
- Modify tests: `tests/web/test_theme.py`, `test_tasks_page.py`, `test_tasks_plan.py`, `test_logs_page.py`, `test_dashboard.py`, `test_timer_panel.py`, `test_settings_projects.py`

```css
.pill {
  display: inline-flex;
  align-items: center;
  min-height: 1.25rem;
  padding: 0 var(--space-2);
  border-radius: var(--radius-full);
  background: var(--tag-bg);
  color: var(--ink-muted);
  font-size: var(--text-xs);
  font-weight: 600;
  line-height: 1.6;
  white-space: nowrap;
}
.pill--ok { background: var(--ok-soft); color: var(--ok); }
.pill--danger { background: var(--danger-soft); color: var(--danger); }
```

| 화면 | 지금 | 바꾼 뒤 |
|---|---|---|
| 태스크 카드 | 카테고리 글자, 주차 꼬리표(`.task-card__tag`), `예상 초과`(`.task-card__over`) | `pill(category, extra="task-card__category")`, `pill(week_tag, extra="task-card__tag")`(주차 라벨 `2026-W42`는 옆에 보조 글자로 남김), `pill("예상 초과", "danger", "task-card__over")` |
| 다음 주 계획 | `(이월 후보)` 글자 | `pill("이월 후보")`(괄호 없음) |
| 기록 표 | 카테고리 칸 글자 | 카테고리 `pill` |
| 최근 기록 | `payment/dev` 한 칸 | 프로젝트 글자 + 카테고리 `pill`(칸 머리 `프로젝트/카테고리` 그대로) |
| 타이머 | `진행 중`(`.timer__state` 초록 글자) | `pill("진행 중", "ok")` |
| 프로젝트 표 | 상태 칸 `보관`/`사용 중` 글자 | `pill("보관")` / `pill("사용 중", "ok")` |

- 표 행 높이(36px)는 그대로다. 꼬리표 높이(1.25rem)가 행 안에 들어간다.
- 고칠 기존 테스트:
  - `test_tasks_page.py`(119·147·160행 부근): class 표지(`task-card__over`·`__tag`·`__category`)는 그대로 남으므로 찾기는 통과한다. 각 요소에 `pill`(위험은 `pill--danger`) class가 있는지 단언을 더한다.
  - `test_tasks_plan.py`(60·61·133행 부근): `(이월 후보)` 글자 대신 `<span class="pill">이월 후보</span>`를 확인한다.
  - `test_dashboard.py`(226행 부근): 최근 기록 행 글자 기대를 새 마크업의 글자로 고친다(Task 8-6에서 한 번 더 바뀐다).
  - 타이머 `진행 중`(test_dashboard.py 264행 부근), 프로젝트 표 `보관`(test_settings_page.py 48행 부근)은 글자가 같아 그대로 통과한다.
- 화면 낭독기에는 글자 그대로 읽힌다(꼬리표는 장식 class만 더한다).

**테스트 케이스**

| 대상 | 케이스 | 기대 |
|---|---|---|
| 토큰·대비 | 새 토큰 셋, `(--ink-muted, --tag-bg)`·`(--ok, --ok-soft)`·`(--danger, --danger-soft)` 4.5 이상 | 두 테마 |
| 태스크 카드 | 카테고리 있음·없음, 이번 주·다음 주·지난 주·주차 없음, 예상 초과 | 각 `pill` 마크업과 글자, 없는 값은 꼬리표 없음 |
| 계획 패널 | 이월 후보 | `<span class="pill">이월 후보</span>` |
| 기록 표·최근 기록 | 카테고리 | `pill` 안의 카테고리 글자 |
| 타이머 | 진행 중 | `pill pill--ok` |
| 프로젝트 표 | 보관·사용 중 | 두 꼬리표 |
| CSS | `.task-card__tag`·`.task-card__over` 규칙이 없다, `.pill`·`.pill--ok`·`.pill--danger`가 있다 | |

- [ ] RED → GREEN → 커밋 `feat: 카테고리·주차·상태 표시를 공용 꼬리표(pill)로 통일`
- [ ] 메인 세션: 전후 스크린샷 → 사용자 승인

---

## Task 8-6: 프로젝트 색 점과 같은 색 규칙

**Files:**
- Modify: `src/logbook/web/pages/views.py`(`project_color()`, `LogRowView.project_color`), `task_views.py`(`TaskCardView.project_color`), `summary.py`(차트 색 규칙), `settings.py`(같은 검증 재사용), `templates/partials/marks.html`(`project_mark`), `task_card.html`, `log_row.html`, `recent.html`, `components.css`(`.project-mark`, `.dot`)
- Modify tests: `tests/web/test_views.py`, `test_dashboard.py`, `test_tasks_page.py`, `test_logs_page.py`

```python
# web/pages/views.py
def project_color(project: Project) -> str:
    """지정한 색(검증된 #rrggbb)이 있으면 그 색, 없으면 프로젝트 ID로 고른 CHART_PALETTE 색.

    ID는 바뀌지 않으므로 같은 프로젝트는 어느 화면·어느 주에서도 같은 색이다.
    """
    color = project.color or ""
    if services.is_valid_color(color):
        return color
    return CHART_PALETTE[(project.id - 1) % len(CHART_PALETTE)]
```
- `CHART_PALETTE`는 `summary.py`에서 `views.py`로 옮긴다. `summary.py`와 `tests/web/test_views.py`는 `logbook.web.pages.views`에서 import한다. `views`와 `summary`는 서로 import하지 않으므로 순환 import는 없다(검토에서 확인). `Project` 타입은 `TYPE_CHECKING` 안에서 import한다.
- 차트: `summary.py`는 `services.list_projects(s, include_archived=True)`로 얻은 Project 객체로 `{slug: project_color(project)}`를 만들고, `project_colors(slugs, explicit)`는 없앤다. 막대·도넛 색이 이번 주에 나타난 순서가 아니라 프로젝트 ID로 정해진다(색 점과 같음). 카테고리 색 규칙은 그대로다.
- 템플릿: 태스크 카드의 프로젝트 이름, 기록 표의 프로젝트 칸, 최근 기록의 프로젝트 글자를 `project_mark(slug, color)`로 바꾼다. 태스크 카드는 `<span class="task-card__project">` 안에 `project_mark`를 넣어 기존 class 표지와 굵은 글씨 규칙을 남긴다.
- `.project-mark { display: inline-flex; align-items: center; gap: var(--space-1); }`, `.dot { flex: none; }`

**테스트 케이스**

| 대상 | 케이스 | 기대 |
|---|---|---|
| `project_color` | 지정 색 / 없음(ID 1, 2, 팔레트 길이+1) / 잘못된 값(`"red"`) | 그 색 / `CHART_PALETTE[0]`, `[1]`, `[0]` / 팔레트 색 |
| 차트 | 이번 주에 프로젝트 b(ID 2)만 기록 | b의 색이 `CHART_PALETTE[1]`(전에는 순서상 `[0]`) |
| 차트 | 지정 색 프로젝트 | 지정 색(지금과 같음) |
| 기존 테스트 | `test_views.py`의 `project_colors` 테스트 세 개 | `project_color` 테스트로 바꾼다 |
| 기존 테스트 | `test_dashboard.py`의 `EXPECTED_CHART`(50·55행 부근) | `common`(ID 1)의 색을 `PALETTE_ORANGE`에서 `PALETTE_BLUE`(`CHART_PALETTE[0]`)로 고친다. 카테고리 색은 그대로 |
| 기존 테스트 | `test_dashboard.py` 최근 기록 행 글자(226행 부근) | 색 점 마크업 뒤의 글자로 고친다 |
| 마크업 | 태스크 카드·기록 표·최근 기록 | `<svg class="dot" … fill="#…">` + slug, `aria-hidden="true"` |
| CSP | 위 화면 HTML | `style=` 속성이 없다 |

- [ ] RED → GREEN → 커밋 `feat: 프로젝트 색 점과 화면·차트 공통 프로젝트 색 규칙 추가`
- [ ] 메인 세션: 전후 스크린샷(차트 색 변화 포함) → 사용자 승인

---

## Task 8-7: 문서 마무리와 Phase 8 완료

- [ ] **SPEC.md**
  - 3장(설정): `[web]`의 `heading_font`·`document_font`·`body_font`, 기본값, 이름 규칙, 설치되지 않으면 기본 글꼴, 다시 시작 없이 반영
  - 6장(웹): `GET /fonts.css`, 설정 화면의 글꼴 줄, 디자인 토큰 원칙(색은 데이터·상태에만, 강조색 하나, 꼬리표·색 점), 프로젝트 색 규칙(지정 색 또는 ID 팔레트, 차트 포함)
- [ ] **README.md**: 글꼴 설정 절(부크크 폰트는 부크크에서 받아 PC에 설치하고 약관을 따른다, 설정 예시, Windows·macOS 설치 방법 한 줄씩), 화면 설명의 바뀐 모양
- [ ] **CLAUDE.md, AGENTS.md**: `web/fonts.py`, `web/pages/fonts.py`, `partials/marks.html`, `static/css` 설명(토큰 종류)
- [ ] **ROADMAP.md**: Phase 8 체크
- [ ] **화면 확인(메인 세션, Edge 헤드리스)**: 다섯 화면 × 1280·375·320px × 밝은·어두운, 가로 넘침 없음, 키보드 포커스, 글꼴 적용 경로
- [ ] **브라우저 확인(사용자, Windows·macOS, 절차는 PR 댓글)**: 부크크 폰트를 설치한 PC에서 제목·큰 숫자·보고서 글꼴, 설정 화면 미리보기, 설정 파일을 고친 뒤 새로 고침, 어두운 테마
- [ ] **전체 검증:** ruff, format, mypy(core strict, 전체), pytest(core·web 100%), GitHub Actions 두 OS
- [ ] **PR:** develop 대상, `Closes #<이슈 번호>`

---

## 크로스 플랫폼 체크리스트 (Phase 8 추가분)

- 글꼴 이름은 OS와 상관없이 같다(`Bookk Gothic`, `Bookk Myungjo`). 설치되지 않은 OS에서는 기존 글꼴로 넘어간다.
- 명조 대체 글꼴: macOS `AppleMyungjo`, Windows `Batang`, 그 밖 `Noto Serif KR`, 마지막 `serif`
- 설정 파일의 한글 글꼴 이름(예: `나눔고딕`)은 UTF-8로 읽고 CSS에도 그대로 쓴다(`/fonts.css`는 `charset=utf-8`).
- 스크린샷 확인은 Windows Edge 헤드리스다. macOS Safari 모양은 사용자 확인 항목이다.

---

## 설계 결정 요약 (계획 승인 시 함께 확정)

1. **글꼴은 이름만 쓴다:** 폰트 파일을 저장소에 넣지 않는다. 라이선스·용량 문제가 없고, 사용자가 원하는 설치 글꼴로 바꿀 수 있다.
2. **`/fonts.css`는 `no-store`다:** 몇 줄짜리라 매번 받아도 부담이 없고, 설정을 고친 뒤 새로 고침만으로 반영된다.
3. **글꼴 이름은 하나만 받는다:** 쉼표 목록을 받지 않는다. 대체 글꼴은 서버가 기존 OS 글꼴 목록을 붙인다. CSS 주입을 막으려고 따옴표·세미콜론·중괄호 등을 거부한다.
4. **입력칸 경계는 3:1을 지킨다:** 옅은 경계선(`--rule`)은 장식용이고, 입력칸 테두리는 별도 토큰(`--control-border`)으로 3:1 이상이다.
5. **프로젝트 색은 ID로 고정한다:** 같은 프로젝트는 어느 화면에서나 같은 색이다. 차트 색이 이번 주 순서에서 ID 순서로 바뀐다(지정 색은 그대로).
6. **화면 구조는 바꾸지 않는다:** 버튼·폼·칸반 구성은 Phase 9에서 바꾼다. Phase 8은 겉모양만이다.

---

## 사용자 결정 (2026-10-14)

- 디자인 개선을 두 Phase로 나눈다: Phase 8 디자인 시스템, Phase 9 화면 고도화(칸반, 등록·수정 화면 분리, 끌어 놓기 + 중단 열(SortableJS), 대시보드 위계)
- 글꼴: 폰트 파일을 넣지 않고 설치된 글꼴을 설정에서 지정한다(방법 A). 설치 글꼴 목록에서 고르기(방법 B)는 하지 않는다.
- 구현: Task마다 서브에이전트 구현 1명 + 검토 1명, Task마다 사용자 승인
- 1번(색 토큰)을 계획 없이 먼저 적용한 커밋은 되돌리고 이 계획대로 다시 한다.

---

## 계획 검토 (2026-10-14)

사실 확인 에이전트 1명(Sonnet)이 코드·대비 수치·정규식·CSS 동작을 확인했다(Edge 헤드리스 실험 포함).
- 맞음: 기존 코드 전제, 대비 26개 수치, 글꼴 이름 정규식 판정, `overflow: clip` 안의 가로 스크롤 유지, reduced-motion 규칙이 transition을 끔, 나중 스타일시트의 `var(--font-sans)` 참조
- 반영: 팔레트는 `views.py`로 옮김(순환 import 없음), 차트 색 테스트(`common` 색)·`project_colors` 테스트 교체, `.timer__state` 규칙 삭제, 꼬리표에 기존 class 표지를 남기는 `extra` 인자, 표 머리·바닥 선의 실제 속성 이름, `/fonts.css`를 `STYLESHEETS`에 넣지 않음과 링크 테스트 기대
- 참고: 이 PC의 Edge는 `prefers-reduced-motion: reduce`가 켜져 있다. 누름 효과(scale)는 transition 없이 즉시 적용된다.

---

## 후속 항목 (Phase 8 범위 밖, 기록만)

1. Phase 9 전체(칸반 고도화, 등록·수정 화면 분리, 끌어 놓기·중단 열, 대시보드 위계)
2. 설치 글꼴 목록에서 고르기와 웹에서 설정 저장(방법 B)
3. 어두운 테마의 차트 팔레트 대비 점검(Phase 6 후속 4)
