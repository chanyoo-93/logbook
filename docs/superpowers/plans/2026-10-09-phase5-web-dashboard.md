# Phase 5 구현 계획 (웹 대시보드 — 기본)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 다음을 구현한다.
- `lb serve`로 여는 로컬 웹 대시보드: 대시보드(`/`), 기록(`/logs`)
- SPEC 6장의 JSON API 전부: `/api/logs`, `/api/tasks`, `/api/stats`, `/api/report`, `/api/timer/*` (결정 W2)

**Architecture:**
- **계층:** web(`logbook.web`)은 CLI처럼 `core.services`와 허용된 core 진입점만 쓴다. web은 `logbook.cli`를 import하지 않는다. CLI는 `lb serve` 명령 함수 안에서만 `logbook.web.server`를 import한다(FastAPI·uvicorn 지연 로드).
- **화면:** 서버 렌더링(Jinja2)과 HTMX를 쓴다. 화면 라우트가 서비스를 직접 불러 HTML 전체나 조각을 돌려준다. JSON API는 연동·테스트용으로 따로 있고, 화면은 API를 부르지 않는다.
- **서버:** `lb serve`가 설정과 DB를 먼저 확인하고 127.0.0.1에 소켓을 연 뒤 uvicorn에 넘긴다. 포트·DB 오류를 uvicorn의 영어 로그가 아니라 한국어 한 줄로 알리려는 것이다.
- **보안:** 인증이 없는 로컬 서버다. 다른 웹사이트가 사용자의 브라우저를 통해 기록을 읽거나 바꾸지 못하게 다음 세 가지를 미들웨어로 건다.
  - Host 헤더 검사(DNS 리바인딩 방어)
  - 교차 출처 쓰기 차단(CSRF 방어)
  - CSP 헤더
- **정적 파일:** htmx와 Chart.js는 패키지 안에 넣는다(결정 W3). 인터넷 없이 동작하고 CSP를 `'self'`로 좁힐 수 있다.
- **스키마:** 바뀌지 않는다. week_notes는 Phase 6에서 다룬다.

**Tech Stack:**
- 기존: Python 3.11+(CI 3.12), uv, Typer, Rich, SQLAlchemy 2.1, Jinja2 3.1
- 새 런타임 의존성(결정 W1): FastAPI 0.143, uvicorn 0.54, python-multipart 0.0.32. Starlette 1.7, pydantic 2.14 등은 전이 의존성이다.
- 새 dev 의존성: httpx2 2.13. FastAPI `TestClient`(Starlette 1.7)는 httpx2를 먼저 찾고, httpx를 쓰면 deprecation 경고를 낸다(W1 보완, 2026-10-09 이슈 게이트에서 확정).
- 정적 파일: htmx 2.0.11(0BSD), Chart.js 4.5.1(MIT)
- 테스트·검사: pytest, ruff, mypy(strict는 core만)

**선행 조건:**
- **브랜치:** `feat/phase5-web-dashboard`(develop `66c1be7`에서 분기, 이미 만들어 둠)
- **uv PATH:** 이 PC에서는 uv가 PATH에 없다.
  - Git Bash: `export PATH="/c/Users/User/AppData/Local/Microsoft/WinGet/Packages/astral-sh.uv_Microsoft.Winget.Source_8wekyb3d8bbwe:$PATH"`
  - PowerShell: `$env:Path = "$env:LOCALAPPDATA\Microsoft\WinGet\Packages\astral-sh.uv_Microsoft.Winget.Source_8wekyb3d8bbwe;$env:Path"`
- **사용자 결정:** 문서 끝의 W1~W4는 2026-10-09 승인 게이트에서 확정했다(모두 추천안).
- **Task 공통 완료 조건:** 아래 명령을 모두 통과한 뒤 커밋한다.
  - `uv run ruff check .`
  - `uv run ruff format --check .`
  - `uv run mypy src/logbook/core`
  - `uv run pytest`
- **커밋 메시지:** Conventional Commits 형식이다. type만 영어이고 설명은 한국어로 쓴다.
- **TDD:** 각 Task는 실패하는 테스트를 먼저 쓰고(RED), 최소 구현으로 통과시킨 뒤(GREEN), 정리한다.
- **사용자 문구 규칙(Phase 3에서 정함):**
  - 변수 값 바로 뒤에 조사를 붙이지 않는다. 예: `포트를 열 수 없습니다: 8765 (…)`처럼 쓴다.
  - core 문구에는 `—` 같은 기호를 넣지 않는다. 웹 화면 문구는 브라우저가 유니코드를 그리므로 `✔`·`—`를 그대로 쓴다.
  - 식별자(테스트 함수 이름 포함)는 영어다.
- **서브에이전트 실행 규칙(Phase 4에서 이어짐):**
  - 삭제 명령(rm, Remove-Item, rmdir, git clean)을 쓰지 않는다. 임시 파일은 매번 새 임시 폴더를 만들어 쓰고, 정리가 필요하면 보고만 한다.
  - 다른 프로세스를 강제로 끝내지 않는다(taskkill, Stop-Process, kill). 테스트 코드가 자기가 띄운 서버나 자식 프로세스를 끄는 것은 괜찮다.
  - 실제 `~/.logbook`, 실제 클립보드, 실제 브라우저를 쓰지 않는다. 테스트는 `webbrowser.open`을 monkeypatch한다.
  - `lb serve`를 터미널에서 직접 띄우지 않는다(끝나지 않는다). 서버 동작은 테스트 안의 스레드 서버와 서브프로세스 테스트로 확인한다.

---

## 파일 구조

| 파일 | 구분 | 책임 |
|---|---|---|
| `src/logbook/core/ids.py` | 생성 | `MAX_ID`, `parse_id()`(cli/runtime에서 옮김), `check_id()`(JSON 정수 ID) |
| `src/logbook/core/weeks.py` | 수정 | `clock_label()`, `total_label()`, `full_day()`(cli/render에서 옮김. CLI와 웹이 같은 표기를 쓴다) |
| `src/logbook/core/config.py` | 수정 | `[web].host`는 `127.0.0.1`·`localhost`만 받는다 |
| `src/logbook/core/services/tasks.py` | 수정 | `count_done_tasks()`(services/report.py에서 옮김) |
| `src/logbook/core/services/stats.py` | 수정 | `DailyProjectResult`, `daily_project_minutes()`(요일 x 프로젝트) |
| `src/logbook/core/services/worklogs.py` | 수정 | `recent_worklogs()` |
| `src/logbook/core/services/report.py`, `services/__init__.py` | 수정 | 옮긴 함수 사용, 새 함수 공개 |
| `src/logbook/cli/runtime.py` | 수정 | `parse_id`·`MAX_ID`는 core.ids 재노출, `parse_port()`, `MAX_PORT` |
| `src/logbook/cli/render.py` | 수정 | `clock_label`·`total_label`·`full_day`는 core.weeks 재노출 |
| `src/logbook/cli/commands/serve.py` | 생성 | `lb serve [--port] [--open]` |
| `src/logbook/cli/main.py` | 수정 | serve 등록 |
| `src/logbook/web/__init__.py` | 생성 | 문서 문자열만(import 없음) |
| `src/logbook/web/context.py` | 생성 | `WebContext`(설정·엔진·설정 파일 경로·시계), `get_context()` |
| `src/logbook/web/security.py` | 생성 | `LocalOnlyMiddleware`(Host 검사, 교차 출처 쓰기 차단, 보안 헤더) |
| `src/logbook/web/errors.py` | 생성 | 오류 분류(상태 코드·code), API·HTMX·페이지별 오류 응답, 예외 처리기 등록 |
| `src/logbook/web/app.py` | 생성 | `create_app(ctx) -> FastAPI` |
| `src/logbook/web/server.py` | 생성 | `open_listen_socket()`, `build_server()`, `serve()` |
| `src/logbook/web/api/__init__.py` | 생성 | API 라우터 묶음(`/api`) |
| `src/logbook/web/api/envelope.py` | 생성 | 응답 봉투 `ok()`, `fail()` |
| `src/logbook/web/api/schemas.py` | 생성 | 요청 본문 모델(pydantic), 공통 입력 도우미 |
| `src/logbook/web/api/serialize.py` | 생성 | ORM·결과 객체를 JSON용 dict로 바꾼다 |
| `src/logbook/web/api/logs.py`, `tasks.py`, `stats.py`, `report.py`, `timer.py` | 생성 | API 엔드포인트 |
| `src/logbook/web/pages/__init__.py` | 생성 | 화면 라우터 묶음 |
| `src/logbook/web/pages/templating.py` | 생성 | Jinja2 환경(자동 이스케이프, StrictUndefined), `render()`, `is_htmx()` |
| `src/logbook/web/pages/views.py` | 생성 | 행·타이머·기록 문구·폼 선택지 뷰 데이터, `worklog_version()`, `record_text()` |
| `src/logbook/web/pages/summary.py` | 생성 | 대시보드 요약 숫자와 차트 데이터(`build_summary`, `project_colors`) |
| `src/logbook/web/pages/dashboard.py` | 생성 | `GET /`, `POST /logs`(빠른 기록) |
| `src/logbook/web/pages/timer.py` | 생성 | `GET /timer`, `POST /timer/stop` |
| `src/logbook/web/pages/logs.py` | 생성 | `GET /logs`, 행 조각, 인라인 수정·삭제 |
| `src/logbook/web/templates/*.html`, `templates/partials/*.html` | 생성 | 레이아웃과 조각 |
| `src/logbook/web/static/css/app.css` | 생성 | 디자인 토큰과 레이아웃 |
| `src/logbook/web/static/js/app.js`, `js/dashboard.js` | 생성 | 이벤트 위임(포커스, 연결 오류 알림), 차트 그리기 |
| `src/logbook/web/static/vendor/` | 생성 | `htmx-2.0.11.min.js`, `chart-4.5.1.umd.min.js`, 각 라이선스, `README.md`(출처·버전·sha256) |
| `tests/core/test_ids.py` 외 core 테스트 | 생성·수정 | core 추가분 |
| `tests/web/` | 생성 | `conftest.py`, `helpers.py`(HTML 파서 도우미, 데이터 준비), API·화면·보안·서버·계층 테스트 |
| `tests/cli/test_serve.py` | 생성 | `lb serve` |
| `tests/cli/helpers.py`, `tests/cli/test_entry.py` | 수정 | 가드 목록·케이스 추가 |
| `tests/core/test_report_render.py` | 수정 | 휠 포함 테스트에 web 파일 추가 |
| `pyproject.toml`, `uv.lock` | 수정 | 의존성 |
| `README.md`, `docs/SPEC.md`, `docs/ROADMAP.md`, `CLAUDE.md`, `AGENTS.md` | 수정 | 사용법, 명세, 체크박스, 구조·허용 목록 |

---

## Phase 5 공통 규칙

### 계층
- web은 `logbook.cli`를 import하지 않는다(`tests/web/test_layering.py`가 새 인터프리터로 확인한다).
- web은 SQL·ORM 쿼리를 쓰지 않는다. sqlalchemy는 `if TYPE_CHECKING:` 안에서 타입으로만 import한다(같은 테스트가 AST로 확인한다). 허용 core 진입점은 CLI와 같고 `core.ids`가 더해진다.
- 서비스가 돌려준 ORM 객체는 세션 안에서 뷰 데이터나 JSON용 dict로 바꾼다. 템플릿 렌더링과 응답 생성은 세션을 닫은 뒤에 한다(닫힌 세션의 지연 로드 금지).

### 요청 처리
- 엔드포인트는 모두 동기 `def`다. FastAPI가 스레드 풀에서 실행하므로 SQLite 호출이 이벤트 루프를 막지 않는다. SQLAlchemy는 파일 DB에 QueuePool과 `check_same_thread=False`를 기본으로 쓰므로 엔진 하나를 스레드끼리 나눠 써도 된다.
- DB 세션은 핸들러 본문에서 `with ctx.session() as s:`로 연다(`core.db.session_scope`). yield 의존성으로 세션을 열지 않는다. 커밋이 응답 전에 끝나야 커밋 오류(잠금 등)가 그 응답에 반영된다.
- 시각: `ctx.now()`는 시간대가 붙은 지금 시각이다(기본 `datetime.now().astimezone()`). `ctx.today()`는 `ctx.now().date()`다. 테스트는 고정 시계를 넣는다. core는 시각을 직접 만들지 않는다(Phase 3 규칙).
- 주차·날짜 해석은 CLI와 같다: `parse_week(text, today=ctx.today(), week_start=cfg.week_start)`, `parse_date(...)`.
- 설정은 `lb serve`를 시작할 때 한 번 읽는다. 바꾸면 서버를 다시 시작한다(README에 적는다).

### 보안 (로컬 전용, 인증 없음)
1. **바인딩:** 항상 `127.0.0.1`에 연다. 설정 `[web].host`는 `127.0.0.1`과 `localhost`만 받고(Task 5-1), 화면에 보여 줄 주소(`http://{host}:{port}`)에만 쓴다.
2. **Host 검사:** Host 헤더의 호스트 이름(포트 제외, 소문자 비교)이 `127.0.0.1`이나 `localhost`가 아니면 403이다. Host 헤더가 없어도 403이다. 공격자가 자기 도메인을 127.0.0.1로 바꿔 응답을 읽는 DNS 리바인딩을 막는다.
3. **교차 출처 쓰기 차단:** GET·HEAD·OPTIONS가 아닌 요청은 Go 1.25 `net/http.CrossOriginProtection`과 같은 규칙으로 판정한다.
   - `Sec-Fetch-Site`가 있으면 `same-origin`이나 `none`일 때만 허용한다.
   - 없고 `Origin`이 있으면, Origin의 `host:port`가 Host 헤더와 같을 때만 허용한다(`Origin: null`은 거부).
   - 둘 다 없으면 허용한다. 브라우저가 아닌 클라이언트(curl, 스크립트)라서 CSRF 대상이 아니다.
4. **보안 헤더(모든 응답):**
   - `Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; font-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'`
   - `X-Content-Type-Options: nosniff`
   - `X-Frame-Options: DENY`
   - `Referrer-Policy: same-origin`
   - `/static/`이 아닌 응답에는 `Cache-Control: no-store`도 붙인다.
   - 500 응답은 Starlette의 `ServerErrorMiddleware`가 보낸다. 이 미들웨어는 사용자 미들웨어보다 바깥에 있어 500 응답이 `LocalOnlyMiddleware`를 지나지 않는다. 그래서 헤더 목록을 `security.security_headers(path)`로 두고, 미들웨어와 500 처리기가 함께 쓴다.
