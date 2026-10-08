# Phase 3 구현 계획 (CLI — 태스크·계획·타이머)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Phase 2의 CLI 골격 위에 다음 명령을 구현한다.
- `lb task add|list|edit|start|done|drop`
- `lb plan`, `lb plan carry`
- `lb start|status|stop|cancel` 타이머

`lb task edit`는 SPEC에 없던 명령으로, 2026-10-08 사용자 결정 T1로 추가한다.

**Architecture:**
- Phase 2 계획서의 "CLI 공통 규칙"을 그대로 따른다(`docs/superpowers/plans/2026-10-06-phase2-cli.md`).
  - 명령 실행 순서, 지연 import 규칙, 출력 규칙, 오류와 종료 코드, CLI 테스트 규칙을 말한다.
- 도메인 규칙은 모두 core에 둔다. CLI는 문자열 파싱과 출력만 맡는다.
  - 태스크 상태 파서
  - 보관 프로젝트 제외 규칙
  - 이월 대상 선정
  - 타이머 시작·종료·취소
  - 경과 시간 반올림
- 시각은 CLI의 `runtime.now()` 한 곳에서 만든다. 이 값은 로컬 시간대가 붙은 aware datetime이다.
  - core 타이머 서비스는 `now`를 인자로 받는다.
  - 기록 날짜와 표시 시각은 `now.tzinfo`(로컬 시간대) 기준으로 계산한다.
  - 테스트는 고정 시간대(UTC+9)와 고정 시각을 주입해 두 OS에서 같은 결과를 낸다.
- 스키마는 바뀌지 않는다. `tasks`, `active_timer`, `worklogs.started_at/ended_at`이 Phase 1에 이미 있다. 마이그레이션이 없다.

**Tech Stack:** Python 3.11+(CI는 3.12), uv, Typer 0.27, Rich 15, SQLAlchemy 2.1, pytest, ruff, mypy(strict는 core만). 새 의존성은 없다.

**선행 조건:**
- **브랜치:** `feat/phase3-task-plan-timer`(develop `c49d3a6`에서 분기, 이미 만들어 둠)
- **uv PATH:** 이 PC에서는 uv가 PATH에 없다.
  - Git Bash: `export PATH="/c/Users/User/AppData/Local/Microsoft/WinGet/Packages/astral-sh.uv_Microsoft.Winget.Source_8wekyb3d8bbwe:$PATH"`
  - PowerShell: `$env:Path = "$env:LOCALAPPDATA\Microsoft\WinGet\Packages\astral-sh.uv_Microsoft.Winget.Source_8wekyb3d8bbwe;$env:Path"`
- **사용자 결정:** 문서 끝의 T1~T4는 2026-10-08 승인 게이트에서 확정했다(모두 추천안).
- **Task 공통 완료 조건:** 아래 명령을 모두 통과한 뒤 커밋한다.
  - `uv run ruff check .`
  - `uv run ruff format --check .`
  - `uv run mypy src/logbook/core`
  - `uv run pytest`
  - 빠른 반복에는 `uv run pytest -m "not subprocess"`를 쓴다.
- **커밋 메시지:** Conventional Commits 형식이다. type만 영어이고 설명은 한국어로 쓴다.
- **TDD:** 각 Task는 실패하는 테스트를 먼저 쓰고(RED), 최소 구현으로 통과시킨 뒤(GREEN), 정리한다.

---

## 파일 구조

| 파일 | 구분 | 책임 |
|---|---|---|
| `src/logbook/core/taskstatus.py` | 생성 | `TaskStatus`(models에서 이동), `OPEN_STATUSES`, `parse_statuses()`. SQLAlchemy를 import하지 않는다 |
| `src/logbook/core/models.py` | 수정 | `TaskStatus`를 taskstatus에서 import해 그대로 노출(기존 import 경로 유지) |
| `src/logbook/core/duration.py` | 수정 | `parse_duration(text, *, max_minutes=MAX_MINUTES)`. `None`이면 상한 없음(예상 공수용) |
| `src/logbook/core/services/_resolve.py` | 생성 | 기록·타이머가 함께 쓰는 해석 규칙을 worklogs에서 옮김: `clean_note`, `resolve_category`, `pick_slug`, `target_project` |
| `src/logbook/core/services/worklogs.py` | 수정 | 위 함수를 `_resolve`에서 import(동작 동일) |
| `src/logbook/core/services/tasks.py` | 수정 | `list_tasks(include_archived=)`, `actual_minutes_by_task()`, `carry_candidates()`, `carry_tasks()` |
| `src/logbook/core/services/timer.py` | 생성 | `StartedTimer`, `TimerStopped`, `start_timer()`, `get_timer()`, `stop_timer()`, `cancel_timer()`, `elapsed_minutes()`, `MAX_ROUND_MINUTES` |
| `src/logbook/core/services/__init__.py` | 수정 | 새 함수 공개 |
| `src/logbook/cli/runtime.py` | 수정 | `now()`, `WeekOpt` 재사용, `parse_round()` |
| `src/logbook/cli/render.py` | 수정 | 태스크·타이머 요약 줄과 표 |
| `src/logbook/cli/commands/task.py` | 생성 | `lb task add\|list\|edit\|start\|done\|drop` |
| `src/logbook/cli/commands/plan.py` | 생성 | `lb plan`(목록 콜백), `lb plan carry` |
| `src/logbook/cli/commands/timer.py` | 생성 | `lb start`, `lb status`, `lb stop`, `lb cancel` |
| `src/logbook/cli/main.py` | 수정 | `COMMAND_MODULES`에 task, plan, timer 추가 |
| `tests/core/test_taskstatus.py` | 생성 | 상태 파서 |
| `tests/core/test_duration.py`, `test_services_tasks.py`, `test_services_worklogs.py` | 수정 | 상한 해제, 보관 제외, 실적 일괄 조회, 이월, 옮긴 도우미 회귀 |
| `tests/core/test_services_timer.py` | 생성 | 타이머 서비스 |
| `tests/cli/conftest.py` | 수정 | `clock` fixture(고정 시각, UTC+9)와 `runtime.now` 고정 |
| `tests/cli/test_task.py`, `test_task_edit.py`, `test_task_status.py`, `test_plan.py`, `test_timer.py` | 생성 | 명령별 CliRunner 테스트 |
| `tests/cli/test_entry.py` | 수정 | import 가드 경우와 서브프로세스 타이머 왕복 |
| `README.md`, `docs/SPEC.md`, `docs/ROADMAP.md`, `CLAUDE.md`, `AGENTS.md` | 수정 | 사용법, 명세 보강(T1~T4, 타이머 규칙), 체크박스, 디렉터리 설명 |
| `docs/superpowers/plans/2026-10-08-phase3-task-plan-timer.md` | 생성 | 이 계획 |

---

## Phase 3 공통 규칙 (Phase 2 규칙에 더해)

### 시각과 시간대
- `runtime.now()`는 `datetime.now().astimezone()`를 돌려준다. 로컬 시간대가 붙은 aware datetime이며, 테스트가 monkeypatch하는 단일 지점이다(`runtime.today()`와 같은 방식).
- **시간대 계산:**
  - core 타이머 서비스는 시각을 직접 만들지 않고, `now: datetime`을 키워드 인자로 받는다.
  - naive datetime이면 `ValueError`를 낸다. 이는 프로그래밍 오류다.
  - 로컬 날짜와 표시 시각은 `x.astimezone(now.tzinfo)`로 계산한다.
- **zoneinfo 미사용:** `zoneinfo`는 쓰지 않는다. 시스템 로컬 오프셋만 쓰므로 Windows에 IANA DB가 없어도 된다(`tzdata`는 이미 의존성에 있다).
- **표시 시각:** `HH:MM`(`f"{t.hour:02d}:{t.minute:02d}"`)으로 쓴다.
  - 오늘이 아니면 앞에 `MM-DD (요일) `을 붙인다(`weeks.day_label`).
  - `strftime`의 `%-H` 같은 Unix 전용 지정자는 쓰지 않는다.
