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

- [x] 이 계획서를 커밋한다: `docs: Phase 8 디자인 시스템 구현 계획 추가`

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

- [x] RED → GREEN → 커밋 `style: 색·표면 토큰을 따뜻한 바탕과 옅은 경계·겹 그림자로 바꾸고 입력칸 경계 대비를 맞춤` (f3386e7)
- [x] 메인 세션: 전후 스크린샷 → 사용자 승인 (2026-10-14)

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

- [x] RED → GREEN → 커밋 `style: 모서리 단계(4·8·12px)와 버튼 누름 효과 추가` (7e9d662, 보완 b859716 요약 패널 모서리, 9e2c178 표 안 버튼 포커스 윤곽선)
- [x] 메인 세션: 전후 스크린샷(키보드 포커스 1장 포함) → 사용자 승인 (2026-10-14)

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

- [x] RED → GREEN → 커밋 `feat: 설정에서 설치된 글꼴을 지정하는 /fonts.css와 설정 화면 미리보기 추가` (0ded719)
- [x] 메인 세션: 전후 스크린샷. 이 PC에 부크크가 없으면 임시 설정의 `heading_font`를 설치된 글꼴(예: `Malgun Gothic`, 문서는 `Batang`)로 바꿔 적용 경로를 확인한다 → 사용자 승인 (2026-10-14. 바탕·궁서로 경로 확인 뒤 사용자가 부크크를 설치해 다시 확인. 본문 명조 Light 보기용 스크린샷도 봤고, 기본값은 계획대로 본문 기존 글꼴로 결정)

---

## Task 8-4: 타이포그래피 (제목·큰 숫자 고딕, 보고서 명조)

**Files:**
- Modify: `app.css`(자간 토큰, `.masthead__brand`), `dashboard.css`(`.panel__title`, `.stat__value`), `tasks.css`(`.board__title`, `.board__col-title`, `.plan__title`), `report.css`(`.report__title`, `.report-notes__title`, `.report__preview`, `.report-polish__text`)
- Modify tests: `tests/web/test_css_layout.py`

| 대상 | 바꾼 뒤 |
|---|---|
| `.panel__title`, `.board__title`, `.board__col-title`, `.plan__title`, `.report__title`, `.report-notes__title` | `font-family: var(--font-heading); letter-spacing: var(--tracking-title);` (굵기 700 유지) |
| `.masthead__brand` | `font-family: var(--font-heading); letter-spacing: var(--tracking-display);` (아래 줄 참고, 2026-10-14 계획 모순 정정) |
| `.stat__value` | `font-family: var(--font-heading); letter-spacing: var(--tracking-display);` (기존 `-0.02em` 대체) |
| `.report__preview`, `.report-polish__text` | `font-family: var(--font-document);` (`.report__preview`의 `font: inherit` 뒤에 둔다) |
| 그대로 | 본문, 표, 입력칸, 버튼, 차트 글꼴 |

- `.masthead__brand`의 `letter-spacing: -0.03em`은 `var(--tracking-display)`로 바꾼다(큰 글자일수록 좁게).

**테스트 케이스**

| 대상 | 케이스 | 기대 |
|---|---|---|
| CSS | 위 표의 선언이 각 셀렉터에 있다 | `_declarations`로 확인(파라미터 표에 행 추가) |
| CSS | 자간 토큰 두 개가 `:root`에 있다 | |

- [x] RED → GREEN → 커밋 `style: 제목·큰 숫자에 제목 글꼴과 자간, 보고서 미리보기에 문서 글꼴 적용` (3385a51, 사용자 결정으로 보고서 미리보기 15px ec08c57)
- [x] 메인 세션: 전후 스크린샷(다섯 화면, 보고서 요약 패널 포함) → 사용자 승인 (2026-10-14, 글꼴 통일 Task 8-4b와 함께 승인)

---

## Task 8-4b: 글꼴 통일 (사용자 결정, 2026-10-14)

Task 8-4 확인 중 사용자가 "글꼴이 다 달라 통일성이 떨어진다"고 했다. 전부 명조와 전부 고딕 보기용 스크린샷을 비교한 뒤 **전부 부크크 고딕**으로 정했다(보고서 문서 영역 포함, 차트 글자 포함). 8-4의 보고서 미리보기 15px(ec08c57)는 그대로 둔다.

**Files:**
- Modify: `src/logbook/core/config.py`(`WebConfig` 기본값), `src/logbook/web/static/css/app.css`(글꼴 토큰 기본값), `src/logbook/web/fonts.py`(문서 글꼴 대체 목록), `src/logbook/web/static/js/dashboard.js`(차트 글꼴)
- Modify tests: `tests/core/test_config.py`(기본값·기본 설정 문서), `tests/web/test_fonts.py`(출력 기대), `tests/web/test_settings_page.py`(글꼴 줄), `tests/web/test_css_layout.py` 또는 `test_theme.py`(토큰), 차트 글꼴을 확인하는 정적 JS 테스트(새로 더함)

| 대상 | 지금 | 바꾼 뒤 |
|---|---|---|
| `WebConfig` 기본값 | `heading_font="Bookk Gothic"`, `document_font="Bookk Myungjo"`, `body_font=""` | 셋 다 `"Bookk Gothic"` |
| `app.css` 기본값(설정 스타일시트가 없을 때) | `--font-document: var(--font-serif)` | `--font-document: var(--font-sans)`. 쓰는 곳이 없어지는 `--font-serif` 토큰은 지운다 |
| `fonts_css` 대체 목록 | 문서 글꼴 뒤에 `var(--font-serif)` | `var(--font-sans)`(세 글꼴 모두 같은 대체 목록) |
| 차트 글꼴(`dashboard.js`) | `Chart.defaults.font.family = cssVariable("--font-sans")` | `cssVariable("--font-body")`. 테마가 바뀌어 다시 그릴 때도 같다 |
| 굵기 | | 부크크 고딕은 Light(300)·Bold(700) 두 개뿐이다. 400·500 글자는 Light, 600 이상은 Bold로 그려진다(CSS 글꼴 고르기 규칙). 굵기 값은 바꾸지 않는다 |

- 부크크를 설치하지 않은 PC는 세 글꼴 모두 기존 OS 고딕(`--font-sans`)으로 보인다.
- 설정 화면 글꼴 줄은 세 줄 모두 `Bookk Gothic`이 된다. `body_font = ""`로 두면 지금처럼 `기본 글꼴`이다.
- README·SPEC의 기본값 설명은 Task 8-7에서 맞춘다.

**테스트 케이스**

