# Phase 6 구현 계획 (웹 대시보드 — 계획·보고서)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** SPEC 6장 "Phase 6에 남은 것"을 모두 구현한다(결정 P1).
- 화면 세 개
  - `/tasks`: 칸반, 카드 수정, 다음 주 계획 패널, 이월
  - `/report`: 미리보기, 복사, 다운로드, 특이사항·리스크 입력
  - `/settings`: 프로젝트 관리, 카테고리 확인
- `week_notes` 테이블: 첫 실제 마이그레이션(스키마 2)이다. 적용 전에 DB를 자동으로 백업하고, 내보내기는 형식 2로 올린다.
- 대시보드 타이머 시작·취소. API에 `GET /api/timer`와 `POST /api/timer/cancel`을 더한다.
- 웹 공통: 설정 파일 자동 반영, 정적 파일 캐시 무효화, 다크모드
- CLI `lb project edit`, `lb project unarchive`(결정 P4)

**Architecture:**
- **계층:** Phase 5와 같다.
  - web은 `core.services`와 허용된 core 진입점만 쓰고, SQL·ORM 쿼리를 쓰지 않는다.
  - 새 화면도 서비스를 직접 불러 HTML 전체나 조각을 돌려준다.
- **스키마:** `week_notes(week, risks, notes, updated_at)`를 스키마 2로 추가한다.
  - 마이그레이션은 고정 DDL로 쓴다.
  - 적용 직전에 같은 폴더에 DB 백업을 만든다. 업데이트 뒤 처음 실행한 `lb` 명령이 사용자의 실제 DB를 바꾸기 때문이다.
- **설정 자동 반영:** 요청이 올 때 설정 파일 내용의 해시를 보고, 바뀌었으면 다시 읽는다. 한 요청은 처음 받은 설정 하나만 쓴다(요청별 스냅숏).
- **버전 확인:** 화면에서 바꾸는 요청은 화면이 본 값의 버전을 함께 보낸다. 그사이 값이 바뀌었으면 409로 막는다(Phase 5 기록 화면과 같은 방식).
  - 대상: 태스크 상태 변경·수정, 특이사항 저장, 프로젝트 수정·보관, 타이머 취소
- **다크모드:** `prefers-color-scheme: dark`에서 CSS 색 토큰만 바꾼다. OS 테마가 바뀌면 차트는 CSS 변수를 다시 읽어 그린다.

**Tech Stack:**
- 기존과 같다: Python 3.11+(CI 3.12), uv, Typer, Rich, SQLAlchemy 2.1, Jinja2 3.1, FastAPI 0.143, Starlette 1.7, uvicorn 0.54, htmx 2.0.11, Chart.js 4.5.1
- 새 의존성은 없다(게이트 전 기본 결정).

**선행 조건:**
- **브랜치:** `feat/phase6-web-plan-report`(develop `44ddf9f`에서 분기, 이미 만들어 둠)
- **uv PATH:** 이 PC에서는 uv가 PATH에 없다.
  - Git Bash: `export PATH="/c/Users/User/AppData/Local/Microsoft/WinGet/Packages/astral-sh.uv_Microsoft.Winget.Source_8wekyb3d8bbwe:$PATH"`
  - PowerShell: `$env:Path = "$env:LOCALAPPDATA\Microsoft\WinGet\Packages\astral-sh.uv_Microsoft.Winget.Source_8wekyb3d8bbwe;$env:Path"`
- **사용자 결정:** 문서 끝의 P1~P4는 2026-10-13 승인 게이트에서 확정했다. P1·P2는 추천안보다 넓게 골랐으므로 계획에서 범위를 줄이지 않는다.
- **Task 공통 완료 조건:** 아래 명령을 모두 통과한 뒤 커밋한다.
  - `uv run ruff check .`
  - `uv run ruff format --check .`
  - `uv run mypy src/logbook/core`
  - `uv run pytest`
- **커밋 메시지:** Conventional Commits 형식이다. type만 영어이고 설명은 한국어로 쓴다.
- **TDD:** 각 Task는 실패하는 테스트를 먼저 쓰고(RED), 최소 구현으로 통과시킨 뒤(GREEN), 정리한다.
- **사용자 문구 규칙(Phase 3에서 정함):**
  - 변수 값 바로 뒤에 조사를 붙이지 않는다. 예: `옮겼습니다: 2026-W42 → 2026-W43`처럼 쓴다.
  - core 문구에는 `—` 같은 기호를 넣지 않는다. 웹 화면 문구는 `✔`·`—`·`→`를 그대로 쓴다.
  - CLI 출력의 기호는 `render.ok_mark()`·`info_mark()`·`arrow()`로 만든다. 콘솔이 UTF-8이 아니면 ASCII로 바뀐다(`·`는 `-`, `→`는 `->`). 테스트 기대도 같은 함수로 만든다.
  - 식별자(테스트 함수 이름 포함)는 영어다.
- **서브에이전트 실행 규칙(Phase 5에서 이어짐):**
  - 삭제 명령(rm, Remove-Item, rmdir, git clean)을 쓰지 않는다. 임시 파일은 매번 새 임시 폴더를 만들어 쓰고, 정리가 필요하면 보고만 한다.
  - 다른 프로세스를 강제로 끝내지 않는다(taskkill, Stop-Process, kill). 테스트 코드가 자기가 띄운 서버나 자식 프로세스를 끄는 것은 괜찮다.
  - 실제 `~/.logbook`, 실제 클립보드, 실제 브라우저를 쓰지 않는다.
    - 실제 DB를 열면 스키마 2로 올라가므로 특히 조심한다. 마이그레이션 시험은 항상 `tmp_path`의 DB로 한다.
  - `lb serve`를 터미널에서 직접 띄우지 않는다(끝나지 않는다).
  - 화면 모양 확인(Edge 헤드리스 스크린샷)은 메인 세션이 한다. 서브에이전트는 HTML·헤더를 테스트로 확인한다.

---

## 파일 구조

| 파일 | 구분 | 책임 |
|---|---|---|
| `src/logbook/core/models.py` | 수정 | `WeekNote` 모델 |
| `src/logbook/core/db.py` | 수정 | 스키마 2 마이그레이션, 마이그레이션 전 백업, `InitResult.backup_path`, `open_database(on_upgrade=…)` |
| `src/logbook/core/services/week_notes.py` | 생성 | `clean_note_text()`, `get_week_note()`, `save_week_note()` |
| `src/logbook/core/report.py`, `core/templates/report.md.j2` | 수정 | `ReportData.notes`·`risks`, 보고서 3절 |
| `src/logbook/core/services/report.py` | 수정 | 3절 값 채우기, `next_week_plan()` 공개 |
| `src/logbook/core/services/tasks.py` | 수정 | `done_tasks_in_week()` |
| `src/logbook/core/services/projects.py` | 수정 | `update_project()`, `unarchive_project()` |
| `src/logbook/core/services/backup.py`, `backup_import.py` | 수정 | 내보내기 형식 2, `week_notes`, 형식 1 가져오기 유지 |
| `src/logbook/core/taskstatus.py` | 수정 | `parse_status()`(web/api/tasks.py의 `_status`를 옮김) |
| `src/logbook/core/services/__init__.py` | 수정 | 새 함수 공개 |
| `src/logbook/cli/runtime.py` | 수정 | `announce_upgrade()`, `session()`이 업그레이드 알림을 넘긴다, `CONFLICT_MESSAGE`(task.py에서 옮김) |
| `src/logbook/cli/commands/init.py`, `serve.py`, `data.py` | 수정 | 백업 줄, 업그레이드 알림 전달, 특이사항 개수 |
| `src/logbook/cli/commands/project.py` | 수정 | `lb project edit`, `lb project unarchive` |
| `src/logbook/web/config_watch.py` | 생성 | `ConfigWatcher`, `ConfigSnapshot`, `restart_keys()` |
| `src/logbook/web/context.py` | 수정 | 요청별 맥락(`get_context`가 설정 스냅숏을 씀), 설정 알림 필드 |
| `src/logbook/web/app.py`, `server.py` | 수정 | `create_app(ctx, watcher=…)`, 서버가 watcher를 만들고 업그레이드 알림을 넘긴다 |
| `src/logbook/web/security.py` | 수정 | `/static/` 응답에 `Cache-Control: no-cache` |
| `src/logbook/web/errors.py` | 수정 | 409 문구 상수 `TASK_CHANGED`, `NOTES_CHANGED`, `PROJECT_CHANGED`, `TIMER_CHANGED` |
| `src/logbook/web/reporting.py` | 생성 | 보고서 데이터·Markdown·다운로드 파일 이름(API와 화면 공용) |
| `src/logbook/web/api/report.py`, `api/timer.py`, `api/tasks.py` | 수정 | `reporting` 사용, 타이머 상태·취소, `parse_status` 사용 |
| `src/logbook/web/pages/views.py` | 수정 | `content_version()`, `timer_version()`, 타이머 뷰 필드, 선택지 함수 공개 |
| `src/logbook/web/pages/panels.py` | 수정 | 공용 문구(`NO_CHANGE`, `CATEGORY_REQUIRED`, `NOTE_REQUIRED`), `timer_panel_context()` |
| `src/logbook/web/pages/timer.py`, `dashboard.py`, `logs.py` | 수정 | 타이머 시작·취소, 옮긴 문구 사용 |
| `src/logbook/web/pages/task_views.py` | 생성 | 칸반·카드·편집·계획 패널 뷰 데이터, `task_version()` |
| `src/logbook/web/pages/tasks.py` | 생성 | `/tasks` 라우트 |
| `src/logbook/web/pages/report.py` | 생성 | `/report` 라우트, `notes_version()` |
| `src/logbook/web/pages/settings.py` | 생성 | `/settings` 라우트, `project_version()` |
| `src/logbook/web/pages/__init__.py`, `templating.py` | 수정 | 라우터 등록, 설정 알림 공용 값 |
| `src/logbook/web/templates/` | 생성·수정 | `tasks.html`, `report.html`, `settings.html`, 새 조각, `base.html` 메뉴·알림·`color-scheme` |
| `src/logbook/web/static/css/app.css` | 수정 | 새 화면, 다크 토큰 |
| `src/logbook/web/static/js/app.js` | 수정 | `data-focus` 포커스, `.is-editing` 키보드 |
| `src/logbook/web/static/js/report.js` | 생성 | 보고서 복사 |
| `src/logbook/web/static/js/dashboard.js` | 수정 | OS 테마가 바뀌면 차트를 다시 그린다 |
| `tests/` | 생성·수정 | 각 Task의 표 |
| `README.md`, `docs/SPEC.md`, `docs/ROADMAP.md`, `CLAUDE.md`, `AGENTS.md` | 수정 | 사용법, 명세, 체크박스, 구조 |

### 화면·API 경로 (새로 생기는 것)

| 메서드·경로 | 응답 | Task |
|---|---|---|
| `GET /api/timer` | JSON `{timer}`(없으면 `null`) | 6-6 |
| `POST /api/timer/cancel` | JSON `{timer}`(지운 타이머) | 6-6 |
| `POST /timer/start`, `POST /timer/cancel` | 타이머 패널 | 6-6 |
| `GET /tasks?project=` | 페이지, HTMX면 보드 조각 | 6-7 |
| `POST /tasks` | 추가 폼 + OOB 보드·계획 | 6-7 |
| `POST /tasks/{id}/status` | 보드 + OOB 계획 | 6-7 |
| `GET /tasks/{id}/edit`, `GET /tasks/{id}/card` | 카드 조각 | 6-8 |
| `PATCH /tasks/{id}` | 보드 + OOB 계획 | 6-8 |
| `POST /tasks/carry` | 계획 + OOB 보드 | 6-8 |
| `GET /report?week=` | 페이지, HTMX면 본문 조각 | 6-9 |
| `GET /report/download?week=` | `text/markdown` 첨부 파일 | 6-9 |
| `POST /report/notes` | 본문 조각 | 6-9 |
| `GET /settings` | 페이지 | 6-10 |
| `POST /settings/projects` | 프로젝트 구역 | 6-10 |
| `GET /settings/projects/{slug}/edit`, `.../row` | 행 조각 | 6-10 |
| `PATCH /settings/projects/{slug}` | 프로젝트 구역 | 6-10 |
| `POST /settings/projects/{slug}/archive`, `.../unarchive` | 프로젝트 구역 | 6-10 |

---

## Phase 6 공통 규칙

### Phase 5 규칙 유지
Phase 5 계획서(`2026-10-09-phase5-web-dashboard.md`)의 공통 규칙을 그대로 따른다. 계층, 요청 처리, 보안, JSON API, 화면(HTMX), 표기가 모두 해당한다. 특히 다음을 지킨다.
- 템플릿에 인라인 코드(`<script>` 본문, `on…=`, `hx-on`, `style=`, `<style>`)를 쓰지 않는다. 새 화면 테스트도 `inline_code_violations()`로 확인한다.
- 오류 응답은 우리가 만든 조각이다. 놓일 자리는 `HX-Retarget`·`HX-Reswap`으로 정하고, HTMX 오류 응답에는 `HX-Push-Url: false`를 붙인다.
- 변경 폼·버튼에는 `hx-sync="this:drop"`과 `hx-disabled-elt`를 둔다.
- 세션 안에서 ORM 객체를 뷰 데이터로 바꾸고, 템플릿 렌더링은 세션을 닫은 뒤에 한다.
- 폼 입력에는 고정 id를 둔다. htmx는 교체 뒤 같은 id를 가진 입력의 포커스를 되살린다(오류로 폼이 다시 그려져도 입력하던 칸에 남는다).

### 설정 자동 반영 (Phase 5의 "설정은 시작할 때 한 번 읽는다"를 바꾼다)
- `lb serve`는 `ConfigWatcher`를 만들어 앱에 넘긴다(Task 6-5).
  - `get_context(request)`는 요청마다 `watcher.current()`를 한 번 불러 그 요청의 `WebContext`를 만들고 `request.state`에 둔다.
  - 그래서 한 요청 안에서는 설정이 바뀌지 않는다. 핸들러와 템플릿 공용 값이 같은 설정을 본다.
- **바로 반영되는 값:** `categories`, `default_project`, `daily_target_minutes`, `week_start`, `report.author`, `report.title_format`
  - `git.*`도 같이 바뀌지만 아직 쓰는 곳이 없다.
- **다시 시작해야 반영되는 값:** `db_path`, `web.host`, `web.port`(`RESTART_KEYS`)
  - 이 값이 바뀌면 화면 위에 `RESTART_REQUIRED`를 보여 준다. 실행 중인 DB와 포트는 그대로 쓴다.
  - 그래서 화면에 DB 경로를 보여 줄 때는 `cfg.db_path`가 아니라 실제로 연 DB(`ctx.engine.url.database`)를 쓴다. 다시 시작하기 전에는 두 값이 다를 수 있다.
- **읽기 실패:** TOML 문법이 틀렸거나 값이 잘못됐으면 직전 설정으로 계속 동작한다. 화면 위에는 `CONFIG_RELOAD_FAILED`를 `role="alert"`로 보여 주고, 파일을 고치면 다음 요청에서 사라진다.
- 알림은 전체 페이지(`base.html`)에만 나온다. HTMX 조각과 JSON API에는 싣지 않는다.
- 테스트 fixture `web_ctx`·`client`는 지금처럼 watcher 없이 앱을 만든다. 자동 반영은 watcher를 넘긴 앱으로 따로 시험한다.

### 버전 확인 (화면의 변경 요청)

| 대상 | 함수(모듈) | 들어가는 값 | 409 문구 |
|---|---|---|---|
| 기록(Phase 5) | `worklog_version`(views) | 기존과 같다 | `RECORD_CHANGED` |
| 태스크 | `task_version`(task_views) | id, project_id, title, description, status, category, estimate_minutes, planned_week, due_date, external_ref, created_at, done_at | `TASK_CHANGED` |
| 특이사항 | `notes_version`(pages.report) | week, risks, notes. 행이 없으면 `""` | `NOTES_CHANGED` |
| 프로젝트 | `project_version`(pages.settings) | id, slug, name, description, color, archived, created_at | `PROJECT_CHANGED` |
| 타이머 | `timer_version`(views) | started_at, project_id, category, note, task_id | `TIMER_CHANGED` |