- **테스트 기준 시각:**
  - `FIXED_NOW = datetime(2026, 10, 1, 9, 30, tzinfo=timezone(timedelta(hours=9)))`(목요일, 오늘 fixture와 같은 날)
  - `clock` fixture가 `clock.advance(minutes=…)`로 시각을 옮긴다.

### import 가드에 추가되는 원칙
- 상태 파서(`parse_statuses`)와 `--round` 파서는 SQLAlchemy 없이 동작해야 한다.
- 따라서 `TaskStatus`를 `core/taskstatus.py`로 옮기고, `models.py`는 그것을 import한다.
- **강제 수단:** CLI 상단과 형식 오류 경로에서 `logbook.core.models`·`services`를 import하지 않는다. 기존 import 가드 테스트가 이를 강제한다.

### 출력 표기
| 대상 | 형식 | 예 |
|---|---|---|
| 태스크 요약 | `#{id} {slug}[/{category}] {title}` | `#43 payment/design 환불 API 설계`, 카테고리가 없으면 `#44 admin 권한 정리` |
| 태스크 상세 꼬리 | ` (예상 4h · 2026-W42 · 참조 #43 · 마감 10-15)` | 값이 있는 항목만, 없으면 꼬리 전체 생략 |
| 상태 | key 그대로(`todo`, `doing`, `done`, `dropped`) | 화면 값을 그대로 `--status`에 쓸 수 있게 한다(카테고리 key 표시와 같은 이유) |
| 타이머 요약 | `{slug}/{category} — {note}[ [#43]]` | `payment/design — 환불 API 설계 [#43]` |
| 시각 | `09:30` 또는 `09-30 (수) 22:10` | 오늘이 아니면 날짜를 붙인다 |

- 사용자 데이터(제목, 메모, slug, 참조)는 항상 `rich.text.Text`로 감싼다(Phase 2 규칙).
- `—`는 `render.dash()`, `·`는 `render.info_mark()`를 쓴다.

---

## Task 3-0: 계획 문서 저장

- [x] 이 문서를 `docs/superpowers/plans/2026-10-08-phase3-task-plan-timer.md`로 저장하고 커밋한다: `docs: Phase 3 태스크·계획·타이머 구현 계획 추가`

---

## Task 3-1: core — 상태 파서와 예상 공수용 시간 파싱

**Files:**
- Create: `src/logbook/core/taskstatus.py`, `tests/core/test_taskstatus.py`
- Modify: `src/logbook/core/models.py`, `src/logbook/core/duration.py`, `tests/core/test_duration.py`

```python
# core/taskstatus.py (SQLAlchemy를 import하지 않는다)
class TaskStatus(enum.StrEnum):          # models.py에서 그대로 옮긴다(값·순서 동일)
    TODO = "todo"; DOING = "doing"; DONE = "done"; DROPPED = "dropped"

OPEN_STATUSES: tuple[TaskStatus, ...] = (TaskStatus.TODO, TaskStatus.DOING)
ALL_KEYWORD = "all"

def parse_statuses(text: str) -> tuple[TaskStatus, ...]:
    """'todo,doing'처럼 쉼표로 구분한 상태 목록. 'all'은 네 상태 전부. 입력 순서대로, 중복 제거."""

# core/models.py
from logbook.core.taskstatus import TaskStatus   # 기존 `from logbook.core.models import TaskStatus` 유지

# core/duration.py
def parse_duration(text: str, *, max_minutes: int | None = MAX_MINUTES) -> int: ...
```

`parse_statuses` 규칙:
- 각 항목은 앞뒤 공백을 지우고 소문자로 바꾼다. 빈 항목(`todo,,doing`, 끝 쉼표)은 건너뛴다.
- `all`은 다른 값과 함께 써도 네 상태 전부가 된다(`TaskStatus` 정의 순서).
- 결과가 비었거나(`""`, `" , "`) 모르는 값이 있으면 다음 문구로 `InvalidInputError`를 낸다.
  - 문구: `상태가 올바르지 않습니다: '{text}'. todo, doing, done, dropped, all 중에서 쉼표로 구분해 쓰세요 (예: todo,doing).`
  - `'{text}'`는 원래 입력 전체다.
  - 40자를 넘으면 `duration._echo`처럼 앞 40자와 `...`만 남긴다. 이를 위해 `_echo`를 공개 함수 `echo_input`으로 바꾸고 duration 안의 호출도 고친다.

`parse_duration(max_minutes=None)`:
- 24시간 상한 검사만 건너뛴다. 형식 검사와 1분 미만 거부는 그대로다.
- 기본값은 지금과 같다. 기존 호출과 문구는 바뀌지 않는다.

**테스트: test_taskstatus.py**
| 입력 | 기대 |
|---|---|
| `"todo"`, `"TODO"`, `" todo "` | `(TODO,)` |
| `"todo,doing"`, `"doing, todo"` | 입력 순서 그대로 |
| `"todo,todo,doing"` | `(TODO, DOING)` |
| `"todo,,doing,"` | `(TODO, DOING)` |
| `"all"`, `"done,all"` | 네 상태(정의 순서) |
| `""`, `" , "`, `"todo,x"`, `"완료"` | 위 문구 정확 일치 |
| 45자 입력 | 문구 안 입력이 앞 40자 + `...` |
| `import logbook.core.taskstatus` 후 새 인터프리터에서 `"sqlalchemy" not in sys.modules` | 참(서브프로세스, `@pytest.mark.subprocess`) |
| `from logbook.core.models import TaskStatus`가 같은 객체 | `models.TaskStatus is taskstatus.TaskStatus` |

**테스트: test_duration.py 추가**
| 입력 | 기대 |
|---|---|
| `parse_duration("40h", max_minutes=None)` | `2400` |
| `parse_duration("40h")` | 기존 24시간 초과 문구 |
| `parse_duration("0m", max_minutes=None)` | 기존 1분 미만 문구 |
| `parse_duration("abc", max_minutes=None)` | 기존 형식 문구 |
| `parse_duration("2h", max_minutes=60)` | `ValueError` (아래 참고) |

> `max_minutes`에 24시간이 아닌 값을 줄 호출자는 이번 Phase에 없다. 그래서 상한 문구는 그대로 두고, 인자는 `MAX_MINUTES`와 `None`만 허용한다.
> - 다른 값이면 `ValueError("max_minutes must be MAX_MINUTES or None")`를 낸다. 이는 프로그래밍 오류다.
> - 테스트는 `parse_duration("2h", max_minutes=60)`이 `ValueError`인지 확인한다.

- [x] RED: 위 테스트 작성 → `uv run pytest tests/core/test_taskstatus.py tests/core/test_duration.py -q` 실패 확인
- [x] GREEN: taskstatus.py 생성, models.py import 교체, duration 수정
- [x] 전체 검증 후 커밋 `feat: 태스크 상태 파서와 상한 없는 예상 공수 파싱 추가`

---

## Task 3-2: core — 태스크 목록 보관 제외, 실적 일괄 조회, 이월

**Files:**
- Modify: `src/logbook/core/services/tasks.py`, `src/logbook/core/services/__init__.py`, `tests/core/test_services_tasks.py`

```python
def list_tasks(
    s, *, project_slug=None, statuses=None, week=None, include_archived: bool = False
) -> list[Task]
    """project_slug를 주면 보관 여부와 상관없이 그 프로젝트의 태스크를 돌려준다."""

def actual_minutes_by_task(s: Session, task_ids: Collection[int]) -> dict[int, int]
    """태스크별 연결 기록 합계(분). GROUP BY 쿼리 한 번. 기록이 없는 id는 결과에 없다. 빈 입력은 쿼리 없이 {}."""

def carry_candidates(s: Session, week: Week) -> list[Task]
    """week에 계획된 todo·doing 태스크(보관 프로젝트 제외), id 순."""

def carry_tasks(s: Session, week: Week, task_ids: Collection[int]) -> list[Task]
    """carry_candidates(week) 중 task_ids에 든 태스크의 planned_week를 week.next()로 옮긴다.
    옮긴 태스크를 id 순으로 돌려준다. 그 사이 상태·주차가 바뀌었거나 보관된 태스크는 건너뛴다."""
```

