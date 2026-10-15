# Phase 9 구현 계획 (웹 대시보드 — 화면 고도화)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Phase 8 디자인 시스템 위에서 태스크 보드와 대시보드의 화면 구조를 바꾼다(ROADMAP Phase 9).
- 중단 시각 기록(스키마 4): "중단" 열이 이번 주에 중단한 태스크를 정확히 고르게 한다.
- 칸반 고도화: 상태 색을 옅게 깐 열 머리와 건수, 흰 카드, 실적/예상 진행 막대
- 태스크 등록·수정을 별도 화면으로 옮긴다. 카드를 누르면 수정 화면으로 간다.
- 카드의 버튼을 모두 없애고, 카드를 열 사이로 끌어 놓아 상태를 바꾼다(SortableJS, 로컬 포함). 보드에 "중단" 열(이번 주에 중단한 것)을 더한다.
- 대시보드 위계: 오늘 공수의 하루 목표 대비 진행 막대, 진행 중 타이머를 화면에 하나뿐인 강조 띠로

**Architecture:**
- 계층 규칙은 그대로다. web은 `core.services`와 허용된 core 진입점만 쓰고, SQL·ORM 쿼리를 쓰지 않는다.
- 새 화면은 전체 페이지의 HTMX 폼이다. 저장에 성공하면 서버가 `HX-Redirect`로 보드(`/tasks?added=ID` 또는 `?updated=ID`, 필터 프로젝트 유지)로 보내고, 보드가 결과 줄을 보여 준다. 입력 오류·버전 충돌(409)은 같은 화면에 입력값 그대로 문구를 보여 준다.
- 끌어 놓기는 기존 상태 변경 주소(`POST /tasks/{id}/status`, 버전 확인)를 그대로 쓴다. 성공하면 서버가 보드를 다시 그린다(지금과 같다). 실패하면(409·404·400·503·연결 오류) 오류 문구는 지금처럼 `#flash`에 보이고, `board.js`가 보드를 다시 불러와 카드를 제자리로 돌린다.
- SortableJS는 htmx·Chart.js처럼 npm tarball에서 꺼낸 원본을 `static/vendor`에 넣는다(Phase 5 결정 W3, CDN 없음). 내려받기와 무결성 확인은 메인 세션이 한다. CSP는 바꾸지 않는다(SortableJS는 스타일을 CSSOM으로만 바꾼다. 화면 확인으로 검증한다).
- 스키마 4: `tasks.dropped_at`(중단 시각)을 더한다. 완료 시각(`done_at`)과 같은 규칙으로 들어가고 빠진다. 충돌 확인 버전(`task_version`)과 JSON API(`/api/tasks`)도 `done_at`과 대칭으로 `dropped_at`을 갖는다.

**Tech Stack:** 기존과 같다. 새 의존성은 SortableJS 1.15.7이다.
- MIT, 2026-02-11 배포, `https://registry.npmjs.org/sortablejs/-/sortablejs-1.15.7.tgz`
- integrity `sha512-Kk8wLQPlS+yi1ZEf48a4+fzHa4yxjC30M/Sr2AnQu+f/MPwvvX9XjZ6OWejiz8crBsLwSq8GHqaxaET7u6ux0A==`
- 사용자가 Phase 8 결정 게이트에서 "SortableJS 로컬 포함"을 골랐다. 메인 세션이 vendor 직전에 레지스트리에서 최신 버전을 다시 확인하고, 더 새 버전이 있으면 사용자에게 알린다.

**선행 조건:**
- **브랜치:** `feat/screen-refresh`(develop `cb7e76c`, Phase 8 병합 뒤에서 분기). PR은 develop 대상이다.
- **uv PATH:** Phase 8 계획서와 같다.
- **진행 규칙(사용자 결정):**
  - 이 계획서를 사용자가 승인한 뒤 이슈를 만들고 구현한다.
  - Task마다 구현 1명 + 통합 검토 1명(Sonnet, effort medium)이 끝나면, 메인 세션이 바꾸기 전후 스크린샷(다섯 화면과 새 화면 × 1280·375·320px × 밝은·어두운)과 비교 페이지를 만들어 사용자 승인을 받은 뒤 다음 Task로 간다.
  - 화면 변화가 없는 Task 9-1은 Task 9-2와 함께 승인받는다.
- **Task 공통 완료 조건, 커밋 메시지, TDD, 문구 규칙, 서브에이전트 실행 규칙:** Phase 8 계획서와 같다. 덧붙여:
  - 파일을 지우지 않는다(`git rm` 포함). 쓰지 않게 된 템플릿·테스트 파일은 `git mv`로 새 용도에 맞는 이름으로 옮겨 내용을 바꾸거나, 옮길 곳이 없으면 메인 세션에 보고한다. 코드 안의 함수·라우트·줄을 지우는 편집은 괜찮다.
  - 서브에이전트는 외부 네트워크(npm 레지스트리 포함)를 쓰지 않는다. SortableJS vendor 파일은 Task 9-4 전에 메인 세션이 넣는다.
  - 메인 세션은 에이전트가 같은 작업 트리를 고치는 동안 전체 pytest를 돌리지 않는다(Phase 8 보완에서 진행 중 테스트가 섞여 실패로 보였다).

---

## 결정 (2026-10-15 결정 게이트, 사용자 확정)

| # | 결정할 것 | 결정 |
|---|---|---|
| D1 | 끌 수 없는 사용자(키보드·화면 낭독기·끌기 어려운 사용자, WCAG 2.2 2.5.7)의 상태 변경 | 수정 화면의 "상태" 선택(할 일·진행 중·완료·중단). 카드는 링크라 Tab과 Enter로 연다 |
| D2 | 중단 열에 보여 줄 것 | **이번 주에 중단한 태스크**. 태스크에 중단 시각(`dropped_at`)을 기록한다(스키마 4, 백업 형식 4). 기존 중단 태스크는 마지막 수정 시각(`updated_at`)으로 채운다 |
| D3 | 등록·수정 화면의 항목 | `lb task add`·`edit`의 범위에 설명을 더한다: 제목, 프로젝트(등록만), 카테고리, 예상, 계획 주차, 마감일, 외부 참조, 설명. 수정 화면은 상태도 바꾼다. 설명은 웹에서만 고친다(CLI에는 설명 옵션이 없다) |
| D4 | 저장 뒤 | 보드로 돌아가 결과 줄(`✔ 태스크 추가: …`, `✔ 수정했습니다: …`)을 보여 준다. 필터는 유지한다 |
| D5 | 중단 열로 끌 때 확인 창 | 없음. 중단 열에서 다시 끌어 되돌릴 수 있다 |
| D6 | 같은 열 안에서 순서 바꾸기 | 없음(보드 정렬 규칙 유지, 순서 저장 필드 없음) |
| D7 | 대시보드 진행 막대 | "이번 주 공수" 칸 아래에 **오늘 공수 / 하루 목표**(예: 오늘 2h 30m / 목표 8h) |
| D8 | 타이머 강조 띠 | 색 뒤집기: 밝은 테마는 진한 띠(글자 밝게), 어두운 테마는 밝은 띠(글자 어둡게). 강조색(파랑)은 링크·포커스·주 버튼 전용으로 남는다 |
| D9 | 보드 열 배치 | 4열(1100px 이상), 2×2(720~1099px), 1열(720px 미만). 가로 스크롤 없음 |

