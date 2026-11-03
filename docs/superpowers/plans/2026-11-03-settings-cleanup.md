# Phase 9 보완: 설정 화면 정리 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 설정 화면에서 같은 모양의 반복을 걷어 내고, 읽기 전용 정보를 사람 말로 보여 준다.

2026-10-26 전 화면 평가 P3 "설정 화면의 반복과 읽기 전용 정보"를 다룬다.
- 카테고리 9행마다 색 칸·`자동`·`저장`이 있어 같은 모양이 27번 나온다. 색 하나를 바꿀 때마다 `저장`을 눌러야 한다.
- 설정 정보에 `monday`처럼 설정 파일 값이 그대로 보인다.
- 프로젝트 추가 폼의 slug 규칙은 예시뿐이고, 예시 `payment`는 이미 있는 프로젝트다.

글꼴 미리보기 반복(자동 검사 `repeated-container-text`)은 평가에서 거짓 양성으로 판정했으므로 그대로 둔다.

**기준:** develop fb750a5(PR #34 병합)에서 갈라진 브랜치 `feat/settings-cleanup`.

**진행:**
- 계획서 승인 → Task 순서대로 진행한다. 테스트를 먼저 써서 실패를 확인(RED)한다.
- Task마다 전후 스크린샷을 HTML 비교 페이지 하나로 보여 주고 사용자 승인을 받는다.
- 끝에 문서·전체 검증·최종 리뷰 1회(`final-reviewer`, Sonnet high) → PR(develop) → "logbook QA" 세션 점검.
- 구현은 메인 세션이 직접 한다.

**Tech Stack:** 기존과 같다. 새 의존성은 없다.

---

## 결정 (2026-11-03 결정 게이트, 사용자 확정)

| ID | 결정 |
|---|---|
| C1 | **카테고리 색은 바꾸면 바로 저장한다.** 색을 고르거나 `자동`을 켜고 끄면 그 행이 저장되고 결과 줄이 뜬다. 행마다 있던 `저장` 버튼 9개를 없앤다. 저장 경로(`POST /settings/categories/{key}/color`)와 버전 확인(409)은 그대로 쓴다. |
| C2 | **설정 정보 값을 사람 말로 보이고, 바꾸는 곳을 함께 적는다.** 주 시작 요일 `월요일`/`일요일`, 기본 프로젝트 `common (공통)`. 설정 파일에서 바꾸는 값에는 설정 키(`week_start` 등)를 옅게 덧붙인다. |
| C3 | **slug 칸에 규칙 한 줄과 새 예시를 둔다.** 칸 아래 안내 `영문 소문자나 숫자로 시작, - _ 포함 32자까지. CLI에서 이 이름으로 씁니다.`, 예시는 `payment` 대신 `billing`. |

## 설계

### 카테고리 색 바로 저장(C1)

**템플릿(`partials/category_section.html`)**
- `저장` 버튼과 `동작` 열(숨긴 `thead`의 `동작` 포함)을 뺀다. 열은 4개에서 3개(키, 이름, 색)가 된다.
- 요청은 행(`<tr>`)에 단다. `hx-post="/settings/categories/{key}/color" hx-trigger="change" hx-include="this" hx-target="#category-section" hx-swap="outerHTML" hx-sync="this:drop"`.
  - `change`는 색 고르기 창을 닫을 때(값이 확정될 때)와 `자동` 체크를 바꿀 때 한 번씩 일어나고 행으로 올라온다. 색을 끄는 동안의 `input` 이벤트로는 저장하지 않는다.
  - 색을 고르면 같은 칸의 `자동`을 끄는 기존 `input` 처리(`app.js`)는 그대로다. 그래서 색을 고른 뒤의 `change`는 `자동` 꺼짐 + 새 색으로 저장된다.
  - `자동`을 끄면 지금 칸에 보이는 색(자동 팔레트 색)이 지정 색으로 저장된다. 지금 `저장` 버튼 동작과 같다.
- 입력에 id를 준다: `category-color-{key}`, `category-auto-{key}`. 아래 포커스 유지에 쓴다.
- 표 아래 안내(`CATEGORY_NOTE`) 앞에 "색을 바꾸면 바로 저장됩니다."를 더한다.

**포커스 유지(`app.js`)**
- 지금은 POST 응답으로 영역을 다시 그리면 영역 안 `[data-focus]`(섹션 제목)로 포커스가 간다. 바로 저장에서는 행마다 키보드로 색을 바꾸다 포커스가 제목으로 튀면 안 된다.
- 섹션에 `data-keep-focus`를 붙인다. 이 표시가 있는 대상은 교체 전에 포커스가 있던 요소의 id를 기억했다가, 교체 뒤 같은 id 요소로 포커스를 돌려준다. 그 요소가 없으면 기존 규칙(`[data-focus]`)을 따른다.
- 다른 영역(프로젝트 표 등)의 포커스 규칙은 바뀌지 않는다.

**오류:** 409(다른 곳에서 바뀜), 404, 400은 지금처럼 전역 처리기가 `#flash`에 알리고 표는 그대로 남는다.

### 설정 정보(C2)

**보기 모델(`pages/settings.py`)**
- `SettingsInfoView.week_start`는 `월요일`/`일요일`(`WEEK_START_LABELS = {"monday": "월요일", "sunday": "일요일"}`).
- `default_project`는 `slug (이름)`. `settings_page`가 세션에서 `services.get_project`로 이름을 찾는다. 없으면(설정이 아직 만들지 않은 slug를 가리키면) slug만 보인다.
- 설정 키 덧붙이기: `기본 프로젝트`(`default_project`), `주 시작 요일`(`week_start`), `하루 목표`(`daily_target_minutes`), `DB 파일`(`db_path`). `dd` 안에 `<code class="info__key">week_start</code>`처럼 옅은 글씨로 둔다. 설정 파일 경로는 키가 없으므로 덧붙이지 않는다.
- 섹션 아래 안내에 "이 값들은 설정 파일에서 바꿉니다. 저장하면 화면을 새로 고칠 때 반영됩니다." 한 줄을 글꼴 안내 앞에 더한다(설정 자동 반영 `config_watch`와 맞는 문구인지 구현 때 확인).

### slug 안내(C3)

**템플릿(`partials/project_section.html`):** slug 입력 아래 `<p id="project-slug-hint" class="project-form__hint">…</p>`, 입력에 `aria-describedby="project-slug-hint"`, `placeholder="billing"`. 이름 칸 예시 `결제 서버`도 `정산 서버`로 맞춘다.

**CSS(`settings.css`):** `.project-form__hint`는 안내 글자 색(`--text-muted` 계열)·작은 글자. 폼이 가로로 늘어선 1280px에서 안내 줄 때문에 다른 칸이 밀리지 않는지 스크린샷으로 본다. `.info__key`도 같은 옅은 글씨.

## Task 1: 카테고리 색 바로 저장(C1)

**Files:** `templates/partials/category_section.html`, `static/js/app.js`, `pages/settings.py`(안내 문구), 테스트 `tests/web/test_settings_categories.py`

- [ ] RED: 테스트를 쓰고 실패를 확인한다.
  - 카테고리 표에 `저장` 버튼이 없고 행은 3칸이다.
  - 행에 `hx-post`(그 키의 경로)와 `hx-trigger="change"`가 있고, 입력에 `category-color-{key}`·`category-auto-{key}` id가 있다.
  - 섹션에 `data-keep-focus`가 있다.
  - 저장 동작(색 저장, 자동 되돌림, 409, 변경 없음)은 기존 테스트가 그대로 통과한다.
- [ ] 템플릿·JS·안내 문구 구현 → GREEN
- [ ] 브라우저 확인(헤드리스 Edge): 색을 바꾸면 결과 줄이 뜨고 새로 고쳐도 남는다. `자동`을 켜면 되돌아간다. 키보드로 `자동` 체크를 Space로 바꾼 뒤 포커스가 그 체크에 남는다.
- [ ] 전후 스크린샷: 설정 화면 1280px과 320px, 밝은·어두운 테마
- [ ] 전후 비교 HTML → 사용자 승인 → 커밋 `feat: 설정 카테고리 색을 바꾸면 바로 저장하고 행별 저장 버튼을 없앤다`

## Task 2: 설정 정보와 slug 안내(C2·C3)

**Files:** `pages/settings.py`, `templates/settings.html`, `templates/partials/project_section.html`, `static/css/settings.css`, 테스트 `tests/web/test_settings_page.py`, `tests/web/test_settings_projects.py`

- [ ] RED: 테스트를 쓰고 실패를 확인한다.
  - 주 시작 요일이 `월요일`(설정 `sunday`면 `일요일`)이고 `monday` 글자가 값으로 나오지 않는다.
  - 기본 프로젝트가 `common (공통)`. 설정이 없는 slug를 가리키면 slug만.
  - 네 값에 설정 키가 덧붙는다.
  - slug 입력에 `aria-describedby`로 이어진 안내가 있고 예시가 `billing`이다.
- [ ] 구현 → GREEN. 기존 테스트 중 `monday`나 `payment` 예시를 보는 것을 고치고 이유를 커밋 본문에 적는다
- [ ] 전후 스크린샷: 설정 화면 1280px과 320px, 밝은·어두운 테마
- [ ] 전후 비교 HTML → 사용자 승인 → 커밋 `feat: 설정 정보를 사람 말로 보이고 slug 규칙을 안내한다`

## Task 3: 문서와 PR

- [ ] SPEC 6장 설정 화면 절에 바로 저장·설정 정보 표기·slug 안내를 적는다
- [ ] ROADMAP Phase 9에 보완 줄을 더하고 체크한다
- [ ] 전체 검증: `ruff check`, `ruff format --check`, `mypy src/logbook/core`, 전체 `pytest`
- [ ] 최종 리뷰 1회(`final-reviewer`) → 지적 반영
- [ ] PR(develop) 생성, "logbook QA" 세션에 점검 요청