- 모두 `views.content_version(*fields)`로 만든다. `worklog_version`의 방식(구분자 `\x1f`로 이어 sha256 앞 16자, None은 빈 문자열)을 공용 함수로 옮긴 것이다. `worklog_version`의 결과 값은 바뀌지 않는다.
- `updated_at`은 넣지 않는다. `update_task`는 바뀐 값이 없어도 `updated_at`을 바꾸므로, 넣으면 내용이 같아도 409가 난다.
- 타이머 정지는 Phase 5처럼 버전을 보지 않는다. 정지는 기록을 남겨 잃는 것이 없지만, 취소는 기록 없이 지우므로 버전을 본다(후속 항목 5).
- 버전 확인과 변경 사이의 밀리초 단위 경쟁 구간은 Phase 5처럼 막지 않는다(후속 항목 3).

### 화면 문구 (Phase 6 공용, 상수로 둔다)

| 상수(모듈) | 문구 |
|---|---|
| `TASK_CHANGED`(errors) | `다른 곳에서 태스크가 바뀌었습니다: #{id}. 목록을 새로 고친 뒤 다시 시도하세요.` |
| `NOTES_CHANGED`(errors) | `다른 곳에서 특이사항이 바뀌었습니다: {week}. 미리보기에 지금 저장된 내용이 있습니다. 입력한 내용으로 바꾸려면 다시 저장하세요.` |
| `PROJECT_CHANGED`(errors) | `다른 곳에서 프로젝트가 바뀌었습니다: {slug}. 목록을 새로 고친 뒤 다시 시도하세요.` |
| `TIMER_CHANGED`(errors) | `다른 곳에서 타이머가 바뀌었습니다. 패널에 지금 타이머를 다시 표시했습니다.` |
| `NO_CHANGE`(panels, logs에서 옮김) | `바뀐 내용이 없습니다.` |
| `CATEGORY_REQUIRED`(panels, dashboard에서 옮김) | 기존 문구 그대로 |
| `NOTE_REQUIRED`(panels) | `메모를 입력하세요. 태스크를 고르면 태스크 제목을 씁니다.` |
| `CONFIG_RELOAD_FAILED`(config_watch) | `설정 파일을 다시 읽지 못해 이전 설정으로 동작합니다: {error}` |
| `RESTART_REQUIRED`(config_watch) | `다시 시작해야 반영되는 설정이 바뀌었습니다: {keys}. lb serve를 다시 시작하세요.` |

- 옮긴 상수는 원래 모듈에서도 같은 이름으로 import해 둔다. 기존 테스트가 `dashboard.CATEGORY_REQUIRED`, `logs.NO_CHANGE`를 쓸 수 있다.
- 화면의 태스크 상태 이름은 보고서와 같은 한국어다: 할 일, 진행, 완료, 중단(`task_views.STATUS_LABELS`). CLI 문구는 그대로 영어 상태 키를 쓴다.

### 포커스와 키보드 (`app.js`, Task 6-6에서 바꾼다)
- 교체 뒤 포커스를 받을 요소에 `data-focus`를 붙인다. 바뀌는 영역마다 하나만 둔다.

| 영역 | `data-focus` |
|---|---|
| `#quick-form`(빠른 기록) | 시간 입력 |
| `#log-table` | 표 제목(`tabindex="-1"`) |
| 기록 편집 행 | 시간 입력 |
| `#timer` | 진행 중이면 정지 버튼, 아니면 시작 폼의 메모 입력 |
| `#task-form`(태스크 추가) | 제목 입력 |
| `#task-board` | 보드 제목(`tabindex="-1"`) |
| 태스크 편집 카드 | 제목 입력 |
| `#task-plan` | 패널 제목(`tabindex="-1"`) |
| `#report-body` | 특이사항 구역 제목(`tabindex="-1"`) |
| `#project-section` | 구역 제목(`tabindex="-1"`) |
| 프로젝트 편집 행 | 이름 입력 |

- `htmx:afterSettle` 규칙(Phase 5 규칙을 일반화한다. afterSwap이 아닌 이유는 Phase 5 db6008c와 같다):
  1. 응답이 2xx이고 대상에 `is-editing`이 있으면 대상 안의 `[data-focus]`로 옮긴다.
  2. 응답이 2xx이고 요청이 POST·PATCH·DELETE면 대상 안의 `[data-focus]`로 옮긴다.
  3. 응답이 4xx이고 대상에 `is-editing`이 있으면 대상 안의 `[data-focus]`로 옮긴다.
  4. 그 밖(GET 필터·주 이동, 타이머 경과 갱신, 그 밖의 오류)은 포커스를 옮기지 않는다. 1분마다 오는 경과 갱신이 입력 중인 칸의 포커스를 뺏지 않게 한다.
- htmx 2.0.11의 처리 순서(계획 검토에서 소스로 확인했다):
  - outerHTML 교체에서 `htmx:afterSettle`의 `event.target`은 새로 들어온 요소다(id는 같다).
  - OOB로 바뀐 요소에서도 같은 이벤트가 난다. OOB가 먼저, 본문 대상이 마지막이다.
  - 그래서 OOB 영역에 `data-focus`가 있어도 본문 대상의 `data-focus`가 마지막 포커스가 된다. POST·PATCH·DELETE의 본문 대상이 되는 영역에는 모두 `data-focus`를 둔다(위 표). OOB 영역만 바꾸는 변경 응답은 만들지 않는다.
- `app.js`는 `[name=duration]`, `#log-table-title`을 직접 가리키지 않는다. 대신 Phase 5 템플릿(빠른 기록, 기록 표, 기록 편집 행)에 `data-focus`를 붙인다.
- Enter 저장·Esc 취소는 `tr.is-editing`에서 `.is-editing`(편집 행·편집 카드)으로 넓힌다. 저장은 `[hx-patch]`, 취소는 `[hx-get]` 버튼이다. 버튼·`textarea` 위의 키와 한글 조합 중의 키는 건드리지 않는다(Phase 5 규칙).

### CSS
- 색은 토큰만 쓴다. `app.css`에서 `:root` 블록(밝은 테마, 어두운 테마) 밖에는 색 값(`#hex`, `rgb()`, `rgba()`, `hsl()`)을 쓰지 않는다. Task 6-11의 테스트가 확인한다. 새 화면은 6-11보다 먼저 만들므로 처음부터 토큰만 쓴다.
- 새 화면도 320px 폭에서 페이지 전체에 가로 스크롤이 없어야 한다. 칸반은 720px 미만에서 한 열로 쌓는다.
- 메뉴가 다섯 개(대시보드·기록·태스크·보고서·설정)로 늘어나므로 `.masthead__nav`에 `flex-wrap: wrap`을 더한다(Task 6-7).
- 넓은 표(프로젝트 표)는 Phase 5의 `.table-wrap`처럼 표만 가로로 스크롤한다. 오류 문구는 행 안이 아니라 알림 영역(`#flash`)에 OOB로 넣는다(Phase 5 d495112와 같은 이유).

---

## Task 6-0: 계획 문서 저장

- [x] 이 문서를 커밋한다: `docs: Phase 6 웹 대시보드(계획·보고서) 구현 계획 추가`

---

## Task 6-1: core — week_notes 테이블, 스키마 2 마이그레이션, 마이그레이션 전 백업

**Files:**
- Modify: `src/logbook/core/models.py`, `src/logbook/core/db.py`, `src/logbook/cli/runtime.py`, `src/logbook/cli/commands/init.py`, `src/logbook/cli/commands/serve.py`, `src/logbook/web/server.py`
- Create: `tests/core/test_db_migration_v2.py`
- Modify tests: `tests/helpers.py`, `tests/core/test_db.py`, `tests/core/test_db_open.py`, `tests/core/test_models.py`, `tests/cli/test_init.py`, `tests/cli/test_runtime.py`, `tests/cli/test_serve.py`

```python
# core/models.py (모듈 문서 문자열의 테이블 목록에 week_notes를 더한다)
class WeekNote(Base):
    """주차별 보고서 특이사항·리스크(보고서 3절). 두 칸이 모두 비면 행을 두지 않는다."""

    __tablename__ = "week_notes"

    week: Mapped[str] = mapped_column(String(8), primary_key=True)  # Week.label: '2026-W41'
    risks: Mapped[str] = mapped_column(Text)
    notes: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[dt.datetime] = mapped_column(default=utcnow, onupdate=utcnow)

# core/db.py
SCHEMA_VERSION = 2

def _upgrade_to_2(conn: Connection) -> None:
    """v2: week_notes 테이블. 모델이 나중에 바뀌어도 이 단계는 그대로 두도록 DDL을 고정한다."""
    conn.exec_driver_sql(
        "CREATE TABLE week_notes ("
        "week VARCHAR(8) NOT NULL, risks TEXT NOT NULL, notes TEXT NOT NULL, "
        "updated_at DATETIME NOT NULL, PRIMARY KEY (week))"
    )

MIGRATIONS: dict[int, Migration] = {2: _upgrade_to_2}

@dataclass(frozen=True)
class InitResult:
    previous_version: int | None  # None: 스키마를 새로 만들었음
    version: int                  # 적용 후 버전
    backup_path: Path | None = None  # 마이그레이션 전에 만든 백업. 올리지 않았으면 None

BACKUP_FAILED = (
    "마이그레이션 전에 데이터베이스를 백업하지 못했습니다: {target} ({detail}). "
    "디스크 공간과 쓰기 권한을 확인한 뒤 다시 실행하세요. 데이터베이스는 바뀌지 않았습니다."
)

def backup_path_for(db_file: Path, version: int, now: datetime) -> Path:
    """'logbook.db.v1-20261013-153000.bak'. 같은 이름이 있으면 '-2', '-3'…을 붙인다(덮어쓰지 않는다)."""

def init_db(engine: Engine, *, now: datetime | None = None) -> InitResult
def open_database(
    path: Path | str,
    *,
    now: datetime | None = None,
    on_upgrade: Callable[[InitResult], None] | None = None,
) -> Engine
def initialize_database(path: Path | str, *, now: datetime | None = None) -> InitResult

# cli/runtime.py
UPGRADED = "데이터베이스를 업그레이드했습니다: v{old} {arrow} v{new}."
UPGRADE_BACKUP = " 이전 데이터베이스 백업: {path}"
def announce_upgrade(result: "InitResult") -> None:
    """stderr에 업그레이드 한 줄을 쓴다(백업이 있으면 경로를 붙인다). 화살표는 render.arrow()다."""

# web/server.py (기존 인자는 그대로 두고 키워드 인자를 하나 더한다)
def serve(..., on_upgrade: Callable[[InitResult], None] | None = None) -> None
```

- **`init_db`:**
  - 새 DB(버전 테이블 없음): `create_all`로 week_notes까지 만들고 `InitResult(None, 2)`를 돌려준다. 백업하지 않는다.
  - 이미 최신: `InitResult(2, 2)`
  - 올림: 쓰기 잠금 트랜잭션(`_transaction`) 안에서 버전을 다시 읽는다. 첫 단계를 적용하기 직전에 한 번만 백업한 뒤 단계를 적용한다. 결과는 `InitResult(잠금 안에서 처음 읽은 버전, 2, 백업 경로)`다.
  - 다른 프로세스가 먼저 올렸으면 잠금 안에서 최신 버전을 보게 된다. 이때는 백업하지 않고 `InitResult(2, 2)`를 돌려준다.
  - `now`가 None이면 `datetime.now().astimezone()`을 쓴다. 백업 파일 이름에만 쓰는 값이다.
- **백업(`_backup_database(engine, version, now) -> Path | None`):**
  - 원본 경로는 `engine.url.database`다. 없거나 `:memory:`면 백업하지 않고 None이다.
  - `_copy_database(source: Path, target: Path)`는 sqlite3 백업 API(`source_conn.backup(target_conn)`)로 복사하고 두 연결을 반드시 닫는다(Windows 파일 잠금). 원본 연결의 timeout은 `BUSY_TIMEOUT_SECONDS`다.
  - 우리 연결이 쓰기 잠금(RESERVED)을 쥐고 있어도 다른 연결은 읽을 수 있다(SQLite 잠금 규칙). 같은 잠금 안에서 하므로 두 프로세스가 동시에 열어도 백업은 한 번만 생긴다.
  - 실패하면(`sqlite3.Error`, `OSError`) 만들다 만 파일을 지우고 `LogbookError(BACKUP_FAILED)`를 낸다. 트랜잭션이 롤백되어 DB는 v1 그대로다.
- **`open_database`:** 버전이 최신과 다르면 `init_db(engine, now=now)`를 부른다. 실제로 올렸으면(`previous_version != version`) `on_upgrade(result)`를 부른다.
- **`initialize_database`:** `init_db`의 결과를 그대로 돌려준다. 지금처럼 바깥에서 버전을 따로 읽지 않는다.
- **CLI:**
  - `runtime.session(cfg)`는 `db.open_database(cfg.db_path, now=now(), on_upgrade=announce_upgrade)`를 부른다. 모든 명령이 이 경로로 DB를 연다.
  - `announce_upgrade`는 `console.print_notice(UPGRADED + UPGRADE_BACKUP)`이다. 백업이 없으면 뒤 문장을 뺀다. render는 함수 안에서 import한다.
  - `lb init`은 `initialize_database(cfg.db_path, now=runtime.now())`를 부른다. 업그레이드 줄 다음에 stdout으로 `{info_mark} 이전 데이터베이스 백업: {path}` 줄을 쓴다(기호는 `render.info_mark()`, 경로는 `Text`).
  - `lb serve`는 `run_server(..., on_upgrade=runtime.announce_upgrade)`를 부른다. `web.server.serve`는 이 값을 받아 `db.open_database(cfg.db_path, now=now(), on_upgrade=on_upgrade)`에 넘긴다.
- **기존 테스트 정리(계획 검토에서 행까지 확인했다):** 고정 숫자 1·2를 `db.SCHEMA_VERSION` 기준으로 바꾼다.
  - 가짜 마이그레이션은 `db.SCHEMA_VERSION + 1`을 쓴다. 순서·누락 테스트는 `+ 2`까지 쓴다.
    - `tests/core/test_db.py`: 231~377행 부근. `== 2`(236·242행)와 `match="v3"`(302행)도 함께 옮긴다.
    - `test_init_db_requires_every_migration`(298~306행)은 이제 실제 `MIGRATIONS[2]`가 있으므로 `SCHEMA_VERSION + 2`로 올리고 `+ 1` 단계만 넣는다. 오류 문구의 버전도 바뀐다.
    - `tests/core/test_db_open.py`: 69·323·343행
    - `tests/cli/test_init.py`: 100행. 106행의 기대 `(v1 → v2)`는 `(v2 → v3)`이 된다.
  - 새 DB의 버전 단정을 바꾼다.
    - `tests/core/test_db.py`: `TABLES`(18행)에 `week_notes`를 더한다. `== 1`과 `version_rows == [1]` 단정(168·195·198·199·205·206·208·226·228·283·306·336·337·355행)은 `db.SCHEMA_VERSION` 기준으로 쓴다.
    - `tests/core/test_db_open.py`: `current_version == 1`(313·330·350행), 148행 `== 2`, 197행 `read_state`
    - `tests/cli/test_init.py`: `(스키마 v1)`(48·91·193행)과 `(스키마 v1, 최신)`(72행)은 f-string으로 `SCHEMA_VERSION`을 쓴다.
  - `init_db`의 반환값을 정수로 비교하는 테스트는 `.version`으로 바꾼다.
  - `InitResult(…)` 비교: `tests/core/test_db_open.py` 167·178·185행은 새 필드 기본값 None으로 그대로 맞는다. 195행은 가짜 마이그레이션도 백업을 만들므로 `backup_path`를 포함해 비교한다.
- **`tests/helpers.py`에 더함:** `make_v1_database(path: Path) -> None`
  - `create_all`로 만든 뒤 `week_notes`를 지우고 버전을 1로 둔다. 엔진은 닫는다.
  - 스키마 2는 v1에 테이블 하나를 더한 것이라 이렇게 만든 DB가 v1과 같다.

**테스트 케이스**