---

## 파일 구조

| 파일 | 구분 | 책임 |
|---|---|---|
| `src/logbook/core/models.py` | 수정 | `Task.dropped_at` |
| `src/logbook/core/db.py` | 수정 | `SCHEMA_VERSION = 4`, `_upgrade_to_4` |
| `src/logbook/core/services/tasks.py`, `services/__init__.py` | 수정 | `set_task_status`의 `dropped_at`, `dropped_tasks_in_week()`, 설명의 줄바꿈 정규화 |
| `src/logbook/core/services/backup.py`, `backup_import.py` | 수정 | 백업 형식 4(`tasks.dropped_at`, 형식별 필드) |
| `src/logbook/web/api/serialize.py` | 수정 | `task_json`에 `dropped_at` |
| `src/logbook/web/pages/tasks.py` | 수정 | 보드(4열, 결과 줄 쿼리), 등록·수정 화면 라우트 |
| `src/logbook/web/pages/task_views.py` | 수정 | 카드 뷰(진행 막대, 링크, 버전), `task_version`에 `dropped_at`, 열 뷰(상태 키·색 이름), 등록·수정 화면 뷰 |
| `src/logbook/web/templates/tasks.html` | 수정 | 추가 폼 대신 "새 태스크" 링크, `{% block scripts %}` 추가(SortableJS·board.js) |
| `src/logbook/web/templates/task_new.html`, `task_edit.html` | 생성 | 등록·수정 화면 |
| `src/logbook/web/templates/partials/task_form.html` | 수정 | 등록·수정 공용 폼(필드 묶음) |
| `partials/task_edit_card.html`, `partials/task_form_response.html` | `git mv` 또는 보고 | 새 구조에서 쓰이지 않으면 새 용도로 옮기거나 메인 세션에 보고 |
| `templates/partials/task_board.html`, `task_card.html` | 수정 | 4열, 끌 수 있는 목록, 버튼 없는 카드 |
| `src/logbook/web/static/js/board.js` | 생성 | SortableJS 연결, 끌어 놓은 뒤 상태 변경 요청, 실패하면 보드 다시 불러오기 |
| `src/logbook/web/static/js/app.js` | 수정 | 새 화면의 Esc 취소(`data-cancel`) |
| `src/logbook/web/static/vendor/sortable-1.15.7.min.js`, `LICENSE-sortablejs.txt`, `README.md` | 생성·수정(메인 세션) | vendor 파일과 출처·sha256, "교체할 때" 절에 `tasks.html` |
| `src/logbook/web/static/css/tasks.css`, `app.css`, `components.css`, `dashboard.css` | 수정 | 열 머리 색, 카드, 4열·2×2·1열(보드 규칙은 지금처럼 `tasks.css`), 진행 막대, 새 화면 폼, 끄는 동안 모양, 강조 띠 토큰 |
| `src/logbook/web/pages/summary.py`, `templates/partials/summary.html`, `templates/partials/timer.html` | 수정 | 오늘 진행 막대, 강조 띠 |
| tests | 수정·생성 | `tests/core`(마이그레이션 v4, 태스크 서비스, 백업), `tests/web/test_tasks_*.py`, `test_api_tasks.py`, `test_static.py`, `test_theme.py`, `test_css_layout.py`, `test_dashboard.py`, `test_timer_panel.py`, `tests/web/helpers.py` |
| `docs/SPEC.md`, `README.md`, `CLAUDE.md`, `AGENTS.md`, `docs/ROADMAP.md` | 수정 | 문서 |

---

## Phase 9 공통 규칙

### 상태 색과 새 토큰

| 토큰 | 밝은 | 어두운 | 쓰임 |
|---|---|---|---|
| `--accent-soft` | `#e6f0fb` | `#1d2c3d` | "진행 중" 열 머리 바탕(글자 `--accent-hover`/`--accent`, 대비 4.5 이상으로 고른다) |
| `--band-bg` | `#1f1e1c` | `#ecebe9` | 타이머 강조 띠 바탕(색 뒤집기) |
| `--band-ink` | `#f6f5f4` | `#191918` | 띠 글자 |
| `--band-muted` | 띠 위 대비 4.5 이상인 회색 | 같은 조건 | 띠 보조 글자 |

- 열 머리: 할 일 `--tag-bg`(중립), 진행 중 `--accent-soft`, 완료 `--ok-soft`, 중단 `--danger-soft`. 머리 글자는 각 상태 색(`--ink-muted`, `--accent-hover`, `--ok`, `--danger`)이고, 대비는 `test_theme.py`의 쌍으로 확인한다.
- 정확한 색 값은 구현자가 대비 4.5 이상이 되도록 고르고 테스트 쌍에 더한다(위 값은 출발점).
- 색 값은 Phase 8 규칙대로 `app.css`의 `:root` 두 블록에만 둔다.

### 카드

```
[#5] 색인 재구축 스크립트                    ← 카드 전체가 수정 화면 링크(a.task-card__link)
● search  dev  2026-W41 지난 주              ← 색 점, 카테고리 꼬리표, 주차와 꼬리표(Phase 8)
▬▬▬▬▬▬▬▬▬▬▬▭▭▭  실적 3h / 예상 2h  예상 초과   ← 진행 막대(예상이 있을 때만), 넘으면 위험색
```
- `li.task-card`에 `data-task-id`, `data-version`. 목록 `ul.board__cards`에 `data-status`(`todo`·`doing`·`done`·`dropped`).
- 진행 막대는 CSP 때문에 `style` 속성을 못 쓰므로 **SVG**로 그린다: `<svg class="progress" viewBox="0 0 100 4" preserveAspectRatio="none" aria-hidden="true"><rect class="progress__track" width="100" height="4"/><rect class="progress__fill" width="{{ percent }}" height="4"/></svg>`. `percent`는 서버가 계산한 0~100 정수다. 넘으면 `progress--over`.
- 화면 낭독기용 글자는 막대 옆의 "실적 3h / 예상 2h"가 맡는다.
- 카테고리 꼬리표는 Phase 8 보완의 `category_pill`(사용자 지정 색)을 그대로 쓴다.
- 카드 링크 주소는 보드 필터를 싣는다(`/tasks/{id}/edit?project=…`).