5. **API 문서 끔:** `FastAPI(docs_url=None, redoc_url=None, openapi_url=None)`. Swagger UI는 CDN 스크립트를 불러 CSP와 어긋나고, 오프라인에서 동작하지 않는다.
6. **템플릿:** `jinja2.Environment(autoescape=True, undefined=StrictUndefined)`다. `|safe`와 `Markup()`을 쓰지 않는다.
   - 차트 데이터는 작은따옴표 속성 `data-chart='{{ chart|tojson }}'`에 넣는다. Jinja `tojson`은 `<`·`>`·`&`·`'`를 이스케이프하므로 작은따옴표 속성에서 안전하다(큰따옴표 속성에는 쓰지 않는다).
   - `<script type="application/json">`은 쓰지 않는다. htmx는 `allowScriptTags: false`면 교체되는 조각의 `<script>`를 종류와 상관없이 지운다(htmx 2.0.11 `normalizeScriptTags`). 그러면 OOB로 바뀐 요약에서 차트 데이터가 사라진다.
   - 템플릿 파일 이름은 `.html`이다. Starlette 기본 환경의 `select_autoescape()`는 `.j2`를 이스케이프하지 않으므로 기본 환경을 쓰지 않는다.
7. **인라인 코드 금지(CSP):** 템플릿에 `<script>` 본문, `on…=` 속성, `hx-on`, `style=` 속성, `<style>`을 쓰지 않는다. 동작은 `static/js/*.js`가 이벤트 위임으로 붙인다(`tests/web/test_dashboard.py`가 렌더링 결과를 검사한다).

### JSON API 공통
- **응답 봉투:**
  - 성공: `{"ok": true, "data": …, "error": null}`. 목록은 `"meta"`를 더한다.
  - 실패: `{"ok": false, "data": null, "error": {"code": "…", "message": "…"}}`
  - 한글은 이스케이프하지 않는다(Starlette `JSONResponse`가 `ensure_ascii=False`).
- **상태 코드와 code:**

| 상황 | HTTP | code |
|---|---|---|
| `InvalidInputError`, 요청 본문·값 검증 실패 | 400 | `invalid_input` |
| 그 밖의 `LogbookError`(읽기 전용 DB 등) | 400 | `error` |
| `NotFoundError`, 없는 경로 | 404 | `not_found` |
| Host 거부, 교차 출처 쓰기 거부 | 403 | `forbidden` |
| 허용하지 않는 메서드 | 405 | `method_not_allowed` |
| 화면의 기록이 그사이 바뀜(`web.errors.ConflictError`, 화면 전용) | 409 | `conflict` |
| `DatabaseBusyError` | 503 | `busy` |
| `DatabaseNotInitializedError` | 503 | `not_initialized` |
| 예상하지 못한 예외 | 500 | `internal` |

- **직렬화:**
  - 날짜는 `YYYY-MM-DD`, 시각은 UTC ISO 8601(`2026-10-01T00:30:00+00:00`, 백업과 같은 `isoformat()`)이다.
  - 시간은 정수 분(`minutes`)과 표기(`duration`, `format_duration`)를 함께 준다.
  - 상태는 key(`todo` 등), 프로젝트는 slug, 카테고리는 key다.
- **요청 본문:** JSON 객체만 받는다. pydantic 모델은 `ConfigDict(extra="forbid", strict=True)`다. 문자열 필드에 숫자, 정수 필드에 `"42"`를 주면 거부한다.
- **쿼리 값:** 모두 문자열로 받아 core 파서로 검증한다(오류 문구를 한국어로 맞추려는 것이다). 빈 문자열과 공백뿐인 값은 생략한 것으로 본다.
- **웹 문구(상수로 둔다):**

| 상수(모듈) | 문구 |
|---|---|
| `HOST_REJECTED`(security) | `허용되지 않은 Host 헤더입니다: '{host}'. http://127.0.0.1 또는 http://localhost 주소로 여세요.` (`{host}`는 `echo_input`으로 40자 제한) |
| `CROSS_SITE_REJECTED`(security) | `다른 사이트에서 보낸 변경 요청은 받지 않습니다. logbook 화면에서 다시 시도하세요.` |
| `API_NOT_FOUND`(errors) | `요청한 API가 없습니다: {method} {path}` |
| `PAGE_NOT_FOUND`(errors) | `페이지를 찾을 수 없습니다: {path}` |
| `METHOD_NOT_ALLOWED`(errors) | `이 주소는 {method} 요청을 받지 않습니다: {path}` |
| `BODY_FIELD_INVALID`(errors) | `요청 본문이 올바르지 않습니다: '{field}' ({reason}).` |
| `BODY_NOT_JSON`(errors) | `요청 본문을 JSON으로 읽을 수 없습니다. UTF-8로 인코딩한 JSON 객체를 보내세요.` |
| `BODY_NOT_OBJECT`(errors) | `요청 본문은 JSON 객체여야 합니다. Content-Type: application/json으로 보내세요.` |
| `RECORD_CHANGED`(errors) | `다른 곳에서 기록이 바뀌었습니다: #{id}. 목록을 새로 고친 뒤 다시 시도하세요.` |
| `VALUE_INVALID`(errors) | `요청 값이 올바르지 않습니다: '{field}' ({reason}).` (쿼리·경로) |
| `INTERNAL_ERROR`(errors) | `서버 내부 오류가 발생했습니다. lb serve를 실행한 터미널에서 오류 내용을 확인하세요.` |
| `NOT_NULLABLE`(api/schemas) | `'{field}' 값은 비울 수 없습니다.` |

- **검증 오류 문구:** 오류가 여럿이면 첫 번째 하나만 쓴다(CLI의 한 줄 오류와 같다). 아래 순서로 판정한다.
  1. type이 `json_invalid`면 `BODY_NOT_JSON`(`Content-Type: application/json`인 깨진 JSON. loc는 `("body", 위치)`)
  2. loc가 `("body",)`뿐이면 `BODY_NOT_OBJECT`(본문이 없음, 배열 본문, JSON이 아닌 Content-Type이면 type이 `missing`·`model_attributes_type`)
  3. 그 밖은 `{field}`와 `{reason}`으로 쓴다.
     - `{field}`: loc에서 첫 요소(`body`·`query`·`path`)를 뺀 나머지를 `str()`로 바꿔 `.`으로 잇는다(목록 위치는 정수다).
     - `{reason}`(type → 문구): `missing` → `필수 항목입니다`, `extra_forbidden` → `알 수 없는 항목입니다`, `string_type` → `문자열이어야 합니다`, `int_type` → `정수여야 합니다`, 그 밖 → `값이 올바르지 않습니다`
- **본문 해석 실패:** FastAPI는 UTF-8이 아닌 본문 같은 해석 실패를 `HTTPException(400, "There was an error parsing the body")`로 낸다. 400 HTTP 예외는 `invalid_input`과 `BODY_NOT_JSON`으로 바꾼다(우리 코드는 HTTPException을 던지지 않는다).

### 화면(HTMX) 공통
- `base.html`의 htmx 설정 meta(값 그대로):
  `{"includeIndicatorStyles": false, "allowEval": false, "allowScriptTags": false, "selfRequestsOnly": true, "responseHandling": [{"code": "204", "swap": false}, {"code": "[23]..", "swap": true}, {"code": "[45]..", "swap": true, "error": true}]}`
  - `includeIndicatorStyles: false`: htmx가 `<style>`을 넣지 않게 한다(CSP).
  - `allowEval: false`: `hx-on`·`js:` 같은 eval 경로를 끈다(CSP).
  - `allowScriptTags: false`: 교체되는 조각의 `<script>`를 모두 지운다. 그래서 화면 데이터는 속성으로 넘긴다(보안 6).
  - 4xx·5xx도 swap한다. 그래서 오류 응답은 항상 우리가 만든 조각이어야 하고, 놓일 자리는 응답 헤더 `HX-Retarget`·`HX-Reswap`으로 정한다.
  - HTMX 요청의 오류 응답에는 `HX-Push-Url: false`도 붙인다. `hx-push-url`이 있는 필터 요청이 실패해도 주소창이 잘못된 주소로 바뀌지 않게 한다.
- **중복 제출 방지:** 변경 요청을 보내는 폼과 버튼(빠른 기록, 정지, 저장, 삭제)에는 `hx-sync="this:drop"`과 `hx-disabled-elt`를 둔다. Enter를 두 번 눌러도 기록이 두 번 저장되지 않는다.
- **조각과 전체 페이지:** `HX-Request` 헤더가 있고 `HX-History-Restore-Request`가 없을 때만 조각을 돌려준다. 뒤로 가기 복원 요청에는 전체 페이지를 준다(`templating.is_htmx(request)`).
- **알림 영역:** `base.html`의 `<div id="flash" role="status" aria-live="polite">`다. 핸들러가 직접 처리하지 않은 오류(예상 못 한 500, 연결 실패)는 여기 표시한다.
- **변경 응답:** 성공한 변경은 영향을 받는 영역을 `hx-swap-oob="true"`로 함께 바꾼다. 같은 조각 템플릿에 `oob` 변수를 넘겨 루트 요소에 속성을 붙인다.
- **htmx의 DELETE:** htmx 2는 DELETE 매개변수를 쿼리 문자열로 보낸다(`methodsThatUseUrlParams`). 서버는 DELETE의 값을 쿼리에서 읽는다.
- **문구:** 한국어다. core 오류 문구는 CLI 안내(`'lb log'로 확인하세요` 등)를 포함한 그대로 보여 준다(게이트에서 알린 결정, 후속 항목 1). 웹 전용 문구는 각 Task의 표를 따른다.

### 표기 (CLI와 같다)
- 시간 `format_duration`, 날짜 `day_label`(`10-01 (목)`), 연도를 붙인 날짜 `full_day`(`2026-10-01 (목)`), 주차 `week_heading`(`2026-W40 (09-28 ~ 10-04)`)
- 시각 `clock_label(moment.astimezone(now.tzinfo), now.date())`(오늘이면 `09:30`, 아니면 `09-30 (수) 22:10`). DB의 시각은 UTC로 돌아오므로 호출자가 로컬 시간대로 바꿔 넘긴다(CLI `commands/timer.py`와 같다).
- 누적 날짜 `total_label`(`오늘` 또는 `09-30`)
- 기록 한 줄은 `views.record_text(log, with_date=False)`가 `#128 payment/dev 2h — 결제 재시도 로직 구현`, `with_date=True`가 `#128 2026-10-01 (목) payment/dev 2h — 결제 재시도 로직 구현`을 만든다(CLI `worklog_line`·`worklog_record`와 같은 순서, 대시는 항상 `—`). 태스크는 `#42`(없으면 `-`)다.

---

## Task 5-0: 계획 문서 저장

- [x] 이 문서를 커밋한다: `docs: Phase 5 웹 대시보드 구현 계획 추가`

---

## Task 5-1: core — 웹이 함께 쓸 도우미와 집계

**Files:**
- Create: `src/logbook/core/ids.py`, `tests/core/test_ids.py`
- Modify: `src/logbook/core/weeks.py`, `src/logbook/core/config.py`, `src/logbook/core/services/tasks.py`, `services/stats.py`, `services/worklogs.py`, `services/report.py`, `services/__init__.py`, `src/logbook/cli/runtime.py`, `src/logbook/cli/render.py`, `tests/core/test_weeks.py`, `tests/core/test_config.py`, `tests/core/test_services_tasks.py`, `tests/core/test_services_stats.py`, `tests/core/test_services_worklogs.py`

```python
# core/ids.py (SQLAlchemy를 import하지 않는다)
MAX_ID = 2**63 - 1  # SQLite INTEGER 최댓값
MAX_ID_DIGITS = 19
def parse_id(text: str, what: str = "기록") -> int
    """'128', '#128' 형식의 ID. cli/runtime.parse_id를 그대로 옮긴다(문구·동작 같음)."""
def check_id(value: int, what: str = "기록") -> int
    """JSON 정수 ID. bool이거나 1~MAX_ID 밖이면 InvalidInputError:
    '{what} ID가 올바르지 않습니다: {value}. 1 이상의 정수로 입력하세요.'"""

# core/weeks.py (cli/render에서 옮김, 문서 문자열·동작 같음)
def clock_label(moment: datetime, today: date) -> str   # moment는 호출자가 이미 로컬 시간대로 바꾼 값
def total_label(day: date, today: date) -> str
def full_day(d: date) -> str                            # '2026-10-01 (목)'

# core/services/tasks.py (services/report.py의 _done_task_count·_local_midnight를 옮김)
def count_done_tasks(s: Session, week: Week, *, tz: tzinfo) -> int
    """완료 시각의 로컬 날짜(tz 기준)가 주 범위 안인 완료 태스크 수(보관 프로젝트 포함)."""

# core/services/stats.py
@dataclass(frozen=True)
class DailyProjectResult:
    """요일 x 프로젝트(slug) 합계. cells에는 기록이 있는 칸만 들어 있다."""
    week: Week
    days: tuple[date, ...]               # week.days() 7일
    projects: tuple[str, ...]            # 주 합계 내림차순, 같으면 slug 순(stats_matrix와 같다)
    cells: Mapping[tuple[date, str], int]
    day_totals: Mapping[date, int]       # 7일 모두, 기록이 없는 날은 0
    total_minutes: int
def daily_project_minutes(s: Session, week: Week) -> DailyProjectResult

# core/services/worklogs.py
def recent_worklogs(s: Session, *, limit: int) -> list[WorkLog]
    """최근에 입력한 순(id 내림차순) 기록 limit건. project·task를 함께 로드한다.
    limit이 1 미만이면 ValueError(호출 코드의 잘못이라 사용자 문구가 아니다)."""
```