- **list_tasks 기본값:** 보관 프로젝트를 빼는 쪽으로 바꾼다(`list_projects`의 기본값과 같다). 이미 있는 테스트 `test_list_includes_archived_project_tasks`는 아래처럼 바꾼다.
  - `include_archived=True`일 때 포함한다.
  - `project_slug`로 보관 프로젝트를 지정하면 포함한다.
  - 기본값에서는 빠진다.
- **실적 집계 함수:** `task_actual_minutes`는 그대로 둔다(단건). `actual_minutes_by_task`는 목록용이다.
  - 메모리 노트의 N+1 항목을 해소한다.
  - Phase 4 보고서와 Phase 6 칸반도 이 함수를 쓴다.
- **carry_tasks의 updated_at:** 옮긴 태스크마다 `updated_at = utcnow()`로 갱신한다.
- **week_start sunday 모드:** `Week.next()`는 ISO 주차를 기준으로 계산한다. sunday 모드에서도 라벨이 ISO 주차이므로 그대로 맞는다.

**테스트 케이스**
| 케이스 | 기대 |
|---|---|
| 보관 프로젝트 태스크, 기본 호출 | 빠짐 |
| 같은 경우, `include_archived=True` | 포함 |
| 같은 경우, `project_slug="old"` | 포함 |
| `actual_minutes_by_task(s, [t1, t2, t3])`, t1에 2h+30m, t2에 1h, t3 기록 없음, 다른 태스크·태스크 없는 기록 존재 | `{t1: 150, t2: 60}` |
| `actual_minutes_by_task(s, [])` | `{}`, 쿼리 없음(`sqlalchemy.event`로 실행 횟수 0 확인) |
| 태스크 10개 목록 | 실행 쿼리 1회 |
| `carry_candidates(W41)` | W41의 todo·doing만. 다른 주, done, dropped, 보관 프로젝트, 주차 없음은 제외 |
| `carry_tasks(W41, 후보 id 전부)` | 모두 W42, `updated_at` 갱신, 반환은 id 순 |
| `carry_tasks(W41, [후보 하나])` | 그 하나만 옮김 |
| 후보 조회 뒤 하나를 done으로 바꾸고 `carry_tasks` | 그 태스크는 W41에 남고 반환에서 빠짐 |
| `carry_tasks(W41, [후보가 아닌 id, 없는 id])` | `[]`, 아무것도 바뀌지 않음 |
| `carry_tasks(2026-W53, …)` | `2027-W01`로 옮김 (2026년은 W53이 있다) |

- [x] RED → GREEN → 커밋 `feat: 태스크 목록 보관 제외, 태스크별 실적 일괄 조회, 주간 이월 서비스 추가`

---

## Task 3-3: core — 타이머 서비스

**Files:**
- Create: `src/logbook/core/services/timer.py`, `tests/core/test_services_timer.py`
- Create: `src/logbook/core/services/_resolve.py`
- Modify: `src/logbook/core/services/worklogs.py`, `__init__.py`

### 3-3a 공용 해석 규칙 이동(리팩터링, 동작 동일)
worklogs.py의 비공개 함수를 새 모듈 `services/_resolve.py`로 옮기고 이름에서 `_`를 뗀다.
- `clean_note(note) -> str`: 빈 메모면 `메모를 입력하세요. 무엇을 했는지 한 줄로 적어 주세요.`
- `resolve_category(category, task, allowed) -> str`
- `pick_slug(explicit, task, fallback) -> str`
- `target_project(s, slug, task, *, current, task_is_new=True) -> Project`

`_shared.py`에 두지 않는 이유: projects.py가 이미 `_shared.strip_or_none`을 import한다. 그래서 `_shared`가 projects를 import하면 순환이 생긴다. `_resolve.py`는 `_shared`와 `projects`를 import하고, worklogs와 timer가 `_resolve`를 import한다.

worklogs 테스트는 바꾸지 않고 그대로 통과해야 한다. 그것이 이 단계의 검증이다.
- [x] 커밋 `refactor: 기록과 타이머가 함께 쓰는 프로젝트·카테고리 해석 규칙을 공용 모듈로 이동`

### 3-3b 타이머 서비스
```python
MAX_ROUND_MINUTES = 60

class StartedTimer(NamedTuple):
    timer: ActiveTimer
    task_started: bool          # 연결한 태스크를 todo → doing으로 바꿨는지

class TimerStopped(NamedTuple):
    log: WorkLog
    elapsed_minutes: int        # 반올림 전 경과(분, 30초 반올림)

def start_timer(
    s, *, now: datetime, note: str | None, project_slug: str | None = None,
    category: str | None = None, task_id: int | None = None,
    allowed_categories: Collection[str] | None = None, default_project: str = COMMON_SLUG,
) -> StartedTimer

def get_timer(s) -> ActiveTimer | None          # project, task 함께 로드

def elapsed_minutes(started_at: datetime, now: datetime) -> int
    """경과 분(30초 이상 올림). now가 더 이르면 0."""

def stop_timer(
    s, *, now: datetime, extra_note: str | None = None, round_to: int | None = None,
) -> TimerStopped

def cancel_timer(s) -> ActiveTimer               # 지운 타이머(관계 로드됨). 없으면 NotFoundError
```

**start_timer**
- `now`가 naive면 `ValueError`(stop_timer도 같다).
- 이미 타이머가 있으면 `InvalidInputError`를 낸다.
  - 문구: `이미 진행 중인 타이머가 있습니다: {slug}/{category} '{note}' ({시각} 시작). 'lb stop'으로 저장하거나 'lb cancel'로 버리세요.`
  - core 문구에는 `—` 같은 기호를 넣지 않는다. 기호의 ASCII 대체(`platform.symbol`)는 CLI 표시 계층의 일이기 때문이다.
  - `{시각}`은 시작 시각을 `now.tzinfo`로 바꾼 `HH:MM`이다. 날짜가 다르면 `MM-DD HH:MM`이다.
- 해석 순서는 `add_worklog`와 같다(3-3a의 공용 함수를 쓴다).
  - 태스크 → `pick_slug` → `target_project(current=None)`. 보관 프로젝트는 거부한다.
  - 다음으로 `resolve_category`(allowed 검사)를 적용한다.
- 메모: `note`가 `None`이고 태스크가 있으면 태스크 제목을 쓴다. 그 밖의 경우는 `clean_note(note or "")`다(빈 메모 거부).
- 태스크가 todo면 `set_task_status(DOING)`을 적용하고 `task_started=True`를 돌려준다. doing·done·dropped면 바꾸지 않는다.
- 저장: `ActiveTimer(id=1, project, task, category, note, started_at=now)`
- 동시 시작 경합: id=1 행 중복은 `IntegrityError`다. 두 터미널에서 같은 순간에 실행할 때만 생기므로 처리하지 않는다(후속 항목).

**stop_timer**
- 타이머가 없으면 `NotFoundError`를 낸다.
  - 문구: `진행 중인 타이머가 없습니다. 'lb start "메모"'로 시작하세요.`
- `extra_note` 처리:
  - `None`이면 기존 메모를 그대로 쓴다.
  - 앞뒤 공백을 지운 값이 비면 `InvalidInputError`를 낸다.
    - 문구: `덧붙일 메모가 비어 있습니다. 메모를 덧붙이지 않으려면 --note를 빼세요.`
  - 그 밖에는 `f"{timer.note} — {extra}"`로 덧붙인다(결정 T3).
- `round_to` 처리:
  - `None`이 아니면 `1 <= round_to <= MAX_ROUND_MINUTES` 정수여야 한다.
    - bool은 받지 않는다.
    - 위반하면 `InvalidInputError`를 낸다: `반올림 단위는 1~60분 사이의 정수여야 합니다: {round_to!r}`