### 등록·수정 화면

| 화면 | 주소 | 항목 | 저장 |
|---|---|---|---|
| 새 태스크 | `GET /tasks/new` | 제목, 프로젝트(보관 제외, 비우면 기본 프로젝트), 카테고리, 예상, 계획 주차, 마감일, 외부 참조, 설명 | `POST /tasks` → 성공하면 `HX-Redirect: /tasks?added=ID`(필터 프로젝트가 있으면 `&project=`) |
| 태스크 수정 | `GET /tasks/{id}/edit` | 위 항목(프로젝트는 글자로만 보임) + 상태 | `PATCH /tasks/{id}`(버전 확인) → 성공하면 `HX-Redirect: /tasks?updated=ID`(필터 유지) |
- 서비스는 이미 설명·마감일·외부 참조를 받는다(`create_task`의 `description`, `update_task`의 허용 필드). 입력 검증은 지금과 같은 core 함수(`parse_duration`, `parse_week`, `parse_date`, `services.create_task`·`update_task`·`set_task_status`)를 쓴다. 상태가 바뀌면 같은 세션에서 `set_task_status`도 부른다(완료·중단 시각 규칙이 그대로 적용된다).
- 설명은 여러 줄 입력(`textarea`)이다. 브라우저는 줄바꿈을 CRLF로 보내므로 core가 설명의 CRLF를 LF로 바꾼다(Task 9-1). 비우면 설명 없음(`None`)이다.
- 필터 유지: 새·수정 화면에는 보드의 필터 폼이 없다. "새 태스크" 링크, 카드 링크, 폼의 숨은 `project` 칸, 취소 링크, `HX-Redirect`가 모두 필터 프로젝트를 직접 싣는다.
- 오류는 같은 화면에 입력값 그대로, 문구는 `#flash`(Phase 5 규칙)와 폼 아래 결과 줄에 둔다. 409는 "다른 곳에서 태스크가 바뀌었습니다" 문구와 함께 "최신 내용으로 다시 열기" 링크.
- 보드는 `?added=`·`?updated=`가 숫자 ID이고 그 태스크가 있으면 결과 줄을 만든다. 없는 ID나 숫자가 아닌 값은 결과 줄 없이 보드만 보인다(오류 아님). 결과 줄은 주소에 남으므로 새로 고침하면 다시 보인다.
- 키보드(전체 페이지라 HTMX 교체 포커스 규칙이 돌지 않는다):
  - 제목 칸에 `autofocus`를 둔다.
  - 폼은 `<form>`과 제출 버튼이다. 한 줄 칸의 Enter는 브라우저 기본 제출에 맡기고, 설명 칸의 Enter는 줄바꿈이다. 새 폼에는 기존 `.is-editing` Enter 규칙을 쓰지 않는다.
  - Esc는 취소다. 취소 링크에 `data-cancel`을 두고 `app.js`가 Esc(설명 칸 안에서도, 한글 조합 중은 제외)에서 그 링크를 누른다.
  - 400·409로 폼을 다시 그리면 제목 칸(또는 문구가 가리키는 칸)에 포커스가 간다.

### 끌어 놓기 (`static/js/board.js`)

- 초기화: 페이지 로드와 `htmx:afterSettle`에서 하되, 이벤트 대상이 `#task-board`(또는 `.board__cards`를 품은 요소)일 때만 한다. 목록마다 `Sortable.get(list)`로 이미 붙었는지 보고 중복으로 만들지 않는다. 보드가 OOB로 바뀌는 경로도 같은 처리를 탄다.
- `new Sortable(list, { group: "tasks", sort: false, animation: 150, delayOnTouchOnly: true, delay: 150, draggable: ".task-card", ghostClass: "task-card--ghost", chosenClass: "task-card--chosen", onEnd: … })`.
- `onEnd`: `evt.from !== evt.to`면 `htmx.ajax("POST", "/tasks/" + id + "/status", { target: "#task-board", swap: "outerHTML", values: { status: evt.to.dataset.status, version: item.dataset.version, project: <필터 값> } })`.
- 요청이 끝날 때까지 보드의 끌기를 잠근다(`option("disabled", true)`). 기존 버튼의 `hx-sync="this:drop"`처럼 겹치는 요청을 만들지 않는다.
- 실패 복원: 상태 변경 요청이 실패하면 오류 문구는 지금처럼 `#flash`가 보여 준다. 카드는 `board.js`가 제자리로 돌린다.
  - 메인 세션 보완(구현 전, 2026-10-15): 처음 계획은 보드를 GET으로 다시 불러오는 것이었다. 그런데 `app.js`는 `htmx:beforeRequest`마다 `#flash`를 비운다. 그래서 다시 부르는 순간 409 문구가 지워진다. 서버가 꺼진 경우(`htmx:sendError`)에는 GET도 실패해 카드가 잘못된 열에 남는다.
  - 그래서 다시 요청하지 않는다. `htmx.ajax`가 돌려주는 Promise가 끝나면(성공·실패 모두) 끈 카드가 아직 문서 안에 있는지 본다(`item.isConnected`). 있으면 보드가 교체되지 않은 것이다. 이때 카드를 원래 목록(`evt.from`)의 원래 자리(`evt.oldIndex`)로 되돌리고 잠금을 푼다.
  - 성공하면 보드가 통째로 바뀌어 옛 카드는 문서에 없다.
  - 409 문구는 지금 버튼과 같다("목록을 새로 고친 뒤 다시 시도하세요"). 서버 응답은 바꾸지 않는다.
- 빈 열: `ul.board__cards`에 최소 높이를 둬서 카드가 없는 열에도 놓을 수 있게 한다. 빈 열의 높이가 0이면 SortableJS가 놓을 자리를 찾지 못한다.
- 끄는 중에는 카드 링크가 눌리지 않는다(끈 거리가 있으면 click이 없다). 눌렀다 바로 놓으면 링크로 이동한다.
- 인라인 코드 금지(CSP): 이벤트는 board.js에서 붙인다.