- `cli/runtime.py`는 `_ID_PATTERN`, `MAX_ID_DIGITS`, `parse_id` 본문을 지우고 `from logbook.core.ids import MAX_ID as MAX_ID, parse_id as parse_id`로 재노출한다(`core/db.py`의 `default_db_path` 재노출과 같은 형식, ruff F401 회피). 명령 모듈의 `runtime.parse_id(...)` 호출과 기존 테스트는 그대로 둔다.
- `cli/render.py`도 `from logbook.core.weeks import clock_label as clock_label, full_day as full_day, total_label as total_label`로 재노출하고 본문을 지운다. `render.clock_label`·`render.total_label`·`render.full_day`를 쓰는 명령과 테스트는 그대로 둔다.
- 옮긴 이름(`_ID_PATTERN`, `MAX_ID_DIGITS`, `_done_task_count`, `_local_midnight`)을 직접 참조하는 테스트가 없는지 `grep`으로 확인한다(계획 검토 때 확인한 바로는 `runtime.MAX_ID`만 쓰인다).
- `core/config.py`: `LOCAL_HOSTS = ("127.0.0.1", "localhost")`를 두고, `to_web()`에서 `host`가 비어 있지 않은 문자열인지 먼저 보고(기존 검사) 이어서 `LOCAL_HOSTS`에 있는지 본다. 없으면 `self._invalid("host", value, "'127.0.0.1' 또는 'localhost'")`다.
  - 결과 문구: `설정 값이 올바르지 않습니다: web.host = "0.0.0.0" (파일: …). 설정할 수 있는 값: '127.0.0.1' 또는 'localhost'.`
  - 설정 검증은 모든 명령에 걸린다(기존 규칙과 같다).
  - 기존 `tests/core/test_config.py`(140·153행 부근)는 `host = "0.0.0.0"`을 정상 값으로 쓴다. 이 테스트의 host를 `"localhost"`로 바꾸고 port 검증(9000)은 그대로 둔다.
- `services/report.py`는 `count_done_tasks(s, week, tz=tz)`를 부르고, 옮긴 두 함수와 쓰지 않게 된 import를 지운다. 보고서 테스트는 그대로 통과해야 한다.
- `services/__init__.py`에 `DailyProjectResult`, `daily_project_minutes`, `count_done_tasks`, `recent_worklogs`를 더한다(`__all__` 포함).

**테스트 케이스**

| 대상 | 케이스 | 기대 |
|---|---|---|
| `parse_id` | `"128"`, `"#128"`, `" 7 "`, `str(MAX_ID)` | 정수 |
| `parse_id` | `"0"`, `"-1"`, `"12a"`, `"١٢"`(아랍 숫자), `str(MAX_ID + 1)`, 20자리 | `기록 ID가 올바르지 않습니다: '…'. 숫자로 입력하세요 (예: 128 또는 #128).` |
| `parse_id` | `what="태스크"` | `태스크 ID가 …` |
| `check_id` | `1`, `MAX_ID` | 그대로 |
| `check_id` | `0`, `-1`, `MAX_ID + 1`, `True` | `기록 ID가 올바르지 않습니다: 0. 1 이상의 정수로 입력하세요.` 등(값은 `repr`이 아니라 `str`, `True`는 `True`) |
| `clock_label` | 같은 날 09:30, 다른 날 2026-09-30 22:10 | `09:30`, `09-30 (수) 22:10` |
| `total_label` | 같은 날, 2026-09-30 | `오늘`, `09-30` |
| `full_day` | 2026-10-01 | `2026-10-01 (목)` |
| config | `[web] host = "localhost"`, `"127.0.0.1"` | 통과 |
| config | `"0.0.0.0"`, `"::1"`, `"192.168.0.10"` | 위 문구 |
| config | `host = ""` | 기존 `비어 있지 않은 문자열` 문구(검사 순서 확인) |
| `count_done_tasks` | W40(09-28~10-04) 안 완료 2건, 앞뒤 주 완료 각 1건, todo 1건, 보관 프로젝트 완료 1건 | 3 |
| `count_done_tasks` | `done_at = 2026-09-27T15:30Z`(KST 09-28 00:30) | `tz=+09:00`이면 W40에 셈, `tz=UTC`면 세지 않음 |
| `daily_project_minutes` | 09-28 payment 60·common 30, 10-01 payment 120, 지난주 기록 1건 | `days` 7개, `cells` 3칸, `day_totals[09-29] == 0`, `projects == ("payment", "common")`, `total_minutes == 210` |
| `daily_project_minutes` | 합계가 같은 두 프로젝트 | slug 순 |
| `daily_project_minutes` | `week_start="sunday"` 주 | 일요일~토요일 범위만 |
| `daily_project_minutes` | 보관 프로젝트 기록 | 포함 |
| `recent_worklogs` | 기록 12건(날짜 섞음), `limit=10` | id 내림차순 10건, 세션을 닫은 뒤 `log.project.slug`·`log.task` 접근 가능 |
| `recent_worklogs` | `limit=0` | `ValueError` |

- [x] RED → GREEN → 커밋 `refactor: ID 파싱·시각 표기·완료 태스크 수를 core로 옮기고 웹용 집계 추가`

---

## Task 5-2: 의존성과 웹 골격 (보안·오류·응답 봉투)

**Files:**
- Modify: `pyproject.toml`, `uv.lock`, `tests/cli/helpers.py`(가드 목록)
- Create: `src/logbook/web/__init__.py`, `context.py`, `security.py`, `errors.py`, `app.py`, `api/__init__.py`, `api/envelope.py`, `pages/__init__.py`(문서 문자열만), `pages/templating.py`(`is_htmx`만), `tests/web/__init__.py`, `tests/web/conftest.py`, `tests/web/helpers.py`, `tests/web/test_security.py`, `tests/web/test_errors.py`, `tests/web/test_layering.py`

1. **의존성:** `uv add fastapi uvicorn python-multipart`, `uv add --dev httpx2`.
   - 하한은 uv가 쓰는 값(설치 시점 최신)을 그대로 둔다.
   - `uv.lock`에서 fastapi 0.143.x, uvicorn 0.54.x, python-multipart 0.0.32, httpx2 2.13.x인지 확인한다. 계획서와 다른 버전이 잡히면 구현 전에 메인 세션에 보고한다(계획서를 먼저 고친다).
   - uvicorn은 extra(`[standard]`) 없이 쓴다(uvloop·httptools 불필요, Windows에서 asyncio 기본 루프).
   - 테스트에서 실제 서버에 보내는 요청(Task 5-5)도 `httpx2`로 한다(`import httpx2`, API는 httpx와 같다).
2. **가드 목록:** `tests/cli/helpers.py`의 `FORBIDDEN_MODULES`에 `"starlette"`, `"pydantic"`, `"python_multipart"`, `"logbook.web"`를 더한다(fastapi·uvicorn은 이미 있다). 기존 가드 케이스가 모두 그대로 통과해야 한다.

```python
# web/context.py
def _local_now() -> datetime:
    return datetime.now().astimezone()

@dataclass(frozen=True)
class WebContext:
    cfg: Config
    engine: Engine
    config_file: Path                       # 사용자 보고서 템플릿 위치(user_template_path)를 정한다
    now: Callable[[], datetime] = _local_now

    def today(self) -> date: ...            # self.now().date()
    @contextmanager
    def session(self) -> Iterator[Session]: ...   # core.db.session_scope(self.engine)

def get_context(request: Request) -> WebContext  # request.app.state.ctx

# web/security.py
ALLOWED_HOSTNAMES = frozenset({"127.0.0.1", "localhost"})
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
CONTENT_SECURITY_POLICY = "…"               # 공통 규칙 '보안' 4의 값 그대로
def security_headers(path: str) -> tuple[tuple[str, str], ...]
    """보안 4의 헤더 목록. /static/이 아니면 Cache-Control: no-store를 더한다(미들웨어와 500 처리기가 함께 쓴다)."""
def host_allowed(host_header: str | None) -> bool
def cross_site_write(method: str, *, host: str, origin: str | None, fetch_site: str | None) -> bool
    """True면 거부한다. 공통 규칙 '보안' 3의 판정."""
class LocalOnlyMiddleware:
    """순수 ASGI 미들웨어(BaseHTTPMiddleware를 쓰지 않는다). http 요청만 검사하고,
    통과한 응답의 http.response.start에 보안 헤더를 더한다. 거부 응답에도 같은 헤더를 붙인다."""
    def __init__(self, app: ASGIApp) -> None
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None

# web/api/envelope.py
def ok(data: object, *, status_code: int = 200, meta: Mapping[str, object] | None = None) -> JSONResponse
def fail(status_code: int, code: str, message: str) -> JSONResponse

# web/errors.py
RECORD_CHANGED = "다른 곳에서 기록이 바뀌었습니다: #{id}. 목록을 새로 고친 뒤 다시 시도하세요."
class ConflictError(LogbookError):
    """화면이 본 기록이 그사이 바뀌었을 때(409 conflict). Task 5-8의 수정·삭제가 쓴다."""
@dataclass(frozen=True)
class ErrorKind:
    status: int
    code: str
def classify(error: LogbookError) -> ErrorKind    # 공통 규칙의 상태 코드 표(ConflictError는 409)
def error_response(request: Request, kind: ErrorKind, message: str) -> Response
def install_error_handlers(app: FastAPI) -> None  # LogbookError, RequestValidationError, StarletteHTTPException, Exception

# web/app.py
def create_app(ctx: WebContext) -> FastAPI
```

- **`host_allowed`:** 호스트 이름은 마지막 `:` 앞부분이다. 대괄호 IPv6(`[::1]:8765`)는 `[::1]` 그대로 비교하므로 거부된다. 서버가 IPv4에만 열리므로 문제가 없다.
- **`cross_site_write`의 Origin 비교:** `urllib.parse.urlsplit(origin).netloc.lower() == host.lower()`이고 scheme이 `http`일 때만 같은 출처다.
- **거부 응답:** 경로가 `/api/`로 시작하면 `fail(403, "forbidden", 문구)`, 아니면 `text/plain; charset=utf-8` 본문 문구다.
- **`error_response` 분기:**
  - `/api/`로 시작하면 `fail(kind.status, kind.code, message)`
  - `templating.is_htmx(request)`면 알림 조각 `<p class="flash flash--error" role="alert">{message}</p>`. 헤더는 `HX-Retarget: #flash`, `HX-Reswap: innerHTML`, `HX-Push-Url: false`이고 상태 코드는 `kind.status`다.
    - 알림 조각과 오류 페이지는 템플릿 없이 `markupsafe.escape`로 직접 만든다(템플릿 환경은 Task 5-6에서 생긴다).
    - `is_htmx`는 Task 5-2에서 `web/pages/templating.py`에 먼저 만든다(Jinja2 환경과 `render`는 Task 5-6).
  - 그 밖이면 최소 HTML 오류 페이지다. `lang="ko"`, 제목 `오류 · logbook`, `<link rel="stylesheet" href="/static/css/app.css">`, `<p role="alert">{message}</p>`, `<a href="/">대시보드로 돌아가기</a>`를 넣고 인라인 스타일·스크립트는 없다.
- **예외 처리기:**
  - `LogbookError` → `classify`
  - `RequestValidationError` → 400 `invalid_input`, 문구는 공통 규칙의 검증 오류 규칙
  - `StarletteHTTPException` 400 → `invalid_input`, `BODY_NOT_JSON`(본문 해석 실패)
  - 404 → API면 `API_NOT_FOUND`, 화면이면 `PAGE_NOT_FOUND`
  - 405 → `METHOD_NOT_ALLOWED`
  - 그 밖의 HTTP 예외 → 그 상태 코드와 code `error`, 문구 `요청을 처리할 수 없습니다 (HTTP {status}).`
  - `Exception` → 500 `INTERNAL_ERROR`.
    - Starlette의 `ServerErrorMiddleware`가 처리기를 부른 뒤 예외를 다시 던지므로, uvicorn이 traceback을 터미널에 남긴다.
    - 이 응답은 `LocalOnlyMiddleware`를 지나지 않으므로 처리기가 `security_headers(path)`를 직접 붙인다.
- **`create_app`:**
  - `FastAPI(title="logbook", docs_url=None, redoc_url=None, openapi_url=None)`
  - `app.state.ctx = ctx`
  - `install_error_handlers(app)`
  - `app.include_router(api.router, prefix="/api")`(Task 5-2에서는 경로가 없는 라우터)
  - `app.add_middleware(LocalOnlyMiddleware)`
  - 정적 파일 마운트와 화면 라우터는 Task 5-6에서 더한다. 정적 폴더가 없으면 `StaticFiles`가 시작할 때 오류를 내기 때문이다.

**테스트 준비(`tests/web/conftest.py`, `helpers.py`)**
- 시계: `tests.cli.helpers`의 `Clock`, `FIXED_NOW`(2026-10-01 목 09:30 +09:00, W40)를 가져다 쓴다. `clock` fixture는 `Clock()`을 돌려주고 monkeypatch하지 않는다.
- 기존 도우미의 위치:
  - `FIXED_TODAY`는 `tests.conftest`에 있다(`tests.cli.helpers`에는 `FIXED_NOW`만 있다).
  - `hold_lock(db_path: Path, mode)`는 `tests.helpers`에 있다. 웹 테스트에는 CLI의 `db` fixture가 없으므로 `tmp_home / "logbook.db"`를 넘긴다.
  - 잠금 테스트는 `monkeypatch.setattr(db, "BUSY_TIMEOUT_SECONDS", 0.05)`로 대기를 줄인다. 엔진은 연결할 때 이 값을 읽으므로, 테스트 안에서 새 엔진과 컨텍스트를 만들어야 반영된다.
- `web_engine`(tmp_home): `db.initialize_database(path)` → `db.open_database(path)` → `session_scope`에서 `services.ensure_common_project(s)`. 끝나면 `engine.dispose()`.
- `web_ctx`: `WebContext(cfg=config, engine=web_engine, config_file=tmp_home / "config.toml", now=lambda: clock.now)`
- `client`: `with TestClient(create_app(web_ctx), base_url="http://127.0.0.1:8765") as c: yield c`
- `helpers.py`:
  - 데이터 준비: `add_project(engine, slug, name, *, color=None, archived=False)`, `add_log(engine, *, minutes, note, project="common", category="dev", day=FIXED_TODAY, task_id=None) -> int`, `add_task(engine, *, title, project="common", category=None, week=None, estimate=None, status=TaskStatus.TODO, done_at=None) -> int`. 모두 `core.services`를 `session_scope`에서 부른다.
  - HTML 도우미(표준 `html.parser`, 새 의존성 없음): `Element(tag, attrs, text)`, `parse_html(markup) -> list[Element]`, `by_id(markup, element_id) -> Element`(없으면 AssertionError), `all_by_tag(markup, tag)`, `json_attr(markup, element_id, name) -> object`(속성 값을 JSON으로 읽는다). `text`는 자손 텍스트를 공백 하나로 이은 값이다. void 요소(`input`, `meta`, `link`, `br`, `img`)는 끝 태그 없이 닫는다.