- 분 계산(초 단위 경과 `sec`):
  - 기본: `minutes = (sec + 30) // 60`
  - `round_to=n`: `minutes = ((sec + n * 30) // (n * 60)) * n`. 결과가 0이고 `sec >= 30`이면 `n`이다(최소 한 단위).
  - `sec < 30`(기본 계산 0분)이면 `InvalidInputError`를 내고 타이머는 그대로 둔다.
    - 문구: `1분이 지나지 않아 기록하지 않았습니다. 버리려면 'lb cancel'을 실행하세요.`
  - 반올림 결과가 `MAX_MINUTES`(24h)를 넘으면 `InvalidInputError`를 내고 타이머는 그대로 둔다.
    - 문구: `타이머가 24시간을 넘었습니다 (시작 {시각}). 'lb cancel'로 버린 뒤 'lb add'로 날짜별로 나눠 기록하세요.`
- 기록 날짜는 `started_at.astimezone(now.tzinfo).date()`이다. 자정을 넘겨도 시작한 날로 기록한다.
- 기록 저장: `WorkLog(project=timer.project, task=timer.task, category=timer.category, date=…, minutes=…, note=…, started_at=timer.started_at, ended_at=now)`
  - 프로젝트 보관 여부와 카테고리 허용 목록은 다시 검사하지 않는다. 시작할 때 검사했고, 그 뒤 설정이 바뀌어도 멈춘 타이머를 저장할 수 있어야 하기 때문이다.
  - 태스크가 그 사이 삭제되었으면 FK `SET NULL` 덕분에 `task=None`이다.
- 타이머 행을 지우고 flush한다. `TimerStopped(log, elapsed)`를 돌려준다. `log`는 project·task가 로드된 상태다.

**cancel_timer**
- 타이머가 없으면 stop과 같은 `NotFoundError` 문구를 낸다(`'lb start'` 안내).

**테스트 케이스: test_services_timer.py** (`KST = timezone(timedelta(hours=9))`, `T0 = datetime(2026,10,1,9,30,tzinfo=KST)`)
| 케이스 | 기대 |
|---|---|
| `start_timer(now=T0, note="설계", project_slug="payment", category="design")` | 행 1개, started_at == T0(UTC로 저장, 읽으면 같은 순간) |
| `-t` 태스크(todo, category design), note=None | note == 태스크 제목, category design, project 태스크 것, `task_started=True`, 태스크 doing |
| 태스크가 doing·done | `task_started=False`, 상태 그대로 |
| 태스크와 다른 project_slug | add_worklog와 같은 문구 |
| 보관 프로젝트, 없는 프로젝트, 카테고리 없음, 허용 밖 카테고리, 빈 메모 | add_worklog와 같은 문구, 타이머 없음 |
| 타이머가 있는데 다시 시작 | 위 문구 정확 일치(`payment/design '설계' (09:30 시작)`), 기존 타이머 유지 |
| 전날 22:10 시작 타이머가 있는데 시작 | `(09-30 22:10 시작)` |
| naive now | `ValueError` |
| `elapsed_minutes(T0, T0+29s)` / `+30s` / `+90m` / `T0-5m` | 0 / 1 / 90 / 0 |
| stop at T0+1h25m | WorkLog minutes 85, date 2026-10-01, started_at T0, ended_at now, 타이머 없음, `elapsed_minutes=85` |
| stop at T0+1h25m, `round_to=15` | 90 (85→90) |
| stop at T0+7m, `round_to=15` | 15 (0 → 최소 한 단위) |
| stop at T0+22m29s, `round_to=15` | 15 / `+22m30s` → 30 |
| stop at T0+20s | `1분이 지나지 않아…`, 타이머 남음 |
| stop at T0+20s, `round_to=15` | 같은 오류(최소 한 단위 규칙은 sec>=30일 때만) |
| stop at T0+24h1m | 24시간 초과 문구, 타이머 남음 |
| stop at T0+23h50m, `round_to=60` | 24h(1440) 허용 |
| 23:50 시작(KST) → 다음날 00:40 stop | date == 시작일 |
| `extra_note="예외 케이스 정리"` | note == `설계 — 예외 케이스 정리` |
| `extra_note="  "` | 덧붙일 메모 문구, 타이머 남음 |
| `round_to` 0, 61, True, 1.5 | 반올림 단위 문구 |
| 시작 뒤 태스크를 지우고(SQL delete) stop | `log.task is None` |
| 시작 뒤 프로젝트 보관, 설정 카테고리 변경 뒤 stop | 저장 성공 |
| 타이머 없이 stop / cancel | 없음 문구 |
| cancel | 지운 타이머 반환(관계 접근 가능), 행 없음, WorkLog 없음 |
| `get_timer` 없음 / 있음 | None / project 로드된 객체 |

- [x] RED → GREEN → 커밋 `feat: 타이머 시작·종료·취소 서비스 추가`

---

## Task 3-4: CLI 공용 — 시각, 반올림 파서, 태스크·타이머 표기

**Files:**
- Modify: `src/logbook/cli/runtime.py`, `src/logbook/cli/render.py`, `tests/cli/conftest.py`, `tests/cli/test_runtime.py`
- Create: `tests/cli/test_render_task.py`

```python
# runtime.py
def now() -> datetime:  # datetime.now().astimezone(). 테스트가 monkeypatch하는 단일 지점
def parse_round(text: str) -> int
    # ASCII 숫자 1~2자리, 1~60. 아니면 InvalidInputError:
    # "반올림 단위가 올바르지 않습니다: '{text}'. 1~60 사이의 분 단위 숫자로 입력하세요 (예: --round 15)."
StatusOpt = Annotated[str | None, typer.Option("--status", "-s", help="상태: todo,doing,done,dropped,all (쉼표 구분)")]
EstimateOpt = Annotated[str | None, typer.Option("--est", "-e", help="예상 공수 (예: 4h, 90m, 40h)")]
RefOpt = Annotated[str | None, typer.Option("--ref", help="외부 참조 (예: '#43', URL, Jira 키)")]
DueOpt = Annotated[str | None, typer.Option("--due", help="마감일: today, 10-15, 2026-10-15 …")]

# render.py
def clock_label(moment: datetime, today: date) -> str         # "09:30" 또는 "09-30 (수) 22:10"
def task_line(task: "Task") -> "Text"                          # "#43 payment/design 환불 API 설계"
def task_details(task: "Task") -> str                          # " (예상 4h · 2026-W42 · 참조 #43 · 마감 10-15)" 또는 ""
def task_table(tasks, actual: Mapping[int, int]) -> "Table"
def task_lines(tasks, actual) -> "list[Text]"
def plan_table(tasks, actual) -> "Table"
def plan_lines(tasks, actual) -> "list[Text]"
def timer_line(timer: "ActiveTimer") -> "Text"                 # "payment/design — 환불 API 설계 [#43]"
```

- `clock_label`의 `today` 비교는 `moment`의 날짜(`moment.date()`, 이미 로컬로 바꾼 값)로 한다. 호출자는 `x.astimezone(now.tzinfo)`로 넘긴다.
- **task_details:** `참조`는 `Text`로 감싼다(URL·대괄호 안전). 마감은 `MM-DD`로 쓴다(`f"{d.month:02d}-{d.day:02d}"`).
- **task_table** 열: `ID`(우측) | `상태` | `프로젝트` | `카테고리` | `제목`(fold, min 10) | `예상`(우측) | `실적`(우측) | `주차` | `참조`(fold, min 6)
  - 빈 값은 `-`다. 실적 0분도 `-`다(`_minutes_or_dash` 재사용).