| 대상 | 케이스 | 기대 |
|---|---|---|
| 모델 | `create_all` | `week_notes` 열: week(PK, VARCHAR(8)), risks·notes(TEXT NOT NULL), updated_at(NOT NULL) |
| 마이그레이션 | `make_v1_database` + 프로젝트·태스크·기록·타이머 각 1건 → `init_db(now=2026-10-13 15:30:00+09:00)` | `InitResult(1, 2, <폴더>/logbook.db.v1-20261013-153000.bak)`, 기존 행 그대로, `week_notes` 있음, 버전 2 |
| 마이그레이션 | 올린 DB와 새로 만든 DB | `PRAGMA table_info(week_notes)`와 `PRAGMA index_list(week_notes)` 결과가 같다 |
| 백업 내용 | 위 백업 파일을 연다 | 버전 1, `week_notes` 없음, 같은 행 |
| 백업 이름 | 같은 이름 파일이 이미 있음 | `…-153000-2.bak`로 만든다. 기존 파일 내용은 그대로다 |
| 백업 없음 | 새 DB, 최신 DB | 백업 파일이 없고 `backup_path`는 None |
| 백업 실패 | `db._copy_database`가 `sqlite3.OperationalError` | `LogbookError`(BACKUP_FAILED), DB 버전 1 그대로, 백업 파일 없음 |
| 잠금 안 재확인 | 바깥 `current_version`은 1을 돌려주게 하고 실제 DB는 2 | 백업하지 않음, `InitResult(2, 2)` (기존 `test_init_db_rechecks_version_under_lock` 방식) |
| `open_database` | v1 DB, `on_upgrade`가 결과를 모음 | 한 번 불린다. 다시 열면 불리지 않는다 |
| `initialize_database` | v1 DB | `InitResult(1, 2, 경로)` |
| CLI | v1 DB에서 `lb log` | 종료 0, stderr에 `데이터베이스를 업그레이드했습니다: v1 {arrow} v2. 이전 데이터베이스 백업: …` 한 줄(arrow는 `render.arrow()`). 다음 실행에는 없다 |
| CLI | v1 DB에서 `lb init` | 업그레이드 줄 다음에 `{info_mark} 이전 데이터베이스 백업:` 줄 |
| 서버 | v1 DB에서 `lb serve`(`tests/cli/test_serve.py`의 `fake_server`) | 서버 시작 줄보다 먼저 stderr에 업그레이드 줄이 한 번 |
| 회귀 | 가짜 마이그레이션 테스트(번호를 옮긴 것) | 기존과 같은 기대 |

- [x] RED → GREEN → 커밋 `feat: week_notes 테이블과 스키마 2 마이그레이션, 마이그레이션 전 자동 백업 추가`

---

## Task 6-2: core — 특이사항 저장, 보고서 3절, 웹이 쓸 조회 함수

**Files:**
- Create: `src/logbook/core/services/week_notes.py`, `tests/core/test_services_week_notes.py`
- Modify: `src/logbook/core/report.py`, `src/logbook/core/templates/report.md.j2`, `src/logbook/core/services/report.py`, `src/logbook/core/services/tasks.py`, `src/logbook/core/taskstatus.py`, `src/logbook/core/services/__init__.py`, `src/logbook/web/api/tasks.py`
- Modify tests: `tests/core/test_report_render.py`, `tests/core/test_services_report.py`, `tests/core/test_services_tasks.py`, `tests/core/test_taskstatus.py`, `tests/cli/test_report.py`, `tests/web/test_api_report.py`, `tests/web/test_api_tasks.py`

```python
# core/services/week_notes.py
def clean_note_text(text: str) -> str:
    """줄바꿈을 LF로 바꾸고(CRLF, CR), 줄마다 끝 공백을 지우고, 앞뒤 빈 줄을 지운다.
    첫 줄의 앞 공백은 둔다. 공백뿐이면 ''."""
def get_week_note(s: Session, week: Week) -> WeekNote | None:
    """주차의 특이사항·리스크. 저장한 적이 없으면 None."""
def save_week_note(s: Session, week: Week, *, notes: str, risks: str) -> WeekNote | None:
    """두 칸을 clean_note_text로 정리해 저장한다. 둘 다 비면 행을 지우고 None을 돌려준다."""

# core/report.py (기존 필드 뒤, 기본값이 있어 기존 생성 코드가 그대로 맞는다)
@dataclass(frozen=True)
class ReportData:
    ...
    notes: str = ""  # 3절 특이사항(정리된 텍스트, 없으면 '')
    risks: str = ""  # 3절 리스크

# core/services/report.py
def next_week_plan(s: Session, week: Week) -> tuple[PlanGroup, ...]:
    """week 다음 주의 계획(보고서 4절과 같다): 다음 주 todo·doing과 week의 todo·doing(이월 후보)."""
    # 기존 _plan의 이름만 바꿔 공개한다(동작 같음). 웹 계획 패널(Task 6-8)이 쓴다.

# core/services/tasks.py
def done_tasks_in_week(
    s: Session, week: Week, *, tz: tzinfo, project_slug: str | None = None
) -> list[Task]:
    """완료 시각의 로컬 날짜(tz 기준)가 week 안인 완료 태스크(project 함께 로드).
    최근 완료가 먼저, 같으면 id 순이다. project_slug가 없으면 보관 프로젝트는 뺀다(list_tasks와 같다)."""
    # count_done_tasks 안의 범위 계산을 _done_range(week, tz) -> tuple[datetime, datetime]로 뽑아 두 함수가 같이 쓴다.

# core/taskstatus.py
STATUS_INVALID = "태스크 상태가 올바르지 않습니다: '{value}'. todo, doing, done, dropped 중 하나를 쓰세요."
def parse_status(text: str) -> TaskStatus:
    """상태 하나(앞뒤 공백·대소문자 무시). web/api/tasks.py의 _status와 문구를 옮긴다(동작 같음)."""
```

- `weekly_report`는 `get_week_note(s, week)`로 `notes`·`risks`를 채운다. `/api/report?format=json`에도 두 키가 생긴다(`dataclasses.asdict`).
- 기본 템플릿의 3절:

```jinja
## 3. 특이사항 / 리스크
{% if not data.notes and not data.risks %}
(작성하세요)
{% endif %}
{% if data.notes %}
### 특이사항
{{ data.notes }}
{% endif %}
{% if data.notes and data.risks %}

{% endif %}
{% if data.risks %}
### 리스크
{{ data.risks }}
{% endif %}
```

- 사용자 템플릿은 새 값을 쓰지 않으면 지금처럼 그린다. README의 '보고서 템플릿' 절에 `data.notes`, `data.risks`를 더한다(Task 6-12).
- `web/api/tasks.py`는 `_status`와 `STATUS_INVALID`를 지우고 `core.taskstatus`의 것을 쓴다. 기존 API 테스트의 문구가 그대로 맞아야 한다.
- `services/__init__.py`에 `get_week_note`, `save_week_note`, `clean_note_text`, `next_week_plan`, `done_tasks_in_week`를 더한다(`__all__` 포함).

**테스트 케이스**

| 대상 | 케이스 | 기대 |
|---|---|---|
| `clean_note_text` | `"a\r\nb  \r\n\r\n"` | `"a\nb"` |
| `clean_note_text` | `"\n  \n- x\n"`, `"   "`, `"  들여쓴 줄"` | `"- x"`, `""`, `"  들여쓴 줄"` |
| `save_week_note` | W40, notes `"배포 일정 확정"`, risks `""` | 행이 생기고 risks는 `""`. `get_week_note`가 같은 값을 돌려준다 |
| `save_week_note` | 있는 행에 둘 다 빈 값 | 행이 지워지고 None |
| `save_week_note` | 행이 없는데 둘 다 빈 값 | None, 행 없음 |
| `save_week_note` | 있는 행의 값을 바꿈 | 같은 행(week 하나)에 새 값 |
| `weekly_report` | W40에 저장, W41 보고서 | W40은 값이 있고 W41은 둘 다 `""` |
| 렌더링 | 둘 다 비었음 | `## 3. 특이사항 / 리스크\n(작성하세요)\n\n## 4. 다음 주 계획` |
| 렌더링 | notes만 `- 배포 일정 확정` | `## 3. 특이사항 / 리스크\n### 특이사항\n- 배포 일정 확정\n\n## 4. …` |
| 렌더링 | 둘 다 있음 | `### 특이사항\n…\n\n### 리스크\n…\n\n## 4. …` |
| 렌더링 | risks만 | `### 리스크\n…`(특이사항 없음) |
| 렌더링 | notes·risks를 쓰지 않는 사용자 템플릿 | 오류 없이 그린다 |
| `lb report` | W40에 저장 | stdout에 `### 특이사항` |
| `/api/report?format=json` | 저장 | `data.notes`, `data.risks` |
| `next_week_plan` | 보고서 4절 출력(기존 테스트, 회귀) | 출력 그대로 |
| `next_week_plan` | 직접 호출(신규): 다음 주 todo, 이번 주 doing, done·보관 프로젝트 태스크 | 4절과 같은 묶음·항목, 이번 주 건은 `carried=True`, done·보관은 없다 |
| `done_tasks_in_week` | W40 완료 2건(완료 시각 다름), 지난주 완료 1건, 보관 프로젝트 완료 1건, todo 1건 | W40 두 건, 최근 완료가 먼저 |
| `done_tasks_in_week` | 보관 프로젝트 slug를 줌 | 그 프로젝트의 W40 완료 |
| `done_tasks_in_week` | `done_at = 2026-09-27T15:30Z`(KST 09-28 00:30) | `tz=+09:00`이면 W40, `tz=UTC`면 아님(`count_done_tasks`와 같다) |
| `parse_status` | `"done"`, `" DOING "` | `TaskStatus.DONE`, `TaskStatus.DOING` |
| `parse_status` | `"x"`, `""` | `STATUS_INVALID` 문구 |
| API 회귀 | `PATCH /api/tasks/1` `{"status": "x"}` | 400, 기존 문구 그대로 |

- [x] RED → GREEN → 커밋 `feat: 보고서 특이사항·리스크 저장과 3절 출력, 다음 주 계획·이번 주 완료 조회 공개`

---

## Task 6-3: core — 내보내기 형식 2와 가져오기(형식 1·2)

**Files:**
- Modify: `src/logbook/core/services/backup.py`, `src/logbook/core/services/backup_import.py`, `src/logbook/core/services/__init__.py`, `src/logbook/cli/commands/data.py`
- Modify tests: `tests/core/backup_helpers.py`, `tests/core/test_services_backup.py`, `tests/core/test_services_backup_import.py`, `tests/core/test_services_backup_import_validation.py`, `tests/cli/test_data.py`

```python
# core/services/backup.py (모듈 문서 문자열의 형식 버전 설명을 2로 고친다)
FORMAT_VERSION = 2
TABLE_ORDER = ("projects", "tasks", "worklogs", "active_timer", "week_notes")
WEEK_NOTE_FIELDS = ("week", "risks", "notes", "updated_at")
KEY_FIELDS: Mapping[str, str]  # 행을 가리는 키: week_notes는 'week', 나머지는 'id'. 내보내기 순서도 이 키 순이다

@dataclass(frozen=True)
class BackupCounts:
    projects: int
    tasks: int
    worklogs: int
    timers: int
    week_notes: int

# core/services/backup_import.py
SUPPORTED_FORMATS = (1, 2)
FORMAT_TABLES: Mapping[int, tuple[str, ...]]  # 1: 앞의 네 테이블, 2: TABLE_ORDER
```

- **내보내기:** 머리글은 `format: 2`, `schema_version: 2`다. week_notes 행은 마지막에 week 순으로 나온다.
- **가져오기:**
  - `_check_header`가 형식 번호를 돌려주고, 그 값을 `_ImportState.format`에 둔다. format이 `SUPPORTED_FORMATS`에 없으면 기존 문구로 거부한다. 문구 끝은 `이 버전의 logbook이 읽을 수 있는 형식: 1, 2`다.
  - 형식마다 받는 테이블이 다르다(`FORMAT_TABLES[format]`).
    - `_parse_envelope`와 `_check_order`가 이 목록을 쓴다. 모듈 상수 `_TABLE_LIST` 대신 형식별 목록 문자열을 만든다.
    - 형식 1 파일에 week_notes 행이 있으면 기존 '알 수 없는 테이블' 문구다. 나열하는 목록은 형식 1의 것(`projects, tasks, worklogs, active_timer`)이다.
  - 새 값 종류 `week`(`_to_week`):
    - 문자열이고 `[0-9]{4}-W[0-9]{2}`에 맞아야 한다(`re.ASCII`, `fullmatch`).
    - `Week(int(year), int(number))`가 내는 `InvalidInputError`는 `ValueError`로 바꿔 던진다. `_convert`는 `ValueError`만 '값이 올바르지 않습니다' 문구로 바꾸기 때문이다.
    - `Week.label`이 입력과 같아야 한다.
    - 기대 값 설명(`_EXPECTED["week"]`)은 `YYYY-Www 형식의 주차 (예: 2026-W41)`이다.
  - 표에 더할 것: `MODELS["week_notes"]`, `_KINDS["week_notes"]`(week: `week`, risks·notes: `str`, updated_at: `datetime`), `_EXPECTED["week"]`, `_CONVERTERS["week"]`, `_REFERENCES["week_notes"] = ()`. 마지막 것이 없으면 `_check_references`가 KeyError를 낸다.
  - 행 키 일반화
    - `_ImportState.ids`는 `dict[str, set[object]]`로 바꾼다. week는 문자열이고 core는 mypy strict다.
    - `_record`와 `_check_unique`는 `KEY_FIELDS[table]`로 키를 읽는다. active_timer 단일 행 검사는 그대로다.
    - week_notes가 겹치면 `{n}번째 줄: week_notes 행의 week가 중복됩니다: …`이고, 값 표기는 기존 slug 중복 문구와 같다.
  - `_existing_common`은 week_notes 행도 '데이터가 있는 데이터베이스'로 센다.
  - 쓰기 순서는 `TABLE_ORDER`다.
- **CLI:** `_print_done`의 요약 끝에 `특이사항 {counts.week_notes}`를 더한다. 예: `(프로젝트 2 · 태스크 5 · 기록 41 · 타이머 0 · 특이사항 3)`(구분 기호는 `render.info_mark()`)
- **시험 도우미:** `tests/core/backup_helpers.py`의 형식 1 머리글 도우미는 `schema_version`을 1로 고정한다.
  - 지금은 `db.SCHEMA_VERSION`을 써서, 스키마 2가 되면 '형식 1 + 스키마 2'라는 없는 조합이 된다.
  - 고정하면 기존 가져오기 테스트가 실제 형식 1 파일로 돈다.
  - 형식 2 도우미(format 2, `schema_version=db.SCHEMA_VERSION`)를 따로 더한다.
- **기존 테스트 정리(계획 검토에서 행까지 확인했다):**
  - `BackupCounts`를 직접 만드는 곳에 `week_notes=0`을 더한다: `tests/core/test_services_backup.py` 39·47행, `tests/core/test_services_backup_import.py` 41·57행
  - `tests/core/test_services_backup.py`: `HEADER_LINE`(20행)의 format을 2로, `FORMAT_VERSION == 1`(262행)을 2로 바꾼다. `tuple(MODELS) == TABLE_ORDER`(274행)는 MODELS에 더하면 그대로 맞는다.
  - `tests/core/test_services_backup_import.py` 232~233행의 `set(_REFERENCES) == set(TABLE_ORDER)`는 `_REFERENCES`에 더하면 맞는다.
  - `tests/core/test_services_backup_import_validation.py` 42행의 형식 문구 끝을 `1, 2`로 바꾼다.
  - `tests/cli/test_data.py` 19·214·249행의 요약 문자열 끝에 ` · 특이사항 0`을 더한다.

**테스트 케이스**

| 대상 | 케이스 | 기대 |
|---|---|---|
| 내보내기 | W41·W40 특이사항 | 머리글 format 2·schema_version 2, 끝에 week_notes 두 줄(W40, W41 순), 필드는 `WEEK_NOTE_FIELDS` |
| 내보내기 개수 | 위 | `BackupCounts.week_notes == 2` |
| 왕복 | 내보내기 → 새 DB 가져오기 | 모든 행이 같다(특이사항 포함) |
| 형식 1 | 기존 도우미 파일(schema_version 1) | 성공, `week_notes == 0` |
| 형식 1 + week_notes 줄 | 형식 1 머리글 뒤에 week_notes 행 | 알 수 없는 테이블 문구(형식 1 목록) |
| 형식 3 | 머리글 format 3 | 지원하지 않는 형식 문구(`1, 2`) |
| week 값 | `"2026-W53"` | 통과(2026년은 53주) |
| week 값 | `"2027-W53"`, `"2026-w41"`, `"2026-W5"`, `41`, `"2026-41"` | `week_notes.week 값이 올바르지 않습니다: …`(모두 같은 문구) |
| 중복 | 같은 week 두 줄 | 중복 문구 |
| 빈 DB 확인 | 특이사항만 있는 DB에 가져오기 | 데이터가 있는 DB 문구 |
| CLI | `lb export`, `lb import` | 요약에 `특이사항 N` |
| 회귀 | `FORMAT_VERSION` 단정 | 1 → 2 |