**테스트 케이스**

| 파일 | 케이스 | 기대 |
|---|---|---|
| test_security | `host_allowed`: `127.0.0.1:8765`, `localhost:8765`, `LOCALHOST:8765`, `127.0.0.1` | True |
| test_security | `host_allowed`: `evil.example:8765`, `127.0.0.1.evil.example`, `""`, None, `[::1]:8765` | False |
| test_security | `cross_site_write`: GET에 `Sec-Fetch-Site: cross-site` | False |
| test_security | POST + `same-origin` / `none` / `same-site` / `cross-site` | False / False / True / True |
| test_security | POST, fetch_site 없음, Origin `http://127.0.0.1:8765` / `http://evil.example` / `null` / `https://127.0.0.1:8765` | False / True / True / True |
| test_security | POST, 둘 다 없음 | False |
| test_security | 테스트 앱(시험용 경로를 더한 `create_app`)에 Host `evil.example`로 GET `/api/x`, `/x` | 403 봉투(`forbidden`, `HOST_REJECTED`) / 403 text/plain 문구 |
| test_security | POST `/api/x`에 Origin `http://evil.example` | 403 `CROSS_SITE_REJECTED`, 처리기가 불리지 않음 |
| test_security | 정상 응답·404·403·500 응답 | 공통 규칙 '보안' 4의 헤더 모두, `/api/` 응답에 `Cache-Control: no-store` |
| test_errors | 시험용 경로가 `InvalidInputError`·`NotFoundError`·`DatabaseBusyError`·`DatabaseNotInitializedError`·`LogbookError`·`ConflictError`를 던짐 | 각각 400 `invalid_input`, 404 `not_found`, 503 `busy`, 503 `not_initialized`, 400 `error`, 409 `conflict`, 문구 그대로 |
| test_errors | 같은 오류를 화면 경로에서 `HX-Request: true`로 | 알림 조각 + `HX-Retarget: #flash`·`HX-Reswap: innerHTML`·`HX-Push-Url: false`, 같은 상태 코드 |
| test_errors | `HX-Request`와 `HX-History-Restore-Request`가 함께 있음 | 전체 오류 페이지 |
| test_errors | 화면 경로, HTMX 아님 | 오류 페이지(`lang="ko"`, 문구, 대시보드 링크) |
| test_errors | GET `/api/nope`, GET `/nope` | `요청한 API가 없습니다: GET /api/nope`, `페이지를 찾을 수 없습니다: /nope` |
| test_errors | GET만 있는 시험용 경로에 DELETE | 405 `이 주소는 DELETE 요청을 받지 않습니다: …` |
| test_errors | 시험용 POST(모델 `{n: int}`, strict)에 JSON `{}` / `{"n": "1"}` / `{"n": 1, "x": 2}` / `[]` | `요청 본문이 올바르지 않습니다: 'n' (필수 항목입니다).` / `'n' (정수여야 합니다)` / `'x' (알 수 없는 항목입니다)` / `BODY_NOT_OBJECT` |
| test_errors | 같은 경로에 본문 `{`(Content-Type: application/json) / `{"n": 1}`(Content-Type 없음) / 본문 없음 / cp949로 인코딩한 `{"n": "가"}`(application/json) | `BODY_NOT_JSON` / `BODY_NOT_OBJECT` / `BODY_NOT_OBJECT` / `BODY_NOT_JSON`, 모두 400 `invalid_input` |
| test_errors | 시험용 모델의 목록 필드 오류(loc에 정수 위치) | `'items.1' (…)`처럼 정수가 문자열로 이어짐(TypeError 없음) |
| test_errors | 시험용 경로가 `RuntimeError`(`TestClient(raise_server_exceptions=False)`) | 500 `internal`, `INTERNAL_ERROR` |
| test_errors | `/docs`, `/redoc`, `/openapi.json` | 404 |
| test_errors | JSON 응답 바이트 | 한글이 `\u` 이스케이프 없이 UTF-8로 들어 있음 |
| test_layering | 새 인터프리터에서 `import logbook.web.app` | `logbook.cli`로 시작하는 모듈이 `sys.modules`에 없음 |
| test_layering | `src/logbook/web/**/*.py`의 AST | `sqlalchemy` import는 `if TYPE_CHECKING:` 안에만 있음, `logbook.cli` import 없음 |

- [x] RED → GREEN → 커밋 `feat: 웹 대시보드 의존성과 보안·오류 처리 골격 추가`

---

## Task 5-3: JSON API — 기록과 집계

**Files:**
- Create: `src/logbook/web/api/schemas.py`, `api/serialize.py`, `api/logs.py`, `api/stats.py`, `tests/web/test_api_logs.py`, `tests/web/test_api_stats.py`
- Modify: `src/logbook/web/api/__init__.py`

```python
# api/schemas.py
class Body(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

class LogCreate(Body):
    duration: str
    note: str
    project: str | None = None
    category: str | None = None
    date: str | None = None        # parse_date 입력(today, yesterday, mon~sun, 2026-10-01, 10-01)
    task_id: int | None = None

class LogPatch(Body):              # 보낸 키만 바꾼다(model_fields_set). null은 task_id만 허용(연결 해제)
    duration: str | None = None
    note: str | None = None
    category: str | None = None
    project: str | None = None
    date: str | None = None
    task_id: int | None = None

def optional_text(value: str | None) -> str | None     # 쿼리 값: strip해서 비면 None
def changed_fields(body: Body, *, nullable: frozenset[str]) -> dict[str, object]
    """보낸 키와 값. nullable에 없는 키가 null이면 NOT_NULLABLE. 하나도 없으면 호출자가 문구를 낸다."""

# api/serialize.py
def iso_utc(moment: datetime | None) -> str | None
def week_meta(week: Week) -> dict[str, str]             # {"week": "2026-W40", "start": "2026-09-28", "end": "2026-10-04"}
def worklog_json(log: WorkLog) -> dict[str, object]
def stats_json(result: StatsResult) -> dict[str, object]
```

- `worklog_json`의 키: `id`, `date`, `minutes`, `duration`, `note`, `project`(slug), `category`, `task_id`, `started_at`, `ended_at`, `created_at`
- `stats_json`: `week_meta` 키와 `by`, `total_minutes`, `count`, `rows`(`key`, `label`, `minutes`, `count`)

| 메서드·경로 | 입력 | 동작 | 성공 응답 |
|---|---|---|---|
| `GET /api/logs` | `week`(기본 this), `project`, `category` | `list_worklogs(week=…, project_slug=…, category=…)` | 200, `data`: 기록 배열, `meta`: `week_meta` + `count` + `total_minutes` |
| `POST /api/logs` | `LogCreate` | `lb add`와 같다: `parse_duration` → `check_id(task_id, "태스크")` → `parse_date`(없으면 오늘) → `add_worklog(…, allowed_categories=tuple(cfg.categories), default_project=cfg.default_project, today=ctx.today())` → `day_total_minutes` | 201, `{"log": …, "day_total_minutes": 330}` |
| `PATCH /api/logs/{log_id}` | `LogPatch` | `parse_id(log_id)`, `changed_fields(body, nullable={"task_id"})`. 비면 `바꿀 항목을 하나 이상 지정하세요: duration, note, category, project, date, task_id`. `task_id: null`은 `clear_task=True`. `update_worklog(…, allowed_categories=…)` | 200, `{"log": …}` |
| `DELETE /api/logs/{log_id}` | | `parse_id` → `delete_worklog` | 200, `{"id": 128}` |
| `GET /api/stats` | `week`(기본 this), `by`(기본 project) | `stats_by(s, week, by, category_labels=cfg.categories)`. 잘못된 by는 core 문구 | 200, `stats_json` |

- `PATCH /api/logs`의 이름 대응(`update_worklog` 인자): `duration` → `parse_duration` → `minutes`, `note` → `note`, `category` → `category`, `project` → `project_slug`, `date` → `parse_date` → `work_date`, `task_id`(정수) → `check_id` → `task_id`, `task_id: null` → `clear_task=True`
- 경로의 ID는 `str`로 받아 `parse_id`로 검증한다(FastAPI의 `int` 변환을 쓰지 않는다. 문구를 CLI와 같게 하려는 것이다).
- `task_id`(JSON 정수)는 `check_id(value, "태스크")`로 범위를 본다.

**테스트 케이스** (clock 고정, W40 = 09-28~10-04)

| 케이스 | 기대 |
|---|---|
| 기록 3건(W40 2건, W39 1건) + GET `/api/logs` | W40 2건(날짜·id 순), `meta`가 `{"week": "2026-W40", "start": "2026-09-28", "end": "2026-10-04", "count": 2, "total_minutes": …}` |
| `?week=last`, `?project=payment`, `?category=dev`, `?project=`(빈 값) | 각각 필터 / 빈 값은 필터 없음 |
| `?week=x` / `?project=nope` | 400 주차 문구 / 404 core 프로젝트 문구 |
| POST `{"duration": "2h", "note": "결제 재시도", "project": "payment", "category": "dev"}` | 201, `log.minutes == 120`, `duration == "2h"`, `date == "2026-10-01"`, `created_at`가 `+00:00`로 끝남, `day_total_minutes` |
| POST에 `task_id`만(프로젝트·카테고리 없음) | 태스크의 프로젝트·카테고리 |
| POST `date: "yesterday"` | `2026-09-30` |
| POST `duration: "25h"` / `duration: 90`(숫자) / `note` 없음 / `task_id: "42"` / `task_id: 0` / `extra: 1` | core 24시간 문구 / `'duration' (문자열이어야 합니다)` / `'note' (필수 항목입니다)` / `'task_id' (정수여야 합니다)` / `태스크 ID가 올바르지 않습니다: 0. …` / `'extra' (알 수 없는 항목입니다)` |
| POST 카테고리 없음·태스크 없음 | 400, core `MISSING_CATEGORY_MESSAGE` 그대로 |
| POST 보관 프로젝트 | 400 core 문구 |
| POST, `hold_lock(db, "EXCLUSIVE")` 중 | 503 `busy`, core 잠금 문구, DB 변화 없음 |
| PATCH `{"duration": "90m", "note": "고침"}` | 200, 값 반영 |
| PATCH `{"task_id": null}` / 다른 태스크 id | 연결 해제 / 연결 변경 |
| PATCH `{}` / `{"note": null}` | 위 '바꿀 항목' 문구 / `'note' 값은 비울 수 없습니다.` |
| PATCH `/api/logs/abc` / `/api/logs/999` | 400 `기록 ID가 올바르지 않습니다: 'abc'. …` / 404 core 문구 |
| DELETE 성공 후 같은 id DELETE | 200 `{"id": …}` / 404 |
| GET `/api/stats` | `by == "project"`, 행은 시간 내림차순, `label`은 프로젝트 이름 |
| `?by=category` / `?by=day` | 라벨이 설정 카테고리 라벨 / 7행, 라벨 `09-28 (월)`, 기록 없는 날 0 |
| `?by=x` / `?week=2026-W99` | 400 core 집계 기준 문구 / 400 주차 문구 |
| POST `/api/logs`에 Origin `http://evil.example` | 403, DB 변화 없음 |

- [x] RED → GREEN → 커밋 `feat: 기록·집계 JSON API 추가`

---

## Task 5-4: JSON API — 태스크, 보고서, 타이머

**Files:**
- Create: `src/logbook/web/api/tasks.py`, `api/report.py`, `api/timer.py`, `tests/web/test_api_tasks.py`, `tests/web/test_api_report.py`, `tests/web/test_api_timer.py`
- Modify: `api/schemas.py`, `api/serialize.py`, `api/__init__.py`

```python
# api/schemas.py
class TaskCreate(Body):
    title: str
    project: str | None = None      # 없으면 cfg.default_project
    category: str | None = None
    estimate: str | None = None     # parse_duration(text, max_minutes=None), 예: "40h"
    week: str | None = None         # parse_week
    due: str | None = None          # parse_date
    ref: str | None = None
    description: str | None = None

class TaskPatch(Body):              # null은 category·estimate·week·due·ref·description만(값 비우기)
    title: str | None = None
    category: str | None = None
    estimate: str | None = None
    week: str | None = None
    due: str | None = None
    ref: str | None = None
    description: str | None = None
    status: str | None = None       # todo|doing|done|dropped

class TimerStart(Body):
    note: str | None = None
    project: str | None = None
    category: str | None = None
    task_id: int | None = None

class TimerStop(Body):
    note: str | None = None         # lb stop --note와 같다(' — '로 덧붙임)
    round: int | None = None        # 1~60, core가 검증

# api/serialize.py
def task_json(task: Task, actual_minutes: int) -> dict[str, object]
def timer_json(timer: ActiveTimer, now: datetime) -> dict[str, object]
```

- `task_json`의 키: `id`, `project`, `title`, `description`, `status`, `category`, `estimate_minutes`, `planned_week`, `due_date`, `external_ref`, `created_at`, `updated_at`, `done_at`, `actual_minutes`
- `timer_json`의 키: `project`, `category`, `note`, `task_id`, `started_at`, `elapsed_minutes`(`services.elapsed_minutes`)

| 메서드·경로 | 입력 | 동작 | 성공 응답 |
|---|---|---|---|
| `GET /api/tasks` | `status`(기본 `todo,doing`), `week`, `project` | `parse_statuses`, `parse_week`, `list_tasks(…)`. project를 주면 보관 프로젝트도 보인다(CLI와 같다). 실적은 `actual_minutes_by_task(s, ids)` 한 번 | 200, `data`: 태스크 배열, `meta`: `{"count": n}` |
| `POST /api/tasks` | `TaskCreate` | `create_task(…, allowed_categories=tuple(cfg.categories))` | 201, 태스크(실적 0) |
| `PATCH /api/tasks/{task_id}` | `TaskPatch` | `parse_id(task_id, "태스크")`. `changed_fields(body, nullable={"category","estimate","week","due","ref","description"})`. 비면 `바꿀 항목을 하나 이상 지정하세요: title, category, estimate, week, due, ref, description, status`. status 밖의 필드는 `update_task(s, id, allowed_categories=…, **fields)`(필드 이름 `estimate_minutes`·`planned_week`·`due_date`·`external_ref`로 바꿔 넘김). 이어서 status가 있으면 `set_task_status` | 200, 태스크(실적 포함) |
| `GET /api/report` | `week`(기본 this), `format`(기본 `md`, 쿼리 이름 `format`, 매개변수 이름 `report_format`) | 세션 안에서 `weekly_report(s, week, tz=now.tzinfo, title_format=…, author=…, category_labels=…)`, 세션을 닫은 뒤 md면 `render_markdown(data, template_path=user_template_path(ctx.config_file))` | md: `{"week": "2026-W40", "markdown": "…"}`, json: `dataclasses.asdict(data)` |
| `POST /api/timer/start` | `TimerStart`(본문 생략 가능) | `start_timer(now=ctx.now(), …, allowed_categories=…, default_project=…)` | 201, `{"timer": …, "task_started": true}` |
| `POST /api/timer/stop` | `TimerStop`(본문 생략 가능) | `stop_timer(now=ctx.now(), extra_note=note, round_to=round)` → `day_total_minutes` | 200, `{"log": …, "elapsed_minutes": 85, "day_total_minutes": …}` |