- **task_lines** 형식: `#43 doing payment/design 환불 API 설계 · 예상 4h · 실적 2h 30m · 2026-W42 · 참조 #43`. 값이 있는 항목만 넣는다.
- **plan_table** 열: `ID` | `상태` | `프로젝트` | `제목`(fold) | `예상` | `실적`. 정렬은 서비스 순서 그대로다(아래 Task 3-8).
- **plan_lines** 형식: `#43 doing payment 환불 API 설계 · 예상 4h · 실적 2h 30m`
- **conftest:** `clock` fixture(autouse 아님)와 autouse `monkeypatch.setattr(runtime, "now", lambda: clock_holder.now)`를 둔다.
  - 기본 시각은 `FIXED_NOW`다.
  - `clock.advance(**timedelta_kwargs)`로 시각을 옮긴다.
  - autouse `deterministic_cli`가 `runtime.now`도 고정하도록 고친다. `clock` fixture를 쓰지 않는 테스트도 `FIXED_NOW`를 받는다.

**테스트:** `parse_round` 경계(`"1"`, `"60"`, `"0"`, `"61"`, `"015"`, `"1.5"`, `""`, `"١٥"`(아랍 숫자))와 `clock_label` 두 경우를 확인한다. `task_details`는 모든 값이 있을 때, 하나도 없을 때, 참조에 `[bold]`가 든 경우를 확인한다. 표 필요 폭은 `assert_fits`로 확인한다.

- [x] RED → GREEN → 커밋 `feat: CLI 시각·반올림 파서와 태스크·타이머 표기 추가`

---

## Task 3-5: lb task add, lb task list

**Files:**
- Create: `src/logbook/cli/commands/task.py`, `tests/cli/test_task.py`
- Modify: `src/logbook/cli/main.py`, `tests/cli/test_entry.py`

`task_app = typer.Typer(cls=LogbookGroup, help="태스크(할 일)를 추가·조회·수정하고 상태를 바꿉니다.", no_args_is_help=True)`

**lb task add**
| 인자·옵션 | 짧은 | 기본값 | 의미 |
|---|---|---|---|
| `제목` | | 필수 | 할 일 한 줄 |
| `--project` | `-p` | `cfg.default_project` | |
| `--category` | `-c` | 없음 | 지정하면 설정 목록으로 검사 |
| `--est` | `-e` | 없음 | `parse_duration(max_minutes=None)`. 24시간을 넘어도 된다 |
| `--week` | `-w` | 없음 | `this`, `next`, `2026-W42` |
| `--ref` | | 없음 | 외부 참조. `#`로 시작하면 따옴표 필요 |
| `--due` | | 없음 | `parse_date` 규칙 |

순서(Phase 2 규칙): `parse_duration` → 설정 → `parse_week`/`parse_date` → `services.create_task(...)`.

출력: `✔ 태스크 추가: #1 payment/design 환불 API 설계 (예상 4h · 2026-W41 · 참조 #43)`

**lb task list**
| 옵션 | 짧은 | 기본값 | 의미 |
|---|---|---|---|
| `--project` | `-p` | 없음 | 지정하면 보관 프로젝트도 볼 수 있다 |
| `--status` | `-s` | `todo,doing` (결정 T2) | `parse_statuses` |
| `--week` | `-w` | 없음(전체 주차) | |

- 머리줄은 `태스크 ({상태 목록})`이다. 주차를 주면 ` · 2026-W42`, 프로젝트를 주면 ` · payment`를 붙인다. 예: `태스크 (todo, doing) · 2026-W41`
- 목록이 비면 `태스크가 없습니다.`를 출력한다.
- 표는 `console.print_table(render.task_table(...), lambda: render.task_lines(...))`로 출력한다.
  - 실적은 같은 세션에서 `services.actual_minutes_by_task(s, [t.id for t in tasks])`로 구한다.
- 꼬리줄: `태스크 3건 / 예상 12h / 실적 7h 30m`. 예상이 없는 태스크는 합계에서 뺀다.
- 정렬은 서비스 순서(계획 주차, id)를 그대로 쓴다.
- 설정에 없는 카테고리는 lb log처럼 경고하지 않는다(필터 옵션이 아니다).

**테스트 케이스: test_task.py** (`initialized`, `project add payment "결제 서버"`, `project add old "옛 프로젝트"` 후 보관)
| 케이스 | 기대 |
|---|---|
| `task add "환불 API 설계" -p payment -c design --est 4h --week this --ref "#43"` | stdout 정확 일치(위 예, 주차 2026-W40), DB 값 확인 |
| `task add "권한 정리"` | `✔ 태스크 추가: #1 common 권한 정리` (꼬리 없음) |
| `--est 40h` | estimate 2400 |
| `--est 0m` / `--est abc` | core 문구, 태스크 없음 |
| `--week ""`, `--week 2026-W99`, `--due 13-45` | core 문구 |
| `-c xyz` | 카테고리 허용 목록 문구 |
| `-p old` | 보관 프로젝트 문구 |
| 제목 `"  "` | `태스크 제목을 입력하세요. …` |
| 제목 `[bold]x[/bold]`, `--ref "[link]"` | 글자 그대로 |
| `task list`(todo 2, doing 1, done 1, dropped 1, 보관 프로젝트 todo 1) | todo·doing 3건만, 꼬리줄 합계 정확 |
| `task list -s all` | 보관 제외 5건 |
| `task list -s done,dropped` | 2건 |
| `task list -s x` | 상태 문구, exit 1 |
| `task list -p old` | 보관 프로젝트 태스크 1건 |
| `task list -w this` | 해당 주만, 머리줄에 ` · 2026-W40` |
| 실적: 태스크 #1에 `lb add 2h x -t 1`, `lb add 30m y -t 1` | 실적 열 `2h 30m` |
| 태스크 없음 | `태스크 (todo, doing)\n태스크가 없습니다.\n` |
| 폭 60으로 줄인 콘솔(Phase 2 `narrow` 방식) | 안내 stderr + 한 줄 목록, `assert_fits` |
| `task` (인자 없음) | help 출력, exit 2 (`lb project`와 같다) |
| init 전 `task list` | `lb init` 안내 |

**import 가드 추가(test_entry.py):** `task --help`, `task add --help`, `task list --help`, `task add x --est abc`, `task list -s x`. 마지막 둘은 rc 1이고 오류 문구로 시작해야 한다.

- [x] RED → GREEN → 커밋 `feat: lb task add·list 명령 추가`

---

## Task 3-6: lb task edit (결정 T1)

**Files:**
- Modify: `src/logbook/cli/commands/task.py`
- Create: `tests/cli/test_task_edit.py`

| 옵션 | 짧은 | 의미 |
|---|---|---|
| `ID` | | 태스크 ID (`43`, `"#43"`) |
| `--title` | | 새 제목 |
| `--category` | `-c` | 새 카테고리 |
| `--est` | `-e` | 새 예상 공수(상한 없음) |
| `--week` | `-w` | 새 계획 주차 |
| `--ref` | | 새 참조 |
| `--due` | | 새 마감일 |
| `--no-category`, `--no-est`, `--no-week`, `--no-ref`, `--no-due` | | 해당 값을 비운다(bool 플래그, 이름 하나만 지정) |

- **프로젝트 변경:** 프로젝트는 바꾸지 않는다. 연결된 기록의 프로젝트와 어긋나기 때문이다(설계 결정 8).
- **오류 처리:**
  - 같은 필드에 값과 `--no-…`를 함께 주면 `--week와 --no-week는 함께 쓸 수 없습니다. 하나만 지정하세요.`를 낸다.
  - 아무 옵션도 없으면 `바꿀 항목을 하나 이상 지정하세요. 예: lb task edit 43 --est 6h --week next`를 낸다.
  - 둘 다 DB보다 먼저 검사한다.
- **서비스 호출:** 바꿀 필드만 dict로 모아 `services.update_task(s, id, allowed_categories=tuple(cfg.categories), **fields)`를 부른다.
  - 키는 `title`, `category`, `estimate_minutes`, `planned_week`, `due_date`, `external_ref`다.
  - `--no-…`는 값 `None`이다.