- [x] RED → GREEN → 커밋 `feat: 내보내기 형식 2에 특이사항을 담고 형식 1 파일도 계속 가져오기`

---

## Task 6-4: core·CLI — 프로젝트 수정·보관 해제

**Files:**
- Modify: `src/logbook/core/services/projects.py`, `src/logbook/core/services/__init__.py`, `src/logbook/cli/commands/project.py`, `src/logbook/cli/commands/task.py`, `src/logbook/cli/runtime.py`
- Modify tests: `tests/core/test_services_projects.py`, `tests/cli/test_project.py`, `tests/cli/test_entry.py`(명령별 import 가드 parametrize, 343행 부근부터)

```python
# core/services/projects.py
def update_project(s: Session, slug: str, **fields: Any) -> Project:
    """넘긴 필드만 create_project와 같은 규칙으로 검증해 고친다. color·description의 None은 값을 비운다.

    필드: name, color, description. 그 밖의 이름은 TypeError. slug는 바꿀 수 없다.
    보관된 프로젝트도 고칠 수 있다. 모든 값을 검증한 뒤에만 바꾼다.
    """
def unarchive_project(s: Session, slug: str) -> Project:
    """보관을 해제한다. 보관되어 있지 않아도 그대로 반환한다."""
```

- `name`은 비울 수 없다. None이나 공백이면 `create_project`와 같은 문구(`프로젝트 이름이 비어 있습니다. 이름을 입력하세요.`)다.
- `color`는 `_validate_color`, `description`은 `strip_or_none`(공백뿐이면 None)으로 처리한다.

```
lb project edit SLUG [--name 이름] [--color '#4f46e5'] [--description 설명] [--no-color] [--no-description]
lb project unarchive SLUG
```

- `edit`의 검사는 DB·설정 없이 한다. SQLAlchemy를 로드하지 않는다.
  - `tests/cli/test_entry.py`의 명령별 import 가드 parametrize에 `project-edit-help`, `project-unarchive-help`, `project-edit-nothing`, `project-edit-conflict` 줄을 더한다. `task-edit-nothing`·`task-edit-conflict` 줄과 같은 방식이다. `tests/cli/helpers.py`는 바꾸지 않는다.
  - `lb task edit`처럼 (값 옵션, 비우기 옵션, 필드) 표(`_CLEARABLE`)로 충돌 검사와 비우기를 한 번에 한다: (`--color`, `--no-color`, color), (`--description`, `--no-description`, description)
  - 옵션을 하나도 주지 않으면 `EDIT_NOTHING`이다.
  - 값과 비우기를 함께 주면 `CONFLICT_MESSAGE`다. `cli/commands/task.py`의 것을 `runtime.py`로 옮겨 두 명령이 함께 쓴다. task.py에서도 같은 이름으로 import해 둔다.
- `edit` 출력은 add와 같은 모양이다: `{ok_mark} 프로젝트 수정: payment (결제 서버) #4f46e5`. 색이 없으면 색을 뺀다.
- `unarchive` 출력은 `{ok_mark} 프로젝트 보관 해제: payment`다. 이미 보관되지 않았으면 `{info_mark} 보관되지 않은 프로젝트입니다: payment`이다(archive의 '이미 보관된 프로젝트입니다' 줄과 같은 모양).
- `project_app`의 help는 `프로젝트를 추가·조회·수정·보관합니다.`로 바꾼다.
- `--no-color`의 help는 `색상을 비웁니다.`다. 출력 색과 헷갈리지 않게 설명을 붙인다.

| 상수(모듈) | 문구 |
|---|---|
| `EDIT_NOTHING`(cli.commands.project) | `바꿀 항목을 하나 이상 지정하세요. 예: lb project edit payment --color '#22c55e'` (`lb task edit`의 `NOTHING_TO_CHANGE_MESSAGE`와 같은 모양) |
| `CONFLICT_MESSAGE`(cli.runtime, task.py에서 옮김) | `{}와 {}는 함께 쓸 수 없습니다. 하나만 지정하세요.` (기존 문구 그대로) |

**테스트 케이스**

| 대상 | 케이스 | 기대 |
|---|---|---|
| `update_project` | name `" 새 이름 "`, color `"#22c55e"`, description `" 설명 "` | `"새 이름"`, `"#22c55e"`, `"설명"` |
| `update_project` | color None, description None 또는 `"  "` | 둘 다 None |
| `update_project` | name `""`, color `"red"` | 각 문구. 다른 필드도 바뀌지 않는다 |
| `update_project` | 모르는 필드, 없는 slug | `TypeError`, `NotFoundError` |
| `update_project` | 보관된 프로젝트 | 고쳐진다 |
| `unarchive_project` | 보관됨, 사용 중, common | False가 된다 / 그대로 / 그대로 |
| `lb project edit` | `--name`, `--color`, `--no-color`, `--description`, `--no-description`, 함께 | 바뀐 값과 출력 줄 |
| `lb project edit` | 옵션 없음, `--color`+`--no-color` | 종료 1, 각 문구, SQLAlchemy 로드 안 함 |
| `lb project edit` | 없는 slug | 종료 1, core 문구 |
| `lb project unarchive` | 보관됨, 사용 중 | 두 출력 |
| 가드 | `lb project edit --help`, `lb project unarchive --help` | 웹·SQLAlchemy 로드 안 함 |

- [x] RED → GREEN → 커밋 `feat: 프로젝트 수정·보관 해제 서비스와 lb project edit·unarchive 추가`

---

## Task 6-5: 웹 공통 — 설정 자동 반영과 정적 파일 캐시

**Files:**
- Create: `src/logbook/web/config_watch.py`, `tests/web/test_config_watch.py`, `tests/web/test_config_reload.py`
- Modify: `src/logbook/web/context.py`, `src/logbook/web/app.py`, `src/logbook/web/server.py`, `src/logbook/web/security.py`, `src/logbook/web/pages/templating.py`, `src/logbook/web/templates/base.html`, `src/logbook/web/static/css/app.css`
- Modify tests: `tests/web/test_context.py`, `tests/web/test_static.py`, `tests/web/test_security.py`, `tests/cli/test_serve.py`(서버가 watcher를 만들어 넘기는지, `fake_server` 사용)

```python
# web/config_watch.py
RESTART_KEYS = ("db_path", "web.host", "web.port")
CONFIG_RELOAD_FAILED = "설정 파일을 다시 읽지 못해 이전 설정으로 동작합니다: {error}"
RESTART_REQUIRED = "다시 시작해야 반영되는 설정이 바뀌었습니다: {keys}. lb serve를 다시 시작하세요."

@dataclass(frozen=True)
class ConfigSnapshot:
    cfg: Config
    notice: str = ""  # 화면 위 알림. 비면 없음
    notice_error: bool = False

class ConfigWatcher:
    """설정 파일 내용(바이트)이 바뀌면 다시 읽는다. 여러 스레드가 함께 불러도 된다(Lock)."""
    def __init__(
        self, path: Path, initial: Config, *, loader: Callable[[Path], Config] = load_config
    ) -> None
    def current(self) -> ConfigSnapshot

def restart_keys(before: Config, after: Config) -> tuple[str, ...]:
    """RESTART_KEYS 중 값이 다른 것(RESTART_KEYS 순서)."""

# web/context.py
@dataclass(frozen=True)
class WebContext:
    cfg: Config
    engine: Engine
    config_file: Path
    now: Callable[[], datetime] = _local_now
    config_notice: str = ""
    config_notice_error: bool = False

    def with_snapshot(self, snapshot: ConfigSnapshot) -> WebContext:
        """cfg와 알림을 스냅숏 값으로 바꾼 사본(dataclasses.replace)."""

def get_context(request: Request) -> WebContext:
    """요청의 맥락. watcher가 없으면 app.state.ctx를 그대로(같은 객체) 돌려준다.

    watcher가 있으면 그 요청의 설정 스냅숏으로 만든 맥락을 request.state에 두고 돌려준다.
    app.state.watcher와 request.state의 값은 getattr(…, None)로 읽는다(최소 앱 테스트에는 없다).
    """

# web/app.py
def create_app(ctx: WebContext, *, watcher: ConfigWatcher | None = None) -> FastAPI
    # app.state.ctx = ctx, app.state.watcher = watcher
```

- **서명:** 파일 바이트의 sha256이다. 설정 파일은 수백 바이트라 요청마다 읽어도 비용이 작다.
  - 수정 시각을 쓰지 않으므로 파일 시스템의 시각 정밀도와 상관없다. 같은 크기로 값만 바꾼 경우(포트 8765 → 8766)도 잡는다.
  - 읽기에 실패하면(`OSError`, 없는 파일 포함) 서명은 None이다. 파일이 없으면 `load_config`가 기본값을 쓴다.
  - 첫 서명은 생성자에서 잰다. 그래서 파일을 그대로 두면 loader를 한 번도 부르지 않는다.
- **다시 읽기:** 서명은 `loader(path)`를 부르기 전에 잰다. 서명이 바뀐 요청에서만 loader를 부른다.
  - 읽는 사이에 파일이 또 바뀌면 다음 요청에서 다시 읽는다.
  - 성공·실패와 상관없이 새 서명을 기억하므로, 같은 내용의 파일을 요청마다 다시 읽지 않는다.
  - 실패(`LogbookError`): 직전 `cfg`를 그대로 쓴다. 알림은 `CONFIG_RELOAD_FAILED.format(error=str(error))`, `notice_error=True`다.
  - 성공: `restart_keys(initial, new)`가 있으면 알림은 `RESTART_REQUIRED`(`notice_error=False`)이고, 없으면 알림이 없다. `cfg`는 새 값이다. 핸들러는 DB 경로·포트를 `cfg`에서 읽지 않으므로(엔진과 소켓은 시작할 때 정해진다) 새 값을 그대로 둔다.
- **화면:** `templating._shared_context`에 `config_notice`, `config_notice_error`를 더한다. `base.html`은 머리 다음에 다음 줄을 둔다.
  - `<p class="config-notice[ config-notice--error]" role="alert|status">{{ config_notice }}</p>`
- **서버:** `web.server.serve`가 `ConfigWatcher(config_file, cfg)`를 만들어 `create_app(ctx, watcher=watcher)`에 넘긴다.
- **정적 파일:** `security_headers(path)`는 `/static/` 경로에 `("Cache-Control", "no-cache")`를 더한다. 그 밖은 `no-store` 그대로다.
  - Starlette `StaticFiles`가 ETag·Last-Modified를 붙이고 조건부 요청에 304를 돌려준다.
  - 그래서 브라우저는 매번 바뀌었는지만 확인하고, 바뀐 CSS·JS는 새로 고침만으로 받는다. Phase 5 후속 항목 9를 해결한다.
- `config_watch`는 `core.config.load_config`만 쓴다(허용된 core 진입점).

**테스트 케이스**

| 대상 | 케이스 | 기대 |
|---|---|---|
| `ConfigWatcher` | 파일 그대로 두고 여러 번 | loader 0회, `initial` |
| `ConfigWatcher` | `[categories]`에 `ops = "운영"` 추가 | 새 cfg, 알림 없음 |
| `ConfigWatcher` | 같은 크기로 포트만 바꿈(8765 → 8766) | 감지한다, 재시작 알림 |
| `ConfigWatcher` | TOML 문법 오류 | 이전 cfg, `notice_error`, 알림에 core 문구 포함. 다시 불러도 loader는 1회 |
| `ConfigWatcher` | 다시 고침 | 새 cfg, 알림 없음 |
| `ConfigWatcher` | `db_path`, `[web] port` 바꿈 | 알림 `…: db_path, web.port. …`, `notice_error=False`, cfg는 새 값 |
| `ConfigWatcher` | 파일을 지움 | loader 결과(기본값) |
| `ConfigWatcher` | 파일이 바뀐 뒤 스레드 8개가 동시에 `current()` | loader 1회, 모두 같은 스냅숏 |
| 앱 | watcher 앱에서 카테고리를 더한 뒤 `GET /` | 빠른 기록 카테고리 선택지에 `ops — 운영` |
| 앱 | 설정을 깨뜨린 뒤 `GET /logs` | 200, `config-notice--error`(`role="alert"`), 기존 카테고리로 동작 |
| 앱 | 설정을 깨뜨린 뒤 `GET /api/logs` | 200 JSON, 알림 없음 |
| 앱 | 설정을 깨뜨린 뒤 HTMX `GET /logs` | 조각에 알림 없음 |
| 앱 | 한 요청에서 핸들러와 템플릿 | 같은 스냅숏(`get_context`가 `request.state`의 값을 돌려준다) |
| 앱 | watcher 없는 앱(기존 fixture) | 알림 없음, 기존 동작 그대로 |
| 맥락 | `app.state.watcher`가 없는 최소 앱(기존 `test_get_context_reads_app_state`) | `app.state.ctx`와 같은 객체 |
| 정적 | `GET /static/css/app.css` | `Cache-Control: no-cache`, ETag 있음, CSP 등 보안 헤더 |
| 정적 | 같은 ETag로 `If-None-Match` | 304, 보안 헤더 |
| 페이지 | `GET /` | `Cache-Control: no-store`(그대로) |
| 서버 | `lb serve`(`fake_server`) | `create_app`에 설정 파일 경로의 `ConfigWatcher`가 넘어간다 |

- [x] RED → GREEN → 커밋 `feat: 웹 대시보드가 설정 파일 변경을 재시작 없이 반영하고 정적 파일을 매번 확인하게 함`

---

## Task 6-6: 타이머 — API 상태·취소, 대시보드에서 시작·취소, 공용 포커스 규칙

**Files:**
- Modify: `src/logbook/web/api/timer.py`, `src/logbook/web/pages/timer.py`, `src/logbook/web/pages/views.py`, `src/logbook/web/pages/panels.py`, `src/logbook/web/pages/dashboard.py`, `src/logbook/web/pages/logs.py`, `src/logbook/web/errors.py`, `src/logbook/web/templates/partials/timer.html`, `timer_stop_response.html`, `quick_form.html`, `log_table.html`, `log_edit_row.html`, `src/logbook/web/static/js/app.js`, `src/logbook/web/static/css/app.css`
- Modify tests: `tests/web/test_api_timer.py`, `tests/web/test_timer_panel.py`, `tests/web/test_dashboard.py`, `tests/web/test_views.py`, `tests/web/test_logs_edit.py`, `tests/web/test_quick_add.py`

```python
# web/pages/views.py
def content_version(*fields: object) -> str:
    """구분자(\x1f)로 이어 sha256한 앞 16자. None은 빈 문자열이다(worklog_version에서 옮김)."""
def worklog_version(log: WorkLog) -> str          # content_version을 쓴다(결과 같음)
def timer_version(timer: ActiveTimer) -> str      # started_at(isoformat), project_id, category, note, task_id

@dataclass(frozen=True)
class TimerView:
    ...(기존)
    version: str         # timer_version
    cancel_confirm: str  # '버릴 타이머: payment/design — 설계 (시작 09:30 · 경과 1h 25m)\n버릴까요? 기록은 남지 않습니다.'

@dataclass(frozen=True)
class TimerStartValues:
    """시작 폼에 채워 둘 값(입력 문자열 그대로, 비면 '자동')."""
    note: str = ""
    project: str = ""
    category: str = ""
    task: str = ""

def project_choices(...)   # 기존 _project_choices를 공개 이름으로(동작 같음)
def category_choices(...)  # 기존 _category_choices를 공개 이름으로

# web/pages/panels.py
def timer_panel_context(
    s: Session,
    ctx: WebContext,
    now: datetime,
    *,
    values: TimerStartValues | None = None,  # None이면 빈 값. 기본값에서 만들면 ruff B008에 걸린다
    message: str = "",
    is_error: bool = False,
) -> dict[str, Any]:
    """타이머 패널 값. 진행 중이면 TimerView, 아니면 시작 폼의 선택지(quick_form_options)와 값."""
```