---

## Task 9-0: 계획 문서 저장

- [x] ROADMAP Phase 9 항목을 결정대로 고치고 이 계획서를 커밋한다: `docs: ROADMAP Phase 9 결정 반영`(6de6d96), `docs: Phase 9 화면 고도화 구현 계획 추가`(4189757)

---

## Task 9-1: 중단 시각 기록 (core: 스키마 4·서비스·백업 형식 4)

**Files:**
- Modify: `src/logbook/core/models.py`(`Task.dropped_at`, docstring), `core/db.py`(`SCHEMA_VERSION = 4`, `_upgrade_to_4`, `MIGRATIONS`, 마이그레이션 주석), `core/services/tasks.py`(`set_task_status`, `dropped_tasks_in_week`, 설명 줄바꿈), `core/services/__init__.py`, `core/services/backup.py`, `core/services/backup_import.py`
- Modify tests:
  - 마이그레이션 버전 하드코딩: `test_db_migration_v2.py`, `test_db_migration_v3.py`(80행 `SCHEMA_VERSION == 3`, `InitResult(…, 3, …)` 계열)를 최신 버전 기준으로
  - 새 `test_db_migration_v4.py`
  - `tests/core/test_services_tasks.py`
  - 백업: `tests/core/backup_helpers.py`(`header_v3()`가 `db.SCHEMA_VERSION`을 써서 4가 되므로 3으로 고정, `header_v4()` 추가, 태스크 행 사전을 형식별로), `test_services_backup*.py`
  - `tests/web/helpers.py`의 `add_task`에 `dropped_at` 인자(지난주 중단 케이스용)

```python
# core/models.py (Task, done_at 다음에 둔다: ALTER TABLE ADD COLUMN이 끝에 붙이므로 새 DB와 같은 순서)
    done_at: Mapped[dt.datetime | None]
    dropped_at: Mapped[dt.datetime | None]  # 중단 시각(스키마 4). 중단 상태가 아니면 None
```

```python
# core/db.py: 고정 DDL이다. 모델이 나중에 바뀌어도 이 단계는 그대로 둔다.
def _upgrade_to_4(conn: Connection) -> None:
    conn.exec_driver_sql("ALTER TABLE tasks ADD COLUMN dropped_at DATETIME")
    # 이미 중단한 태스크는 중단 시각을 모르므로 마지막 수정 시각으로 채운다(사용자 결정 D2).
    conn.exec_driver_sql("UPDATE tasks SET dropped_at = updated_at WHERE status = 'dropped'")
```
- 새 DB(`create_all`)와 올린 DB는 `PRAGMA table_info(tasks)`로 비교한다(사실 확인 실험에서 14열이 모두 같았다). `sqlite_master`의 CREATE 문은 줄바꿈이 달라 비교하지 않는다.
- 원본 SQL이라 `updated_at`의 `onupdate`가 돌지 않는다. 마이그레이션이 `updated_at`을 바꾸지 않는지 테스트로 확인한다.
- 스키마 3 입력 DB는 새 모델의 `create_all`로 만들 수 없다(4가 된다). `tests/helpers.py`의 `make_v1_database` 뒤에 `SCHEMA_VERSION`을 3으로 둔 `init_db`로 올리거나, `make_v3_database` 도우미를 둔다.

**서비스**

| 함수 | 동작 |
|---|---|
| `set_task_status` | 중단으로 바뀌면 `dropped_at = utcnow()`, 중단에서 다른 상태로 바뀌면 `None`, 중단에서 중단이면 그대로 둔다(`done_at`과 같은 규칙, `tasks.py` 130~141행 부근) |
| `dropped_tasks_in_week(s, week, *, tz, project_slug=None)` | 중단 태스크 중 `dropped_at`이 그 주의 로컬 자정 구간 안인 것. 최근 것이 먼저, 같으면 id 순. 보관 프로젝트 처리(지정하지 않으면 제외, 지정하면 그 프로젝트만, 없는 slug는 `NotFoundError`)는 `done_tasks_in_week`와 같다 |
| 설명 줄바꿈 | `create_task`·`update_task`는 이미 설명을 받는다. 설명의 CRLF·CR을 LF로 바꾼다(`week_notes`의 정규화와 같은 방식). 웹·API·저장 비교가 같은 값을 본다 |

**백업 (형식 4)**
- `backup.py`: `FORMAT_VERSION = 4`. `TASK_FIELDS`에 `dropped_at`(`done_at` 다음)을 더한다. 형식 1~3용 태스크 필드는 상수(예: `TASK_FIELDS_BEFORE_4`)나 `fields_for(table, fmt)`로 둔다(모델에서 만들지 않는다는 docstring 규칙 유지, docstring의 형식 버전도 고친다).
- `backup_import.py`:
  - `SUPPORTED_FORMATS = (1, 2, 3, 4)`, `FORMAT_TABLES`에 `4: TABLE_ORDER`
  - `_KINDS["tasks"]["dropped_at"]`은 선택 시각
  - `_check_field_names`·`_convert_fields`가 형식을 받아 형식별 필드 집합을 쓴다. 형식 1~3의 `tasks` 줄에 `dropped_at`이 있으면 기존 "알 수 없는 필드" 오류다.
  - 형식 1~3을 가져올 때는 변환 뒤 중단 태스크의 `dropped_at = updated_at`, 나머지는 `None`으로 채운다(마이그레이션과 같은 규칙).
  - `_check_invariants`: 형식 4에서만 중단 상태와 `dropped_at`이 함께 있거나 함께 없는지 본다(`done_at` 검사가 이미 있다, 415행 부근). 형식 1~3 행에는 키가 없어 검사하지 않는다.
- 결과 줄(`lb export`·`lb import`)은 바뀌지 않는다(새 테이블이 없다).

**테스트 케이스**