- **출력:** `✔ 수정했습니다: #1 payment/design 환불 API 설계 (예상 6h · 2026-W41 · 참조 #43)`

**테스트 케이스**
| 케이스 | 기대 |
|---|---|
| `--est 6h --week next` | 출력 정확 일치, DB 반영 |
| `--title "새 제목"` | 제목 변경 |
| `--no-week --no-ref` | 둘 다 None, 꼬리에서 빠짐 |
| `--week next --no-week` | 함께 쓸 수 없음 문구(정확), DB 그대로 |
| 옵션 없음 | 바꿀 항목 문구 |
| `--title ""` | `태스크 제목을 입력하세요. …` |
| `abc`, `0`, `99999999999999999999` | 태스크 ID 문구 |
| 없는 ID | `태스크 #9가 없습니다. 'lb task list'로 확인하세요.` |
| `-c xyz` | 허용 목록 문구 |
| `-p payment` | Click 문법 오류 exit 2(옵션 없음) |

import 가드: `task edit --help`, `task edit 1`(바꿀 항목 없음, rc 1), `task edit abc --est 1h`(rc 1).

- [x] RED → GREEN → 커밋 `feat: lb task edit 명령 추가`

---

## Task 3-7: lb task start, done, drop

**Files:**
- Modify: `src/logbook/cli/commands/task.py`
- Create: `tests/cli/test_task_status.py`

세 명령은 같은 내부 함수 `_change_status(task_id_text, status)`를 쓴다.
- 바꾸기 전 상태를 읽고 `services.set_task_status`를 부른다. 같은 세션에서 처리한다.
- 출력:
  - 상태가 바뀌면: `✔ #1 todo → doing: payment/design 환불 API 설계`
  - 이미 그 상태면: `· 태스크 #1 상태는 이미 doing입니다: payment/design 환불 API 설계`. exit 0이고, `updated_at`은 서비스 규칙대로 갱신된다.
  - `done`이면 끝에 ` (실적 5h 30m / 예상 4h)`를 붙인다. 예상이 없으면 ` (실적 5h 30m)`이다.
    - 실적은 `services.task_actual_minutes`로 구한다.
    - 이미 done인 경우에도 붙인다.
- `done`이나 `dropped`를 다시 `start`하면 doing으로 돌아간다. 서비스가 `done_at`을 지운다.
- 진행 중 타이머가 이 태스크에 연결되어 있어도 막지 않는다(타이머는 독립).

**테스트 케이스:** 세 명령의 정상 경로, 이미 같은 상태, done의 실적 꼬리(예상 있음·없음), done → start 되돌리기(`done_at is None`), 없는 ID, 잘못된 ID 형식을 확인한다. import 가드에는 `task start abc`, `task done --help`를 추가한다.

- [x] RED → GREEN → 커밋 `feat: lb task start·done·drop 상태 변경 명령 추가`

---

## Task 3-8: lb plan, lb plan carry

**Files:**
- Create: `src/logbook/cli/commands/plan.py`, `tests/cli/test_plan.py`
- Modify: `src/logbook/cli/main.py`, `tests/cli/test_entry.py`

`plan_app = typer.Typer(cls=LogbookGroup, help=…)`이며, `lb log`처럼 하위 명령 없이 실행하면 목록을 보여 준다(`invoke_without_command=True`).

**lb plan [--week/-w]** (기본 `this`, 결정 T2)
- 조회: `services.list_tasks(s, week=w, statuses=(TODO, DOING, DONE))`. 중단(dropped)은 계획에서 뺀다(설계 결정 7).
- 정렬: CLI에서 `(task.project.slug, task.id)`로 정렬한다. 표에서 같은 프로젝트끼리 붙게 하려는 것이다.
- 출력:
  ```
  2026-W40 (09-28 ~ 10-04) 계획   예상 12h / 실적 7h 30m / 태스크 5건 (완료 2건)
  ID  상태   프로젝트  제목           예상   실적
   1  doing  payment   환불 API 설계    4h   2h 30m
  …
  프로젝트별 예상: payment 8h · admin 4h
  ```
  - 머리줄의 주차 표기는 `weeks.week_heading`을 쓴다.
  - 프로젝트별 줄에는 예상이 있는 프로젝트만 slug 순으로 적는다. 하나도 없으면 줄을 생략한다.
  - 예상 없는 태스크가 있으면 프로젝트별 줄 뒤에 `예상이 없는 태스크 2건`을 덧붙인다.
- 비었으면 머리줄(`… 계획   예상 0m / 실적 0m / 태스크 0건`) 다음에 `이 주에 계획된 태스크가 없습니다.`를 출력한다.
- 하위 명령 앞의 `-w`는 거부한다. 문구: `--week는 'lb plan' 목록에만 쓸 수 있습니다. 이월할 주는 'lb plan carry -w last'처럼 하위 명령 뒤에 쓰세요.`

**lb plan carry [--week/-w] [--yes/-y]** (결정 T4)
- 원본 주는 `-w`이고 기본은 `this`다. 대상은 원본 주의 다음 주다.
- 1단계 조회 세션: `services.carry_candidates(s, src)`
  - 비었으면 `이월할 태스크가 없습니다 ({src.label}의 todo·doing 태스크).`를 출력하고 exit 0으로 끝낸다.
- 확인(`--yes`가 없을 때):
  - stderr에 `이월할 태스크 ({src.label} → {dst.label}):`과 후보 줄(`render.task_line` + 상태)을 쓴다.
  - 이어서 `runtime.confirm("다음 주로 옮길까요?")`를 부른다.
  - 거절하면 `이월을 취소했습니다.`, 입력이 없으면 `확인 입력을 받지 못해 옮기지 않았습니다. 확인 없이 옮기려면 --yes를 붙이세요.`를 낸다. 둘 다 exit 1이다.
- 2단계 변경 세션: `moved = services.carry_tasks(s, src, [후보 id])`
- 출력: `✔ {len(moved)}건을 {dst.label}로 옮겼습니다.` 다음에 옮긴 태스크 줄을 하나씩 출력한다.
  - 후보 중 그 사이 상태가 바뀌어 빠진 것이 있으면 stderr에 `주의: {n}건은 확인하는 동안 바뀌어 옮기지 않았습니다.`를 쓴다.

**테스트 케이스: test_plan.py**
| 케이스 | 기대 |
|---|---|
| W40에 todo·doing·done·dropped 각 1, W41에 1, 보관 프로젝트 W40 todo 1 | `plan`: dropped·W41·보관 제외 3건, 머리줄 수치 정확 |
| 프로젝트 두 개와 예상 없는 태스크 | 프로젝트별 줄, `예상이 없는 태스크 1건` |
| `plan -w next` | W41 태스크 |
| 빈 주 | 빈 안내 |
| `plan -w x` | 주차 형식 문구 |
| `plan -w next carry` | 하위 명령 앞 옵션 거부 문구 |
| `plan carry` + `y` | stdout 정확 일치, W40 todo·doing이 W41로, done은 W40에 남음, stderr에 목록과 프롬프트 |
| `plan carry` + `n` / 입력 없음 | 각 문구, exit 1, 아무것도 안 바뀜 |
| `plan carry --yes` | 프롬프트 없음 |
| `plan carry -w last --yes` | W39 → W40 |
| 후보 없음 | 안내, exit 0, 프롬프트 없음 |
| 확인 중 변경: `runtime.confirm`을 monkeypatch해 답하기 전에 후보 하나를 done으로 바꾼다 | 나머지만 이동, stderr 주의 문구 |

import 가드: `plan --help`, `plan carry --help`, `plan -w x`(rc 1), `plan carry -w x`(rc 1).

- [x] RED → GREEN → 커밋 `feat: lb plan 주간 계획 조회와 이월 명령 추가`

---

## Task 3-9: lb start, lb status

**Files:**
- Create: `src/logbook/cli/commands/timer.py`, `tests/cli/test_timer.py`
- Modify: `src/logbook/cli/main.py`, `tests/cli/test_entry.py`