- **API:**
  - `GET /api/timer` → 200 `{"timer": timer_json(…)}`. 없으면 `{"timer": null}`이다.
  - `POST /api/timer/cancel` → 200 `{"timer": 지운 타이머의 timer_json}`. 없으면 404 `not_found`(`NO_TIMER_MESSAGE`)다. 본문은 받지 않는다(보내도 쓰지 않는다).
  - 직렬화는 세션 안에서 한다(`cancel_timer`가 관계를 로드한 객체를 돌려준다).
- **화면 `POST /timer/start`** (form: `note`, `project`, `category`, `task`):
  1. 세션 전 검증: 태스크가 없고 메모가 비면 `NOTE_REQUIRED`, 태스크가 없고 카테고리가 비면 `CATEGORY_REQUIRED`다. 태스크 ID는 `parse_id`로 읽는다.
  2. `services.start_timer(s, now=…, note=note.strip() or None, project_slug=project or None, category=category or None, task_id=…, allowed_categories=…, default_project=cfg.default_project)`
  3. 성공하면 진행 중 패널을 돌려준다. 결과 줄은 `TIMER_STARTED`이고, todo 태스크를 doing으로 바꿨으면 뒤에 `TASK_STARTED`를 붙인다.
  4. 실패(`LogbookError`)하면 지금 상태로 패널을 다시 그린다. 그사이 CLI가 타이머를 시작했으면 진행 중 패널이 나온다. 아니면 입력값을 채운 시작 폼이 나온다. 오류 문구를 함께 보여 주고, 상태 코드는 `classify`가 정한다.
- **화면 `POST /timer/cancel`** (form: `version`):
  - 세션 하나에서 `services.get_timer`로 지금 타이머를 읽는다.
  - 없으면 `NotFoundError(NO_TIMER_MESSAGE)`이고, 시작 폼 패널과 오류(404)를 보여 준다.
  - `timer_version`이 다르면 `ConflictError(TIMER_CHANGED)`이고, 지금 타이머 패널과 오류(409)를 보여 준다.
  - 같으면 `services.cancel_timer` 뒤 시작 폼 패널과 `TIMER_CANCELED`를 보여 준다. 기록은 남지 않는다.
- **패널 템플릿(`partials/timer.html`):**
  - 진행 중: 정지 버튼(`data-focus`)과 취소 버튼(`hx-post="/timer/cancel"`)이 있다.
    - 취소 버튼에는 `hx-vals='{{ {"version": timer.version}|tojson }}'`과 `hx-confirm="{{ timer.cancel_confirm }}"`을 둔다.
  - 진행 중이 아님: `<form id="timer-start" hx-post="/timer/start" hx-target="#timer" hx-swap="outerHTML" hx-sync="this:drop" hx-disabled-elt="find button">`
    - 메모(`id="timer-note"`, `data-focus`, placeholder `무엇을 하나요 (태스크를 고르면 생략)`)
    - 프로젝트·카테고리·태스크 선택(id `timer-project` 등, 빠른 기록과 같은 선택지와 '자동' 항목)
    - 시작 버튼
  - Phase 5의 안내 문구 `터미널에서 lb start로 시작하세요.`는 지운다.
- 공용 문구를 옮긴다. `NO_CHANGE`는 logs에서, `CATEGORY_REQUIRED`는 dashboard에서 panels로 옮기고, `NOTE_REQUIRED`를 더한다. 원래 모듈에서도 같은 이름으로 import해 둔다.
- 패널을 그리는 모든 경로는 `timer_panel_context`를 쓴다. 정지가 성공했을 때, 경과 갱신 중 타이머가 사라졌을 때(`/timer/elapsed`), `GET /timer`, 대시보드가 모두 해당한다. 시작 폼에 선택지가 있어야 하기 때문이다.
- 정지는 Phase 5 그대로다(버전을 보지 않는다).
- `app.js`는 공통 규칙의 포커스·키보드 규칙으로 바꾼다. 빠른 기록 시간, 기록 표 제목, 기록 편집 행 시간에 `data-focus`를 붙여 Phase 5 동작을 유지한다.

| 상수(pages.timer) | 문구 |
|---|---|
| `TIMER_STARTED` | `✔ 타이머 시작: {scope} — {note} ({started})` |
| `TASK_STARTED` | ` (태스크 #{id}: 할 일 → 진행)` |
| `TIMER_CANCELED` | `✔ 타이머를 버렸습니다: {scope} — {note} (경과 {elapsed})` |

**테스트 케이스**

| 대상 | 케이스 | 기대 |
|---|---|---|
| `GET /api/timer` | 없음, 진행 중 | `{"timer": null}`, 타이머 필드(`timer_json`과 같다) |
| `POST /api/timer/cancel` | 진행 중 | 200, 지운 타이머 값, DB에 타이머·새 기록 없음 |
| `POST /api/timer/cancel` | 없음 | 404 `not_found`, `NO_TIMER_MESSAGE` |
| `POST /api/timer/cancel` | 다른 출처 Origin | 403 |
| 대시보드 | 타이머 없음 | 시작 폼(선택지가 빠른 기록과 같다), 인라인 코드 없음 |
| 시작 | 메모+카테고리 | 진행 중 패널, `TIMER_STARTED`, DB 타이머 |
| 시작 | todo 태스크만 | 메모는 태스크 제목, 태스크 doing, 결과 줄 끝에 `TASK_STARTED` |
| 시작 | 메모 없음·태스크 없음 / 카테고리 없음·태스크 없음 | 400 `NOTE_REQUIRED` / 400 `CATEGORY_REQUIRED`, 입력값 유지 |
| 시작 | 이미 진행 중(CLI로 시작) | 400 core 문구, 패널은 진행 중 타이머 |
| 시작 | 보관 프로젝트 | 400 core 문구 |
| 취소 | 같은 버전 | 시작 폼 패널, `TIMER_CANCELED`, 타이머 없음, 기록 없음 |
| 취소 | 다른 버전(취소 후 다시 시작) | 409 `TIMER_CHANGED`, 타이머 그대로, 패널은 지금 타이머 |
| 취소 | 타이머 없음 | 404 `NO_TIMER_MESSAGE`, 시작 폼 패널 |
| 취소 버튼 | 진행 중 패널 | `hx-confirm` 문구, `hx-vals`의 version |
| 정지 | 성공 | 시작 폼 패널(선택지 있음), 요약·최근 기록 OOB(기존) |
| 경과 갱신 | 타이머가 사라짐 | 시작 폼 패널(PANEL_RETARGET, 기존) |
| `data-focus` | 빠른 기록, 기록 표, 기록 편집 행, 타이머(두 상태) | 각 영역에 하나씩 |
| 버전 | `content_version` | 기존 `worklog_version` 결과와 같다(회귀) |
| 버전 | `timer_version` | 시작 시각·메모가 다르면 다르다 |

- [x] RED → GREEN → 커밋 `feat: 대시보드에서 타이머 시작·취소, API에 타이머 상태 조회·취소 추가`

---

## Task 6-7: 태스크 화면 — 칸반, 상태 변경, 추가

**Files:**
- Create: `src/logbook/web/pages/task_views.py`, `src/logbook/web/pages/tasks.py`, `src/logbook/web/templates/tasks.html`, `partials/task_form.html`, `task_form_response.html`, `task_filters.html`, `task_board.html`, `task_board_response.html`, `task_card.html`, `tests/web/test_tasks_page.py`, `tests/web/test_tasks_status.py`, `tests/web/test_tasks_add.py`
- Modify: `src/logbook/web/pages/__init__.py`, `src/logbook/web/templates/base.html`(메뉴 `태스크`, `active == "tasks"`), `src/logbook/web/errors.py`(`TASK_CHANGED`), `src/logbook/web/static/css/app.css`

```python
# web/pages/task_views.py
STATUS_LABELS: Mapping[TaskStatus, str]  # 할 일, 진행, 완료, 중단(보고서와 같다)

def task_version(task: Task) -> str

@dataclass(frozen=True)
class StatusAction:
    status: str   # 'doing'
    label: str    # '시작'
    confirm: str  # 확인 창 문구, 없으면 ''

@dataclass(frozen=True)
class TaskCardView:
    id: int
    title: str
    project: str    # slug
    category: str   # key 또는 ''
    week: str       # '2026-W42' 또는 ''
    week_tag: str   # '이번 주' | '다음 주' | '지난 주' | ''
    actual: str     # 연결 기록 합계 '3h'(없으면 '0m')
    estimate: str   # '4h' 또는 ''
    over: bool      # 실적이 예상보다 많음
    version: str
    actions: tuple[StatusAction, ...]

@dataclass(frozen=True)
class TaskColumnView:
    key: str      # 'todo' | 'doing' | 'done'
    title: str    # '할 일' | '진행 중' | '이번 주 완료'
    cards: tuple[TaskCardView, ...]

@dataclass(frozen=True)
class TaskBoardView:
    columns: tuple[TaskColumnView, ...]
    project: str  # 필터('' = 전체)
    message: str = ""
    is_error: bool = False

@dataclass(frozen=True)
class TaskFormValues:
    """추가 폼에 채워 둘 값(입력 문자열 그대로)."""
    title: str = ""
    task_project: str = ""
    task_category: str = ""
    estimate: str = ""
    week: str = ""

def task_board(s: Session, ctx: WebContext, project: str, *, message: str = "", is_error: bool = False) -> TaskBoardView
```

- **메뉴:** `base.html`에 `태스크`(`active == "tasks"`)를 더하고, `.masthead__nav`에 `flex-wrap: wrap`을 더한다(공통 규칙 CSS).
- **열:** 이번 주는 `week_of(ctx.today(), cfg.week_start)`로 정한다.
  - 할 일·진행 중: `list_tasks(project_slug=…, statuses=(TODO, DOING))`를 상태로 나눈다. 순서는 계획 주차, id다.
  - 이번 주 완료: `done_tasks_in_week(s, this_week, tz=now.tzinfo, project_slug=…)`
  - 중단한 태스크와(필터가 없을 때) 보관 프로젝트의 태스크는 보이지 않는다.
  - 실적은 `actual_minutes_by_task`로 한 번에 구한다.
- **카드 버튼:**

| 상태 | 버튼(바꿀 상태) |
|---|---|
| todo | 시작(doing), 완료(done), 중단(dropped, 확인) |
| doing | 완료(done), 할 일로(todo), 중단(dropped, 확인) |
| done | 다시 열기(doing) |

- 버튼은 `hx-post="/tasks/{id}/status"`를 보낸다.
  - `hx-vals='{{ {"status": a.status, "version": card.version}|tojson }}'`, `hx-include="#task-filters"`
  - `hx-target="#task-board"`, `hx-swap="outerHTML"`
- **`GET /tasks?project=`:**
  - 페이지 구성: 추가 폼(`#task-form`), 필터(`#task-filters`, 프로젝트 선택), 보드(`#task-board`)
  - 필터를 바꾸면 `hx-get="/tasks"`, `hx-target="#task-board"`, `hx-push-url="true"`로 보낸다. HTMX 응답은 보드 조각이다. Task 6-8부터는 계획 패널 OOB도 함께 보내 두 영역이 같은 필터를 쓴다.
  - 없는 프로젝트: 전체 페이지는 오류 문구와 함께 그린다(logs와 같다). HTMX면 오류를 던져 알림 영역에 쓴다.
  - 필터 선택지는 보관 프로젝트를 포함한다(`project_choices`). 보관 프로젝트를 고르면 그 태스크가 보인다(list_tasks 규칙).
- **`POST /tasks/{id}/status`** (form: `status`, `version`, `project`):
  - `parse_id`, `parse_status`를 먼저 한다.
  - 세션 하나에서 `get_task` → `task_version`이 다르면 `ConflictError(TASK_CHANGED)`를 낸다. 같으면 `set_task_status`를 부른다.
  - 응답은 보드(결과 줄 `STATUS_CHANGED`)다. Task 6-8 뒤에는 계획 패널 OOB도 함께 보낸다.
  - 오류는 던져서 알림 영역에 쓴다(Phase 5 삭제 409와 같다). 보드는 그대로다.
- **`POST /tasks`** (form: `title`, `task_project`, `task_category`, `estimate`, `week`, `project`(필터)):
  - 추가 폼 필드 이름은 필터의 `project`와 겹치지 않게 `task_project`·`task_category`로 쓴다(Phase 5 편집 행의 `log_project`와 같은 이유).
  - 프로젝트 선택지는 보관 프로젝트를 뺀다(`project_choices(s, archived=False)`). 보관 프로젝트로 추가하는 400 시험은 직접 POST로 한다.
  - 값 해석:
    - 프로젝트: 비면 `cfg.default_project`
    - 카테고리: 비면 None
    - 예상: `parse_duration(text, max_minutes=None)`. 비면 None
    - 주차: `parse_week(text, today=…, week_start=…)`. 비면 None
  - `create_task(..., allowed_categories=tuple(cfg.categories))`
  - 성공 응답은 추가 폼(`#task-form`, 제목·예상은 비우고 프로젝트·카테고리·주차는 유지)과 결과 줄 `TASK_ADDED`다. 보드를 OOB로 함께 보낸다.
  - 실패하면 입력값을 채운 추가 폼과 오류 문구를 돌려준다. 상태 코드는 `classify`가 정하고, 보드는 보내지 않는다.

| 상수(pages.tasks) | 문구 |
|---|---|
| `TASK_ADDED` | `✔ 태스크 추가: #{id} {project} · {title}{details}` (`details`: 있는 것만 ` (예상 4h, 2026-W43)`) |
| `STATUS_CHANGED` | `✔ #{id} {old} → {new}: {project} · {title}{tail}` (완료면 `tail`이 ` (실적 5h 30m / 예상 4h)`, 예상이 없으면 ` (실적 5h 30m)`) |
| `DROP_CONFIRM` | `중단할 태스크: #{id} {project} · {title}\n중단할까요? 중단한 태스크는 이 화면에 보이지 않습니다.` |

**테스트 케이스**

| 대상 | 케이스 | 기대 |
|---|---|---|
| 페이지 | `GET /tasks` | 200, 메뉴 `aria-current`, 세 열, 추가 폼, 필터, 인라인 코드 없음 |
| 열 | todo 2건(다른 주), doing 1건, 이번 주 완료 1건, 지난주 완료 1건, dropped 1건, 보관 프로젝트 todo 1건 | 할 일 2, 진행 중 1, 이번 주 완료 1. dropped·보관은 없다 |
| 카드 | 예상 4h, 실적 5h | `실적 5h / 예상 4h`, 넘침 표시. 예상이 없으면 `실적 0m`만 |
| 카드 | 주차 이번 주·다음 주·지난주·없음 | 주차 표시와 꼬리표 |
| 필터 | `?project=payment` | payment 태스크만. HTMX면 보드 조각 |
| 필터 | `?project=nope` | 전체 페이지는 404와 문구. HTMX는 알림 조각 |
| 필터 | 보관 프로젝트 | 그 프로젝트의 태스크 |
| 상태 | todo → doing(버전 같음) | 진행 중 열로 옮김, `STATUS_CHANGED`, DB doing |
| 상태 | doing → done | done_at 기록, 결과 줄 꼬리에 실적 |
| 상태 | done → doing(다시 열기) | done_at 지움 |
| 상태 | 중단 버튼 | `hx-confirm` 문구 |
| 상태 | 다른 버전(CLI로 제목 수정) | 409 `TASK_CHANGED`(알림 조각), DB 그대로 |
| 상태 | status `x` / 없는 태스크 | 400 `STATUS_INVALID` / 404 core 문구 |
| 추가 | 제목+프로젝트+카테고리+예상+주차 `next` | 폼은 프로젝트·카테고리·주차 유지(제목·예상 빔), `TASK_ADDED`, OOB 보드에 새 카드 |
| 추가 | 제목 비움 / 예상 `abc` / 보관 프로젝트(직접 POST) | 400 각 문구, 입력값 유지, OOB 보드 없음 |
| 추가 폼 | 프로젝트 선택지 | 보관 프로젝트가 없다 |
| 추가 | 프로젝트 비움 | `default_project`에 추가 |
| 보안 | 다른 출처에서 `POST /tasks` | 403 |

- [x] RED → GREEN → 커밋 `feat: 태스크 화면 칸반과 상태 변경·추가`

---

## Task 6-8: 태스크 화면 — 카드 수정, 다음 주 계획 패널, 이월

**Files:**
- Create: `src/logbook/web/templates/partials/task_edit_card.html`, `task_plan.html`, `tests/web/test_tasks_edit.py`, `tests/web/test_tasks_plan.py`
- Modify: `src/logbook/web/pages/task_views.py`, `src/logbook/web/pages/tasks.py`, `partials/task_board_response.html`, `task_form_response.html`, `src/logbook/web/static/css/app.css`