- 상태 값이 네 가지 밖이면 `태스크 상태가 올바르지 않습니다: '{value}'. todo, doing, done, dropped 중 하나를 쓰세요.`(`all`도 거부)다.
- 보고서 형식이 `md`·`json` 밖이면 `보고서 형식이 올바르지 않습니다: '{value}'. md 또는 json을 쓰세요.`다. `format`은 대소문자를 구분하지 않는다.
- 사용자 템플릿 오류(core `InvalidInputError`)는 400이고 core 문구(파일 경로·줄 번호)를 그대로 쓴다.

**테스트 케이스**

| 케이스 | 기대 |
|---|---|
| GET `/api/tasks` 기본 | todo·doing만, `planned_week`·id 순, `actual_minutes`(연결 기록 합) |
| `?status=all` / `?status=done,dropped` / `?status=x` | 4상태 / 2상태 / 400 core 상태 문구 |
| `?week=next` / `?project=old`(보관) / 보관 프로젝트 태스크를 project 없이 | 다음 주 계획만 / 보임 / 안 보임 |
| POST `{"title": "환불 API 설계", "project": "payment", "category": "design", "estimate": "40h", "week": "next", "due": "10-15", "ref": "#43"}` | 201, `estimate_minutes == 2400`, `planned_week == "2026-W41"`, `due_date == "2026-10-15"`, `status == "todo"` |
| POST project 생략 | 설정 기본 프로젝트(`common`) |
| POST `title: "  "` / 보관 프로젝트 / 없는 카테고리 | 400 core 문구 |
| PATCH `{"estimate": null, "week": "2026-W42"}` | 예상 비움, 주차 변경, `updated_at` 갱신 |
| PATCH `{"status": "done"}` / 이어서 `{"status": "doing"}` | `done_at` 기록 / `done_at` 비움 |
| PATCH `{"title": "새 제목", "status": "doing"}` | 둘 다 반영 |
| PATCH `{}` / `{"title": null}` / `{"status": "all"}` / `/api/tasks/x` | 문구 / `'title' 값은 비울 수 없습니다.` / 상태 문구 / 400 `태스크 ID가 …` |
| GET `/api/report` | `markdown`이 `lb report`와 같은 렌더링 결과(같은 데이터로 `render_markdown` 직접 호출해 비교) |
| `?format=json` / `?format=JSON` / `?format=pdf` | `title`·`matrix`·`sections`·`plan` 키, 튜플은 배열 / 같음 / 400 |
| `?week=last` | 지난주 제목 |
| 설정 폴더(`ctx.config_file`과 같은 폴더)의 `report.md.j2` 재정의 / 문법 오류 템플릿 | 사용자 템플릿 결과 / 400 core 템플릿 문구 |
| POST `/api/timer/start` `{"note": "환불 API 설계", "project": "payment", "category": "design"}` | 201, `started_at`이 FIXED_NOW의 UTC, `elapsed_minutes == 0` |
| start에 todo 태스크 id만 | 메모는 태스크 제목, `task_started: true`, 태스크가 doing |
| 이미 진행 중일 때 start | 400 core 문구 |
| clock을 85분 옮긴 뒤 stop(본문 없음) | 200, `log.minutes == 85`, `log.started_at`·`ended_at`, `elapsed_minutes == 85`, 타이머 없어짐 |
| stop `{"note": "리뷰 반영", "round": 15}` | 메모 `… — 리뷰 반영`, 90분 |
| stop `{"round": 0}` / 타이머 없음 / 30초 뒤 stop | 400 core 반올림 문구 / 404 `NO_TIMER_MESSAGE` / 400 1분 문구, 타이머 남음 |

- [x] RED → GREEN → 커밋 `feat: 태스크·보고서·타이머 JSON API 추가`

---

## Task 5-5: CLI — lb serve

**Files:**
- Create: `src/logbook/web/server.py`, `src/logbook/cli/commands/serve.py`, `tests/cli/test_serve.py`, `tests/web/test_server.py`
- Modify: `src/logbook/cli/runtime.py`(`parse_port`, `MAX_PORT`), `src/logbook/cli/main.py`(`serve` 등록), `tests/cli/test_entry.py`(가드 케이스), `tests/cli/test_runtime.py`

```python
# cli/runtime.py
MAX_PORT = 65535  # core.config.MAX_PORT와 같은 값(테스트가 확인). config를 import하지 않으려고 따로 둔다
def parse_port(text: str) -> int
    """ASCII 숫자 1~5자리, 1~MAX_PORT. 아니면 InvalidInputError:
    '포트가 올바르지 않습니다: '{text}'. 1~65535 사이의 숫자로 입력하세요 (예: --port 8765).'"""

# web/server.py
BIND_ADDRESS = "127.0.0.1"
def open_listen_socket(port: int) -> socket.socket
    """socket.create_server((BIND_ADDRESS, port)). OSError는 LogbookError:
    '포트를 열 수 없습니다: {port} ({error.strerror or error}). 다른 프로그램이 쓰고 있으면 --port로 다른 포트를 지정하세요.'
    create_server는 Windows에서 SO_REUSEADDR를 켜지 않는다(포트 가로채기 방지)."""
def build_server(app: FastAPI) -> uvicorn.Server
    """uvicorn.Config(app, log_level="warning", access_log=False, server_header=False, lifespan="off")"""
def serve(
    cfg: Config, *, config_file: Path, port: int, open_browser: bool,
    now: Callable[[], datetime], on_ready: Callable[[str], None], on_browser_failed: Callable[[str], None],
) -> None
```

`serve()` 순서:
1. `engine = db.open_database(cfg.db_path)`. `lb init` 전이면 core 문구로 끝난다.
2. `sock = open_listen_socket(port)`
3. `server = build_server(create_app(WebContext(cfg, engine, config_file, now)))`
4. `url = f"http://{cfg.web.host}:{port}"`, `on_ready(url)`
5. `open_browser`면 `webbrowser.open(url)`을 부르고, False를 돌려주거나 `webbrowser.Error`가 나면 `on_browser_failed(url)`을 부른다. 소켓이 이미 listen 중이라 서버 시작 전의 접속은 대기열에서 기다린다.
6. `server.run(sockets=[sock])`
   - `except KeyboardInterrupt: pass`. uvicorn은 Ctrl+C를 받으면 정상 종료한 뒤 SIGINT를 다시 일으키므로(`capture_signals`), 여기서 KeyboardInterrupt가 난다.
7. `finally`에서 `sock.close()`와 `engine.dispose()`를 한다.

```python
# cli/commands/serve.py
def serve(
    port: Annotated[str | None, typer.Option("--port", metavar="PORT", help="포트 (기본: 설정 web.port, 8765)")] = None,
    open_browser: Annotated[bool, typer.Option("--open", help="브라우저로 대시보드를 엽니다.")] = False,
) -> None:
    """웹 대시보드를 실행합니다. 이 컴퓨터(127.0.0.1)에서만 열리고 Ctrl+C로 끕니다."""
```

- **실행 순서:**
  1. `--port`가 있으면 `runtime.parse_port(port)`(설정·DB 없이 끝나는 검증)
  2. `cfg = runtime.settings()`
  3. 함수 안에서 `from logbook.core.config import config_path`, `from logbook.web.server import serve as run_server`. FastAPI·uvicorn은 여기서 처음 로드된다.
  4. `run_server(cfg, config_file=config_path(), port=…, open_browser=…, now=runtime.now, on_ready=…, on_browser_failed=…)`
  5. 돌아오면 `웹 대시보드를 종료했습니다.`
- **출력:**
  - 시작: `✔ 웹 대시보드: http://127.0.0.1:8765 (끄려면 Ctrl+C)`. `✔`는 `render.ok_mark()`다.
  - 브라우저 실패: `console.print_warning("브라우저를 열지 못했습니다. 주소를 직접 여세요: {url}")` → stderr `주의: …`
  - 종료: `웹 대시보드를 종료했습니다.`(stdout), 종료 코드 0. Ctrl+C가 서버의 정상 종료 방법이므로 130이 아니다(SPEC 5 종료 코드 표에 예외로 적는다).
- **오류:** 포트 형식, 설정(`web.host` 등), DB 없음, 포트 사용 중은 모두 `오류: …` 한 줄이고 exit 1이다.

**테스트 케이스**

| 파일 | 케이스 | 기대 |
|---|---|---|
| test_runtime | `parse_port`: `"8765"`, `"1"`, `"65535"` / `"0"`, `"65536"`, `"abc"`, `" 80"`, `"８０"`(전각), `"123456"` | 정수 / 위 문구 |
| test_runtime | `runtime.MAX_PORT == config.MAX_PORT` | 같음 |
| test_serve | `lb init` 전 `serve` | `오류: 데이터베이스가 없습니다: …`, exit 1 |
| test_serve | 설정 `[web] host = "0.0.0.0"` | config 문구, exit 1 |
| test_serve | `build_server`를 가짜로 바꿔(`run()`이 KeyboardInterrupt) `serve` | stdout 두 줄(시작 줄·종료 줄), exit 0, 이후 `os.replace(db, …)` 성공(엔진 dispose), 같은 포트에 다시 `open_listen_socket` 성공(소켓 닫힘) |
| test_serve | 가짜 서버 + `--port 9123` | 시작 줄 주소의 포트가 9123 |
| test_serve | 설정 `host = "localhost"` | 시작 줄 `http://localhost:8765` |
| test_serve | `--open` + `webbrowser.open` monkeypatch(True) / False / `webbrowser.Error` | URL로 한 번 호출 / stderr 주의 문구, exit 0 / 같은 주의 문구 |
| test_serve | 다른 소켓이 포트를 잡은 상태에서 `serve --port P` | `오류: 포트를 열 수 없습니다: P (…). …`, exit 1, 엔진 dispose |
| test_server | 실제 uvicorn: `open_listen_socket(0)`(임시 포트)로 연 소켓과 `build_server(app)`을 스레드에서 `run(sockets=[sock])` → `server.started`가 될 때까지(최대 10초) 기다림 → `httpx2.get(f"http://127.0.0.1:{port}/api/stats")` | 200, 봉투, 보안 헤더. 끝에 `server.should_exit = True`, `join(timeout=10)` |
| test_entry(가드) | `serve --help` / `serve --port abc` | exit 0 / exit 1, `오류: 포트가 올바르지 않습니다`, 금지 모듈 없음 |
| test_serve(subprocess) | 빈 포트를 고르고(바인드 후 닫음) `run_lb(["init"], …)` → `subprocess.Popen([sys.executable, "-c", "from logbook.cli.main import run; run()", "serve", "--port", P], env=lb_env(…))`, `/api/stats`가 200이 될 때까지 최대 30초 폴링 | 200. 끝에 자식 프로세스를 `terminate()`·`wait(timeout=10)`(이 테스트가 띄운 프로세스만) |
| test_serve(subprocess, Windows 제외) | 위와 같이 띄운 뒤 `proc.send_signal(signal.SIGINT)` | 종료 코드 0, stdout에 `웹 대시보드를 종료했습니다.` |

- 서브프로세스 테스트는 `@pytest.mark.subprocess`다.
- 설치된 `lb` 실행 파일(`LAUNCHER`) 대신 인터프리터를 직접 띄운다. Windows의 진입점 exe는 파이썬을 자식 프로세스로 띄우는 런처라, `terminate()`가 런처만 끝내고 서버를 남길 수 있다.
- 첫 테스트는 stdout·stderr를 `subprocess.DEVNULL`로 준다. 두 번째는 출력을 읽어야 하므로 `PIPE`와 `communicate(timeout=10)`를 쓴다(서버 출력은 몇 줄뿐이다).
- Ctrl+C 테스트는 `@pytest.mark.skipif(sys.platform == "win32", …)`다. Windows는 자식에게만 Ctrl+C를 보내기 어렵다(`CTRL_C_EVENT`는 같은 콘솔의 모든 프로세스에 간다). Windows의 Ctrl+C 동작은 Task 5-9 수동 확인으로 본다.

- [ ] RED → GREEN → 커밋 `feat: lb serve 웹 대시보드 실행 명령 추가`

---

## Task 5-6: 화면 골격 — 정적 파일, 레이아웃, 대시보드 조회

**Files:**
- Create: `pages/views.py`, `pages/summary.py`, `pages/dashboard.py`(GET `/`만), `templates/base.html`, `templates/dashboard.html`, `templates/partials/summary.html`, `partials/recent.html`, `partials/timer.html`(표시만), `static/css/app.css`, `static/js/app.js`, `static/js/dashboard.js`, `static/vendor/*`, `static/favicon.svg`, `tests/web/test_views.py`, `tests/web/test_dashboard.py`, `tests/web/test_static.py`
- Modify: `src/logbook/web/app.py`(정적 파일, 화면 라우터, MIME 등록), `pages/__init__.py`(화면 라우터 `router`), `pages/templating.py`(Jinja2 환경, `render`), `tests/core/test_report_render.py`(휠 테스트)