**lb start [메모] [-p] [-c] [-t]**
- `메모`는 선택 인자다. `-t`를 주고 메모를 생략하면 태스크 제목을 쓴다(설계 결정 4). 둘 다 없으면 core가 빈 메모 문구를 낸다.
- 순서: `parse_id(-t)` → 설정 → 세션에서 `services.start_timer(s, now=runtime.now(), …, allowed_categories=tuple(cfg.categories), default_project=cfg.default_project)`
- 출력:
  ```
  ✔ 타이머 시작: payment/design — 환불 API 설계 [#1] (09:30)
  · 태스크 #1 상태를 doing으로 바꿨습니다.          ← task_started일 때만
  ```

**lb status**
- 진행 중인 타이머가 있으면 두 줄을 출력한다.
  ```
  진행 중: payment/design — 환불 API 설계 [#1]
  시작 09:30 · 경과 1h 25m
  ```
  - 경과는 `format_duration(elapsed_minutes(...))`다. 0분이면 `0m`이다.
- 타이머가 없으면 `진행 중인 타이머가 없습니다.`를 출력하고 exit 0으로 끝낸다(조회 명령이라 오류가 아니다).

**테스트 케이스(`clock` 사용)**
| 케이스 | 기대 |
|---|---|
| `start "환불 API 설계" -p payment -c design` | 출력 정확 일치 |
| `start -t 1`(todo, design) | 메모 = 제목, 두 번째 줄 있음 |
| `start -t 1`(doing) | 두 번째 줄 없음 |
| 이미 진행 중 | core 문구, exit 1 |
| `start` (메모·태스크 없음) | 빈 메모 문구 |
| `start "x"` (카테고리 없음) | `카테고리를 지정하세요. 예: -c dev` |
| `start x -t abc` | 태스크 ID 문구, DB 접근 전 |
| `status` 없음 | 안내, exit 0 |
| start 후 `clock.advance(minutes=85)`, `status` | `시작 09:30 · 경과 1h 25m` |
| 전날 22:10 시작(DB에 직접 넣거나 clock 되돌려 start) 후 오늘 status | `시작 09-30 (수) 22:10 · 경과 …` |
| 메모 `-5% 개선` | `start -c dev -- "-5% 개선"` 성공 |

import 가드: `start --help`, `status --help`, `start x -t abc`(rc 1).

- [ ] RED → GREEN → 커밋 `feat: lb start·status 타이머 명령 추가`

---

## Task 3-10: lb stop, lb cancel (결정 T3, T4)

**Files:**
- Modify: `src/logbook/cli/commands/timer.py`, `tests/cli/test_timer.py`, `tests/cli/test_entry.py`

**lb stop [--note/-n] [--round N]**
- 순서: `parse_round` → 설정 → 세션에서 `services.stop_timer(s, now=runtime.now(), extra_note=note, round_to=round)`를 부른다. 같은 세션에서 `day_total_minutes(s, log.date)`도 구한다.
- 출력은 `lb add`와 같은 형식이다. 경과 시간과 저장한 시간이 다를 때만 둘째 줄을 붙인다.
  ```
  ✔ #3 payment/design 1h 30m — 환불 API 설계 — 예외 케이스 정리 (오늘 누적 4h)
  · 경과 1h 25m을 15분 단위로 반올림했습니다.
  ```

**lb cancel [--yes/-y]**
- 조회 세션: `get_timer`. 없으면 core와 같은 문구로 `InvalidInputError`를 낸다(exit 1).
- 확인(`--yes`가 없을 때): `runtime.confirm(f"버릴 타이머: {timer_line} (시작 {시각} · 경과 {경과})\n버릴까요?")`
  - 거절하면 `취소하지 않았습니다. 타이머는 계속 진행됩니다.`, 입력이 없으면 `확인 입력을 받지 못해 버리지 않았습니다. 확인 없이 버리려면 --yes를 붙이세요.`를 낸다. 둘 다 exit 1이다.
- 변경 세션: 다시 `get_timer`로 읽는다.
  - `started_at`이나 요약 줄이 확인한 것과 다르면 `확인하는 동안 타이머가 바뀌어 버리지 않았습니다. 다시 실행하세요.`를 내고 exit 1로 끝낸다(lb log rm과 같은 방식).
  - 같으면 `services.cancel_timer(s)`를 부른다.
- 출력: `✔ 타이머를 버렸습니다: payment/design — 환불 API 설계 (경과 25m)`

**테스트 케이스**
| 케이스 | 기대 |
|---|---|
| start → advance 85m → `stop` | `#1 … 1h 25m — 환불 API 설계 (오늘 누적 1h 25m)`, 둘째 줄 없음, DB started_at/ended_at |
| `stop --round 15` | 1h 30m + 반올림 안내 줄 |
| `stop -n "예외 케이스 정리"` | 메모 덧붙임 |
| `stop -n ""` | 덧붙일 메모 문구, 타이머 남음 |
| `stop --round 0`, `--round abc` | CLI 반올림 문구, DB 접근 전 |
| advance 20s → `stop` | 1분 미만 문구, `status`로 타이머 남음 확인 |
| 타이머 없음 `stop` | 없음 문구 |
| 전날 23:50 start → 오늘 00:40 stop (clock) | 기록 날짜 전날, `(09-30 누적 50m)` |
| `cancel` + `y`/`ㅛ` | 버림 문구, 타이머·기록 없음 |
| `cancel` + `n` / 입력 없음 | 각 문구, exit 1, 타이머 남음 |
| `cancel --yes` | 프롬프트 없음 |
| 확인 중 다른 타이머로 바뀜(monkeypatch confirm에서 cancel+start) | 바뀜 문구, 새 타이머 남음 |
| 타이머 없음 `cancel` | 없음 문구, 프롬프트 없음 |

**서브프로세스(test_entry.py, cp949·cp1252 parametrize 중 하나만, 실제 시각)**
- `lb init` → `lb start "한글 타이머" -c dev` → `lb status` → `lb stop`을 실행한다.
  - stop은 1분 미만이라 rc 1이고, stderr가 `오류: 1분이 지나지 않아`로 시작해야 한다.
- 이어서 `lb cancel --yes`가 rc 0이어야 한다.
- 이 테스트로 실제 로컬 시간대(`astimezone()`)와 UTF-8 출력 경로를 확인한다.

import 가드: `stop --help`, `cancel --help`, `stop --round abc`(rc 1).

- [ ] RED → GREEN → 커밋 `feat: lb stop·cancel 타이머 명령 추가`

---

## Task 3-11: 문서 마무리와 Phase 3 완료

**Files:** Modify `README.md`, `docs/SPEC.md`, `docs/ROADMAP.md`, `CLAUDE.md`, `AGENTS.md`

- [ ] **README "사용법"** 명령 예시와 명령 요약 표에 다음을 추가한다.
  - 태스크: add, list, edit, start, done, drop
  - 계획: plan, plan carry
  - 타이머: start, status, stop, cancel
  - 셸 주의: `--ref "#43"`처럼 `#` 값은 따옴표로 감싼다.
- [ ] **docs/SPEC.md 5장**
  - 태스크/계획:
    - `lb task edit` 줄과 옵션 목록을 추가한다(T1). 프로젝트는 바꿀 수 없다고 적는다.
    - `lb task list` 기본은 todo·doing이고 `-s all`을 받는다. 보관 프로젝트는 `-p`로 지정할 때만 보인다(T2).
    - `lb plan` 기본은 이번 주이고 dropped는 빠진다. carry는 `-w`로 원본 주를 고르고 확인을 받는다(`--yes`)(T4).
    - `lb task add`의 `--due`와 `--est` 상한 없음을 적는다.
  - 타이머:
    - 메모를 생략하면 태스크 제목을 쓴다. `-t` 태스크가 todo면 doing으로 바꾼다.
    - stop 규칙: 30초 반올림, 1분 미만과 24시간 초과는 거부(타이머 유지), 기록 날짜는 시작한 날, `--round N`(1~60)은 최소 한 단위, `--note`는 ` — `로 덧붙인다(T3).
    - cancel은 확인을 받는다(T4).
    - `lb status`는 타이머가 없어도 exit 0이다.
  - 종료 코드 표의 1번 설명에 "이월·타이머 취소 확인 거절"을 더한다.