```python
# web/pages/task_views.py
@dataclass(frozen=True)
class TaskEditValues:
    """편집 카드에 채워 둘 값(입력 문자열 그대로, 오류 뒤에도 유지)."""
    title: str
    task_category: str  # key 또는 ''
    estimate: str       # '4h' 또는 ''
    week: str           # '2026-W42' 또는 ''
    version: str

@dataclass(frozen=True)
class TaskEditView:
    id: int
    project: str
    values: TaskEditValues
    categories: tuple[Choice, ...]  # 설정 카테고리 + 현재 값(category_choices)
    error: str = ""

@dataclass(frozen=True)
class PlanPanelView:
    heading: str                  # '다음 주 계획 2026-W43 (10-19 ~ 10-25)'
    groups: tuple[PlanGroup, ...]  # core.report.PlanGroup 그대로(프로젝트 필터 적용)
    carry_ids: tuple[int, ...]    # 표시된 이월 후보(PlanItem.carried)의 id
    carry_confirm: str
    message: str = ""
    is_error: bool = False

def edit_values(task: Task) -> TaskEditValues
def plan_panel(s: Session, ctx: WebContext, project: str, *, message: str = "", is_error: bool = False) -> PlanPanelView
```

- **편집 카드:** `GET /tasks/{id}/edit`가 `<article id="task-{id}" class="card is-editing">`를 돌려준다. `GET /tasks/{id}/card`는 보기 카드를 돌려준다(취소).
  - 입력: 제목(`data-focus`), 카테고리 선택('없음' 포함), 예상(텍스트), 주차(텍스트, placeholder `this, next, 2026-W43`), 숨긴 version
  - 저장: `hx-patch="/tasks/{id}"`, `hx-include="closest .card, #task-filters"`, `hx-target="#task-board"`, `hx-swap="outerHTML"`, `hx-sync="this:drop"`, `hx-disabled-elt="this"`
  - 취소: `hx-get="/tasks/{id}/card"`
- **`PATCH /tasks/{id}`** (form: `title`, `task_category`, `estimate`, `week`, `version`, `project`):
  - 세션 전에 예상(`parse_duration(…, max_minutes=None)`)과 주차(`parse_week`)를 해석한다. 빈 값은 None이다.
  - 세션 안에서 버전을 확인하고, 바뀐 것만 `update_task`에 넘긴다(Phase 5 기록 수정의 `_changes`와 같은 방식).
    - 제목: `title.strip() != task.title`
    - 카테고리: 빈 값은 None
    - 예상: 분 값 비교
    - 주차: label 비교
  - 바뀐 것이 없으면 결과 줄은 `NO_CHANGE`다.
  - 응답은 보드(결과 줄 `TASK_UPDATED`)와 계획 패널 OOB다.
  - 오류(`InvalidInputError`, `ConflictError`)면 편집 카드를 입력값 그대로 다시 그린다.
    - 헤더: `HX-Retarget: #task-{id}`, `HX-Reswap: outerHTML`, `HX-Push-Url: false`
    - 문구는 `#flash`에 OOB로 넣는다(Phase 5 `log_edit_row.html`과 같다).
- **계획 패널(`#task-plan`)**:
  - 보드 아래에 둔다. 넓은 화면에서도 아래다.
  - 이번 주 기준 `next_week_plan(s, this_week)`를 쓴다. 프로젝트 필터가 있으면 그 프로젝트 묶음만 보여 준다.
  - 묶음마다 `{project} (예상 {estimate_total})`과 항목 `#{id} {title} — 예상 {estimate}`를 보여 준다. 이월 후보에는 `(이월 후보)`를 붙인다(보고서 4절과 같은 표기).
  - 계획이 없으면 `계획된 태스크가 없습니다.`다.
  - 이월 버튼은 이월 후보가 있을 때만 보인다.
    - `hx-post="/tasks/carry"`, `hx-vals='{{ {"ids": ids_text}|tojson }}'`(쉼표로 이은 id), `hx-include="#task-filters"`
    - `hx-target="#task-plan"`, `hx-swap="outerHTML"`, `hx-sync="this:drop"`, `hx-disabled-elt="this"`, `hx-confirm="{{ plan.carry_confirm }}"`
- **`POST /tasks/carry`** (form: `ids`, `project`):
  - 각 id를 `parse_id`로 읽는다. 하나도 없으면 `CARRY_EMPTY`다.
  - `carry_tasks(s, this_week, ids)`를 부른다. 그사이 바뀐 태스크는 서비스가 건너뛴다.
  - 응답은 계획 패널(결과 줄 `CARRIED`, 건너뛴 것이 있으면 `CARRY_SKIPPED`를 붙인다)과 보드 OOB다. 카드의 주차 꼬리표가 바뀐다.
  - 옮긴 건수가 0이면 성공 줄을 쓰지 않는다. `ConflictError(CARRY_NONE)`로 보고, 지금 상태로 계획 패널과 보드 OOB를 다시 그려 409로 돌려준다(`render_error`). 화면을 열어 둔 채 주가 바뀐 경우가 여기에 해당한다.
- Task 6-7의 응답들(필터 GET의 HTMX 응답, 상태 변경, 추가)에 계획 패널 OOB를 더한다. 필터 GET에서는 패널도 같은 필터를 쓴다.

| 상수(pages.tasks) | 문구 |
|---|---|
| `TASK_UPDATED` | `✔ 수정했습니다: #{id} {project} · {title}` |
| `CARRY_CONFIRM` | `이번 주의 할 일·진행 태스크를 다음 주로 옮길까요?\n{this} → {next}, {count}건` |
| `CARRIED` | `✔ {count}건을 옮겼습니다: {this} → {next}` |
| `CARRY_SKIPPED` | ` {count}건은 그사이 바뀌어 옮기지 않았습니다.` |
| `CARRY_EMPTY` | `옮길 태스크가 없습니다.` |
| `CARRY_NONE` | `옮긴 태스크가 없습니다. 그사이 상태나 계획 주차가 바뀌었습니다. 패널을 지금 상태로 다시 표시했습니다.` |

**테스트 케이스**

| 대상 | 케이스 | 기대 |
|---|---|---|
| 편집 | `GET /tasks/1/edit` | `is-editing` 카드, 현재 값, 제목에 `data-focus`, version |
| 편집 | 설정에 없는 카테고리를 가진 태스크 | 선택지에 현재 값 |
| 저장 | 제목·카테고리·예상·주차 바꿈 | 보드와 `TASK_UPDATED`, DB 반영, 계획 패널 OOB |
| 저장 | 카테고리·예상·주차를 비움 | DB 값 None |
| 저장 | 바꾼 것 없음 | `NO_CHANGE` |
| 저장 | 주차 `2026-W99`, 예상 `abc` | 400, 편집 카드에 입력값 유지, `HX-Retarget: #task-1`, `#flash` OOB 문구 |
| 저장 | 다른 버전 | 409 `TASK_CHANGED`, 입력값 유지 |
| 취소 | `GET /tasks/1/card` | 보기 카드 |
| 계획 | 다음 주 todo 1건(예상 8h), 이번 주 doing 1건(예상 4h) | 보고서 4절과 같은 묶음, 이월 후보 표시, `carry_ids`는 이번 주 건 |
| 계획 | 프로젝트 필터 | 그 프로젝트 묶음만, 이월 id도 그 프로젝트만 |
| 계획 | 계획 없음 | `계획된 태스크가 없습니다.`, 이월 버튼 없음 |
| 이월 | 표시된 id로 POST | 계획 주차가 다음 주로 바뀜, `CARRIED`, OOB 보드 꼬리표 `다음 주` |
| 이월 | 확인 사이에 한 건이 done | `CARRY_SKIPPED` 포함 |
| 이월 | `ids` 비움 / `ids=x` | 400 `CARRY_EMPTY` / 400 ID 문구 |
| 이월 | 화면을 연 뒤 주가 바뀜(시계를 7일 옮긴 뒤 POST) | 409 `CARRY_NONE`, 패널은 지금 상태 |
| 응답 | 상태 변경·추가·수정 | 계획 패널 OOB 포함 |
| 응답 | 필터 GET(HTMX) `?project=payment` | 계획 패널 OOB가 같은 필터(payment 묶음만) |
| 버튼 | 이월, 편집 카드 저장 | `hx-swap="outerHTML"`. 저장은 `hx-target="#task-board"` |
| 키보드 | `app.js` | `.is-editing` 안의 Enter·Esc 규칙(공통 규칙, 테스트는 정적 파일 내용 확인 정도) |

- [x] RED → GREEN → 커밋 `feat: 태스크 카드 수정과 다음 주 계획 패널·이월`

---

## Task 6-9: 보고서 화면 — 미리보기, 복사, 다운로드, 특이사항

**Files:**
- Create: `src/logbook/web/reporting.py`, `src/logbook/web/pages/report.py`, `src/logbook/web/templates/report.html`, `partials/report_nav.html`, `partials/report_body.html`, `src/logbook/web/static/js/report.js`, `tests/web/test_report_page.py`, `tests/web/test_report_notes.py`, `tests/web/test_report_download.py`
- Modify: `src/logbook/web/api/report.py`, `src/logbook/web/pages/__init__.py`, `src/logbook/web/templates/base.html`(메뉴 `보고서`), `src/logbook/web/errors.py`(`NOTES_CHANGED`), `src/logbook/web/static/css/app.css`, `tests/web/test_api_report.py`(회귀), `tests/core/test_report_render.py`(휠 포함 목록에 `logbook/web/static/js/report.js`), `tests/web/test_static.py`(MIME 목록 54~58행과 LF 검사 목록 169~175행에 `report.js`)

```python
# web/reporting.py (API와 화면 공용)
def report_data(s: Session, ctx: WebContext, week: Week, now: datetime) -> ReportData
    """services.weekly_report(tz=now.tzinfo or UTC, title_format·author·category_labels는 설정)."""
def report_markdown(ctx: WebContext, data: ReportData) -> str
    """render_markdown(data, template_path=user_template_path(ctx.config_file)). 세션 밖에서 부른다."""
def download_name(week: Week) -> str  # 'weekly-report-2026-W42.md'

# web/pages/report.py
def notes_version(note: WeekNote | None) -> str  # 없으면 ''

@dataclass(frozen=True)
class NotesValues:
    notes: str
    risks: str
    version: str

@dataclass(frozen=True)
class ReportBodyView:
    week: str           # '2026-W42'
    heading: str        # week_heading
    markdown: str       # 렌더링 결과(템플릿 오류면 '')
    preview_error: str  # 사용자 템플릿 오류 문구(있으면 미리보기 대신 보여 준다)
    download_url: str   # '/report/download?week=2026-W42'
    notes: NotesValues
    message: str = ""
    is_error: bool = False
```

- `api/report.py`는 `reporting`을 쓰도록 바꾼다. 응답은 지금과 같고, json에 notes·risks가 더해질 뿐이다.
- **`GET /report?week=`** (기본 this):
  - 페이지 구성
    - 주 이동(`report_nav.html`): 이전 주·다음 주 링크와 주차 입력 폼. `hx-get`, `hx-target="#report-body"`, `hx-push-url="true"`
    - 본문(`#report-body`): 복사 버튼, 내려받기 링크, 미리보기 `<pre id="report-markdown">`, 특이사항 폼
  - HTMX 응답은 본문 조각과 주 이동 OOB다.
  - 잘못된 주차는 기록 페이지와 같이 처리한다. 전체 페이지는 오류 문구와 함께 그리고, HTMX는 알림 조각이다.
  - 사용자 템플릿 오류(`render_markdown`의 `InvalidInputError`)가 나도 페이지는 200이다. 미리보기 자리에 오류 문구를 보여 주고, 특이사항 폼은 그대로 쓸 수 있다.
- **`GET /report/download?week=`:**
  - `Response(markdown, media_type="text/markdown; charset=utf-8")`
  - `Content-Disposition: attachment; filename="weekly-report-2026-W42.md"`. ASCII 이름이라 `filename*`이 필요 없다.
  - 내용은 `report_markdown`과 같다(UTF-8, LF).
  - 잘못된 주차나 템플릿 오류는 공통 오류 처리(400 오류 페이지)다.
- **`POST /report/notes`** (form: `week`, `notes`, `risks`, `version`):
  - 주차는 숨긴 값이고 `parse_week`로 읽는다.
  - 세션 하나에서 다음 순서로 한다.
    1. `get_week_note`로 지금 행을 읽는다.
    2. `notes_version`이 다르면 `ConflictError(NOTES_CHANGED)`를 낸다.
    3. `save_week_note`로 저장한다.
    4. 보고서 데이터를 다시 만든다.
  - 렌더링은 세션 밖에서 한다.
  - 결과 줄은 `NOTES_SAVED`다. 저장 전과 후의 버전이 같으면 `NO_CHANGE`다.
  - **409:** 미리보기는 지금 저장된 내용으로 다시 그린다. 폼의 두 칸에는 사용자가 입력한 값을 그대로 두고, version은 지금 값으로 바꾼다. 그래서 다른 곳의 변경을 본 뒤 한 번 더 저장하면 입력한 내용으로 바뀐다. 문구는 폼 안에 `role="alert"`로 둔다.
  - **400(주차 오류):** 입력값을 유지하고 폼 안에 문구를 둔다.
- **복사(`report.js`):** `[data-copy-target]` 버튼에 이벤트 위임으로 붙인다.
  - `navigator.clipboard.writeText(대상.textContent)`로 복사한다. 127.0.0.1·localhost는 보안 컨텍스트라 쓸 수 있다.
  - 실패하면 선택 범위(Range·Selection)로 `document.execCommand("copy")`를 시도한다.
  - 결과는 `#copy-status`(`role="status"`)에 `COPIED` 또는 `COPY_FAILED`로 쓴다.
  - `report.html`의 `{% block scripts %}`에서 불러온다. 인라인 코드는 없다.
- 특이사항 폼:
  - `<form id="report-notes" hx-post="/report/notes" hx-target="#report-body" hx-swap="outerHTML" hx-sync="this:drop" hx-disabled-elt="find button">`
  - 숨긴 week·version, `textarea#report-notes-text`(name `notes`)와 `textarea#report-risks-text`(name `risks`), 저장 버튼
  - 구역 제목 `<h2 tabindex="-1" data-focus>특이사항 · 리스크</h2>`

| 상수(모듈) | 문구 |
|---|---|
| `NOTES_SAVED`(pages.report) | `✔ 특이사항·리스크를 저장했습니다: {week}` |
| `COPIED`(report.js) | `보고서를 클립보드에 복사했습니다.` |
| `COPY_FAILED`(report.js) | `복사하지 못했습니다. 미리보기에서 직접 선택해 복사하세요.` |

**테스트 케이스**

| 대상 | 케이스 | 기대 |
|---|---|---|
| 페이지 | `GET /report` | 200, 메뉴 `aria-current`, `<pre>`에 `# 주간업무보고`, 복사 버튼 `data-copy-target="report-markdown"`, 내려받기 링크 `/report/download?week=2026-W40`, 빈 특이사항 폼, `report.js`, 인라인 코드 없음 |
| 페이지 | `?week=last` | W39 제목, 이전·다음 링크 |
| 페이지 | `?week=abc` | 전체 페이지 400과 주차 문구. HTMX는 알림 조각 |
| 페이지 | 설정 폴더의 `report.md.j2` 문법 오류 | 200, 미리보기 자리에 템플릿 오류 문구, 폼은 있다 |
| 내려받기 | `?week=2026-W40` | 200, `text/markdown; charset=utf-8`, `attachment; filename="weekly-report-2026-W40.md"`, 본문은 `/api/report`의 markdown과 같다, `Cache-Control: no-store` |
| 내려받기 | `?week=abc` | 400 |
| 저장 | notes·risks(version `""`) | 본문 조각, 미리보기에 `### 특이사항`, `NOTES_SAVED`, DB 행 |
| 저장 | CRLF 입력 | LF로 저장 |
| 저장 | 둘 다 비움 | 행 삭제, 미리보기 `(작성하세요)` |
| 저장 | 같은 값 다시 | `NO_CHANGE` |
| 저장 | 다른 버전(다른 탭에서 먼저 저장) | 409 `NOTES_CHANGED`, textarea에 입력값, 미리보기는 저장된 값, 폼 version은 지금 값 |
| 저장 | 숨긴 week `abc` | 400 주차 문구 |
| 보안 | 다른 출처에서 `POST /report/notes` | 403 |
| API 회귀 | `GET /api/report`(md, json) | 기존 기대 + json의 notes·risks |
| 휠 | 포함 목록 | `logbook/web/static/js/report.js` |
| 정적 | `GET /static/js/report.js` | `text/javascript`, UTF-8, CR 없음(test_static 목록) |