1. **정적 파일 내려받기(결정 W3):**
   - 스크래치패드에 새 빈 폴더를 만들고 npm tarball 두 개를 받는다.
     - `https://registry.npmjs.org/htmx.org/-/htmx.org-2.0.11.tgz`
     - `https://registry.npmjs.org/chart.js/-/chart.js-4.5.1.tgz`
   - 레지스트리 메타데이터(`https://registry.npmjs.org/<이름>/<버전>`)의 `dist.integrity`(sha512)와 받은 파일의 해시가 같은지 확인한다.
   - 압축은 `python -I`로 다른 폴더의 스크립트에서 풀고, `tarfile`의 `filter="data"`를 쓴다. 내려받은 폴더 안에서 인터프리터를 실행하지 않는다.
   - 복사 위치(`static/vendor/`):
     - `package/dist/htmx.min.js` → `htmx-2.0.11.min.js`
     - `package/LICENSE` → `LICENSE-htmx.txt`
     - `package/dist/chart.umd.min.js` → `chart-4.5.1.umd.min.js`
     - `package/LICENSE.md` → `LICENSE-chartjs.md`
   - `vendor/README.md`에 파일별 버전, 원본 URL, 라이선스, 저장소에 넣은 파일의 sha256을 표로 적는다.
2. **app.py:**
   - `mimetypes.add_type("text/javascript", ".js")`, `mimetypes.add_type("text/css", ".css")`를 `create_app`에서 부른다. Windows 레지스트리가 `.js`를 `text/plain`으로 등록한 PC가 있는데, 그러면 `nosniff`가 스크립트를 막는다.
   - `app.mount("/static", StaticFiles(packages=[("logbook.web", "static")]), name="static")`
   - `app.include_router(pages.router)`
3. **templating.py:**
   - `TEMPLATES = Jinja2Templates(env=jinja2.Environment(loader=jinja2.PackageLoader("logbook.web", "templates"), autoescape=True, undefined=jinja2.StrictUndefined, trim_blocks=True, lstrip_blocks=True))`
   - `def render(request, name, context, *, status_code=200, headers=None) -> HTMLResponse`(`TEMPLATES.TemplateResponse(request, name, context, …)`)
   - `def is_htmx(request) -> bool`(Task 5-2에서 만든 것)
4. **뷰 데이터(세션 안에서 만든다):** `pages/views.py`는 행·타이머·기록 문구·버전을, `pages/summary.py`는 요약·차트를 맡는다.

```python
# pages/views.py
RECENT_LIMIT = 10

@dataclass(frozen=True)
class LogRowView:
    id: int
    day: str            # '10-01 (목)'
    full_day: str       # '2026-10-01 (목)'(삭제 확인 문구)
    iso_date: str       # '2026-10-01'(편집 행의 date 입력)
    project: str
    category: str
    duration: str
    note: str
    task: str           # '#42' 또는 '-'
    version: str        # worklog_version

@dataclass(frozen=True)
class TimerView:
    scope: str          # 'payment/design'
    note: str
    task: str | None    # '#43'
    started: str        # clock_label(timer.started_at.astimezone(now.tzinfo), now.date())
    elapsed: str        # format_duration(elapsed_minutes)

def worklog_version(log: WorkLog) -> str
    """id·date·minutes·note·project_id·category·task_id·created_at를 '\x1f'로 이어 sha256한 앞 16자."""
def record_text(log: WorkLog, *, with_date: bool) -> str   # 공통 규칙 '표기'의 기록 한 줄
def log_row(log: WorkLog) -> LogRowView
def timer_view(timer: ActiveTimer, now: datetime) -> TimerView

# pages/summary.py
CHART_PALETTE = ("#2f6fde", "#e8590c", "#2b8a3e", "#c2255c", "#7048e8",
                 "#0b7285", "#e67700", "#5c940d", "#a61e4d", "#495057")

@dataclass(frozen=True)
class SummaryView:
    heading: str        # week_heading
    total: str          # format_duration, 0이면 '0m'
    count: int
    done_count: int
    chart: dict[str, object]   # 아래 '차트 데이터'
    has_logs: bool

def build_summary(s: Session, ctx: WebContext, week: Week, now: datetime) -> SummaryView
def project_colors(slugs: Sequence[str], explicit: Mapping[str, str | None]) -> dict[str, str]
    """설정한 색(projects.color)이 있으면 그 색, 없으면 slugs 순서대로 CHART_PALETTE를 돌려 쓴다."""
```

- **차트 데이터**(`SummaryView.chart`, 값은 분):

```json
{
  "daily": {"labels": ["09-28 (월)", "…"], "target": 480,
            "datasets": [{"label": "payment", "color": "#4f46e5", "data": [60, 0, 0, 120, 0, 0, 0]}]},
  "projects": {"labels": ["payment", "common"], "colors": ["#4f46e5", "#e8590c"], "data": [180, 30]},
  "categories": {"labels": ["개발", "회의"], "colors": ["#2f6fde", "#2b8a3e"], "data": [180, 30]}
}
```

  - daily의 프로젝트 순서·색과 projects의 순서·색은 같다(`daily_project_minutes().projects`와 `project_colors`).
  - categories는 `stats_by(…, "category", category_labels=cfg.categories)` 순서다. 색은 그 카테고리의 설정 순서 위치로 팔레트에서 고른다(예: dev는 0번, meeting은 2번이라 주마다 색이 같다). 설정에 없는 key는 설정 개수 뒤의 위치를 이름 순으로 받는다.
  - target은 `cfg.daily_target_minutes`다.
- **`build_summary`가 부르는 서비스:** `daily_project_minutes`, `stats_by(project)`, `stats_by(category)`, `count_done_tasks(tz=now.tzinfo)`, `list_projects(include_archived=True)`(색)

5. **화면 구성(결정 W4: 기록 우선 업무 도구, Swiss 계열):**
   - `base.html`:
     - `<html lang="ko">`, `charset`·`viewport`, 제목 `{페이지} · logbook`, htmx 설정 meta, CSS, favicon
     - 머리: 앱 이름, 탐색(대시보드 `/`, 기록 `/logs`, 현재 페이지에 `aria-current="page"`), 이번 주 표기
     - `<main id="main">`, 알림 영역 `#flash`
     - 스크립트(모두 `defer`): htmx, `app.js`, 대시보드에서만 Chart.js와 `dashboard.js`
   - `dashboard.html`(위에서 아래로):
     1. 빠른 기록 자리(`#quick-form`, Task 5-7에서 채움)
     2. 요약 `#summary`
     3. 타이머 `#timer`
     4. 최근 기록 `#recent`
   - `partials/summary.html`(`<section id="summary">`, `oob`면 `hx-swap-oob="true"`):
     - 큰 숫자 세 개: 이번 주 공수 / 기록 N건 / 완료 태스크 N건
     - 루트 요소는 `<section id="summary" data-chart='{{ chart|tojson }}'>`다(보안 6. 작은따옴표 속성).
     - 차트 세 개(`<canvas>`에 `role="img"`와 요약 `aria-label`)
     - 차트마다 `<details><summary>표로 보기</summary><table>…</table></details>`(스크린 리더·인쇄용 같은 데이터)
     - 기록이 없으면 차트 대신 `이번 주 기록이 없습니다.`
   - `partials/timer.html`(`<section id="timer">`):
     - 진행 중이면 `진행 중`, `payment/design — 환불 API 설계 [#43]`, `시작 09:30 · 경과 1h 25m`
     - 없으면 `진행 중인 타이머가 없습니다. 터미널에서 lb start로 시작하세요.`
   - `partials/recent.html`(`<section id="recent">`): 제목 `최근 기록`, 표(ID, 날짜, 프로젝트/카테고리, 시간, 메모, 태스크). 비면 `기록이 없습니다.`
6. **CSS(`app.css`):**
   - **토큰(`:root`):**
     - 색: `--bg #f7f7f5`, `--surface #ffffff`, `--ink #15171c`, `--ink-muted #5a6170`, `--rule #dcdfe4`, `--accent #2448c8`, `--ok #0f7a3d`, `--danger #b42318`
     - 글꼴: `--font-sans: "Pretendard", "Apple SD Gothic Neo", "Malgun Gothic", "Noto Sans KR", system-ui, sans-serif`. 웹 글꼴을 내려받지 않고 OS 한글 글꼴을 쓴다(오프라인, 의존성 없음).
     - 글자 크기, 간격 단계
     - 다크모드(Phase 6)는 토큰만 바꾸면 되도록 모든 색을 토큰으로 쓴다.
   - **색의 쓰임:** 색은 데이터(프로젝트·카테고리)와 상태(ok·danger)에만 쓴다. `--accent`는 링크·포커스·주 버튼에만 쓴다.
   - **숫자:** 모든 숫자에 `font-variant-numeric: tabular-nums`를 준다. 요약 숫자는 `clamp(2rem, 1.4rem + 2.4vw, 3.25rem)`, 굵기 700이다.
   - **레이아웃:**
     - 최대 폭 1200px
     - 빠른 기록 줄은 `position: sticky; top: 0`이고 한 줄 배치다. 좁으면 줄바꿈한다.
     - 요약 숫자 사이는 세로 괘선으로 나눈다.
     - 차트 행은 막대 2 : 도넛 1(두 도넛을 세로로 쌓음)이다.
     - 표는 행 높이 36px, 가는 가로 괘선만 쓴다.
     - 720px 미만은 한 열이다.
   - **상태:**
     - 포커스: `outline: 2px solid var(--accent); outline-offset: 2px`
     - 버튼: hover와 active(`transform: translateY(1px)`)
     - 진행 중 타이머 점: `opacity` 맥박. `prefers-reduced-motion: reduce`면 애니메이션·전환을 끈다.
     - `.visually-hidden` 클래스
7. **JS:**
   - `dashboard.js`:
     - `#summary`의 `data-chart`를 `JSON.parse`해 막대(요일별 프로젝트 누적 + 목표선 `line` 데이터셋), 도넛 두 개를 그린다.
     - 축과 툴팁은 분을 `1h 30m` 형식으로 보여 준다(`format_duration`과 같은 규칙).
     - 색은 데이터의 값, 글꼴은 CSS 변수에서 읽는다.
     - `prefers-reduced-motion`이면 `animation: false`다.
     - `htmx:load`로 새로 들어온 요소가 `#summary`면(OOB 교체 포함) 이전 차트를 `destroy()`하고 다시 그린다.
   - `app.js`:
     - `htmx:beforeRequest`에서 `#flash`를 비운다(지난 오류가 남지 않게).
     - `htmx:sendError`에 `#flash`로 `서버에 연결할 수 없습니다. lb serve가 실행 중인지 확인하세요.`를 쓴다.
     - 빠른 기록의 포커스는 Task 5-7에서 더한다.

**테스트 데이터(`test_dashboard.py` 공통):**
- payment(색 `#4f46e5`) 기록: 09-28 dev 60분, 10-01 dev 120분
- common 기록: 09-30 meeting 30분
- 지난주 기록 1건
- W40 안에 완료한 태스크 1건

**테스트 케이스**

| 파일 | 케이스 | 기대 |
|---|---|---|
| test_views | `worklog_version` | 같은 기록이면 같은 값, 8개 필드 중 하나만 바꿔도 달라짐, 16자 소문자 16진수 |
| test_views | `project_colors(["a","b","c"], {"a": None, "b": "#123456", "c": None})` | `{"a": 팔레트[0], "b": "#123456", "c": 팔레트[2]}` |
| test_views | `timer_view`: UTC로 저장된 `2026-09-30T13:10Z` 시작, now는 FIXED_NOW(+09:00) / 오늘 `00:30Z` 시작 | `started == "09-30 (수) 22:10"` / `09:30` |
| test_views | `record_text` | `#1 payment/dev 2h — 메모`, `with_date=True`면 `#1 2026-10-01 (목) payment/dev 2h — 메모` |
| test_dashboard | GET `/` | 200, `text/html; charset=utf-8`, `lang="ko"`, 제목 `대시보드 · logbook`, 대시보드 링크에 `aria-current="page"`, 머리의 `2026-W40 (09-28 ~ 10-04)` |
| test_dashboard | 요약 | `3h 30m`, `기록 3건`, `완료 태스크 1건` |
| test_dashboard | `json_attr(html, "summary", "data-chart")` | 위 형식과 값이 정확히 같음(payment 색 `#4f46e5`, common은 팔레트 값, target 480) |
| test_dashboard | 최근 기록 | id 내림차순, 12건이면 10건만 |
| test_dashboard | 기록 없는 주 | `이번 주 기록이 없습니다.`, `canvas` 없음 |
| test_dashboard | 타이머 없음 / 진행 중(clock 85분 이동) | 안내 문구 / `시작 09:30`·`경과 1h 25m` |
| test_dashboard | 메모 `<script>alert(1)</script>`, 프로젝트 이름에 `"` | 이스케이프되어 나옴(원문 태그 없음) |
| test_dashboard | 렌더링 결과 검사 | 모든 `<script>`에 `src`가 있음, ` style=`·` on[a-z]+=`·`hx-on` 없음 |
| test_dashboard | `hold_lock(db, "EXCLUSIVE")` 중 GET `/` | 503 오류 페이지와 core 잠금 문구 |
| test_static | `/static/css/app.css` / `/static/js/app.js` / vendor 두 파일 | 200, `text/css; charset=utf-8` / `text/javascript; charset=utf-8`, 보안 헤더 있음, `Cache-Control: no-store` 없음 |
| test_static | vendor 파일 sha256 | `vendor/README.md` 표의 값과 같음 |
| test_static | htmx 설정 meta | JSON 파싱 값이 공통 규칙의 설정과 같음 |
| test_report_render(휠) | 휠 목록 | 기존 기본 템플릿과 `logbook/web/templates/base.html`, `logbook/web/static/css/app.css`, `logbook/web/static/vendor/htmx-2.0.11.min.js` 포함. 테스트 이름을 `test_wheel_contains_package_data`로 바꾼다 |

- [ ] RED → GREEN → 커밋 `feat: 웹 대시보드 레이아웃·요약·차트 화면 추가`

---

## Task 5-7: 대시보드 상호작용 — 빠른 기록, 타이머 정지

**Files:**
- Create: `templates/partials/quick_form.html`, `src/logbook/web/pages/timer.py`, `tests/web/test_quick_add.py`, `tests/web/test_timer_panel.py`
- Modify: `pages/dashboard.py`, `pages/views.py`(폼 선택지), `pages/__init__.py`, `templates/dashboard.html`, `partials/timer.html`, `static/js/app.js`, `static/css/app.css`

```python
# pages/views.py
@dataclass(frozen=True)
class Choice:
    value: str
    label: str

@dataclass(frozen=True)
class QuickFormOptions:
    projects: tuple[Choice, ...]    # 보관하지 않은 프로젝트: Choice('payment', 'payment — 결제 서버')
    categories: tuple[Choice, ...]  # 설정 순서: Choice('dev', 'dev — 개발')
    tasks: tuple[Choice, ...]       # 보관하지 않은 프로젝트의 todo·doing: Choice('42', '#42 payment · 환불 API 설계')
def quick_form_options(s: Session, cfg: Config) -> QuickFormOptions
```