| 대상 | 케이스 | 기대 |
|---|---|---|
| 마이그레이션 | 중단·완료·할 일 태스크가 있는 v3 DB → v4 | 행 수 그대로, 중단 태스크만 `dropped_at = updated_at`, `updated_at` 그대로, 버전 4, 백업 1개 |
| 마이그레이션 | v1 → v4 | 세 단계 모두 적용, 백업 1개 |
| 마이그레이션 | 새 DB와 올린 DB | `PRAGMA table_info(tasks)`가 같음 |
| 서비스 | 할 일 → 중단 → 할 일 / 중단 → 중단 / 완료 → 중단 | 시각 기록 → `None` / 처음 시각 유지 / `done_at` 지워지고 `dropped_at` 기록 |
| `dropped_tasks_in_week` | 이번 주 중단 / 지난주 중단 / 보관 프로젝트 / 프로젝트 지정 / 시간대 경계(KST) | 포함 / 제외 / `done_tasks_in_week`와 같은 규칙 / 그 프로젝트만 / 로컬 날짜 기준 |
| 설명 | CRLF가 든 설명으로 만들기·고치기 | LF로 저장, 같은 내용을 CRLF로 다시 보내면 바뀐 것 없음 |
| 백업 | 내보내기 / 형식 4 왕복 / 형식 3 파일(중단 태스크 포함) / 형식 3 파일에 `dropped_at` 키 / 형식 4 불변식 위반 / 형식 4에 `dropped_at` 키 없음 | 머리글 4·`dropped_at` 필드 / 같음 / `dropped_at = updated_at` / 오류 / 오류 / 오류 |

- [x] RED → GREEN → 커밋 `feat: 태스크 중단 시각 기록(스키마 4, 백업 형식 4)` (78f1724)
  - 구현이 정한 것: `fields_for(table, fmt)`와 `TASK_FIELDS_BEFORE_4`로 형식별 필드, v2 테스트의 `seed_v1`을 고정 SQL로(새 모델에 열이 생겨서), 새 테스트는 `test_services_tasks_dropped.py`·`test_services_backup_import_v4.py`로 나눔
- [x] 메인 세션: 이전 버전으로 만든 스키마 3 DB(Phase 8 최종 스크린샷 DB)의 복사본에서 태스크 #7을 중단(수정 시각 10-08)으로 두고 `lb stats`를 실행했다.
  - `데이터베이스를 업그레이드했습니다: v3 → v4. 이전 데이터베이스 백업: …\lb.db.v3-20261015-144857.bak`
  - 버전 4, #7만 `dropped_at = 2026-10-08 01:00`(수정 시각 그대로), 나머지는 비어 있음
  - `lb export` 머리글 `format 4`·`schema_version 4`, 태스크 줄에 `dropped_at`
  - 화면 변화가 없으므로 승인은 Task 9-2와 함께 받았다(사용자 승인 2026-10-15).

---

## Task 9-2: 칸반 고도화 (모양)

**Files:** `task_views.py`(카드 진행 막대 값, 열 키), `task_board.html`, `task_card.html`, `tasks.css`, `app.css`(`--accent-soft` 등), tests(`test_tasks_page.py`, `test_theme.py`, `test_css_layout.py`)

- 열 머리: 상태 색 바탕의 둥근 띠 안에 점·제목·건수. `board__col`은 바탕·테두리·그림자를 없애 흰 카드가 떠 보이게 한다(`tasks.css` 91~98행 부근).
- 카드: `--surface`, `1px solid var(--rule)`, `--radius-sm`, `--shadow-soft`. 왼쪽 굵은 띠를 없앤다(`.task-card`의 `border-left: 3px`, `.task-card--over`·`.task-card.is-editing`의 띠 색 규칙, 137·141·213행 부근). 예상 초과는 막대 색과 꼬리표가 알린다.
- 진행 막대: 예상이 있을 때만. `percent = min(100, round(actual / estimate * 100))`, 넘으면 `over`.
- 이 Task에서는 버튼·폼은 그대로 둔다(9-3·9-4에서 바꾼다). 열은 아직 3개다(중단 열은 9-4).

| 대상 | 케이스 | 기대 |
|---|---|---|
| 카드 뷰 | 예상 없음 / 실적 0 / 절반 / 초과 | 막대 없음 / 0 / 50 / 100과 over |
| 템플릿 | 막대 SVG | `width` 속성에 정수, `aria-hidden`, `style=` 없음 |
| CSS | 열 머리 상태 색 클래스, 카드 왼쪽 띠 규칙 없음(세 곳), 진행 막대 규칙 | |
| 토큰·대비 | 새 토큰 두 테마, 열 머리 글자/바탕 쌍 4.5 이상 | |

- [x] RED → GREEN → 커밋 `feat: 칸반 열 머리 상태 색, 흰 카드, 실적·예상 진행 막대` (7f73d43)
  - 구현이 정한 것: 진행 중 열 머리 글자는 `--accent-hover`(`--accent`는 밝은 테마에서 4.5 미만), 열 머리 앞 점, `board__col` 모서리도 없앰(바탕·테두리가 없어서), `--band-*` 토큰은 9-5용으로 미리 정의, `progress_percent` 도우미(예상 0 방어)
  - 검토 minor: 진행 막대 채움·트랙의 비글자 대비 테스트(선택), 중단 열 머리 클래스는 9-4에서
  - 사용자 요청 보완: 완료 열 제목 "이번 주 완료" → "완료"(96e27d5, 문서 2ba8dbb)
- [x] 메인 세션: 전후 스크린샷·비교 페이지(compare-9-2.html, 가로 넘침 없음) → 9-1과 함께 사용자 승인(2026-10-15)

---

## Task 9-3: 태스크 등록·수정 화면 분리

**Files:** `pages/tasks.py`, `task_views.py`, 새 `task_new.html`·`task_edit.html`, `partials/task_form.html`(공용 필드), `tasks.html`, `task_card.html`(카드 전체 링크, "수정" 버튼 삭제), `static/js/app.js`(`data-cancel` Esc), CSS(새 화면 폼 배치), tests(`test_tasks_add.py`→새 화면, `test_tasks_edit.py`→새 화면(115~121행의 `/tasks/{id}/card` 사용 포함), `test_tasks_page.py`)

- 보드에서 추가 폼을 빼고 머리에 "새 태스크" 주 버튼(링크)을 둔다.
- 카드 인라인 수정(`GET /tasks/{id}/edit` 조각, `GET /tasks/{id}/card`, 카드용 `PATCH`)을 새 화면으로 바꾼다. `GET /tasks/{id}/edit`는 전체 페이지가 된다. `GET /tasks/{id}/card`는 쓰는 곳이 없어지면 라우트를 지운다(코드 줄 삭제는 허용).
- `partials/task_edit_card.html`과 `partials/task_form_response.html`(폼 + 보드 OOB)이 쓰이지 않게 되면 `git mv`로 새 용도에 옮기거나 메인 세션에 보고한다.
- 수정 화면의 상태 선택(D1): 바꾸면 저장할 때 `set_task_status`도 부른다(완료·중단 시각 규칙 적용).
- 항목(D3): 제목, 프로젝트(등록만), 카테고리, 예상, 계획 주차, 마감일, 외부 참조, 설명, 상태(수정만).
- 저장 뒤(D4): 보드로 돌아가 결과 줄. 필터 유지(공통 규칙의 필터 유지 경로).
- 키보드: 공통 규칙의 "키보드" 항목을 따른다. 카드 링크에 포커스 윤곽선, Enter로 수정 화면.
- 상태 버튼(시작·완료 등)은 9-4에서 지운다.