- [x] RED → GREEN → 커밋 `feat: 보고서 화면(미리보기·복사·내려받기·특이사항 입력)`

---

## Task 6-10: 설정 화면 — 프로젝트 관리, 카테고리 확인

**Files:**
- Create: `src/logbook/web/pages/settings.py`, `src/logbook/web/templates/settings.html`, `partials/project_section.html`, `partials/project_row.html`, `partials/project_edit_row.html`, `tests/web/test_settings_page.py`, `tests/web/test_settings_projects.py`
- Modify: `src/logbook/web/pages/__init__.py`, `src/logbook/web/templates/base.html`(메뉴 `설정`), `src/logbook/web/errors.py`(`PROJECT_CHANGED`), `src/logbook/web/static/css/app.css`

```python
# web/pages/settings.py
def project_version(project: Project) -> str

@dataclass(frozen=True)
class ProjectRowView:
    slug: str
    name: str
    color: str          # 견본에 쓸 색: #[0-9a-fA-F]{6}에 맞을 때만 값, 아니면 ''
    color_text: str     # 표에 글자로 보여 줄 원래 값(없으면 '')
    description: str    # 또는 ''
    archived: bool
    is_common: bool     # 보관 버튼을 두지 않는다
    version: str
    archive_confirm: str

@dataclass(frozen=True)
class ProjectAddValues:
    slug: str = ""
    name: str = ""
    color: str = ""

@dataclass(frozen=True)
class ProjectEditValues:
    name: str
    color: str
    description: str
    version: str

@dataclass(frozen=True)
class ProjectSectionView:
    rows: tuple[ProjectRowView, ...]  # 보관 포함, slug 순
    add_values: ProjectAddValues
    message: str = ""
    is_error: bool = False

@dataclass(frozen=True)
class SettingsInfoView:
    config_file: str   # str(Path) 그대로(Windows 역슬래시)
    db_path: str       # 실제로 연 DB(ctx.engine.url.database). cfg.db_path가 아니다(공통 규칙)
    categories: tuple[Choice, ...]  # (key, 라벨), 설정 순서
    default_project: str
    week_start: str
    daily_target: str  # format_duration
```

- **페이지 `GET /settings`:**
  - 프로젝트 구역(`#project-section`): 표와 추가 폼
  - 설정 정보 구역: 설정 파일 경로, DB 경로, 카테고리(키·라벨), 기본 프로젝트, 주 시작 요일, 하루 목표
    - 모두 읽기만 한다. 안내 문구 `CATEGORY_NOTE`를 함께 보여 준다.
    - 설정 자동 반영(Task 6-5) 덕분에 설정 파일을 고치고 새로 고치면 바뀐 값이 보인다.
- **표의 열:** slug, 이름, 색, 설명, 상태(사용 중·보관), 동작
  - 색은 견본 `<svg class="swatch" width="14" height="14" aria-hidden="true"><rect width="14" height="14" fill="{{ row.color }}"/></svg>`와 글자(`color_text`)로 보여 준다.
    - 견본은 뷰가 `#[0-9a-fA-F]{6}`로 확인한 색에만 그린다. `lb import`는 색 형식을 검사하지 않아 다른 문자열이 DB에 있을 수 있다. 그런 값은 견본 없이 글자로만 보여 준다(자동 이스케이프).
    - SVG 표시 속성(`fill`)은 CSP의 인라인 스타일이 아니다. 색이 실제로 보이는지는 메인 세션이 Edge 헤드리스로 확인한다.
  - 동작: 수정, 보관(common은 없음, 확인 창) 또는 보관 해제
  - 표는 `.table-wrap` 안에 둔다(좁은 화면에서는 표만 가로로 스크롤한다).
- **`POST /settings/projects`** (form: `slug`, `name`, `color`):
  - `create_project(s, slug.strip(), name, color=color.strip() or None)`
  - 응답은 구역(결과 줄 `PROJECT_ADDED`, 추가 폼 비움)이다. 실패하면 입력값을 유지하고 문구를 보여 준다(상태 코드는 `classify`).
  - 설명은 CLI `lb project add`처럼 추가할 때 받지 않는다. 수정에서 넣는다.
  - 색 입력은 텍스트다(placeholder `#4f46e5`). 비우면 색이 없다. 브라우저 색 선택기(`type="color"`)는 빈 값을 보낼 수 없어서 쓰지 않는다.
- **편집 행:** `GET /settings/projects/{slug}/edit` → `<tr id="project-{slug}" class="is-editing">`이다. 이름(`data-focus`), 색, 설명, 숨긴 version, 저장(`hx-patch`), 취소(`hx-get …/row`)가 있다.
- **`PATCH /settings/projects/{slug}`** (form: `name`, `color`, `description`, `version`):
  - 세션 안에서 버전을 확인하고, 바뀐 것만 `update_project`에 넘긴다.
    - 이름: `name.strip()` 비교
    - 색: 빈 값은 None
    - 설명: 공백뿐이면 None
  - 결과 줄은 `PROJECT_UPDATED`다. 바뀐 것이 없으면 `NO_CHANGE`다.
  - 오류면 편집 행을 입력값 그대로 다시 그린다. `HX-Retarget: #project-{slug}`이고, 문구는 `#flash` OOB다.
- **`POST /settings/projects/{slug}/archive`·`/unarchive`** (form: `version`):
  - 버전을 확인한 뒤 `archive_project`·`unarchive_project`를 부른다. 응답은 구역이다.
  - 보관한 프로젝트가 `cfg.default_project`면 결과 줄 끝에 `DEFAULT_ARCHIVED`를 붙인다.
  - common 보관 요청은 core 문구(400)다. 화면에는 버튼이 없다.
- **버튼과 폼의 HTMX 속성:** 추가 폼은 `hx-post="/settings/projects"`, 편집 행의 저장과 보관·해제 버튼은 각 경로로 보낸다. 모두 `hx-target="#project-section"`, `hx-swap="outerHTML"`, `hx-sync="this:drop"`, `hx-disabled-elt`를 둔다. 편집 행의 취소만 `hx-target="closest tr"`이다.
- slug는 `[a-z0-9_-]`라 id와 CSS 선택자에 그대로 쓸 수 있다. 경로의 잘못된 slug는 `get_project`의 NotFoundError(404, 알림)다.

| 상수(pages.settings) | 문구 |
|---|---|
| `PROJECT_ADDED` | `✔ 프로젝트 추가: {slug} ({name})` |
| `PROJECT_UPDATED` | `✔ 프로젝트 수정: {slug} ({name})` |
| `PROJECT_ARCHIVED` | `✔ 프로젝트 보관: {slug} (과거 기록은 집계에 계속 포함됩니다)` |
| `PROJECT_UNARCHIVED` | `✔ 프로젝트 보관 해제: {slug}` |
| `DEFAULT_ARCHIVED` | ` 보관한 프로젝트가 설정의 default_project입니다. 설정 파일의 default_project를 바꾸세요.` |
| `ARCHIVE_CONFIRM` | `보관할 프로젝트: {slug} ({name})\n보관할까요? 과거 기록은 집계에 계속 포함되고, 새 기록과 태스크는 추가할 수 없습니다.` |
| `CATEGORY_NOTE` | `카테고리와 기본값은 설정 파일에서 바꿉니다. 저장한 뒤 화면을 새로 고치면 반영됩니다.` |

**테스트 케이스**

| 대상 | 케이스 | 기대 |
|---|---|---|
| 페이지 | `GET /settings` | 200, 메뉴 `aria-current`, 표(common, payment, 보관 프로젝트), 카테고리 목록, 경로, 인라인 코드 없음 |
| 페이지 | common 행 | 보관 버튼 없음 |
| 추가 | 올바른 값 | 새 행, `PROJECT_ADDED`, 폼 비움 |
| 추가 | 중복 slug / 잘못된 slug / 색 `red` / 이름 비움 | 400 core 문구, 입력값 유지 |
| 편집 | `GET …/edit` | 입력에 현재 값, 이름에 `data-focus` |
| 편집 | 이름·색·설명 바꿈 / 색·설명 비움 | `PROJECT_UPDATED`, DB 반영 / None |
| 편집 | 바꾼 것 없음 | `NO_CHANGE` |
| 편집 | 다른 버전 | 409 `PROJECT_CHANGED`, 입력값 유지, `#flash` OOB |
| 편집 | 색 `#12` | 400, 입력값 유지 |
| 보관 | 같은 버전 | 보관됨, `PROJECT_ARCHIVED`, 확인 문구 속성 |
| 보관 | default_project를 보관 | 결과 줄에 `DEFAULT_ARCHIVED` |
| 보관 | common으로 직접 POST | 400 core 문구 |
| 보관 해제 | 같은 버전 | 사용 중으로, `PROJECT_UNARCHIVED` |
| 보관·해제 | 다른 버전 | 409 |
| 설정 반영 | watcher 앱에서 카테고리를 더한 뒤 새로 고침 | 새 카테고리 표시 |
| 설정 반영 | watcher 앱에서 `db_path`를 바꾼 뒤 새로 고침 | 화면의 DB 경로는 실제로 연 DB 그대로, 위에 재시작 알림 |
| 견본 | 가져오기로 들어간 잘못된 색(`red`) | 견본 없음, 글자 `red` |
| 보안 | 다른 출처에서 쓰기 | 403 |

- [x] RED → GREEN → 커밋 `feat: 설정 화면(프로젝트 추가·수정·보관·보관 해제, 카테고리 확인)`

---

## Task 6-11: 다크모드

**Files:**
- Modify: `src/logbook/web/static/css/app.css`, `src/logbook/web/templates/base.html`, `src/logbook/web/errors.py`(`_error_page`), `src/logbook/web/static/js/dashboard.js`
- Create: `tests/web/test_theme.py`
- Modify tests: `tests/web/test_errors.py`, `tests/web/test_dashboard.py`, `tests/web/test_static.py`(161~166행의 색 리터럴 테스트를 test_theme.py로 옮긴다)

- `:root`에 `color-scheme: light dark;`를 더해 폼 컨트롤·스크롤바도 테마를 따르게 한다.
- `@media screen and (prefers-color-scheme: dark) { :root { … } }`에 아래 색 토큰 12개를 다시 정한다. 시작 값은 아래와 같고, 대비 테스트가 통과하도록 조정할 수 있다.
  - `screen`으로 한정하므로 인쇄는 밝은 토큰을 쓴다(기존 `@media print`, 744~756행). 어두운 OS에서 인쇄해도 흰 종이에 흰 글자가 나오지 않는다.
  - 글꼴·간격 같은 색이 아닌 토큰은 다시 정하지 않는다.

| 토큰 | 밝은 테마(기존) | 어두운 테마 |
|---|---|---|
| `--bg` | `#f7f7f5` | `#0f1115` |
| `--surface` | `#ffffff` | `#171a21` |
| `--ink` | `#15171c` | `#e6e8ec` |
| `--ink-muted` | `#5a6170` | `#a1a8b5` |
| `--rule` | `#dcdfe4` | `#2c313b` |
| `--row-hover` | `#f0f1f3` | `#1f232c` |
| `--accent` | `#2448c8` | `#8aa4ff` |
| `--accent-hover` | `#1b3aa3` | `#a9bcff` |
| `--accent-ink` | `#ffffff` | `#0b1020` |
| `--ok` | `#0f7a3d` | `#4fc283` |
| `--danger` | `#b42318` | `#ff7b72` |
| `--shadow-raised` | 기존 | `0 8px 14px -10px rgba(0, 0, 0, 0.8)` |

- `base.html`과 오류 페이지에 `<meta name="color-scheme" content="light dark">`를 둔다. CSS를 읽기 전에도 바탕이 테마를 따라 깜박임이 줄어든다.
- `dashboard.js`는 `window.matchMedia("(prefers-color-scheme: dark)")`의 `change`에서 `drawCharts()`를 부른다. 글자색·격자·도넛 테두리·목표선은 그릴 때마다 CSS 변수를 다시 읽는다(기존 코드).
- 데이터 색(프로젝트 색, `CHART_PALETTE`)은 바꾸지 않는다. 어두운 바탕에서 약한 색이 있을 수 있다(후속 항목 4).
- 토큰 밖의 색 값이 Phase 5 CSS에 남아 있으면 이 Task에서 토큰으로 옮긴다.

- **테스트의 블록 찾기:** 파일 맨 앞의 첫 `:root {`부터 짝이 맞는 `}`까지가 밝은 블록이다. `@media screen and (prefers-color-scheme: dark) {` 안의 `:root {…}`가 어두운 블록이다. 중괄호 짝을 세는 작은 함수로 자른다.

**테스트 케이스(`tests/web/test_theme.py`)**

| 대상 | 케이스 | 기대 |
|---|---|---|
| 토큰 | 밝은 블록, 어두운 블록 | 위 표의 색 토큰 12개가 두 블록에 모두 있다 |
| 대비 | 두 테마의 (ink, bg), (ink, surface), (ink-muted, surface), (ink-muted, bg), (accent, surface), (accent-ink, accent), (danger, surface), (ok, surface) | WCAG 대비 4.5 이상 |
| 하드코딩 | 두 `:root` 블록을 잘라낸 나머지 | `#hex`, `rgb(`, `rgba(`, `hsl(` 없음. 기존 `test_app_css_uses_color_literals_only_in_the_token_block`(test_static.py 161~166행)은 이 테스트로 옮기고 지운다 |
| 인쇄 | 어두운 블록의 미디어 쿼리 | `screen`으로 한정 |
| `color-scheme` | `:root` | `color-scheme: light dark` |
| meta | `GET /`, 오류 페이지 | `<meta name="color-scheme" content="light dark">` |

- [x] RED → GREEN → 커밋 `feat: 다크모드(OS 설정을 따르는 색 토큰, 테마가 바뀌면 차트를 다시 그림)`

---

## Task 6-12: 문서 마무리와 Phase 6 완료

- [x] **README:**
  - 웹 대시보드: 태스크·보고서·설정 화면, 타이머 시작·취소, 다크모드(OS 설정)
  - 설정 자동 반영: 바로 반영되는 값과 다시 시작해야 하는 값
  - 업데이트 시 DB 업그레이드와 백업 파일(위치, 이름, 되돌리는 방법)
  - `lb project edit`, `lb project unarchive`
  - 내보내기 형식 2(형식 1 파일도 가져온다). 144·147행의 내보내기 대상 설명에 특이사항을 더한다.
  - 보고서 템플릿 값 `data.notes`, `data.risks`와 3절 예시. 96행의 '저장 기능은 이후 단계에서 추가합니다'를 고친다.
  - JSON API 추가(`GET /api/timer`, `POST /api/timer/cancel`)
- [x] **SPEC:**
  - 2장 데이터 모델: week_notes를 테이블 설명에 더하고, 스키마 버전 2와 마이그레이션 전 백업을 설명한다(62~63행 schema_version 절). 6장 395행의 '추가 데이터' 문장은 지우거나 2장 참조로 바꾼다.
  - 3장: 설정 자동 반영(웹)
  - 5장: `lb project edit|unarchive`. 내보내기 설명(251행: 형식 버전, 머리글 예시, 행 순서)과 성공 출력 예시(253행)를 형식 2로 고친다.
  - 6장: Phase 6 화면 동작(태스크·보고서·설정), 타이머 시작·취소, 버전 확인 대상, 정적 파일 캐시, API 추가. "Phase 6에 남은 것"은 후속 항목 목록으로 바꾼다.
  - 7장: 3절 형식(456행 문장 포함)
- [x] **ROADMAP:** Phase 6 네 항목을 `[x]`로 바꾼다.
- [x] **CLAUDE.md·AGENTS.md(같은 내용):** 디렉터리 구조에 새 모듈을 더한다(`core/services/week_notes.py`, `web/config_watch.py`, `web/reporting.py`, `web/pages/tasks.py`·`task_views.py`·`report.py`·`settings.py`, `static/js/report.js`). 허용 core 진입점은 바뀌지 않는다.
- [x] **자동 확인(이 PC, 임시 `LOGBOOK_DB`·`LOGBOOK_CONFIG`):**
  - v1 DB(develop `44ddf9f`로 만든 임시 DB 복사본)에서 `lb log`를 실행한다. 업그레이드 알림이 나오고, 백업 파일이 생기고, 데이터가 그대로인지 본다.
  - `lb project edit`·`unarchive`, `lb export`(형식 2), 그 파일을 새 DB에 `lb import`