- **빠른 기록 폼(`partials/quick_form.html`):**
  - `<form id="quick-form" hx-post="/logs" hx-target="this" hx-swap="outerHTML" hx-sync="this:drop" hx-disabled-elt="find button">`
  - 입력(모두 `<label>`과 연결하고, 좁은 줄이라 라벨은 `.visually-hidden`):
    - 시간 `name="duration"`(`autocomplete="off"`, placeholder `2h, 90m, 1:30`, 페이지를 열면 포커스)
    - 메모 `name="note"`
    - 프로젝트 `name="project"`: 첫 항목은 `value=""`, `자동 (태스크 또는 {default_project})`
    - 카테고리 `name="category"`: 첫 항목은 `value=""`, `자동 (태스크)`
    - 태스크 `name="task"`: 첫 항목은 `value=""`, `없음`
    - 버튼 `기록`(Enter로 제출)
  - 결과 줄 `<p class="form-message" role="status">` 또는 오류 `role="alert"`
- **`POST /logs`(form, `Annotated[str, Form()] = ""` 다섯 개):**
  1. 웹 검증:
     - 시간이 비면 `시간을 입력하세요. 예: 2h, 90m, 1:30`
     - 카테고리와 태스크가 모두 비면 `카테고리를 고르세요. 태스크를 고르면 태스크의 카테고리를 씁니다.`(core의 `-c dev` 안내 대신)
  2. `parse_duration(duration)`, task가 있으면 `parse_id(task, "태스크")`
  3. `add_worklog(…, project_slug=project or None, category=category or None, task_id=…, default_project=cfg.default_project, today=ctx.today(), allowed_categories=…)`, `day_total_minutes`
  4. 성공(200):
     - 새 폼. 시간·메모는 비우고 프로젝트·카테고리·태스크 선택은 유지한다.
     - 결과 줄 `✔ #128 payment/dev 2h — 결제 재시도 로직 구현 (오늘 누적 5h 30m)`. 누적 날짜는 `total_label`이다.
     - `#summary`와 `#recent`를 OOB로 함께 보낸다.
  5. 오류: `classify(error)`의 상태 코드와, 입력값을 그대로 둔 폼 + 오류 줄(core·웹 문구 그대로)이다. DB는 바뀌지 않는다.
- **타이머 패널:**
  - 진행 중이면 경과 표시만 1분마다 갱신한다: `<span id="timer-elapsed" hx-get="/timer/elapsed" hx-trigger="every 60s" hx-swap="outerHTML">경과 1h 25m</span>`. 패널 전체를 바꾸면 정지 버튼의 포커스가 1분마다 사라지기 때문이다. 타이머가 없으면 폴링 요소도 없다.
  - 정지 버튼: `<button hx-post="/timer/stop" hx-target="#timer" hx-swap="outerHTML" hx-sync="this:drop" hx-disabled-elt="this">정지</button>`. 저장하는 동작이라 확인 창이 없다.
- **`GET /timer`:** 패널 조각
- **`GET /timer/elapsed`:** 경과 `<span>` 조각이다. 그사이 타이머가 없어졌으면(CLI에서 정지 등) 빈 패널을 `HX-Retarget: #timer`, `HX-Reswap: outerHTML`로 돌려준다.
- **`POST /timer/stop`:**
  - `stop_timer(s, now=ctx.now())` → `day_total_minutes`
  - 성공: 빈 패널 + 결과 줄 `✔ #129 payment/design 1h 25m — 환불 API 설계 (오늘 누적 6h 55m)` + OOB `#summary`·`#recent`
  - 오류(1분 미만, 24시간 초과, 타이머 없음): `classify` 상태 코드와, 현재 상태로 다시 그린 패널 + 오류 줄(core 문구)
- **`app.js`:** `htmx:afterSwap`에서 교체된 요소가 `#quick-form`이고 응답이 2xx면 `[name=duration]`에 포커스한다.

**테스트 케이스**

| 파일 | 케이스 | 기대 |
|---|---|---|
| test_quick_add | GET `/` 폼 | 선택지: 보관 프로젝트 없음, 카테고리는 설정 순서, 태스크는 todo·doing만(`#42 payment · …`), 각 입력에 연결된 `label` |
| test_quick_add | POST `duration=2h&note=결제 재시도&project=payment&category=dev` | 200, 결과 줄 정확히 일치, DB에 기록, 응답에 `id="summary"`·`id="recent"`와 `hx-swap-oob="true"`, 요약이 갱신된 값 |
| test_quick_add | 선택 유지 | 새 폼에서 project·category 선택 유지, duration·note 비어 있음 |
| test_quick_add | 성공 응답의 OOB `#summary` | `data-chart` 속성이 있고 JSON에 새 기록이 반영됨(htmx가 지우는 `<script>`가 없음) |
| test_quick_add | 폼 속성 | `hx-sync="this:drop"`, `hx-disabled-elt="find button"` |
| test_quick_add | `task=42`만(프로젝트·카테고리 자동) | 태스크의 프로젝트·카테고리로 기록 |
| test_quick_add | 프로젝트 자동, 태스크 없음 | 설정 `default_project`로 기록 |
| test_quick_add | `duration=` / `duration=abc` / `note=` / 카테고리·태스크 없음 / 다른 프로젝트의 태스크 + project 지정 | 400과 각 문구(웹 2개, core 3개), 입력값 유지, DB 변화 없음 |
| test_quick_add | Origin `http://evil.example` | 403, DB 변화 없음 |
| test_quick_add | 메모에 `<b>x</b>` | 결과 줄에서 이스케이프 |
| test_timer_panel | GET `/timer` 없음 / 진행 중 | 안내 문구, `#timer-elapsed` 없음 / `#timer-elapsed`에 `hx-trigger="every 60s"`, 정지 버튼에 `hx-disabled-elt` |
| test_timer_panel | GET `/timer/elapsed` 진행 중(85분) / 타이머 없음 | `경과 1h 25m` span / 빈 패널과 `HX-Retarget: #timer`·`HX-Reswap: outerHTML` |
| test_timer_panel | 85분 뒤 POST `/timer/stop` | 200, 결과 줄 정확히 일치, 기록 날짜는 시작한 날, 타이머 없음, OOB 두 개 |
| test_timer_panel | 30초 뒤 stop / 타이머 없음 | 400·1분 문구, 패널은 진행 중 상태 그대로 / 404·`NO_TIMER_MESSAGE`, 빈 패널 |

- [ ] RED → GREEN → 커밋 `feat: 대시보드 빠른 기록 폼과 타이머 정지 추가`

---

## Task 5-8: 기록 페이지 — 필터, 인라인 수정, 삭제

**Files:**
- Create: `src/logbook/web/pages/logs.py`, `templates/logs.html`, `partials/log_table.html`, `partials/log_row.html`, `partials/log_edit_row.html`, `tests/web/test_logs_page.py`, `tests/web/test_logs_edit.py`
- Modify: `pages/views.py`(필터·편집 선택지), `pages/__init__.py`, `static/css/app.css`

| 메서드·경로 | 입력 | 응답 |
|---|---|---|
| `GET /logs` | `week`(기본 this), `project`, `category`(빈 값은 전체) | 전체 페이지. `is_htmx`면 `#log-table` 조각 |
| `GET /logs/{log_id}/row` | | 표시 행 조각 |
| `GET /logs/{log_id}/edit` | | 편집 행 조각 |
| `PATCH /logs/{log_id}` | form: `duration`, `note`, `log_date`, `log_project`, `log_category`, `log_task`, `version` + 필터 `week`, `project`, `category` | 성공: `#log-table` 조각(필터 반영) + 결과 줄. 오류: 편집 행 + 오류 줄, `HX-Retarget: #log-{id}`, `HX-Reswap: outerHTML` |
| `DELETE /logs/{log_id}` | 쿼리: `version`, `week`, `project`, `category` | 성공: `#log-table` 조각 + 결과 줄. 오류: 알림 영역(공통 처리) |

- **필터 폼:**
  - `<form id="log-filters" hx-get="/logs" hx-target="#log-table" hx-swap="outerHTML" hx-push-url="true" hx-trigger="change, submit">`
  - 주차 묶음 `<div id="week-nav">`: `◀ 이전 주` 링크, 주차 입력(`name="week"`, 값 `2026-W40`), `다음 주 ▶` 링크. 링크에는 일반 `href`(현재 project·category 포함)와 `hx-get`·`hx-target="#log-table"`·`hx-swap="outerHTML"`·`hx-push-url="true"`를 함께 둔다.
  - 프로젝트 선택: `전체` + 모든 프로젝트(보관은 `(보관)` 표시)
  - 카테고리 선택: `전체` + 설정 카테고리
  - 표 조각을 돌려주는 모든 응답(GET `/logs`의 HTMX 응답, PATCH·DELETE 성공)은 `#week-nav`를 OOB로 함께 보낸다. 이전·다음 주 링크로 표만 바뀌어도 주차 입력과 링크가 표의 주와 같게 유지된다. 그래서 이후 수정·삭제·필터 요청이 같은 주로 간다.
  - 주차 형식이 틀리면 400이다. 전체 페이지 요청이면 필터와 오류 줄을 보여 주고, HTMX 요청이면 알림 영역에 쓴다.
- **표(`partials/log_table.html`, `<section id="log-table">`):**
  - 머리: `week_heading`
  - 열: ID, 날짜, 프로젝트, 카테고리, 시간, 메모, 태스크, 동작(`<th scope="col">`)
  - 꼬리: `합계 5h / 기록 5건`
  - 비면 `기록이 없습니다.`
  - 결과 줄 자리 `role="status"`
- **표시 행(`<tr id="log-128">`):**
  - `수정` 버튼: `hx-get="/logs/128/edit" hx-target="closest tr" hx-swap="outerHTML"`
  - `삭제` 버튼: `hx-delete="/logs/128"`, `hx-vals='{"version": "…"}'`, `hx-include="#log-filters"`, `hx-target="#log-table"`, `hx-swap="outerHTML"`, `hx-sync="this:drop"`, `hx-disabled-elt="this"`
    - `hx-confirm="삭제할 기록: #128 2026-10-01 (목) payment/dev 2h — 메모&#10;삭제할까요?"`(CLI `lb log rm`과 같은 확인. `&#10;`은 줄바꿈)
- **편집 행:**
  - 입력: 시간 `duration`(값 `format_duration`), 메모 `note`, 날짜 `log_date`(`type="date"`, ISO), 프로젝트 `log_project`, 카테고리 `log_category`, 태스크 `log_task`(첫 항목 `없음`), `version`(hidden)
  - 프로젝트 선택지는 보관하지 않은 프로젝트에 현재 프로젝트를 더한다(보관이면 `(보관)`). 카테고리는 설정에 현재 값을 더한다. 태스크는 열린 태스크에 현재 태스크를 더한다.
  - 행은 `<tr id="log-128" class="is-editing">`다. 들어오면 `app.js`가 `htmx:afterSwap`에서 `[name=duration]`에 포커스한다.
  - `저장`: `hx-patch="/logs/128" hx-include="closest tr, #log-filters" hx-target="#log-table" hx-swap="outerHTML" hx-sync="this:drop" hx-disabled-elt="this"`
  - `취소`: `hx-get="/logs/128/row" hx-target="closest tr" hx-swap="outerHTML"`
  - 오류 줄은 동작 칸 안의 `<p class="row-error" role="alert">`다. 행을 하나로 유지해야 이후 취소·저장의 `closest tr`이 그대로 동작한다.
  - 표 행 안에는 `<form>`을 둘 수 없어서 `hx-include`로 값을 모은다. 편집 필드 이름에 `log_`를 붙인 것은 필터의 `project`·`category`와 겹치지 않게 하려는 것이다.
- **PATCH 처리(바뀐 항목만 넘긴다. CLI `lb log edit`처럼 지정한 것만 바꾸는 규칙):**
  1. DB 없이 끝나는 검증을 먼저 한다: 경로의 `parse_id`, 필터의 `parse_week`, `parse_duration(duration)`, `parse_date(log_date)`, `log_task`가 있으면 `parse_id(…, "태스크")`.
  2. 나머지는 모두 세션 하나(`with ctx.session() as s:`) 안에서 한다. 중간에 오류가 나면 모두 롤백되어 DB가 바뀌지 않는다. 잠금 오류는 `session_scope`가 503 `busy`로 바꾼다.
     - 필터 project가 있으면 `get_project`로 먼저 확인한다(없으면 404).
     - `get_worklog` 후 `worklog_version(log) != version`이면 `ConflictError(RECORD_CHANGED.format(id=…))`(409)
     - 바뀐 항목을 고른다(문자열은 비교 전에 strip):
       - 분이 `log.minutes`와 다름
       - `note.strip()`이 `log.note`와 다름
       - 날짜가 `log.date`와 다름
       - `log_project.strip()`이 `log.project.slug`와 다름
       - `log_category.strip()`이 `log.category`와 다름
       - `log_task`가 비었는데 기존 태스크가 있으면 `clear_task=True`. 값이 있고 `log.task_id`와 다르면 그 태스크
     - 바뀐 것이 없으면 갱신하지 않고 결과 줄 `바뀐 내용이 없습니다.`
     - 있으면 `update_worklog(…, allowed_categories=…)`. 보관 프로젝트의 옛 기록도 프로젝트를 바꾸지 않으면 고칠 수 있다(core 규칙).
     - 같은 세션에서 필터로 `list_worklogs`를 불러 표 뷰 데이터를 만든다.
  3. 성공 결과 줄은 `✔ 수정했습니다: #128 2026-10-01 (목) payment/dev 1h 30m — 메모`다. 바뀐 기록이 필터 밖으로 나가면 표에서 빠진다.
- **DELETE 처리:** PATCH와 같은 순서다. DB 없는 검증을 먼저 하고, 세션 하나에서 필터 확인 → 버전 확인 → `delete_worklog` → 목록 순으로 한다.
  - `version`이 다르면 409다. SQLite는 지운 최대 id를 다시 쓰므로, 오래 열어 둔 화면에서 다른 기록을 지우지 않게 하려는 것이다.
  - 결과 줄은 `✔ 삭제했습니다: #128 2026-10-01 (목) payment/dev 2h — 메모`다.

**테스트 케이스**