| 대상 | 케이스 | 기대 |
|---|---|---|
| config | `[web]` 글꼴 키 없음 / 기본 설정 문서 | 셋 다 `Bookk Gothic` |
| `fonts_css` | 기본 설정 | `--font-heading`·`--font-document`·`--font-body` 세 줄, 모두 `var(--font-sans)` 대체 |
| CSS | `:root` 기본값 | `--font-document: var(--font-sans)`, `--font-serif` 없음(전 CSS 검사) |
| JS | `dashboard.js` | `cssVariable("--font-body")`로 차트 글꼴을 정하고 `--font-sans`를 쓰지 않는다 |
| 설정 화면 | 기본 설정 | 세 줄 모두 `Bookk Gothic` |

- [x] RED → GREEN → 커밋 `style: 글꼴 기본값을 부크크 고딕으로 통일하고 차트도 본문 글꼴을 따르게 함` (eb15067)
- [x] 메인 세션: 전후 스크린샷(8-4 결과 대비) → 사용자 승인. 승인되면 8-4도 함께 체크한다 (2026-10-14)

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

- [x] RED → GREEN → 커밋 `feat: 카테고리·주차·상태 표시를 공용 꼬리표(pill)로 통일` (3ac2574)
- [x] 메인 세션: 전후 스크린샷(compare-8-5.html) → 사용자 지시(2026-10-14 밤: Phase 8의 남은 Task를 진행하고 아침에 한 번에 확인, Phase 9는 진행하지 않음)에 따라 진행, 아침 일괄 확인 → 사용자 승인(2026-10-15, Task 8-9와 함께)

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

- [x] RED → GREEN → 커밋 `feat: 프로젝트 색 점과 화면·차트 공통 프로젝트 색 규칙 추가` (52b4503)
- [x] 메인 세션: 전후 스크린샷(compare-8-6.html, 차트 색 변화 포함, 가로 넘침 없음) → 사용자 지시(2026-10-14 밤)에 따라 진행, 아침 일괄 확인 → 사용자 승인(2026-10-15, Task 8-9와 함께)
- 관찰(아침 확인에서 묻는다, 계획에서 바꾸지 않음): 시험 데이터에서 `common`(ID 1)이 계획대로 `CHART_PALETTE[0]`(파랑)이 되어, 지정 색인 `payment`(남색)·`search`(하늘색)와 함께 프로젝트 차트에 파란 계열이 셋 놓인다. 카테고리 차트의 첫 색(개발)도 같은 파랑이다. 대안: 프로젝트 색을 팔레트에서 한 칸 밀어 쓴다(ID 1 → 주황). 설계 결정 5(ID로 고정)는 그대로이고 시작 위치만 바뀐다.

---

## Task 8-7: 문서 마무리와 Phase 8 완료

- [x] **SPEC.md** (3f3e70b)
  - 3장(설정): `[web]`의 `heading_font`·`document_font`·`body_font`, 기본값, 이름 규칙, 설치되지 않으면 기본 글꼴, 다시 시작 없이 반영
  - 6장(웹): `GET /fonts.css`, 설정 화면의 글꼴 줄, 디자인 토큰 원칙(색은 데이터·상태에만, 강조색 하나, 꼬리표·색 점), 프로젝트 색 규칙(지정 색 또는 ID 팔레트, 차트 포함)
- [x] **README.md** (3f3e70b): 글꼴 설정 절(부크크 폰트는 부크크에서 받아 PC에 설치하고 약관을 따른다, 설정 예시, Windows·macOS 설치 방법 한 줄씩), 화면 설명의 바뀐 모양
- [x] **CLAUDE.md, AGENTS.md** (3f3e70b): `web/fonts.py`, `web/pages/fonts.py`, `partials/marks.html`, `static/css` 설명(토큰 종류)
- [x] **ROADMAP.md** (3f3e70b): Phase 8 체크
  - 최종 리뷰 반영(c320fe5): `document_font` 사용처(보고서 미리보기와 문장 다듬기 결과 글, 특이사항 입력란은 본문 글꼴)와 모서리 토큰 사용처(태스크 카드 8px)를 문서에서 바로잡았다. README 글꼴 설치 방법은 두 OS 모두 글꼴 파일을 두 번 클릭하는 경로로 고쳤다(95b5b29).