- [x] **화면 확인(메인 세션, Edge 헤드리스, `ui-visual-verification` 기준):**
  - 다섯 화면(`/`, `/logs`, `/tasks`, `/report`, `/settings`) × 밝은·어두운 테마 × 1280px·375px 스크린샷을 찍는다. 320px도 한 장씩 찍어 머리 메뉴 줄바꿈과 태스크·설정 표를 본다. 어두운 테마는 `--force-dark-mode` 또는 `--blink-settings=preferredColorScheme=0`으로 켜고, 둘 중 동작하는 것을 기록한다.
  - 카드 수정·상태 변경·이월, 특이사항 저장 흐름에서 결과 줄·오류 알림이 보이는 자리(뷰포트·가로 스크롤 안)에 있는지 잰다.
  - 프로젝트 색 견본이 보이는지 본다.
- [ ] **브라우저 확인(사용자, Windows·macOS, 절차는 PR 댓글):** Windows는 2026-10-14에 전 항목 확인했다. macOS는 병합 뒤 사용자가 따로 확인한다.
  - 칸반: 상태 변경, 카드 수정(Enter·Esc, 한글 조합), 이월
  - 보고서: 복사(실제 클립보드), 내려받기, 특이사항(한글 조합)
  - 설정: 프로젝트 추가·수정·보관·보관 해제
  - 타이머: 시작·취소
  - 설정 파일을 고친 뒤 새로 고침
  - OS 다크 모드 전환(차트 포함)
  - 절차서 규칙([[manual-check-procedures]])을 지킨다: 새 터미널마다 임시 DB 환경변수, 동작이 일어나는 순서, 행은 ID로 가리킨다. 이번 Task부터 정적 파일은 no-cache라 Ctrl+F5 안내가 필요 없다.
  - 업그레이드 시험은 임시 DB 복사본으로 한다. 실제 DB는 사용자가 원할 때 업그레이드하고, 그때 백업 위치를 안내한다.
- [x] **전체 검증:** `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy src/logbook/core`, `uv run mypy src/logbook`, `uv run pytest`(커버리지: 전체, core·web 100% 유지), GitHub Actions `windows-latest`·`macos-latest`
- [x] **PR:** develop 대상, `Closes #13` (#14)

---

## 크로스 플랫폼 체크리스트 (Phase 6 추가분)

- 백업 파일 이름에 Windows 금지 문자가 없다(`logbook.db.v1-20261013-153000.bak`). 시각 형식은 `%Y%m%d-%H%M%S`이고 `%-d` 같은 Unix 전용 형식을 쓰지 않는다.
- sqlite3 백업에 쓰는 연결 두 개를 모두 닫는다. 안 닫으면 Windows에서 백업 파일이나 임시 폴더를 지우지 못한다.
- 백업이 실패하면 만들다 만 파일을 지운다.
- `textarea`는 줄바꿈을 CRLF로 보낸다(HTML 규격). 저장할 때 LF로 바꾼다.
- 다운로드 파일 이름은 ASCII이고, 내용은 UTF-8·LF다.
- 설정 파일 변경은 파일 내용의 해시로 감지한다. 파일 시스템마다 다른 수정 시각 정밀도에 기대지 않는다.
- 어두운 테마는 `screen`에만 적용한다. 인쇄는 OS 테마와 상관없이 밝은 토큰이다.
- 경로 표시(설정 화면)는 `str(Path)` 그대로다(Windows는 역슬래시).
- 복사는 Clipboard API가 기본이다. 127.0.0.1·localhost는 보안 컨텍스트다. 실패하면 선택 후 `execCommand("copy")`로 대신한다.

---

## 설계 결정 요약 (기술 결정, 계획 승인 시 함께 확정)

1. **week_notes 키:** SPEC대로 `week`(PK, `Week.label`)다. 두 칸이 모두 비면 행을 지운다. 그러면 "행이 있다 = 쓴 내용이 있다"가 된다.
2. **마이그레이션 DDL 고정:** 모델이 나중에 바뀌어도 v2 단계는 그대로다. 올린 DB와 새로 만든 DB의 테이블 구조가 같은지 테스트로 지킨다.
3. **백업 시점:** 쓰기 잠금 안에서 버전을 다시 읽은 뒤, 첫 단계 직전에 한 번만 한다. sqlite3 백업 API를 쓰므로 일관된 사본이 나온다. 백업이 실패하면 마이그레이션도 하지 않는다. 오래된 백업은 자동으로 지우지 않는다(후속 항목 12).
4. **업그레이드 알림:** core는 출력하지 않는다. `open_database(on_upgrade=…)` 콜백으로 넘기고, CLI·서버가 stderr에 쓴다.
5. **보고서 3절:** `### 특이사항`·`### 리스크`이고, 빈 칸은 뺀다. 둘 다 비면 `(작성하세요)`다. `ReportData`의 새 필드에는 기본값이 있어 사용자 템플릿과 기존 코드가 깨지지 않는다.
6. **내보내기 형식 2:** 행 키를 일반화한다(`KEY_FIELDS`). 형식 1 파일도 계속 가져온다.
7. **설정 자동 반영:** 요청별 스냅숏으로 반영한다. 변경은 파일 내용 해시로 감지한다. 읽기에 실패하면 직전 설정으로 동작하고, DB·주소·포트는 다시 시작해야 한다. 화면의 DB 경로는 실제로 연 DB다.
8. **정적 파일 캐시:** 게이트에서는 `?v=버전`을 말했지만 `Cache-Control: no-cache` + ETag(304)로 바꿨다. 서버를 띄운 채 CSS를 고쳐도 새로 고침만으로 반영되고, 코드가 단순하다.
9. **버전 확인 확대:** 태스크, 특이사항, 프로젝트, 타이머 취소에 409를 둔다. `content_version`을 함께 쓴다. 타이머 정지는 Phase 5처럼 버전을 보지 않는다.
10. **다음 주 계획 패널:** 보고서 4절과 같은 함수(`next_week_plan`)를 써서 두 화면이 같은 내용을 보인다.
11. **칸반:** 완료 열은 이번 주에 완료한 것만이다. 중단한 태스크는 보이지 않고, 상태는 버튼으로 바꾼다(끌어 놓기는 키보드로 쓸 수 없다).
    - 완료 열은 보관 프로젝트를 빼고(list_tasks와 같다), 보고서 1절의 완료 태스크 수는 보관 프로젝트를 포함한다(Phase 4 규칙). 그래서 두 수가 다를 수 있다.
12. **프로젝트 추가 폼:** CLI `lb project add`와 같은 항목(slug·이름·색)이다. 설명은 수정에서 넣는다. 색 입력은 텍스트다(비우면 색 없음).
13. **다크모드:** 토큰만 바꾼다. 대비 테스트와 색 값 하드코딩 금지 테스트로 지킨다.
14. **화면 상태 이름:** 한국어(할 일·진행·완료·중단, 보고서와 같다)다. CLI 출력은 그대로다.
15. **새 의존성 없음.** 스키마 변경은 week_notes 하나다.

## 사용자 결정 (2026-10-13 승인 게이트에서 확정)

- **P1. 범위:** SPEC 6장 "Phase 6에 남은 것" 전부다. 추천안(ROADMAP 4항목 + 캐시)보다 넓다.
  - ROADMAP 4항목: 태스크, week_notes와 보고서, 설정, 다크모드
  - 웹 타이머 시작·취소(API 상태·취소 포함)
  - 설정 자동 반영
  - 정적 파일 캐시 무효화
- **P2. 태스크 화면:** 상태 버튼, 추가 폼, 계획 패널의 이월에 더해 카드 인라인 수정(제목·예상·주차·카테고리)까지 한다. 수정에는 버전 확인(409)을 붙인다. 추천안보다 넓다.
- **P3. 특이사항:** 특이사항·리스크 두 칸(SPEC 테이블 그대로)이다. 입력은 `/report` 화면에서만 하고, `lb report` 출력에도 반영한다(추천안).
- **P4. CLI 짝:** 프로젝트 이름·색·설명 수정과 보관 해제를 core 서비스로 만들고, CLI `lb project edit`·`unarchive`와 웹에 함께 넣는다(추천안).

게이트 전에 알린 기본 결정(이의 없음):
- 다크모드는 OS·브라우저 설정을 따르고 토글은 없다.
- 보고서 미리보기는 Markdown 원문이다. HTML 렌더링은 새 의존성이 필요하다.
- 새 의존성은 없고, 오류 문구는 core 문구를 그대로 쓴다.
- 첫 실제 마이그레이션 전에 DB를 자동 백업한다. 내보내기는 형식 2이고, 가져오기는 형식 1도 받는다.

2026-10-13 설계 요약 승인: 게이트 뒤 보여 준 설계 요약(화면별 동작, 설정 자동 반영 방식, 정적 파일 캐시 방식 변경, 진행 방식)을 사용자가 승인했다.

2026-10-13 이슈 게이트(모두 추천안):
- 이슈 #13을 만들었다.
- 구현은 서브에이전트 방식이다.
  - Task마다 구현 1명과 통합 검토 1명(명세·품질을 함께 본다)을 두고, 끝에 최종 리뷰 1명을 둔다.
  - 약 24개다. 검토에서 고칠 것이 나오면 그만큼 늘어난다.
- 모두 Sonnet이고 effort는 medium이다. 6-1(마이그레이션·백업)·6-7(칸반) 구현과 최종 리뷰만 high다.

## 계획 검토 (2026-10-13)

- 리뷰어 2명(core·CLI, 웹)과 검증 1명(fact-verifier)이 검토했다. 모두 Sonnet/medium이다.
- 지적 28건을 26묶음으로 정리했고, 모두 맞거나 일부 맞다는 판정이라 전부 반영했다(major 8묶음, minor 18묶음, critical 없음).
- 검토로 바뀐 설계
  - 설정 변경 감지를 수정 시각·크기에서 파일 내용 해시로 바꿨다. 같은 크기로 값만 바꾼 경우도 잡는다.
  - 어두운 테마는 화면(`screen`)에만 적용한다. 어두운 OS에서 인쇄해도 밝은 토큰을 쓴다.
  - 설정 화면의 DB 경로는 실제로 연 DB에서 읽는다.
  - 프로젝트 색 견본은 형식을 확인한 색에만 그린다(가져오기는 색 형식을 검사하지 않는다).
  - 이월이 0건이면 성공 줄 대신 409로 알리고 패널을 지금 상태로 다시 그린다(화면을 연 채 주가 바뀐 경우 등).
  - 태스크 필터를 바꾸면 계획 패널도 같은 필터로 바뀐다.
- 나머지는 실제 코드에 맞춘 보완이다.
  - 바뀌어야 하는 기존 테스트의 파일·행
  - 가져오기 코드의 id·형식 1 전제
  - CLI 기호(`info_mark`·`arrow`)와 `CONFLICT_MESSAGE` 공용화
  - 버튼의 `hx-swap`, ruff B008, `get_context`의 최소 앱 호환
  - 문서 갱신 위치

## 구현 기록 (2026-10-13)

- 진행
  - Task마다 구현 1명과 통합 검토 1명을 두었고, 모두 Sonnet이다. 6-1~6-11은 모두 첫 검토에서 통과해 수정·재검토가 없었다.
  - 이어서 정리 1명, 문서 1명, 최종 리뷰 1명, 최종 리뷰 수정 1명을 두었다. 모두 합쳐 에이전트 26명이다.
  - 최종 리뷰는 critical·major 없이 minor 12건이었다.
- 계획과 달라진 것
  - **스타일 파일**
    - `app.css`(1266줄)를 순서와 내용을 그대로 둔 채 8개 파일로 나눴다: app, dashboard, logs, components, tasks, report, settings, responsive.
    - 목록은 `web/assets.py`의 `STYLESHEETS` 한 곳에 있고, `base.html`과 오류 페이지가 같이 쓴다.
    - 색 리터럴 금지 검사는 모든 CSS 파일을 본다.
  - **색 형식 검사:** core에 `services.is_valid_color`를 공개했고, 웹 색 견본이 이것을 쓴다.
  - **옵션 충돌 문구:** "{} 옵션과 {} 옵션은 함께 쓸 수 없습니다. 하나만 지정하세요."로 바꿨다. 예전 문구는 `--description`에서 조사가 틀렸다.
  - **가져오기:** week_notes에서 두 칸이 모두 빈 행과 정리되지 않은 값(CRLF, 앞뒤 공백)을 거부한다.
  - **마이그레이션 테스트:** v1 DB는 develop `44ddf9f`로 만든 DDL을 고정해 쓴다(`tests/helpers.py`의 `V1_DDL`).
  - **기존 버그 수정:** UTC보다 앞선 시간대에서 `0001-W01` 보고서가 OverflowError로 끝났다. 완료 범위의 하한을 UTC 최솟값으로 맞춰 고쳤다.
- 화면 확인(Edge 헤드리스)
  - 어두운 테마는 `--blink-settings=preferredColorScheme=0`으로 켰다.
  - Edge 헤드리스 창은 500px 아래로 줄지 않고, 배율 플래그도 CSS 폭을 바꾸지 않는다.
    - 그래서 320·375px는 같은 화면을 세로 구간별 iframe으로 나란히 놓고 쟀다.
    - iframe을 쓰려고 확인 스크립트 안에서만 `frame-ancestors`를 풀었다.
  - 다음 문제를 찾아 927aaf0에서 고쳤다.
    - 320px에서 주 이동 줄과 대시보드 요일 차트가 가로로 넘쳤다.
    - 계획 패널에 안쪽 여백이 없었다.
    - 편집 카드의 입력 칸이 꾸밈 없는 기본 모양이었다.
- 자동 확인(이 PC): v1 DB 업그레이드를 확인했다. 안내가 한 번 나오고, `.v1-…bak`이 생기고, 데이터가 그대로다. `lb project edit`·`unarchive`, 형식 2 내보내기와 가져오기도 확인했다.

## 후속 항목 (Phase 6 범위 밖, 기록만)

1. **웹 전용 오류 문구:** core 문구의 CLI 안내가 웹에도 보인다(Phase 5 후속 1). 예: 타이머 시작 실패의 `'lb stop'으로 저장하거나`
2. **브라우저 E2E:** 새 dev 의존성이 필요하다(Phase 5 후속 2).
3. **버전 확인과 변경 사이의 경쟁 구간:** 이제 태스크·프로젝트·특이사항·타이머 취소에도 해당한다(Phase 5 후속 8).
4. **차트 팔레트:** 프로젝트·카테고리 구분(Phase 5 후속 10)과 어두운 바탕에서의 대비. `CHART_PALETTE`는 흰 바탕 기준이고, 마지막 회색이 어두운 바탕에서 약하다.
5. **타이머 정지의 버전 확인**
6. **태스크 화면 확장:** 끌어 놓기, 설명·마감일·외부 참조 수정, 중단 태스크 보기·복원
7. **웹에서 설정 파일 편집:** 지금은 읽기만 한다.
8. **특이사항 CLI 입력**(`lb report note`, P3에서 고르지 않은 안)
9. **다크모드 수동 토글**(게이트 전 기본 결정)
10. **Phase 4 후속 항목:** 그대로 유지한다(git-collect, LLM, 가져오기 병합, DST, 템플릿 샌드박스, 오프라인 휠 테스트).
11. **LAN 공개:** 비목표다(SPEC 1).
12. **오래된 마이그레이션 백업 정리:** 자동으로 지우지 않는다. 필요하면 정리 명령이나 안내를 더한다.
13. **마지막 주의 보고서:** `9999-W51` 보고서는 다음 주(`9999-W52`)가 지원 범위 밖이라 400이다. 마지막 주에서는 4절을 비우는 방법이 있다.
14. **스타일 파일의 공용 규칙:** 다른 화면도 쓰는 공용 규칙이 화면 이름의 파일에 들어 있다.
    - 표와 구역(`.panel`)은 dashboard.css에 있다.
    - 필터, 주 이동, 편집 행, 작은 버튼은 logs.css에 있다.
    - 공용 파일로 옮기면 캐스케이드 순서가 바뀌므로 화면 확인과 함께 한다.