| 파일 | 케이스 | 기대 |
|---|---|---|
| test_logs_page | GET `/logs` | 제목 `기록 · logbook`, 기록 링크에 `aria-current="page"`, 이번 주 기록이 날짜·id 순, 꼬리 합계 |
| test_logs_page | `?week=last` / `?project=payment` / `?category=dev` / `?project=&category=` | 각 필터 / 빈 값은 전체 |
| test_logs_page | 이전·다음 주 링크 | `href`가 `/logs?week=2026-W39…`·`2026-W41`, 현재 project·category 유지 |
| test_logs_page | HTMX GET `/logs?week=2026-W39` | 표 조각과 OOB `#week-nav`(주차 입력 값 `2026-W39`, 링크 W38·W40) |
| test_logs_page | `HX-Request: true`로 GET | `#log-table` 조각만(`<html` 없음) |
| test_logs_page | `HX-Request`와 `HX-History-Restore-Request` | 전체 페이지 |
| test_logs_page | `?week=x`(전체 요청 / HTMX) | 400, 페이지에 오류 줄 / 알림 조각 |
| test_logs_page | `?project=nope` | 404 core 문구 |
| test_logs_page | 보관 프로젝트 필터 선택지 | `(보관)` 표시 |
| test_logs_page | 삭제 버튼 속성 | `hx-confirm`에 연도 붙은 기록 줄, `hx-vals`의 version이 `worklog_version`과 같음 |
| test_logs_edit | GET `/logs/1/edit` | 편집 행: 현재 값, date 입력 `2026-10-01`, 태스크 `없음` 선택 |
| test_logs_edit | GET `/logs/1/row` | 표시 행 |
| test_logs_edit | PATCH 시간만 `90m`으로 | 200 표 조각, 결과 줄, DB 반영, 다른 필드 그대로 |
| test_logs_edit | PATCH 값 그대로 | `바뀐 내용이 없습니다.`, `update_worklog` 미호출(DB 값 그대로) |
| test_logs_edit | PATCH `log_task=`(기존 태스크 있음) / 다른 태스크 | 연결 해제 / 연결 변경(프로젝트가 다르면 core 문구 400) |
| test_logs_edit | 보관 프로젝트 기록의 메모만 수정 | 성공 |
| test_logs_edit | 날짜를 다음 주로 바꿈 | 성공, 이번 주 표에서 빠짐 |
| test_logs_edit | PATCH `duration=abc` | 400, `HX-Retarget: #log-1`, 편집 행에 입력값과 오류 줄 |
| test_logs_edit | version 다름 | 409, 문구, DB 그대로 |
| test_logs_edit | 없는 id(999) PATCH·DELETE | 404 core 문구 |
| test_logs_edit | DELETE 정상 | 200 표 조각, 결과 줄, DB에서 없어짐 |
| test_logs_edit | DELETE version 다름(삭제 후 같은 id로 새 기록이 생긴 경우) | 409, 새 기록 남음 |
| test_logs_edit | PATCH·DELETE에 Origin `http://evil.example` | 403, DB 그대로 |
| test_logs_edit | PATCH·DELETE에 필터 `week=x` / 필터 `project=nope` | 400 / 404, 둘 다 DB 그대로 |
| test_logs_edit | `hold_lock` 중 PATCH·DELETE(`BUSY_TIMEOUT_SECONDS` 0.05, 새 엔진) | 503 `busy`, DB 그대로 |
| test_logs_edit | W39 기록을 `week=2026-W39` 필터와 함께 PATCH | W39 표 조각과 OOB `#week-nav`(W39) |

- [ ] RED → GREEN → 커밋 `feat: 기록 페이지 필터·인라인 수정·삭제 추가`

---

## Task 5-9: 문서 마무리와 Phase 5 완료

- [ ] **README:**
  - "웹 대시보드" 절 추가
    - 실행: `uv run lb serve`, `--port`, `--open`
    - 화면: 대시보드, 기록
    - 이 컴퓨터에서만 열린다는 점, 설정 `[web]`
    - 설정을 바꾸면 서버를 다시 시작한다
    - Ctrl+C로 끈다
  - "JSON API" 절 추가
    - 응답 봉투, 엔드포인트 표
    - 예시는 curl(`-H "Content-Type: application/json"`)과 PowerShell `Invoke-RestMethod`를 함께 적는다.
    - PowerShell 예시는 한글이 깨지지 않게 본문을 UTF-8 바이트로 보낸다: `-ContentType 'application/json; charset=utf-8' -Body ([Text.Encoding]::UTF8.GetBytes($json))`. Windows PowerShell 5.1은 문자열 본문을 UTF-8로 보내지 않는다.
- [ ] **SPEC:**
  - 3장: `[web].host` 허용 값
  - 5장 데이터 관리: `lb serve` 출력·오류. 종료 코드 표에 "`lb serve`는 Ctrl+C가 정상 종료라 0"
  - 6장:
    - 실행·보안: 루프백, Host 검사, 교차 출처 쓰기 차단, CSP
    - 대시보드·기록 화면 동작: 빠른 기록의 '자동' 규칙, 타이머 정지, 인라인 수정·삭제와 버전 확인
    - 빠른 기록은 오늘 날짜로만 저장한다. 날짜는 기록 페이지에서 고친다.
    - JSON API 계약: 봉투, 상태 코드 표, 필드, 요청 본문, PATCH 규칙
    - Phase 6에 남은 것(태스크·보고서·설정 화면, week_notes, 다크모드)
  - 8장: "CLI에서 FastAPI를 import하지 않는다" → "`lb serve`를 실행할 때만 FastAPI·uvicorn을 import한다(서브프로세스 테스트로 강제)"
- [ ] **ROADMAP:** Phase 5 네 항목을 `[x]`로 바꾼다.
- [ ] **CLAUDE.md·AGENTS.md(같은 내용):**
  - 디렉터리 구조의 `web/`를 실제 구성으로 고친다(context, security, errors, app, server, api/, pages/, templates/, static/vendor).
  - 허용 목록에 `core.ids`를 더한다.
  - "web은 cli를 import하지 않는다"를 더한다.
- [ ] **자동 확인(이 PC, 임시 `LOGBOOK_DB`·`LOGBOOK_CONFIG`):**
  - PowerShell 5.1과 7에서 `lb serve --port abc`, 설정 `host = "0.0.0.0"`, init 전 실행이 각각 한국어 한 줄과 exit 1인지
  - 서버 동작은 Task 5-5의 스레드·서브프로세스 테스트로 확인한다.
- [ ] **브라우저 확인(사용자, 절차는 PR 댓글):**
  - Windows Edge·Chrome
    - 대시보드 표시
    - 한글 IME로 메모를 입력하고 Enter로 기록
    - 기록 후 차트·요약 갱신
    - `lb start`로 띄운 타이머의 정지
    - `/logs` 필터·수정·삭제(확인 창), 이전 주로 옮긴 뒤 수정해도 같은 주 표가 남는지
    - Enter를 빠르게 두 번 눌러도 기록이 한 건만 생기는지
    - 수정 버튼을 누르면 시간 입력에 포커스가 가는지, 타이머 경과가 바뀌어도 정지 버튼의 포커스가 남는지
    - 창 폭 320px에서 가로 스크롤이 생기지 않는지
    - 개발자 도구 콘솔에 CSP 위반이 없는지
    - Ctrl+C로 끈 뒤 종료 문구와 exit 0
  - macOS Safari·Chrome: 위와 같다(나중에).
- [ ] **전체 검증:**
  - ruff, ruff format, mypy(core strict, `uv run mypy src/logbook` 전체도 오류 없음)
  - pytest(전체 80%, core 80%)
- [ ] 커밋 `docs: Phase 5 완료 표시와 웹 대시보드·API 사용 안내 추가`
- [ ] 사용자 확인 후 Phase 5 이슈 생성 → push → develop 대상 PR. CI 두 OS가 녹색이어야 한다. 브라우저 확인 절차는 PR 댓글로 남긴다.

---

## 크로스 플랫폼 체크리스트 (Phase 5 추가분)

- **MIME:** `.js`·`.css` MIME을 직접 등록한다. Windows 레지스트리가 `.js`를 `text/plain`으로 바꿔 둔 PC가 있고, 그러면 `nosniff` 때문에 스크립트가 막힌다. 테스트가 Content-Type을 확인한다.
- **소켓:** `socket.create_server`를 쓴다. Windows에서 `SO_REUSEADDR`를 켜지 않아 다른 프로그램이 같은 포트를 가로챌 수 없다. 포트 사용 중 오류는 OS마다 errno가 다르므로(Windows 10048, macOS 48) 예외 종류가 아니라 `OSError` 전체를 같은 문구로 바꾼다.
- **Ctrl+C:** uvicorn이 두 OS 모두 SIGINT를 받아 정상 종료한 뒤 다시 일으키므로 `KeyboardInterrupt`로 받는다. Windows의 Ctrl+Break(SIGBREAK)는 처리하지 않는다(프로세스 종료).
- **패키지 데이터:** 템플릿은 `jinja2.PackageLoader`, 정적 파일은 `StaticFiles(packages=…)`로 찾는다. `__file__` 기준 경로를 쓰지 않는다. 휠 포함 여부를 테스트한다.
- **인코딩:** HTML·CSS·JS 응답은 `charset=utf-8`이다. 템플릿·정적 파일은 UTF-8·LF로 저장한다(`.gitattributes`).
- **브라우저 열기:** `webbrowser.open()`만 쓴다.
- **글꼴:** OS 한글 글꼴(맑은 고딕, Apple SD 산돌고딕 Neo)을 쓴다. 웹 글꼴 파일은 넣지 않는다.

## 설계 결정 요약 (기술 결정, 계획 승인 시 함께 확정)

1. **화면은 서비스를 직접 부른다:** 화면이 JSON API를 거치지 않으므로 API 계약을 바꿔도 화면이 깨지지 않는다. 두 경로는 core 서비스를 함께 쓴다.
2. **세션은 핸들러 안에서 연다:** FastAPI yield 의존성의 종료 시점은 버전마다 달랐다. 커밋 오류가 응답에 반영되도록 핸들러 본문에서 `with`로 연다.
3. **보안은 미들웨어 한 곳에서:** Host·교차 출처·헤더 규칙을 순수 ASGI 미들웨어 하나에 모아, 화면과 API가 같은 규칙을 받는다. 교차 출처 판정은 Go 1.25의 검증된 규칙을 따른다.
4. **오류는 우리가 만든 조각으로:** 4xx·5xx도 swap하도록 htmx를 설정하고, 놓일 자리를 응답 헤더로 정한다. 사용자는 항상 한국어 문구를 본다.
5. **수정·삭제는 버전을 확인한다:** 화면이 본 기록과 지금 기록이 다르면 409로 멈춘다. CLI `lb log rm`의 확인 중 변경 검사와 같은 목적이고, SQLite의 id 재사용에도 안전하다.
6. **빠른 기록의 '자동' 선택지:** CLI에서 옵션을 생략하는 것과 같다(명시 > 태스크 > 기본 프로젝트). 선택 상자가 늘 값을 갖게 하면 태스크와 프로젝트가 어긋나는 오류가 잦아진다.
7. **표기·파서 공유:** ID 파싱과 시각 표기를 core로 옮겨 CLI와 웹이 같은 문구·표기를 쓴다.
8. **정적 파일은 버전이 붙은 이름으로 넣는다:** 파일 이름에 버전을 넣고 sha256을 README에 적어, 출처 확인과 교체를 테스트로 지킨다.
9. **스키마 변경 없음.** 새 의존성은 W1에서 승인한 것뿐이다. 브라우저 E2E(Playwright)는 새 dev 의존성이라 넣지 않는다(후속 항목 2).

## 사용자 결정 (2026-10-09 승인 게이트에서 확정)

- **W1. 의존성:** fastapi·uvicorn·python-multipart는 필수 의존성이다. CLI는 `lb serve`에서만 지연 import한다(가드 테스트로 강제).
  - dev 의존성은 처음에 httpx로 정했다. 계획 검토에서 Starlette 1.7 TestClient가 httpx2를 권장하고 httpx에는 경고를 내는 것을 확인해, 이슈 게이트에서 httpx2로 바꿨다.
- **W2. API 범위:** SPEC 6장의 JSON API를 모두 만든다(logs·tasks·stats·report·timer). Phase 6은 화면에 집중한다.
- **W3. 정적 파일:** htmx 2.0.11과 Chart.js 4.5.1을 라이선스와 함께 패키지에 넣는다(CDN 아님).
- **W4. 화면 방향:** 기록 우선 업무 도구(Swiss 계열)다.
  - 입력줄을 위에 고정하고, 숫자는 크게, 표는 촘촘하게 둔다.
  - 색은 데이터와 상태에만 쓴다.

게이트에서 함께 알린 기술 결정(이의 없음):
- 서버는 루프백 전용이다. Host 헤더와 쓰기 요청의 Origin을 검사한다.
- 화면은 서비스를 직접 부르고, 웹 삭제는 브라우저 확인 창을 거친다.
- core 오류 문구는 그대로 보여 준다.
- API 응답은 `{ok, data, error}`다.
- 설정은 시작할 때 한 번 읽는다. Ctrl+C로 끄면 종료 코드는 0이다.

## 후속 항목 (Phase 5 범위 밖, 기록만)

1. **웹 전용 오류 문구:** core 문구의 CLI 안내(`'lb log'로 확인하세요`, `-c dev` 등)를 인터페이스별로 나눈다. Phase 3 후속 항목 5(core 문구의 CLI 문법)와 함께 다룬다.
2. **브라우저 E2E:** Playwright 같은 도구는 새 dev 의존성과 브라우저 내려받기가 필요하다. 요청이 있으면 승인받아 Phase 6에서 넣는다.
3. **웹 타이머 시작·취소:** 화면에는 정지만 있다. API에는 `GET /api/timer`(상태)와 취소가 없다.
4. **Phase 6 범위:** `/tasks` 칸반, `/report`와 week_notes(첫 마이그레이션, 내보내기 형식 2), `/settings`, 다크모드
5. **설정 자동 반영:** 지금은 설정을 바꾸면 서버를 다시 시작해야 한다.
6. **LAN 공개:** 인증이 필요하므로 비목표다(SPEC 1).
7. **Phase 4 후속 항목:** 그대로 유지한다(git-collect, LLM, 가져오기 병합, DST, 템플릿 샌드박스, 오프라인 휠 테스트).