| 대상 | 케이스 | 기대 |
|---|---|---|
| `GET /tasks/new` | 기본 / 필터 프로젝트 | 폼 항목 8개, 프로젝트 선택지(보관 제외), 제목 `autofocus`, 취소 링크(`data-cancel`) / 숨은 `project`와 링크에 필터 |
| `POST /tasks` | 정상(설명 포함) / 제목 없음 / 잘못된 예상·주차·마감일 / 모르는 카테고리 / 보관 프로젝트 | `HX-Redirect`(필터 유지)와 생성 / 400 입력값 유지·문구 |
| 보드 | `?added=ID`, `?updated=ID`, 없는 ID, `?added=abc` | 결과 줄 / 결과 줄 / 없음 / 없음(오류 아님) |
| `GET /tasks/{id}/edit` | 기본 / 없는 ID | 값 채운 폼과 상태 선택·버전 / 404 페이지 |
| `PATCH /tasks/{id}` | 값 수정(설명 포함) / 상태만 바꿈(완료·중단) / 변경 없음(설명 CRLF 포함) / 버전 다름 / 잘못된 값 | `HX-Redirect` / 상태와 완료·중단 시각 / 결과 줄 "바뀐 것 없음" / 409 문구·다시 열기 링크 / 400 |
| 카드 | 링크 주소(필터 포함), 수정 버튼 없음 | |
| `app.js` | `data-cancel` Esc 처리, 한글 조합 중 무시 | 정적 검사 |
| 인라인 코드 | 두 화면 | `inline_code_violations(html) == []` |

- [x] RED → GREEN → 커밋 `feat: 태스크 등록·수정을 별도 화면으로 옮기고 카드를 수정 화면 링크로` (6ee47ca)
  - 구현이 정한 것: 바뀐 것이 없으면 수정 화면에 머물며 폼 아래 "바뀐 내용이 없습니다" 결과 줄을 보인다(보드 결과 줄은 추가·수정 두 가지뿐). `task_edit_card.html` → `task_edit.html`, `task_form_response.html` → `task_new.html`로 `git mv`. 인라인 수정 뷰를 등록·수정 공용 `TaskFormView`로 합침. "새 태스크" 링크는 필터가 바꾸는 보드 조각 머리에 둠. 오류 뒤 제목 칸 포커스는 폼의 `data-refocus`(app.js)
  - 메인 세션 보완(6fb77a9): 오류일 때 폼 아래 결과 줄의 `role`을 빼 `#flash`만 알림(화면 낭독기가 두 번 읽었다), 선택 상자의 Esc는 화면 취소로 넘기지 않음(검토 R1·R2)
  - 남은 것: 충돌 확인 버전의 `dropped_at`은 계획대로 9-4에서 넣는다(검토 R4)
- [x] 메인 세션: 전후 스크린샷(compare-9-3.html: 보드, 수정 화면, 새 태스크, 18장 가로 넘침 없음)·비교 페이지 → 사용자 승인(2026-10-15)

---

## Task 9-4: 끌어 놓기로 상태 변경과 중단 열

**Files:** `pages/tasks.py`(4열), `task_views.py`(열·카드 데이터 속성, 상태 버튼 정의 삭제, `task_version`에 `dropped_at`), `web/api/serialize.py`(`task_json`에 `dropped_at`), `task_board.html`, `task_card.html`, `tasks.html`(`{% block scripts %}` 추가), 새 `static/js/board.js`, `tasks.css`(4열·2×2·1열, 끄는 중 모양), tests(`test_tasks_status.py`, `test_tasks_page.py`(15행 `DROP_CONFIRM` import, 270~295행 버튼 검사, 51행 고정 데이터의 중단 태스크가 이제 중단 열에 보임), `test_api_tasks.py`(66행 필드 목록), `test_static.py`, `test_css_layout.py`, 새 태스크 화면 스크립트 목록 테스트)

- **vendor(메인 세션, 이 Task 전에):** 레지스트리에서 최신 버전을 확인하고 tarball을 받아 `dist.integrity`(sha512)를 확인한 뒤 `package/Sortable.min.js`·`package/LICENSE`를 꺼낸다(새 임시 폴더, `tarfile`의 `filter="data"`). README 표에 같은 행 형식(백틱 파일명·sha256)으로 행을 더하고, "교체할 때" 절에 `tasks.html`을 더한다. `test_static.py`의 `VENDOR_FILES`·서빙 목록에 두 파일을 더한다. 커밋 `chore: SortableJS 1.15.7 로컬 포함`.
- 보드: 4열 "할 일·진행 중·완료·중단"(완료·중단 열은 이번 주에 바뀐 것만, 열 제목은 2026-10-15 사용자 요청). 중단 열은 Task 9-1의 `dropped_tasks_in_week`를 쓴다. 빈 열도 `ul`을 그린다(놓을 자리). 빈 안내는 목록 밖 `p.empty`.
- 카드 버튼(시작·완료·할 일로·중단·다시 열기)과 그 정의(`_ACTIONS`, `DROP_CONFIRM` 등)를 지운다. JSON API의 상태 변경은 그대로다.
- `task_version`에 `dropped_at`을 넣는다(`done_at`처럼 "중단 → 할 일 → 중단" 사이의 변경도 충돌로 잡는다). `/api/tasks`의 태스크 JSON에 `dropped_at`(UTC ISO, 없으면 `null`)을 `done_at` 다음에 더한다.
- 중단 열로 끌 때 확인 창이 없다(D5). 열 안 순서는 바꾸지 않는다(D6, `sort: false`).
- 상태 변경 성공 결과 줄은 지금 문구 그대로다("✔ #5 할 일 → 진행: …"). 실패는 공통 규칙의 실패 복원을 따른다.
- 배치(D9): 4열(1100px 이상), 2×2(720~1099px), 1열(720px 미만). 보드 규칙은 지금처럼 `tasks.css`에 둔다(`test_css_layout.py` 81행 부근이 읽는 곳).
- 스크립트: `tasks.html`의 `{% block scripts %}`가 SortableJS와 board.js를 싣는다. 대시보드에는 싣지 않는다(`test_dashboard.py` 349~353행의 목록 그대로).