- [x] **화면 확인(메인 세션, Edge 헤드리스)**: 다섯 화면과 편집 상태 두 개 × 1280·375·320px × 밝은·어두운(42장), 가로 넘침 없음. 키보드 포커스: 좁은 폭에서 잘림 0건, 넓은 폭 후보 2건(설정 표 안 버튼)은 측정 도구가 윤곽선 간격 4px를 가정한 것이고 포커스 스크린샷에서 윤곽선이 버튼 안쪽에 온전히 보인다(8-2 보완 9e2c178). 글꼴 적용 경로: 설정을 `Batang`·`Gungsuh`·빈 값으로 바꾸면 미리보기의 계산된 `font-family` 첫 글꼴이 그 이름이고 빈 값은 기본 고딕 목록이다. 8-6 뒤와 최종 스크린샷은 배치가 같다(다른 픽셀은 임시 DB 경로 글자와 글자 안티앨리어싱).
- [ ] **브라우저 확인(사용자, Windows·macOS, 절차는 PR 댓글)**: 부크크 폰트를 설치한 PC에서 제목·큰 숫자·보고서 글꼴, 설정 화면 미리보기, 설정 파일을 고친 뒤 새로 고침, 어두운 테마
- [x] **전체 검증:** ruff, format, mypy(core strict, 전체), pytest 2853 passed·2 skipped(core·web 100%), GitHub Actions 두 OS 통과(windows-latest 5m24s, macos-latest 4m5s)
- [x] **PR:** develop 대상, `Closes #17` (#18)

---

## 보완: 사용자 지정 색 (사용자 결정, 2026-10-15)

아침 확인에서 차트 팔레트 시작 위치(`common`이 카테고리 첫 색과 같은 파랑, 후속 5)를 여쭸다. 사용자 답은 "꼬리표 pill은 사용자가 정할 수 있도록, 프로젝트 색 점도 사용자가 정할 수 있도록. 차트 색은 그럼 자동으로 이를 따라가면 되겠지."였다. 결정 게이트에서 정한 것은 다음과 같다.

| 결정 | 내용 |
|---|---|
| C1 카테고리 색 저장 | 웹 설정 화면(`/settings`)에서 고르고 DB(`category_colors`)에 저장한다. 카테고리 정의(키·이름)는 지금처럼 설정 파일 `[categories]`에 있다 |
| C2 카테고리 꼬리표 | 그 색을 옅게(20%) 깐 바탕에 본문색 글자를 쓴다. 카테고리 차트는 같은 색(진하게)이다 |
| C3 상태 꼬리표 | 그대로 둔다(주차·예상 초과·이월 후보·진행 중·보관·사용 중은 의미 색 고정) |
| C4 프로젝트 색 | 설정 화면의 추가·수정 칸을 브라우저 색 고르기(`<input type="color">`)와 `자동` 체크로 바꾼다. CLI `--color`는 그대로다 |

- 색을 정하지 않은 카테고리·프로젝트는 지금 규칙을 따른다. 카테고리는 설정 순서 팔레트, 프로젝트는 ID 팔레트다. 팔레트를 한 칸 미는 조정(후속 5)은 하지 않는다.
- 이 보완은 설계 결정 6(Phase 8은 겉모양만)의 예외다. 설정 화면에 카테고리 색 표와 색 고르기 칸이 생기고, DB 스키마가 3으로 오른다.
- 스키마 3이 들어간 버전을 처음 실행하면 기존 DB가 자동으로 업그레이드되고, 그 전에 백업 파일(`logbook.db.v2-YYYYMMDD-HHMMSS.bak`)이 생긴다. 이것은 Phase 6의 v1 → v2와 같은 기존 동작이다.
- 진행은 Phase 8과 같다. 이 보완 계획을 승인받는다 → Task마다 구현 1명 + 검토 1명(Sonnet, medium) → 메인 세션 스크린샷 → 사용자 승인. 결과는 PR #18에 함께 넣는다.
- 8-5(꼬리표)·8-6(색 점)의 승인은 Task 8-9 스크린샷(카테고리 꼬리표가 바뀜)을 확인할 때 함께 받는다.
- **승인:** 사용자가 이 보완 계획(검토 반영본 6d538e6)을 승인했다(2026-10-15).

### 색 규칙 (Task 8-8~8-10 공통)

| 대상 | 색 | 쓰는 곳 |
|---|---|---|
| 카테고리(설정에 있음) | `category_colors`에 행이 있으면 그 색이다. 없으면 설정 `[categories]` 순서 위치의 `CHART_PALETTE` 색이다 | 꼬리표(`/colors.css`), 카테고리 차트, 설정 화면 표 |
| 카테고리(설정에 없음: 설정에서 지운 카테고리로 남은 기록) | 행이 있으면 그 색이다. 없으면 차트는 지금 규칙(설정 개수 뒤 위치를 이름 순으로)을 따르고, 꼬리표는 회색 그대로다 | 같음 |
| 프로젝트 | 지금과 같다(`project_color`: 지정 색, 없으면 ID 팔레트) | 색 점, 프로젝트 차트, 설정 화면 견본 |

- 카테고리 색은 함수 하나가 정한다. `summary.py`의 `category_colors`를 `web/pages/views.py`로 옮겨 `category_color_map(configured, stored, present=())`로 넓힌다. 차트, `/colors.css`, 설정 화면 표가 모두 이 함수를 쓴다.
- 카테고리 키 형식은 한 규칙을 함께 쓴다. `core/config.py`의 `_CATEGORY_KEY`(`[a-z][a-z0-9_-]*`)를 공개 이름으로 바꿔 설정·서비스·가져오기·`/colors.css`·꼬리표 class가 같이 쓴다. 이 형식이면 CSS class 이름(`pill--cat-<키>`)으로 그대로 쓸 수 있다.
- **꼬리표 class는 형식이 맞는 키에만 붙인다.** 기록·태스크의 `category`에는 설정에 없는 문자열이 남을 수 있다(백업 가져오기의 category 종류는 문자열 검사만 한다). 템플릿 필터 `category_class`(templating.py에 등록)가 키가 형식에 맞으면 `pill--cat-<키>`를, 아니면 빈 문자열을 돌려준다. 형식이 틀린 키는 기본 꼬리표(회색)다.
- **`/colors.css`는 순수 함수가 만든다.** `web/colors.py`의 `colors_css(configured, stored)`는 설정 카테고리 키와 저장 색 사전을 받는다. 라우트가 `services.category_colors(s)`로 저장 색을 읽어 넘긴다(web은 SQLAlchemy를 쓰지 않는다, `tests/web/test_layering.py`).
  - 화면을 열 때마다 DB를 한 번 더 읽는다(`no-store`).
  - DB가 잠겨 있거나 없어 `/colors.css`가 실패하면 꼬리표는 회색으로 보인다(허용).
- **색 비교는 대소문자를 무시한다.** `<input type="color">`는 값을 소문자로 보낸다. 저장된 `#4F46E5`와 받은 `#4f46e5`는 같은 색으로 보고 `바뀐 내용이 없습니다.`를 보여 준다. 프로젝트·카테고리 모두 같다.
- **`자동` 체크의 폼 이름과 값:** 카테고리는 `auto`, 프로젝트는 `color_auto`이고 켜짐 값은 `"1"`이다. 꺼지면 키가 오지 않으므로 `FormText` 기본값 `""`로 받는다. 켜져 있으면 색 칸 값은 무시한다.

---

## Task 8-8: 카테고리 색 저장 (core: 모델·마이그레이션·서비스·백업)

**Files:**
- Create: `src/logbook/core/services/category_colors.py`
- Modify:
  - `src/logbook/core/models.py`(`CategoryColor`, 맨 위 docstring의 테이블 목록)
  - `core/db.py`(`SCHEMA_VERSION = 3`, `_upgrade_to_3`, `MIGRATIONS`, 51행 부근 마이그레이션 주석)
  - `core/config.py`(키 정규식 공개)
  - `core/services/__init__.py`(import와 `__all__`)
  - `core/services/projects.py`(색 검증을 공개 함수로)
  - `core/services/backup.py`, `core/services/backup_import.py`
  - `cli/commands/data.py`(내보내기·가져오기 결과 줄)
- Modify tests:
  - `tests/core/test_db.py:18`(`TABLES`)
  - `test_db_migration_v2.py`
    - 102행 `SCHEMA_VERSION == 2`
    - 117·261·270행 `InitResult(1, 2, …)`, 233행 `InitResult(2, 2)`, 274행 `InitResult(None, 2)` → 최신 버전 기준
    - 242~248행: 여러 단계 백업 테스트가 3을 "다음 버전"으로 쓰므로 `SCHEMA_VERSION + 1` 기준으로 바꾼다
  - 새 `test_db_migration_v3.py`, 새 `test_services_category_colors.py`
  - `tests/core/backup_helpers.py:110`(머리글 형식)
  - `test_services_backup.py`: 20~21행(머리글), 262행(`TABLE_ORDER`와 모델 테이블), 264행(`FORMAT_VERSION`), 291행(`(2, 2)`), 320행(export 이름)
  - `test_services_backup_import.py`, `test_services_backup_import_validation.py:258`(형식 2 테이블 순서 문구)
  - 결과 줄: `tests/cli/test_data.py`(19·215·252·268행), `tests/cli/test_entry.py`(254·262행)

```python
# core/models.py
class CategoryColor(Base):
    """카테고리 색. 행이 없으면 자동(설정 순서 팔레트)이다. 카테고리 정의는 설정 파일에 있다."""

    __tablename__ = "category_colors"

    category: Mapped[str] = mapped_column(String(32), primary_key=True)
    color: Mapped[str] = mapped_column(String(7))
    updated_at: Mapped[dt.datetime] = mapped_column(default=utcnow, onupdate=utcnow)
```

```python
# core/db.py: 고정 DDL이다. 모델이 나중에 바뀌어도 이 단계는 그대로 둔다.
def _upgrade_to_3(conn: Connection) -> None:
    conn.exec_driver_sql(
        "CREATE TABLE category_colors (category VARCHAR(32) NOT NULL, color VARCHAR(7) NOT NULL, "
        "updated_at DATETIME NOT NULL, PRIMARY KEY (category))"
    )
```
- 새 DB(`create_all`)와 올린 DB의 `PRAGMA table_info(category_colors)`가 같아야 한다. 기존 v2 테스트와 같은 방식으로 비교한다.

**서비스** (`core/services/category_colors.py`)

| 함수 | 동작 |
|---|---|
| `category_colors(s) -> dict[str, str]` | 저장된 색 전부를 `{키: 색}`으로 돌려준다 |
| `set_category_color(s, category, color) -> None` | 키 형식과 색(`#rrggbb`, 프로젝트와 같은 오류 문구)을 검사한다. 행이 있으면 바꾸고, 없으면 만든다 |
| `clear_category_color(s, category) -> bool` | 행을 지운다(자동으로 되돌림). 지운 행이 있으면 True |

- 키가 설정에 있는지는 web이 확인한다. core 서비스는 설정을 받지 않는다.
- 색 검증은 `projects.py`의 `_validate_color`를 공개 함수로 바꿔 함께 쓴다. 대소문자는 지금 프로젝트처럼 입력 그대로 저장한다.
- 쓰기는 `s.flush()`까지만 한다. 커밋은 호출자의 `session_scope`가 한다(`week_notes.py`와 같다).

**백업 (형식 3)**

| 대상 | 바꾼 뒤 |
|---|---|
| `FORMAT_VERSION` | 3 |
| `TABLE_ORDER` | 끝에 `category_colors`를 더한다. 필드는 `category`, `color`, `updated_at`, 정렬 키는 `category` |
| 가져오기 형식 | `SUPPORTED_FORMATS = (1, 2, 3)`, `FORMAT_TABLES = {1: TABLE_ORDER[:4], 2: TABLE_ORDER[:5], 3: TABLE_ORDER}`. 형식 2 파일에 `category_colors` 줄이 있으면 오류다 |
| 가져오기 검증 | `category`는 키 형식, `color`는 새 검증 종류(`#rrggbb`, 오류 문구 포함), `updated_at`은 시각이다. 키가 겹치면 오류다 |
| 가져오기 표 | `_REFERENCES["category_colors"] = ()`(없으면 `_check_references`가 KeyError), `_KINDS["category_colors"]`(필드 순서는 `FIELDS`와 같게), 새 종류 둘(카테고리 키 형식, `#rrggbb` 색)과 그 `_EXPECTED` 안내 문구·`_CONVERTERS` 변환기 |
| 빈 DB 검사 | `_existing_common`의 모델 목록에 `CategoryColor`를 더한다 |
| 개수 | `BackupCounts.category_colors`(기본값 0). 내보내기(`export_records`)와 가져오기(`import_records`) 모두 센다 |
| 문서 문자열 | `backup.py` 모듈 docstring의 형식 버전 |
| CLI 결과 줄 | `프로젝트 N · 태스크 N · 기록 N · 타이머 N · 특이사항 N · 카테고리 색 N` |

- 알 수 없는 테이블 줄은 지금처럼 `N번째 줄: 알 수 없는 테이블입니다: …` 오류다. 형식 2 파일의 `category_colors` 줄도 이 오류가 된다(추가 코드 없음).
- 기존 `projects.color`의 가져오기 검증(`opt_str`)은 그대로 둔다(범위 밖, 후속 항목).

**테스트 케이스**

| 대상 | 케이스 | 기대 |
|---|---|---|
| 마이그레이션 | 데이터가 있는 v2 DB → v3 | 기존 행 수 그대로, `category_colors` 생김, 버전 3, 백업 1개 |
| 마이그레이션 | v1 → v3 | 두 단계 모두 적용, 백업은 1개 |
| 마이그레이션 | 새 DB와 올린 DB | `PRAGMA table_info(category_colors)`가 같음 |
| 서비스 | 저장 → 바꾸기 → 목록 → 지우기 → 다시 지우기 | 목록 내용, 지우기는 True 다음 False |
| 서비스 | 잘못된 색(`red`, `#12345`), 잘못된 키(`Dev`, `1x`, `a b`) | `InvalidInputError`와 문구 |
| 백업 | 내보내기 | 머리글 `format: 3`, `category_colors` 줄(키 순) |
| 백업 | 가져오기 | 형식 1·2·3을 모두 받음, 형식 2 파일의 `category_colors` 줄은 오류, 잘못된 색·키는 오류, 내보낸 뒤 다시 가져오면 같음 |
| CLI | `lb export`·`lb import` 결과 줄 | `카테고리 색 N` |

- [x] RED → GREEN → 커밋 `feat: 카테고리 색 저장(스키마 3, 서비스, 백업 형식 3)` (3549274)
- [x] 메인 세션: 이전 버전으로 만든 v2 임시 DB의 복사본에 `lb stats`를 실행해 확인했다.
  - `데이터베이스를 업그레이드했습니다: v2 → v3. 이전 데이터베이스 백업: …\lb.db.v2-20261015-105249.bak` 문구가 나온다.
  - 버전이 3이 되고 `category_colors` 테이블이 생긴다.
  - `lb export` 머리글이 `format 3`·`schema_version 3`이고 결과 줄 끝이 `카테고리 색 0`이다.
  - 화면 변화가 없으므로 승인은 Task 8-9와 함께 받았다(사용자 승인 2026-10-15).

---

## Task 8-9: 카테고리 색 화면 (설정 표, /colors.css, 꼬리표, 차트)

**Files:**
- Create: `src/logbook/web/colors.py`(`colors_css`), `web/pages/colors.py`(`GET /colors.css`), `templates/partials/category_section.html`
- Modify:
  - `web/pages/views.py`(`category_color_map`)
  - `web/pages/summary.py`(차트가 저장 색을 따름)
  - `web/pages/settings.py`(카테고리 색 표, 라우트, 버전)
  - `web/errors.py`(`CATEGORY_CHANGED`)
  - `web/assets.py`(`COLORS_CSS_URL`), `web/pages/__init__.py`(라우터 등록)
  - `web/pages/templating.py`(전역 `COLORS_CSS_URL`, 필터 `category_class`)
  - `templates/base.html`, `templates/settings.html`
  - `templates/partials/marks.html`(`category_pill`), `log_row.html`, `recent.html`, `task_card.html`
  - `static/css/app.css`(`--pill-tint: 20%`), `static/css/settings.css`(색 칸)
  - `static/js/app.js`(색을 고르면 같은 행의 `자동` 체크를 끔)
- Modify tests:
  - 꼬리표: `tests/web/test_dashboard.py:228`, `test_logs_page.py:84~85`, `test_tasks_page.py:175`(class 목록은 순서까지 `["pill", "pill--cat-design", "task-card__category"]`처럼)
  - 링크: `tests/web/test_static.py:175`(화면 링크 목록 끝에 `/colors.css`), `:178`(오류 페이지 링크는 화면 링크에서 `/colors.css`를 뺀 목록), `tests/web/test_dashboard.py:369`(허용 접두사에 `COLORS_CSS_URL`)
  - `test_settings_page.py:53`(`dev — 개발` 목록이 표로 옮겨 감)
  - 새 `test_colors.py`(`test_fonts.py`처럼 헤더를 직접 검사), 새 `test_settings_categories.py`
  - `test_theme.py`(대비)

**`/colors.css`** (예)

```css
/* 카테고리 색(설정 화면에서 고른 색, 없으면 자동 팔레트). 서버가 요청마다 만든다. */
.pill--cat-dev { background: color-mix(in srgb, #2f6fde var(--pill-tint), var(--surface)); color: var(--ink); }
.pill--cat-review { background: color-mix(in srgb, #e8590c var(--pill-tint), var(--surface)); color: var(--ink); }
```
- 대상 키는 설정 카테고리 전부(설정 순서)와, 색이 저장된 그 밖의 키(이름 순)다.
- 키가 형식 규칙에 맞지 않거나 색이 `#rrggbb`가 아니면 그 줄을 내지 않는다(CSS 주입 방지).
- 응답은 `text/css; charset=utf-8`이다. `/static/` 밖이라 `no-store`가 붙는다(security.py는 고치지 않는다).
- `base.html`이 `/fonts.css` 다음에 링크한다. 오류 페이지는 링크하지 않는다. 오류 페이지에는 꼬리표가 없고, DB를 읽지 않고 그려져야 한다.
- `--surface`가 테마마다 다르므로 어두운 테마도 따로 정하지 않고 따라간다. `color-mix()`를 모르는 브라우저는 그 선언을 버리므로 기본 꼬리표(회색 바탕)로 보인다.
- 대비: 20%로 섞은 바탕 위의 `--ink` 글자는 어떤 색이든 두 테마 모두 4.5:1 이상이다. 가장 낮은 경우는 어두운 테마에서 `#ffffff`를 골랐을 때 6.97:1이다(18%는 7.47, 25%는 5.86). 팔레트 10색과 극단값(검정·흰색·노랑·하늘·자홍)으로 테스트한다(sRGB 섞기 계산).

**꼬리표 마크업**

```jinja
{# partials/marks.html: 카테고리 꼬리표. 색은 /colors.css의 pill--cat-<키> 규칙이 칠한다.
   category_class는 형식이 맞는 키에만 class를 돌려준다(틀리면 빈 문자열이라 기본 꼬리표). #}
{% macro category_pill(key, extra="") -%}
{%- set cat = key|category_class -%}
<span class="pill{% if cat %} {{ cat }}{% endif %}{% if extra %} {{ extra }}{% endif %}">{{ key }}</span>
{%- endmacro %}
```
- `log_row.html`, `recent.html`, `task_card.html`에 있는 `pill(…category)` 세 곳을 `category_pill`로 바꾼다. 태스크 카드는 `extra="task-card__category"`를 그대로 넘긴다.
- 상태 꼬리표(`pill`)는 그대로다.

**설정 화면 카테고리 색 표** (`#category-section`, 프로젝트 표 다음)

```
카테고리 색
| 키  | 이름 | 색                 | 동작   |
| dev | 개발 | [■ 색 고르기] ☑ 자동 | [저장] |
카테고리 추가와 이름은 설정 파일 [categories]에서 바꿉니다. 저장한 뒤 화면을 새로 고치면 반영됩니다.
```
- 행 id는 `category-{key}`이고 숨은 칸 `version`을 둔다. `version`은 `content_version(키, 저장된 색 또는 "")`이다.
- 색 칸의 값은 지금 쓰는 색이다(저장된 색, 없으면 자동 팔레트 색). `자동` 체크는 저장된 색이 없을 때 켜져 있다.
- 색을 고르면 `app.js`가 같은 행의 `자동` 체크를 끈다. 이벤트 위임이라 HTMX로 다시 그린 표에도 동작한다.
- `저장`은 `POST /settings/categories/{key}/color`(폼 `color`, `auto`, `version`)다.
  - `auto`가 켜져 있으면 행을 지우고, 꺼져 있으면 색을 저장한다.
  - 바뀐 것이 없으면 `바뀐 내용이 없습니다.`를 보여 준다.
- 성공하면 `#category-section`을 다시 그리고 결과 줄을 보여 준다(`✔ dev 색을 저장했습니다.`, `✔ dev 색을 자동으로 되돌렸습니다.`).
- 오류:
  - 버전이 다르면 409(`다른 곳에서 카테고리 색이 바뀌었습니다: dev. 목록을 새로 고친 뒤 다시 시도하세요.`)
  - 설정에 없는 키는 404(`NotFoundError`), 잘못된 색은 400(`InvalidInputError`)
  - 세 오류 모두 라우트에서 잡지 않고 전역 처리기가 `#flash`로 보낸다(`HX-Retarget: #flash`, 프로젝트 보관 409와 같음). 표는 그대로 남는다.
  - 교차 출처 요청은 다른 쓰기처럼 403이다.
- 설정 정보 패널의 카테고리 목록(`info__categories`)은 이 표로 옮기고 지운다. `CATEGORY_NOTE`는 표 아래 안내로 옮겨 위 문구로 고친다.
- 저장한 색은 다른 화면을 열 때 반영된다. `/colors.css`는 `no-store`라 페이지를 열 때마다 새로 받는다.

**차트**
- `summary.py`가 `services.category_colors(s)`를 읽어 `category_color_map`에 넘긴다.
- 저장된 색이 없으면 지금과 같은 색이라 `EXPECTED_CHART`는 그대로 통과한다.

**테스트 케이스**

| 대상 | 케이스 | 기대 |
|---|---|---|
| `category_color_map` | 저장 색 있음 / 없음(설정 순서) / 설정에 없는 키(저장 색 있음·없음) | 저장 색 / 팔레트 위치 / 저장 색 또는 설정 개수 뒤 위치 |
| `colors_css` | 기본 설정, 저장 색 하나, 설정에서 지운 키의 저장 색, 형식이 틀린 키·색 | 설정 순서 줄, 저장 색 반영, 지운 키도 줄이 있음(설정 표에는 없음), 틀린 줄은 없음 |
| `category_class` | `dev`, `ops-2`, `Bad Key`, `한글`, 빈 값 | `pill--cat-dev`, `pill--cat-ops-2`, 나머지는 빈 문자열(기본 꼬리표) |
| `GET /colors.css` | 응답 | `text/css; charset=utf-8`, `no-store`, CSP 헤더. 저장 직후 요청에 새 색이 나옴 |
| 링크 | 화면(base.html) / 오류 페이지 | `/fonts.css` 다음에 `/colors.css` / 링크 없음 |
| 꼬리표 | 기록 표, 최근 기록, 태스크 카드 | `class="pill pill--cat-dev"`(카드는 `task-card__category` 유지). 상태 꼬리표는 그대로 |
| 대비 | 팔레트 10색과 극단값 × 두 테마, 20% 섞기 | `--ink` 대비 4.5 이상 |
| 설정 표 | 기본 상태 | 설정 순서 행, 색 칸 값은 팔레트 색, `자동` 켜짐, 버전 숨은 칸 |
| 설정 표 | 저장 / 자동으로 되돌림 / 바뀐 것 없음 / 저장 `#2F6FDE`에 `#2f6fde` 보냄 | DB 행 생김 / 행 지움 / `바뀐 내용이 없습니다.` / `바뀐 내용이 없습니다.` |
| 설정 표 | 버전 다름 / 설정에 없는 키 / `color=red` / 교차 출처 | 409와 문구 / 404 / 400 / 403. 앞의 셋은 `HX-Retarget: #flash`. DB는 그대로 |
| 설정 표 | 인라인 코드 | `inline_code_violations(html) == []` |
| 차트 | 저장 색이 있는 카테고리 | `categories.colors`가 저장 색. 저장이 없으면 `EXPECTED_CHART` 그대로 |
| JS | `app.js` | 색 고르기 `input` 이벤트에서 같은 행의 `자동` 체크를 끄는 위임 처리가 있다(정적 검사) |

- [x] RED → GREEN → 커밋 `feat: 설정 화면에서 카테고리 색을 고르고 꼬리표·차트가 따르게 함` (13375af)
  - 메인 세션 보완(0a48130): 320px에서 이름 칸만 줄어 글자가 세로로 쌓여서, 이름 칸도 `nowrap`으로 두고 표 안 가로 스크롤로 보게 했다. 프로젝트 표의 같은 현상은 Phase 8 전부터 있었다(손대지 않음).
  - 메인 세션 보완(11780f6): 마지막 행 색 고르기 칸의 바깥 윤곽선이 `.table-wrap`에 0.9px 잘려서, 표 안 버튼처럼 `outline-offset: -2px`로 안쪽에 그렸다. 그 칸에 포커스를 준 스크린샷에서 윤곽선이 온전히 보인다.
- [x] 메인 세션: 전후 스크린샷(compare-8-9.html: 기본 상태 전후, compare-8-9-color.html: 자동 색과 dev에 노랑 저장 비교, 84장 가로 넘침 없음) → 8-5·8-6·8-8과 함께 사용자 승인(2026-10-15)

---

## Task 8-10: 프로젝트 색 고르기

**Files:**
- Modify: `templates/partials/project_section.html`(추가 폼), `project_edit_row.html`(수정 행), `project_row.html`(자동 표시), `web/pages/settings.py`(`color_auto` 처리와 뷰 값), `static/css/settings.css`
- `app.js`는 Task 8-9의 처리를 그대로 쓴다.
- Modify tests: `tests/web/test_settings_projects.py`, `test_settings_page.py`

| 화면 | 지금 | 바꾼 뒤 |
|---|---|---|
| 추가 폼 | 텍스트 칸(`#4f46e5`) | 색 고르기 + `자동` 체크(처음에는 켜짐). 색 고르기의 처음 값은 `CHART_PALETTE[0]`이다 |
| 수정 행 | 텍스트 칸 | 색 고르기 + `자동` 체크. 색 고르기 값은 지금 색(지정 색, 없으면 자동 팔레트 색)이고, 지정 색이 없으면 `자동`이 켜져 있다 |
| 표 색 칸 | 지정 색만 견본과 글자 | 지정 색이면 견본과 `#rrggbb`, 자동이면 자동 팔레트 색 견본과 `자동` |

- 서버: 폼의 `color_auto`가 `"1"`이면 `color=None`, 없으면 `color` 값을 쓴다(검증은 그대로). 수정은 지금처럼 바뀐 항목만 반영하고, 색은 대소문자를 무시하고 비교한다(저장된 `#4F46E5`와 받은 `#4f46e5`는 바뀐 것이 아님).
- 색 고르기 칸은 입력칸 규칙(`--control-border`, 4px 모서리)을 따르고 높이를 다른 입력칸과 맞춘다. 표 안 편집 행이 표 폭을 넘지 않는지 스크린샷으로 확인한다.
- 색 고르기 칸과 `자동` 체크는 Task 8-9의 `.color-field`(`data-color-field`) 마크업과 CSS를 그대로 쓴다. 표 안 색 고르기 칸의 포커스 윤곽선 규칙(`.grid input[type="color"]:focus-visible`, 11780f6)이 수정 행에도 적용된다.
- **프로젝트 표 이름 칸:** 320px에서 이름 글자가 세로로 쌓이는 현상(Phase 8 전부터 있음)을 카테고리 표(8-9 보완 0a48130)와 같이 `nowrap`으로 고친다. 8-9 승인 때 함께 여쭸고 사용자가 승인했다(2026-10-15).

**테스트 케이스**

| 대상 | 케이스 | 기대 |
|---|---|---|
| 추가 | `자동` 켜짐(색 값 무시) / 꺼짐 + `#22c55e` / 꺼짐 + `red` | 색 없음 / 그 색 / 400, 입력값 유지 |
| 수정 행 | 지정 색 있음 / 없음 | `type="color"` 값이 그 색이고 `자동` 꺼짐 / 팔레트 색이고 `자동` 켜짐 |
| 수정 | 지정 색 → `자동` / 자동 → 색 / 바뀐 것 없음 / 저장 `#4F46E5`에 `#4f46e5` 보냄 | `None` / 그 색 / `바뀐 내용이 없습니다.` / `바뀐 내용이 없습니다.` |
| 표 | 지정 색 / 자동 | 견본과 `#rrggbb` / 팔레트 견본과 `자동` |
| 표 | 이름 칸 | `td`에 `nowrap` class |
| 기존 | `test_patch_blank_color_and_description_become_none` | `자동` 체크 기준으로 바꾼다 |
| 인라인 코드 | 추가 폼·수정 행 | `inline_code_violations(html) == []` |

- [ ] RED → GREEN → 커밋 `feat: 설정 화면의 프로젝트 색을 색 고르기와 자동 선택으로 바꿈`
- [ ] 메인 세션: 전후 스크린샷(추가 폼, 수정 행) → 사용자 승인

---

## Task 8-11: 보완 문서와 확인

- [ ] **SPEC.md**
  - 2장: `### week_notes`(62행 부근) 다음에 `### category_colors` 표와 규칙, `### schema_version`(73~74행 "현재 스키마 버전은 2") → 3(버전 3: category_colors 추가)
  - 백업 형식(292행 "JSONL 형식(버전 2)", 296행 week_notes 규칙): 형식 3, 행 순서, `category_colors` 규칙(키 형식, `#rrggbb`, 형식 2 파일에 줄이 있으면 오류), 형식 1·2도 계속 가져옴, 결과 줄
  - 6장 Phase 8 절: 카테고리 색 표, `/colors.css`, 카테고리 꼬리표 색, 프로젝트 색 고르기, 색 규칙
  - 후속 항목: 차트 팔레트 항목 정리
- [ ] **README.md**
  - 설정 화면(카테고리 색, 프로젝트 색 고르기), 백업 형식 3
  - 업그레이드: DB를 여는 `lb` 명령이나 `lb serve`를 처음 실행할 때 스키마 3으로 올리고, 그 전에 백업 파일을 만든다. 올리기 전에는 셸 자동완성 후보가 비어 있다(기존 동작).
- [ ] **CLAUDE.md, AGENTS.md**: services 목록에 `category_colors`, `web/colors.py`, `web/pages/colors.py`, db.py 줄
- [ ] **ROADMAP.md**: Phase 8에 사용자 지정 색 항목
- [ ] **화면 확인(메인 세션, Edge 헤드리스)**
  - 다섯 화면과 설정 카테고리 표 × 1280·375·320px × 밝은·어두운
  - 가로 넘침, 포커스, 꼬리표 색과 차트 색이 같은지
  - 카테고리 색 하나를 저장한 상태
- [ ] **전체 검증, CI, PR #18 본문과 확인 절차 댓글 갱신**

---

## 크로스 플랫폼 체크리스트 (Phase 8 추가분)

- 글꼴 이름은 OS와 상관없이 같다(`Bookk Gothic`). 설치되지 않은 OS에서는 기존 고딕 목록(`--font-sans`)으로 넘어간다.
- Task 8-4b로 명조를 쓰지 않게 되어 명조 대체 글꼴 목록(`--font-serif`: macOS `AppleMyungjo`, Windows `Batang`, `Noto Serif KR`, `serif`)은 없앴다.
- 설정 파일의 한글 글꼴 이름(예: `나눔고딕`)은 UTF-8로 읽고 CSS에도 그대로 쓴다(`/fonts.css`는 `charset=utf-8`).
- 스크린샷 확인은 Windows Edge 헤드리스다. macOS Safari 모양은 사용자 확인 항목이다.

---

## 설계 결정 요약 (계획 승인 시 함께 확정)

1. **글꼴은 이름만 쓴다:** 폰트 파일을 저장소에 넣지 않는다. 라이선스·용량 문제가 없고, 사용자가 원하는 설치 글꼴로 바꿀 수 있다.
2. **`/fonts.css`는 `no-store`다:** 몇 줄짜리라 매번 받아도 부담이 없고, 설정을 고친 뒤 새로 고침만으로 반영된다.
3. **글꼴 이름은 하나만 받는다:** 쉼표 목록을 받지 않는다. 대체 글꼴은 서버가 기존 OS 글꼴 목록을 붙인다. CSS 주입을 막으려고 따옴표·세미콜론·중괄호 등을 거부한다.
4. **입력칸 경계는 3:1을 지킨다:** 옅은 경계선(`--rule`)은 장식용이고, 입력칸 테두리는 별도 토큰(`--control-border`)으로 3:1 이상이다.
5. **프로젝트 색은 ID로 고정한다:** 같은 프로젝트는 어느 화면에서나 같은 색이다. 차트 색이 이번 주 순서에서 ID 순서로 바뀐다(지정 색은 그대로).
6. **화면 구조는 바꾸지 않는다:** 버튼·폼·칸반 구성은 Phase 9에서 바꾼다. Phase 8은 겉모양만이다. 예외: 보완 Task 8-8~8-10(사용자 지정 색, 2026-10-15 사용자 결정)은 설정 화면에 카테고리 색 표와 색 고르기 칸을 더하고 스키마를 3으로 올린다.

---

## 사용자 결정 (2026-10-14)

- 디자인 개선을 두 Phase로 나눈다: Phase 8 디자인 시스템, Phase 9 화면 고도화(칸반, 등록·수정 화면 분리, 끌어 놓기 + 중단 열(SortableJS), 대시보드 위계)
- 글꼴: 폰트 파일을 넣지 않고 설치된 글꼴을 설정에서 지정한다(방법 A). 설치 글꼴 목록에서 고르기(방법 B)는 하지 않는다.
- 구현: Task마다 서브에이전트 구현 1명 + 검토 1명, Task마다 사용자 승인
- 1번(색 토큰)을 계획 없이 먼저 적용한 커밋은 되돌리고 이 계획대로 다시 한다.

## 사용자 결정 (2026-10-15)

- 차트 팔레트 시작 위치 질문에 대한 답으로, 꼬리표(카테고리)와 프로젝트 색 점의 색을 사용자가 정하고 차트가 그 색을 따르게 한다. 결정 C1~C4는 "보완: 사용자 지정 색" 절에 있다. 팔레트를 한 칸 미는 조정은 하지 않는다.

---

## 계획 검토 (2026-10-14)

사실 확인 에이전트 1명(Sonnet)이 코드·대비 수치·정규식·CSS 동작을 확인했다(Edge 헤드리스 실험 포함).
- 맞음: 기존 코드 전제, 대비 26개 수치, 글꼴 이름 정규식 판정, `overflow: clip` 안의 가로 스크롤 유지, reduced-motion 규칙이 transition을 끔, 나중 스타일시트의 `var(--font-sans)` 참조
- 반영: 팔레트는 `views.py`로 옮김(순환 import 없음), 차트 색 테스트(`common` 색)·`project_colors` 테스트 교체, `.timer__state` 규칙 삭제, 꼬리표에 기존 class 표지를 남기는 `extra` 인자, 표 머리·바닥 선의 실제 속성 이름, `/fonts.css`를 `STYLESHEETS`에 넣지 않음과 링크 테스트 기대
- 참고: 이 PC의 Edge는 `prefers-reduced-motion: reduce`가 켜져 있다. 누름 효과(scale)는 transition 없이 즉시 적용된다.

## 계획 검토 (2026-10-15, 보완: 사용자 지정 색)

코드 조사 3명(읽기 전용, Sonnet)의 결과로 초안을 쓰고, 사실 확인 에이전트 1명(Sonnet)이 주장 12개를 확인했다.
- 맞음
  - 코드 위치·이름과 상태 코드 매핑(404·409·400), 전역 처리기의 `#flash` 경로, 마이그레이션 구조와 백업 파일 이름(`v2-…bak`)
  - 고정 DDL과 모델의 `PRAGMA table_info`가 같음(임시 SQLite 실험)
  - `color-mix()`의 `var()` 비율이 Edge에서 sRGB 계산값과 정확히 같음
  - 대비 수치(20%에서 최저 6.97)
  - `app.js` 위임 패턴, `/fonts.css` 링크 방식
- 반영(빠진 곳)
  - 백업 가져오기의 `_REFERENCES`(없으면 KeyError)·검증 종류(카테고리 키 형식 포함)·`BackupCounts`, 깨지는 테스트의 파일·줄(마이그레이션·백업·CLI 결과 줄·링크·꼬리표·설정 화면), SPEC 위치
  - `colors_css`를 순수 함수로(web은 SQLAlchemy를 쓰지 않음)
  - 형식이 틀린 카테고리 키에는 class를 붙이지 않음(`category_class` 필터)
  - `<input type="color">`의 소문자 값 때문에 색 비교는 대소문자 무시, `자동` 체크의 폼 이름과 값
  - 오류 페이지 링크 테스트 조정, 업그레이드 안내 문구(첫 실행 명령, 자동완성)

---

## 구현 기록 (2026-10-14~15)

- **진행 규모:** 서브에이전트 19명(모두 Sonnet)
  - 계획 검토(사실 확인) 1명
  - 워크플로 `phase8-task`: Task 8-1~8-6과 보완 8-4b마다 구현 1명 + 통합 검토 1명(14명, effort medium). 모든 Task가 첫 검토에서 승인돼 수정 라운드는 없었다.
  - 마무리 워크플로: 검토 minor 정리 1명, 문서 1명, 최종 리뷰 1명(high), 최종 리뷰 수정 1명
- **승인:** 8-1~8-4b는 Task마다 사용자 승인을 받았다. 8-5·8-6·8-7은 사용자 지시(2026-10-14 밤: Phase 8의 남은 Task를 진행하고 아침에 한 번에 확인, Phase 9는 진행하지 않음)로 승인 없이 진행했다(아침 일괄 확인).
- **계획과 달라진 것**
  - 계획 없이 먼저 적용한 색 토큰 커밋(f43dab7)을 되돌리고(62297e2) 계획대로 다시 했다.
  - 8-2 보완: 요약 패널 모서리(b859716), 표 안 버튼의 포커스 윤곽선을 안쪽에 그림(9e2c178)
  - 8-4 보완: 보고서 미리보기 15px(ec08c57, 사용자 결정)
  - 8-4b(사용자 결정): 제목·문서·본문·차트 글꼴을 모두 부크크 고딕으로 통일하고 `--font-serif`를 없앴다(eb15067).
  - 8-5: 최근 기록은 프로젝트 글자와 카테고리 꼬리표로 나눴다(8-6에서 프로젝트 글자 앞에 색 점).
  - 8-6: 수정 중인 카드에는 색 점을 넣지 않았다(계획 목록 밖, 후속 4).
- **검토에서 미룬 minor 처리(f1aad24):** 입력칸 테두리 토큰 검사를 CSS 전체로 넓힘(8-1 R1), 글꼴 거부 테스트 세 키(8-3 R1), 설정 화면 글꼴 줄 각각 확인(8-4b R1), HTMX 조각 응답의 꼬리표 단정(8-5 R1), 빈 `timer__state` class 제거(8-5 R2). 8-5 R3(최근 기록의 글자와 꼬리표 간격)은 스크린샷에서 괜찮아 그대로 두었다.
- **최종 리뷰로 고친 것:** major 1건(문서가 `document_font`를 특이사항 입력란에도 쓴다고 적음 → 실제 사용처로 고침, c320fe5). minor: 모서리 토큰 사용처 문서, 낡은 명조 설명의 테스트 이름(755ff59), 계획서 8-7 문서 항목 체크
- **검증(메인 세션):** ruff, ruff format --check, mypy(core strict·전체) 통과. pytest 2853 passed, 2 skipped(커버리지 core·web 100%, 전체 99%이고 미커버 4줄은 기존 cli). 화면 확인은 위 8-7 항목.
- **비교 페이지:** Task마다 전후 스크린샷 비교 페이지를 세션 스크래치패드(`design/compare-8-*.html`, Phase 8 전체는 `design/compare-phase8.html`)에 만들었다. 저장소에는 넣지 않는다.

---

## 후속 항목 (Phase 8 범위 밖, 기록만)

1. Phase 9 전체(칸반 고도화, 등록·수정 화면 분리, 끌어 놓기·중단 열, 대시보드 위계)
2. 설치 글꼴 목록에서 고르기와 웹에서 설정 저장(방법 B)
3. 어두운 테마의 차트 팔레트 대비 점검(Phase 6 후속 4). 프로젝트 색 점도 같은 팔레트라, 어두운 표면에서 짙은 팔레트 색 점의 대비가 낮다(8-6 검토 R2). 점 옆에 slug 글자가 있어 색만으로 정보를 전하지는 않는다.
4. 수정 중인 태스크 카드의 프로젝트 색 점: 수정 폼이 열린 카드에는 프로젝트가 글자만 나온다(8-6 검토 R1). Phase 9의 수정 화면 분리와 함께 정한다.
5. ~~차트 팔레트 시작 위치~~ → 사용자 지정 색(보완 Task 8-8~8-10)으로 정리했다(2026-10-15 사용자 결정). 팔레트를 한 칸 밀지 않는다.
6. 카테고리 색 CLI(`lb category color` 같은 명령)와 JSON API로 색 읽기. 지금은 웹 설정 화면에서만 정한다.
7. 백업 가져오기의 `projects.color` 검증 강화(지금은 문자열 검사만 한다).
8. 설정에서 지운 카테고리의 색 행 정리. 지금은 남겨 두고, 카테고리를 다시 더하면 그 색이 돌아온다.