- [ ] **docs/ROADMAP.md:** Phase 3 세 항목을 `[x]`로 바꾸고, 첫 항목에 `edit`를 덧붙인다.
- [ ] **CLAUDE.md, AGENTS.md(같은 내용):**
  - 디렉터리 구조의 `core/`에 `taskstatus.py # 태스크 상태와 상태 목록 파서 (SQLAlchemy 없음)`를 추가한다.
  - `services/` 설명에 `timer`를 더한다.
  - `commands/` 설명의 예시를 `(init, project, add, log, stats, task, plan, timer)`로 바꾼다.
- [ ] **수동 확인(이 PC, PowerShell 5.1과 7):** 임시 `LOGBOOK_DB`·`LOGBOOK_CONFIG`로 다음을 실행한다.
  - `lb task add "한글 태스크" --est 2h --week this --ref "#1"`
  - `lb task list`, `lb plan`
  - `lb start -t 1`, `lb status`, `lb stop --round 15`, `lb plan carry`(n 응답)
  - 확인 내용: 한글·✔·—·· 출력과 프롬프트 동작
  - macOS는 PR 댓글로 확인 절차를 남긴다(Phase 2와 같은 방식).
- [ ] **전체 검증:**
  - `uv run ruff check .`
  - `uv run ruff format --check .`
  - `uv run mypy src/logbook/core`
  - `uv run pytest`(전체 80%)
  - core 단독 80%: `uv run coverage report --include="*/logbook/core/*" --fail-under=80`
- [ ] 커밋 `docs: Phase 3 완료 표시와 태스크·계획·타이머 사용 안내 추가`
- [ ] 사용자 확인 후 Phase 3 이슈 생성 → push → develop 대상 PR. CI 두 OS 잡이 모두 녹색이어야 한다.

---

## 크로스 플랫폼 체크리스트 (Phase 3 추가분)

- **시간대:** `datetime.now().astimezone()`만 쓴다. `zoneinfo`와 `time.tzname`은 쓰지 않는다. core 테스트는 고정 오프셋(UTC+9)을 쓰므로 CI 러너의 TZ(UTC)와 개발 PC(KST)에서 같은 결과가 나온다.
- **UTC 저장:** `UTCDateTime`이 aware 값을 UTC naive로 저장한다. 읽은 값은 UTC aware이므로, 표시 전에 반드시 `astimezone(now.tzinfo)`로 바꾼다.
- **시각 포맷:** `strftime`의 Unix 전용 지정자(`%-H`, `%-M`)를 쓰지 않는다. `f"{h:02d}:{m:02d}"`로 직접 포맷한다.
- **확인 프롬프트:** carry와 cancel도 `runtime.confirm`(stdin 한 줄, y·yes·ㅛ·ㅛㄷㄴ)을 쓴다. Windows 파이프 입력과 CliRunner에서 같은 동작이다.
- **`#` 값:** `--ref "#43"`, `-t "#1"`처럼 `#`로 시작하는 값은 README에서 따옴표를 안내한다.
- **엔진 정리:** 확인 프롬프트가 있는 명령은 조회 세션과 변경 세션을 나눈다. 사람이 답하는 동안 SQLite 잠금을 쥐지 않기 위해서다. 테스트 끝에서는 `os.replace`로 파일 잠금이 없는지 확인한다.

## 설계 결정 요약 (기술 결정, 계획 승인 시 함께 확정)

1. **TaskStatus 위치:** `core/taskstatus.py`로 옮기고 models에서 다시 노출한다. 상태 파서 오류가 SQLAlchemy 없이 나야 하기 때문이다(Phase 2 로딩 가드 규칙).
2. **보관 프로젝트:** `list_tasks` 기본값을 보관 제외로 바꾼다. `list_projects`와 같은 기본값이다. `-p`로 지정하면 보관 프로젝트도 보인다(과거 확인용). 이월 후보에서는 항상 뺀다.
3. **타이머 시간 규칙:**
   - 경과는 30초 반올림이다. 1분 미만과 24시간 초과는 거부하고 타이머를 남긴다.
   - 기록 날짜는 시작한 날이다.
   - `--round N`은 1~60이고, 결과가 0이면 한 단위로 올린다.
   - 24시간 상한은 `lb add`와 같은 규칙이다.
4. **lb start -t 편의:** 메모를 생략하면 태스크 제목을 쓰고, todo 태스크는 doing으로 바꾼다. SPEC 1의 "10초 안에 기록" 목표에 맞추려는 것이다. `lb task start` + `lb start` 두 번 칠 필요가 없다.
5. **stop은 재검증하지 않는다:** 시작한 뒤 프로젝트를 보관하거나 카테고리 설정을 바꿔도 타이머를 저장할 수 있다. 그렇지 않으면 타이머가 저장도 취소도 아닌 상태로 남는다(취소는 시간을 잃는다).
6. **이월 범위:**
   - 정확히 원본 주에 계획된 todo·doing만 옮긴다. 더 이전 주의 밀린 태스크는 옮기지 않는다.
   - 원본 주는 `-w`로 고른다. 월요일에 지난주 것을 옮기려면 `-w last`를 쓴다.
   - 확인 뒤에 대상을 다시 검사해 바뀐 것은 건너뛴다.
7. **plan 범위:** todo·doing·done을 보이고 dropped는 뺀다. 완료한 것도 그 주 계획의 일부이므로 실적과 함께 보인다.
8. **task edit 범위:** 프로젝트는 바꾸지 않는다(`update_task`도 지원하지 않음). 연결된 기록과 프로젝트가 어긋나는 것을 막기 위해서다. 필요하면 drop 후 다시 만든다.
9. **상태 표기:** 화면에는 key(todo …)를 쓴다. 화면 값을 그대로 `--status`에 쓸 수 있게 하려는 것으로, 카테고리 key 표시와 같은 원칙이다.
10. **새 의존성 없음, 스키마 변경 없음.** 마이그레이션이 필요 없다.

## 사용자 결정 (2026-10-08 승인 게이트에서 확정)

- **T1. 태스크 수정 범위:** `lb task edit` 추가(추천안). rm은 넣지 않고 drop으로 대신한다.
- **T2. 기본 범위:** `lb task list`는 todo·doing, `lb plan`은 이번 주(추천안).
- **T3. `lb stop --note`:** 시작 메모 뒤에 ` — `로 덧붙인다(추천안).
- **T4. 확인 프롬프트:** `lb plan carry`와 `lb cancel` 모두 미리보기 + `[y/N]` 확인, `--yes`로 생략(추천안).

## 후속 항목 (Phase 3 범위 밖, 기록만)

1. **동시 타이머 시작 경합:** 두 터미널이 같은 순간에 `lb start`를 실행하면 `IntegrityError`로 traceback이 날 수 있다. Phase 5에서 Web 타이머를 붙일 때 core에서 `DatabaseBusyError`처럼 변환한다.
2. **태스크 삭제·프로젝트 이동:** 요청이 있으면 `lb task rm`(연결 기록은 FK `SET NULL`)과 프로젝트 이동(연결 기록 처리 정책 필요)을 정한다.
3. **밀린 태스크:** 원본 주보다 이전 주에 계획된 미완료 태스크를 모아 보거나 이월하는 기능(`lb task list --overdue` 등).
4. **Phase 2 후속 항목 1(core 오류 문구에 CLI 문법 포함):** 타이머 문구(`'lb stop'`, `'lb cancel'`)도 같은 정책 대상이다. Phase 5 전에 함께 정한다.
5. **타이머 자동 정지 경고:** 24시간이 넘은 타이머를 `lb status`에서 미리 경고할지(현재는 stop 때 거부만).