| 대상 | 케이스 | 기대 |
|---|---|---|
| 보드 | 4열과 `data-status`, 카드 `data-task-id`·`data-version`, 버튼 없음 | |
| 보드 | 이번 주 중단한 태스크가 중단 열에, 지난주 중단은 없음, 열 건수 | |
| `POST /tasks/{id}/status` | 끌어 놓기 값(중단→할 일 포함) / 버전 다름 / 없는 ID | 보드 / 409와 `#flash` 문구 / 404와 `#flash` 문구 |
| 버전 | 중단 시각이 바뀐 태스크 | 버전이 다르다 |
| API | 태스크 JSON | `dropped_at` 필드(중단이면 시각, 아니면 `null`) |
| 정적 | vendor README 행, sha256, 태스크 화면만 두 스크립트를 싣는다(대시보드엔 없음) | |
| JS | board.js에 `new Sortable`, `Sortable.get`, `htmx.ajax`, `sort: false`, `group`, 실패 복원(`isConnected`, `oldIndex`), 보드를 다시 부르는 GET 없음, 인라인 코드 없음 | 문자열 테스트 |
| CSS | 4열·2×2·1열 미디어 규칙, 끄는 중 모양, 빈 목록 최소 높이 | |

- 메인 세션 화면 확인: Edge 헤드리스에서 board.js의 이동 함수를 직접 불러(끌기 대신) 상태가 바뀌고 보드가 다시 그려지는지, 409를 일부러 일으켜 카드가 제자리로 돌아오는지, 끄는 중 모양, CSP 위반 로그가 없는지 본다.

- [x] vendor(메인 세션): 커밋 `chore: SortableJS 1.15.7 로컬 포함` (c8ea7c9)
  - 레지스트리 최신이 1.15.7(2026-02-11)이고 tarball의 sha512가 계획서 값과 같았다.
  - eval·new Function·style 요소 주입이 없다.
  - `LICENSE-sortablejs.txt`는 원본이 CRLF라 줄 끝만 LF로 바꿨다(README에 적음).
- [ ] RED → GREEN → 커밋 `feat: 카드를 끌어 놓아 상태를 바꾸고 중단 열 추가(SortableJS)`
- [ ] 메인 세션: 전후 스크린샷·끌어 놓기 확인·비교 페이지 → 사용자 승인

---

## Task 9-5: 대시보드 위계

**Files:** `pages/summary.py`(오늘 공수·목표 대비), `templates/partials/summary.html`, `templates/partials/timer.html`, `app.css`(띠 토큰), `dashboard.css`·`components.css`(진행 막대, 띠), tests(`test_dashboard.py`, `test_timer_panel.py`, `test_theme.py`, `test_css_layout.py`)

- 진행 막대(D7): "이번 주 공수" 칸에 `오늘 2h 30m / 목표 8h` 글자와 9-2와 같은 SVG 막대를 둔다. 목표를 넘으면 꽉 찬 막대와 "목표 달성" 꼬리표(ok).
  - 오늘 공수는 `build_summary`에서 `services.day_total_minutes(s, now.date())`로 구하고 `SummaryView`에 필드를 더한다. 빠른 기록 뒤 요약 갱신(OOB)도 같은 함수를 지나므로 같은 값이다(결과 줄의 "오늘 누적"과 같다).
  - 마크업: `dl.stats` 바로 안에 `div`를 넣지 않는다(정의 목록 구조가 깨진다). "이번 주 공수"의 `div.stat` 안 `dd`에 넣거나 `dl` 바로 아래에 둔다.
  - 기록이 없는 날에도 0%로 보이게 차트용 `has_logs` 블록 밖에 둔다.
- 강조 띠(D8): `.timer--running`(진행 중일 때 붙는 class)이 `--band-bg` 바탕, `--band-ink` 글자. 띠 안 버튼은 띠 색에 맞춘 변형(`.timer--running .btn`: 투명 바탕, `--band-ink` 글자, 대비 3:1 이상 테두리). "진행 중" 꼬리표와 점은 띠 위에서도 읽히게 한다.
- 타이머가 없을 때(시작 폼)는 지금 모양 그대로다.

| 대상 | 케이스 | 기대 |
|---|---|---|
| 요약 뷰 | 오늘 0(기록 없음) / 절반 / 목표 초과 | 0%와 막대 / 50% / 100%와 달성 꼬리표 |
| 템플릿 | 막대 SVG, 글자, `dl` 구조 | `style=` 없음, `dl` 직계에 `div` 없음 |
| 갱신 | 빠른 기록 뒤 요약 OOB | 오늘 공수가 늘어난 값 |
| 토큰·대비 | `--band-*` 두 테마, 글자/바탕 4.5 이상, 띠 위 버튼 테두리 3:1 이상 | |
| 타이머 | 진행 중 띠 클래스, 버튼 변형 | |

- [ ] RED → GREEN → 커밋 `feat: 대시보드에 오늘 목표 대비 진행 막대와 진행 중 타이머 강조 띠`
- [ ] 메인 세션: 전후 스크린샷·비교 페이지 → 사용자 승인

---

## Task 9-6: 문서 마무리와 Phase 9 완료

- [ ] **SPEC.md**
  - 2장: `tasks.dropped_at`, `schema_version` 4(버전 4: tasks.dropped_at 추가)
  - 5장 백업 형식 4(`tasks.dropped_at`, 형식 1~3 가져오기 규칙)
  - 6장: 태스크 화면(4열, 끌어 놓기, 중단 열(이번 주), 등록·수정 화면과 주소, 상태 선택, 키보드 경로, 실패 복원), 대시보드(진행 막대, 강조 띠), 의존성(SortableJS), JSON API의 `dropped_at`
  - 후속 항목: 태스크 화면 확장(끌어 놓기·설명·마감일·외부 참조 수정·중단 태스크 보기)을 정리한다
- [ ] **README.md**: 태스크 화면 사용법(끌어 놓기, 새 태스크, 수정 화면), 키보드로 상태 바꾸는 방법, 업그레이드(스키마 4)
- [ ] **CLAUDE.md, AGENTS.md**: `static/js/board.js`, vendor 목록(SortableJS), 새 템플릿
- [ ] **ROADMAP.md**: Phase 9 체크, Phase 8의 "Windows 확인 완료(2026-10-15), macOS 미확인" 표시
- [ ] **화면 확인(메인 세션)**: 다섯 화면 + 새 화면 두 개 × 1280·375·320px × 밝은·어두운, 끌어 놓기 동작, 키보드 경로
- [ ] **브라우저 확인(사용자, Windows·macOS, PR 댓글)**: 마우스·터치패드 끌어 놓기, 중단 열, 새 태스크·수정 화면, 키보드만으로 상태 바꾸기, 409(다른 터미널에서 `lb task edit` 뒤 끌어 놓기)
- [ ] **전체 검증**, **최종 리뷰**, **PR**(develop 대상, `Closes #<이슈>`)

---

## 크로스 플랫폼 체크리스트 (Phase 9 추가분)

- 끌어 놓기는 마우스·터치패드(Windows 정밀 터치패드, macOS 트랙패드) 모두 확인한다. 터치스크린은 SortableJS가 처리하지만 서버가 이 PC에서만 열리므로 확인 범위 밖이다.
- 날짜 경계는 로컬 시간대 기준이다(`dropped_tasks_in_week`는 `done_tasks_in_week`와 같은 방식).
- 스키마 4 업그레이드 백업 이름은 `<DB 파일 이름>.v3-YYYYMMDD-HHMMSS.bak`이다(두 OS 같음). 업그레이드 전에는 셸 자동완성 후보가 비어 있다(기존 동작).
- 설명의 줄바꿈은 LF로 저장한다(브라우저의 CRLF를 core가 바꾼다).

## 설계 결정 요약

1. **상태 변경 주소 하나:** 끌어 놓기, 수정 화면의 상태 선택, JSON API가 같은 서비스 함수를 쓴다.
2. **실패하면 보드를 다시 불러온다:** 상태 변경이 어떤 이유로든 실패하면 board.js가 보드를 다시 불러와 화면과 DB가 어긋난 채 남지 않는다. 오류 문구는 지금처럼 `#flash`다.
3. **중단 시각은 완료 시각과 같은 규칙:** 중단으로 바뀔 때 기록하고 벗어나면 지운다. 기존 중단 태스크는 마지막 수정 시각으로 채운다(정확한 시각을 알 수 없다). 버전과 API도 `done_at`과 대칭이다.
4. **CSP 그대로:** 진행 막대는 SVG 속성, 끌기는 CSSOM이라 인라인 스타일 허용이 필요 없다.
5. **외부 내려받기는 메인 세션만:** SortableJS tarball은 메인 세션이 받아 무결성을 확인한다.

## 사용자 결정 (2026-10-15)

- 결정 게이트 D1~D9를 모두 추천안으로 정했다(위 "결정" 표). D1은 설명을 다시 들은 뒤 골랐다.
- 이미 정해진 방향(Phase 8 결정 게이트): 등록·수정 별도 화면, 카드 버튼 모두 제거와 SortableJS 로컬 포함 끌어 놓기, 보드에 중단 열.
- 계획서 검토 중 사용자가 좌측 내비게이션(위쪽 탭 메뉴를 왼쪽 사이드바로)을 요청했다. 결정 게이트 S1(좁은 화면은 위쪽 메뉴로)만 정한 뒤 "일단 이 요구사항은 다음 페이즈로 넘길게. 내비게이션 메뉴 바는 고려하지 않고, 우선 지금 상태에서 phase 9 진행해줘"라고 했다. 좌측 내비게이션은 ROADMAP Phase 10에 적었고, Phase 9는 지금의 위쪽 메뉴 기준으로 한다(D9의 열 기준도 그대로).
- **승인:** 위 지시로 이 계획서(검토 반영본 da92b1d)를 승인했다(2026-10-15).
- Task 9-2 확인 때 사용자가 "`이번 주 완료`라는 문구를 그냥 `완료`로 고쳐줘"라고 했다. 완료 열 제목을 "완료"로 줄이고(열 내용은 그대로 이번 주에 완료한 것), Task 9-4의 중단 열 제목도 같은 규칙으로 "중단"으로 한다(메인 세션이 밝힌 기본값).

## 계획 검토 (2026-10-15)

사실 확인 에이전트 1명(Sonnet)이 주장 11개를 확인했다(임시 SQLite 실험 포함).
- 맞음: 태스크 모델·`set_task_status`의 완료 시각 규칙·`done_tasks_in_week` 시그니처, `ALTER TABLE ADD COLUMN` 결과와 새 DB의 `PRAGMA table_info`가 같음(14열), 원본 `UPDATE`가 `updated_at`을 바꾸지 않음, 웹 태스크 라우트와 결과 줄, 대시보드 구조, vendor 테스트 방식, CLI 범위(설명 옵션 없음, `lb task drop`이 `set_task_status`를 거침)
- 반영(바뀐 것)
  - 서비스는 이미 설명을 받는다. 대신 설명의 CRLF → LF 정규화를 더했다.
  - 백업 가져오기는 형식별 필드 집합이 없어 형식을 넘기는 구조로 바꾼다. `done_at` 불변식은 이미 있다. 테스트 헤더 도우미를 형식별로 나눈다.
  - 보드 좁은 화면 규칙은 `tasks.css`에 있다(`responsive.css` 아님). `tasks.html`에 스크립트 블록을 새로 만든다. 카드 띠 규칙 세 곳과 `task_form_response.html`을 정리 대상에 넣었다.
  - 새 화면은 전체 페이지라 첫 포커스는 `autofocus`, Enter는 폼 기본 제출, Esc는 `data-cancel`로 정했다.
  - 필터 유지 경로(링크·숨은 칸·`HX-Redirect`)와 `?added=` 잘못된 값 처리를 정했다.
  - 끌어 놓기 실패 복원을 409뿐 아니라 모든 실패로 넓히고, 서버 대신 board.js가 보드를 다시 불러오게 했다. 초기화 중복 방지와 요청 중 잠금을 더했다.
  - `task_version`과 `/api/tasks`에 `dropped_at`을 넣는다(`done_at`과 대칭).
  - 대시보드 막대의 마크업 위치(`dl` 구조)와 `has_logs` 밖 배치, `day_total_minutes`를 정했다.
  - 깨지는 기존 테스트의 파일·줄을 Task별로 적었다.

## 후속 항목 (Phase 9 범위 밖)

1. 지난 중단 태스크 보기(중단 열은 이번 주만 보인다)
2. 같은 열 안 순서(우선순위) 저장
3. 카드 단축키(키보드로 열 이동)
4. 설명 CLI 옵션(`lb task add/edit --desc`)
5. Phase 8 후속 4(수정 중인 카드의 프로젝트 색 점)는 인라인 수정 카드가 없어져 해당 없다(Task 9-3에서 확인)
