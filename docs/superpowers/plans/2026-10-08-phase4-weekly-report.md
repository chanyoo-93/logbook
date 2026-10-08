# Phase 4 구현 계획 (주간보고서와 백업)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 다음을 구현한다.
- 주간 기록과 태스크로 SPEC 7장 형식의 주간업무보고 Markdown을 만드는 `lb report`
- 전체 데이터를 JSONL로 백업·복원하는 `lb export`, `lb import`

**Architecture:**
- **보고서 데이터 조립:** `core.services.weekly_report()`가 DB에서 읽어 불변 데이터(`core.report.ReportData`)를 만든다. 서비스는 DB에 접근하는 유일한 계층이다.
- **렌더링:** `core.report.render_markdown()`이 Jinja2 템플릿으로 Markdown을 만든다.
  - 기본 템플릿은 패키지 안의 `core/templates/report.md.j2`다.
  - 사용자는 설정 파일과 같은 폴더의 `report.md.j2`로 템플릿을 바꿀 수 있다.
  - 숫자·시간 표기는 파이썬에서 미리 만들어 템플릿에는 문자열로 넘긴다. 템플릿이 단순해지고 사용자 템플릿도 같은 표기를 쓰게 된다.
- **백업:** `core.services.export_records()` / `import_records()`가 JSONL 레코드를 만들고 받는다.
  - 복원은 빈 DB(`lb init` 직후)에만 하고, ID를 그대로 보존한다(결정 R3).
- **CLI 규칙:** Phase 2·3의 "CLI 공통 규칙"을 그대로 따른다. CLI는 jinja2와 pyperclip을 직접 import하지 않는다. 렌더링은 `core.report`의 `render_markdown`·`user_template_path`를 명령 함수 안에서(세션을 닫은 뒤) 지연 import해 부르고, 클립보드는 `core.platform.copy_to_clipboard`를 `platform` 모듈 속성으로 부른다(`platform` 모듈은 명령 모듈 상단에서 import한다. Task 4-3의 테스트 준비 규칙). jinja2는 `render_markdown` 안에서, pyperclip은 `copy_to_clipboard` 안에서만 로드된다(기존 import 가드가 강제). CLAUDE.md·AGENTS.md의 허용 목록 갱신은 Task 4-7에서 한다.
- **스키마:** 바뀌지 않는다. 특이사항 절(`week_notes`)은 빈 자리로 둔다(결정 R2).

**Tech Stack:** Python 3.11+(CI는 3.12), uv, Typer 0.27, Rich 15, SQLAlchemy 2.1, Jinja2 3.1(이미 의존성), pyperclip(이미 의존성), pytest, ruff, mypy(strict는 core만). 새 의존성은 없다.

**선행 조건:**
- **브랜치:** `feat/phase4-weekly-report`(develop `eeff16e`에서 분기, 이미 만들어 둠)
- **uv PATH:** 이 PC에서는 uv가 PATH에 없다.
  - Git Bash: `export PATH="/c/Users/User/AppData/Local/Microsoft/WinGet/Packages/astral-sh.uv_Microsoft.Winget.Source_8wekyb3d8bbwe:$PATH"`
  - PowerShell: `$env:Path = "$env:LOCALAPPDATA\Microsoft\WinGet\Packages\astral-sh.uv_Microsoft.Winget.Source_8wekyb3d8bbwe;$env:Path"`
- **사용자 결정:** 문서 끝의 R1~R4는 2026-10-08 승인 게이트에서 확정했다(모두 추천안).
- **Task 공통 완료 조건:** 아래 명령을 모두 통과한 뒤 커밋한다.
  - `uv run ruff check .`
  - `uv run ruff format --check .`
  - `uv run mypy src/logbook/core`
  - `uv run pytest`
- **커밋 메시지:** Conventional Commits 형식이다. type만 영어이고 설명은 한국어로 쓴다.
- **TDD:** 각 Task는 실패하는 테스트를 먼저 쓰고(RED), 최소 구현으로 통과시킨 뒤(GREEN), 정리한다.
- **사용자 문구 규칙(Phase 3에서 정함):**
  - 변수 값 바로 뒤에 조사를 붙이지 않는다. 예: `프로젝트를 찾을 수 없습니다: '{slug}'`처럼 쓴다.
  - core 문구에는 `—` 같은 기호를 넣지 않는다.

---

## 파일 구조

| 파일 | 구분 | 책임 |
|---|---|---|
| `src/logbook/core/report.py` | 생성 | 보고서 데이터 클래스(`ReportData` 등), `render_markdown()`, 템플릿 경로 결정, 템플릿 오류의 한국어 변환. jinja2는 함수 안에서 import한다 |
| `src/logbook/core/templates/report.md.j2` | 생성 | 기본 보고서 템플릿 |
| `src/logbook/core/services/report.py` | 생성 | `weekly_report()`: 한 주의 기록·태스크로 `ReportData`를 조립한다 |
| `src/logbook/core/services/backup.py` | 생성 | `export_records()`, `import_records()`, `BackupCounts`, JSONL 레코드 형식과 검증 |
| `src/logbook/core/services/__init__.py` | 수정 | 새 함수 공개 |
| `src/logbook/cli/runtime.py` | 수정 | `OutOpt`, `prepare_output_path()`, `write_text_file()`(덮어쓰기 확인, UTF-8·LF, 오류 변환) |
| `src/logbook/cli/console.py` | 수정 | `print_raw()`: 보고서를 줄바꿈 그대로 stdout에 쓴다(마크업 해석·줄 접기 없음) |
| `src/logbook/core/config.py` | 수정 | `_expand_home()`을 공개 함수 `expand_home()`으로 바꾼다(`~name`은 두 OS 모두 거부). 설정·환경변수와 `--out`·가져올 파일 경로가 같은 규칙을 쓴다 |
| `src/logbook/cli/commands/report.py` | 생성 | `lb report` |
| `src/logbook/cli/commands/data.py` | 생성 | `lb export`, `lb import` |
| `src/logbook/cli/main.py` | 수정 | 명령 등록 |
| `tests/core/test_report_render.py`, `tests/core/test_services_report.py`, `tests/core/test_services_backup.py` | 생성 | core 테스트 |
| `tests/cli/test_report.py`, `tests/cli/test_data.py` | 생성 | CLI 테스트 |
| `tests/cli/test_entry.py`, `tests/cli/test_runtime.py`, `tests/cli/test_console.py` | 수정 | import 가드, 파일 쓰기 도우미, `print_raw` |
| `README.md`, `docs/SPEC.md`, `docs/ROADMAP.md`, `CLAUDE.md`, `AGENTS.md` | 수정 | 사용법, 명세 보강(R1~R4), 체크박스, 디렉터리 설명 |

---

## Phase 4 공통 규칙

### 보고서 표기
| 대상 | 형식 | 예 |
|---|---|---|
| 제목 | `cfg.report.title_format.format(start=..., end=...)`, `start`·`end`는 `YYYY-MM-DD` 문자열(str) | `주간업무보고 (2026-09-28 ~ 2026-10-04)` |
| 작성자 | `cfg.report.author`가 비면 줄 생략 | `작성자: 홍길동` |
| 시간 | `format_duration`, 0분은 `-`(표 안), `0m`(문장 안) | `19h`, `1h 30m` |
| 비율 | 정수 반올림(half-up), 합계나 값이 0이면 `-` | `54%` (CLI `render.percent`와 같은 규칙. core에 `report.percent_text`로 둔다) |
| 표 열 이름 | 설정의 카테고리 라벨(`lb stats`와 같음). 기록이 있는 카테고리만 | `개발`, `코드리뷰`, `행정/기타` |
| 태스크 상태 | `[완료]`, `[진행]`, `[할 일]`, `[중단]` | |
| 태스크 줄 | `- [완료] 결제 재시도 로직 구현 (#42) — 실제 8h / 예상 6h` | 진행·할 일·중단은 `누적`, 예상이 없으면 ` / 예상 …` 생략 |
| 기타 줄 | `- 기타: 코드리뷰 3h, 운영/배포/장애 30m` | 태스크에 연결되지 않은 기록을 카테고리 라벨별로 합산한다. 시간 내림차순이고, 같으면 공수 요약 표의 열 순서(설정 순서, 설정에 없는 key는 그 뒤에 key 이름 순)를 따른다. 라벨이 같은 key가 여럿이면 한 항목으로 합치고 그중 앞선 key의 열 순서를 쓴다 |
| 다음 주 계획 항목 | `- 환불 API 구현 (#44) — 예상 8h`, 예상 없으면 `- 환불 API 구현 (#44)` | 이번 주에서 넘어온 후보는 끝에 ` (이월 후보)` |

- Markdown 표 안의 사용자 값(프로젝트 slug, 카테고리 라벨)에 있는 `|`는 `\|`로 이스케이프한다. 목록 줄(제목)은 그대로 둔다.
- 보고서 조립(`services/report.py`)에서 태스크 제목과 카테고리 라벨은 `" ".join(text.split())`로 한 줄로 정리한다(줄바꿈, 탭, U+0085, U+2028, U+2029, 연속 공백을 공백 하나로). 표 칸·목록 줄·사용자 템플릿이 모두 한 줄 값을 받고, stdout과 파일이 달라지지 않는다.
- 보고서 문자열은 항상 `\n` 줄바꿈이고 마지막 줄 뒤에 `\n`이 하나 있다.

### 시간대
- 완료 태스크 수는 `done_at`(UTC)을 로컬 날짜로 바꿔 그 주 범위인지 본다. `weekly_report(..., tz=...)`는 CLI에서 `runtime.now().tzinfo`를 받는다. core는 시각을 직접 만들지 않는다(Phase 3 규칙). 이 tz는 현재 시점의 UTC 오프셋 고정 값이라 DST를 반영하지 않는다. DST 지역에서 다른 DST 기간의 주를 보고하면 주 경계 1시간 안의 완료가 옆 주로 셀 수 있다(한국은 영향 없음). CLI 테스트의 `done_at`은 날짜 경계에서 먼 값(정오 부근)으로 넣는다.

### 파일 쓰기 (lb report --out, lb export)
- 경로는 설정·환경변수와 같은 규칙으로 바꾼다. `core.config._expand_home(raw, where)`를 공개 함수 `expand_home(raw, where) -> Path`로 바꿔 쓴다(config.py 안의 호출 네 곳도 같이 고친다). `~`, `~/…`, `~\…`만 홈 기준으로 바꾸고 `~name…`은 두 OS 모두 `InvalidInputError`(`경로가 올바르지 않습니다: --out 값 '~name/x.md'. 홈 디렉터리 기준 경로는 '~/'로 시작하세요.`)로 거부한다. `Path.expanduser()`는 쓰지 않는다(macOS는 `RuntimeError`, Windows는 다른 사용자 프로필 경로로 바꾼다). `where`는 `lb report`·`lb export`가 `"--out"`, `lb import`가 `"가져올 파일 경로"`다. 상대 경로는 현재 폴더 기준이다.
- 쓰기는 `encoding="utf-8", newline="\n"`이다.
- **검사 순서(반드시 이 순서, 예외 종류로 판정하지 않는다):** Windows는 폴더를 열면 `IsADirectoryError`가 아니라 `PermissionError`(errno 13)를 내고 macOS는 `IsADirectoryError`를 낸다. 존재 확인을 폴더 검사보다 먼저 하면 `-o .`에서 폴더 문구 대신 덮어쓰기 질문이 먼저 나온다.
  1. `runtime.prepare_output_path(path_text) -> Path`(DB·설정 없이 끝나는 검증이라 명령 본문 맨 앞에서 부른다): ① `expand_home(path_text, "--out")` ② `path.is_dir()`이면 아래 폴더 문구 ③ `not path.parent.is_dir()`이면 아래 폴더 없음 문구(부모가 없거나 파일인 경우 모두)
  2. `runtime.write_text_file(path, text, *, yes) -> None`(렌더링·내보내기를 마친 뒤 부른다): ④ `path.exists()`이고 `yes`가 False이면 아래 확인 흐름 ⑤ `path.write_text(text, encoding="utf-8", newline="\n")`이고 `OSError`는 아래 그 밖의 문구
- 확인 흐름(결정 R4): 파일이 이미 있고 `--yes`가 없으면 `runtime.require_confirmation` 질문 `파일이 이미 있습니다: {path}\n덮어쓸까요?`를 쓴다.
  - 거절: `덮어쓰지 않았습니다.`
  - 입력 없음: `확인 입력을 받지 못해 덮어쓰지 않았습니다. 확인 없이 덮어쓰려면 --yes를 붙이세요.`
  - 둘 다 exit 1이다.
- 오류 문구:
  - 폴더가 없으면: `저장할 폴더가 없습니다: {parent}. 폴더를 먼저 만들거나 다른 경로를 지정하세요.`
  - 경로가 폴더면: `파일 경로가 아니라 폴더입니다: {path}. 파일 이름까지 지정하세요.`
  - 그 밖의 `OSError`: `파일을 저장하지 못했습니다: {path} ({error.strerror or error}).` (`strerror`가 None일 수 있다)
- 파일 이름은 사용자가 준 그대로 쓴다. 기본 이름을 만들 때만 `platform.timestamp_for_filename`를 쓴다.
- 경로 표기: 성공·확인·오류 문구의 `{path}`는 `prepare_output_path`가 돌려준 Path를 `Text(str(path))`로 쓴다. 상대 경로는 그대로 보여 준다(Windows에서는 구분자가 역슬래시다).

---

## Task 4-0: 계획 문서 저장

- [x] 이 문서를 커밋한다: `docs: Phase 4 주간보고서·백업 구현 계획 추가`

---

## Task 4-1: core — 보고서 데이터 조립

**Files:**
- Create: `src/logbook/core/report.py`(데이터 클래스와 `percent_text`만), `src/logbook/core/services/report.py`, `tests/core/test_services_report.py`
- Modify: `src/logbook/core/services/__init__.py`

```python
# core/report.py (SQLAlchemy를 import하지 않는다)
@dataclass(frozen=True)
class MatrixRow:
    project: str                 # slug
    cells: tuple[str, ...]       # categories 순서의 시간 표기, 0이면 "-"
    total: str
    percent: str

@dataclass(frozen=True)
class TaskLine:
    status: str                  # "완료" | "진행" | "할 일" | "중단"
    title: str
    task_id: int
    actual: str                  # 보고 주 마지막 날까지의 누적(이번 주만이 아님)
    estimate: str | None
    actual_label: str            # "실제"(완료) | "누적"

@dataclass(frozen=True)
class ProjectSection:
    project: str
    total: str                   # 이번 주 이 프로젝트 합계
    tasks: tuple[TaskLine, ...]
    others: tuple[tuple[str, str], ...]   # (카테고리 라벨, 시간), 비면 기타 줄 생략

@dataclass(frozen=True)
class PlanItem:
    title: str
    task_id: int
    estimate: str | None
    carried: bool                # 이번 주 미완료에서 넘어온 후보

@dataclass(frozen=True)
class PlanGroup:
    project: str
    estimate_total: str          # 예상 합계, 하나도 없으면 "0m"
    items: tuple[PlanItem, ...]

@dataclass(frozen=True)
class ReportData:
    title: str
    author: str
    week_label: str              # "2026-W40"
    start: str                   # "2026-09-28"
    end: str
    total: str                   # "35h"
    log_count: int
    done_task_count: int
    categories: tuple[str, ...]  # 표 머리글(라벨)
    matrix: tuple[MatrixRow, ...]
    sections: tuple[ProjectSection, ...]
    plan: tuple[PlanGroup, ...]

def percent_text(part: int, total: int) -> str  # half-up, total/part 0이면 "-"

# core/services/report.py
def weekly_report(
    s: Session, week: Week, *, tz: tzinfo, title_format: str, author: str,
    category_labels: Mapping[str, str],
) -> ReportData
```

조립 규칙(SPEC 7장):
1. **공수 요약:** `stats_matrix(s, week, category_order=tuple(category_labels))`를 재사용한다. 열 머리글은 `category_labels.get(key, key)`이고, 비율은 프로젝트 합계 / 주 합계다. 기록이 없는 주는 `matrix=()`, `total="0m"`.
2. **완료 태스크 수:** `status == DONE`이고 `done_at.astimezone(tz).date()`가 주 범위 안인 태스크 수(보관 프로젝트 포함).
3. **프로젝트별 실적:** 순서는 공수 요약과 같다(합계 내림차순).
   - 이번 주 기록 중 태스크에 연결된 것은 태스크 단위로 묶는다. 순서는 상태 순(완료 `done` → 진행 `doing` → 할 일 `todo` → 중단 `dropped`)이고, 같은 상태 안에서는 id 오름차순이다. `TaskLine.status`는 done→"완료", doing→"진행", todo→"할 일", dropped→"중단"이다.
   - 시간은 보고 주 마지막 날까지의 누적이다. `WorkLog.task_id IN (…) AND WorkLog.date <= week.end` 조건의 태스크별 합계를 쿼리 한 번으로 구한다(`actual_minutes_by_task`는 기간 조건이 없어 쓰지 않는다). 지난 주 보고서가 그 뒤의 기록 때문에 달라지지 않게 하려는 것이다.
   - 상태는 현재 값을 쓰되 완료만 보정한다. `status`가 `done`이어도 `done_at`의 로컬 날짜(`done_at.astimezone(tz).date()`)가 `week.end`보다 뒤면 `진행`/`누적`으로 쓴다(그 주 끝에는 아직 완료가 아니었다. 규칙 2의 완료 수와 같은 기준이다). 진행·할 일·중단은 상태 변경 이력이 없어 현재 값을 쓴다. 정렬과 `actual_label`은 이 보정 뒤의 상태로 정한다.
   - 태스크에 연결되지 않은 이번 주 기록은 카테고리 라벨별로 합산해 `others`에 넣는다.
   - 2절은 이번 주 기록으로만 만든다(핵심 개념: 실적은 WorkLog 집계이고 Task 목록을 실적으로 쓰지 않는다). 이번 주 기록이 없는 태스크는 이번 주에 완료했더라도 2절에 넣지 않고, 이번 주 기록이 없는 프로젝트는 절을 만들지 않는다. 그래서 1절의 완료 태스크 수(규칙 2, 완료 시각 기준)와 2절의 `[완료]` 줄 수(이번 주 기록이 있는 태스크의 보고 주 기준 상태)는 다를 수 있다. 의도한 차이이므로 맞추지 않는다.
4. **다음 주 계획:**
   - 대상: `planned_week == week.next()`인 todo·doing 태스크, 그리고 `planned_week == week`인 todo·doing 태스크(`carried=True`).
   - 보관 프로젝트는 뺀다(`list_tasks` 기본값).
   - 프로젝트 slug 순, 같은 프로젝트 안에서는 다음 주 계획 → 이월 후보 순, 각각 id 순이다.
   - `estimate_total`은 항목들의 예상 합계다.
5. **제목:** `title_format.format(start=week.start.isoformat(), end=week.end.isoformat())`이다.
   - `start`·`end`는 `date`가 아니라 `ReportData.start`·`end`와 같은 `YYYY-MM-DD` 문자열(str)로 넘긴다. `date`를 넘기면 `{start:%-m}` 같은 strftime 지정자가 macOS에서는 동작하고 Windows에서는 `ValueError`가 되어 두 OS의 결과가 달라진다.
   - `try`에는 이 `format` 호출 하나만 둔다. 이 호출이 내는 `KeyError`, `IndexError`, `AttributeError`, `TypeError`, `ValueError`를 모두 `raise ... from error`로 `InvalidInputError`로 바꾼다(없는 이름, 위치 인자, 짝이 맞지 않는 중괄호, 잘못된 변환·형식 지정자, 속성·인덱스 접근).
   - 문구: `보고서 제목 형식이 올바르지 않습니다: '{title_format}'. 사용할 수 있는 이름: {start}, {end}`
   - 이 문구에서 `{start}`, `{end}`는 글자 그대로 보여 준다.

**테스트 데이터 주의:** 완료 태스크의 `done_at`은 `set_task_status`(실제 현재 시각)가 아니라 같은 세션에서 보고 주 안의 고정 시각(`datetime(2026, 9, 30, 3, 0, tzinfo=UTC)`, W40 안이고 정오 부근이라 날짜 경계와 멀다)으로 직접 넣는다. 실제 시각은 W40 뒤라 위 보정에 걸려 `진행`으로 바뀐다. `done_task_count`의 기대값은 고정 값으로 적는다.

**테스트 케이스: test_services_report.py** (`FIXED` 주 2026-W40, 고정 시간대 UTC+9)
| 케이스 | 기대 |
|---|---|
| 빈 주 | `total="0m"`, `log_count=0`, `matrix=()`, `sections=()`, `plan=()` |
| Task 4-2의 기본 템플릿 출력 예시와 같은 시간·태스크 구성(payment·admin·common 세 프로젝트, 카테고리 넷)의 데이터를 서비스로 만든다 | matrix 행·열·비율, 태스크 줄, 기타 줄, 계획 그룹이 예시와 같다. 열 머리글이 라벨이다. 기록 건수·완료 수는 만든 데이터에 맞게 쓰고, 완료 태스크의 `done_at`을 직접 넣어 `done_task_count` 기대값을 적는다 |
| `percent_text` | `(0, 100)`·`(1, 0)` → `-`, `(1, 8)` → `13%`(half-up) |
| 태스크에 연결된 기록 둘(이번 주) + 이전 주 기록 | TaskLine 하나, actual은 이전 주 기록을 포함한 누적 |
| 지난주 보고서: 태스크에 지난주 2h·이번 주 1h 기록, 이번 주 완료 | `[진행]`, `누적` 2h, `done_task_count == 0` (이번 주 기록과 완료는 지난주 보고서에 들어가지 않는다) |
| 한 프로젝트에만 이번 주 기록이 있고, 그 기록이 태스크 다섯(#1 doing, #2 done, #3 dropped, #4 todo, #5 done)에 하나씩 연결됨. done 태스크의 `done_at`은 이번 주 안의 고정 시각 | `[(t.task_id, t.status) for t in data.sections[0].tasks] == [(2, "완료"), (5, "완료"), (1, "진행"), (4, "할 일"), (3, "중단")]` (id 오름차순·내림차순·상태 후 id 내림차순 구현을 모두 잡는다) |
| 완료 태스크, 예상 없음 | `actual_label="실제"`, `estimate=None` |
| 연결되지 않은 기록: ops 30m, review 3h | `others == (("코드리뷰","3h"), ("운영/배포/장애","30m"))` |
| 연결되지 않은 기록: 설정에서 라벨이 같은 두 key(`dev`·`dev2`, 라벨 `개발`) 각 30m, 설정에 없는 key `zeta`·`alpha` 각 1h | `others == (("개발", "1h"), ("alpha", "1h"), ("zeta", "1h"))` (동률은 설정 순서가 먼저, 미등록 key는 이름 순, 같은 라벨은 한 항목) |
| 설정에 없는 카테고리 기록 | 라벨 대신 key |
| 제목 `"첫 줄\n# 둘째\t끝"`, 라벨에 줄바꿈이 든 설정 | `TaskLine.title == "첫 줄 # 둘째 끝"`, 표 머리글 라벨이 한 줄 |
| `done_at`이 UTC로는 전 주 일요일 23:30, KST로는 월요일 | 이번 주 완료로 센다 |
| W39에만 2h 기록하고 W40(KST)에 완료한 태스크, W40 기록은 없음 | `done_task_count == 1`, `matrix == ()`, `sections == ()` |
| W39에 완료했고 W40에도 기록이 있는 태스크 | 그 프로젝트 절에 `status == "완료"`, `actual_label == "실제"`인 TaskLine이 있고 `done_task_count == 0` |
| 다음 주 계획: W41 todo, W41 done, W40 doing, W40 done, 보관 프로젝트 W41 todo | W41 todo + W40 doing(carried), 나머지 제외 |
| 다음 주 계획 순서: payment W41 todo #7, payment W40 doing #3, payment W41 doing #5, admin W40 todo #9 | plan 그룹 `admin`(#9 이월 후보), `payment`(#5, #7, #3 이월 후보) |
| 예상 합계 | 두 항목 4h+8h → `12h`, 하나도 없으면 `0m` |
| `title_format="보고 {start}~{end}"` | 제목 반영 |
| `title_format`이 `"보고 {foo}"`, `"{0}"`, `"보고 {"`, `"}"`, `"보고 ({start} ~ {end)"`, `"{start:%m/%d}"`, `"{start!x}"`, `"{start.year}"`, `"{start[a]}"` 각각 | 모두 위 문구(`'{title_format}'` 자리에 그 값), traceback 없음. `{start:%m/%d}`·`{start.year}`는 문자열로 넘겨야 오류가 난다 |
| 기록 100건 이상 | 데이터를 만든 뒤 `session.expire_all()`을 부르고 `before_cursor_execute` 리스너로 쿼리를 센다(tests/core/test_services_tasks.py의 `_count_queries`와 같은 패턴을 쓰되 그 비공개 함수를 import하지 않는다). 기록 1건일 때와 120건(여러 태스크에 나눠 연결, 연결 안 한 기록 포함)일 때 `weekly_report`의 쿼리 수가 같다. `expire_all`이 없으면 identity map 때문에 N+1이 드러나지 않는다 |

- [x] RED → GREEN → 커밋 `feat: 주간보고서 데이터 조립 서비스 추가`

---

## Task 4-2: core — Markdown 렌더링과 템플릿

**Files:**
- Create: `src/logbook/core/templates/report.md.j2`, `tests/core/test_report_render.py`
- Modify: `src/logbook/core/report.py`

```python
TEMPLATE_NAME = "report.md.j2"

def user_template_path(config_file: Path) -> Path    # config_file.parent / TEMPLATE_NAME
def render_markdown(data: ReportData, *, template_path: Path | None = None) -> str
    """template_path가 있고 파일이 있으면 그 템플릿, 아니면 기본 템플릿."""
```

- **Jinja2 환경:**
  - `jinja2.Environment(autoescape=False, keep_trailing_newline=True, trim_blocks=True, lstrip_blocks=True, undefined=jinja2.StrictUndefined)`
  - 필터 `cell`: 표 칸의 `|`를 `\|`로 바꾼다.
- **기본 템플릿 읽기:** `importlib.resources.files("logbook.core").joinpath("templates/report.md.j2").read_text(encoding="utf-8")`. 휠 설치에서도 동작해야 한다.
- **사용자 템플릿 읽기:** `encoding="utf-8-sig"`(BOM 허용). 템플릿은 `env.from_string(source)`로 컴파일한다.
- **템플릿 변수:** `data`(ReportData) 하나만 넘긴다.
- **출력 정리:** CRLF를 `\n`으로 바꾸고, 끝의 빈 줄을 하나의 `\n`으로 맞춘다.
- **오류 변환:** 사용자 템플릿에서 난 오류만 `InvalidInputError`로 바꾼다(기본 템플릿에서 난 오류는 버그이므로 바꾸지 않는다). 파일 경로는 항상 보여 주고, 줄 번호는 구할 수 있을 때 보여 준다.
  - 줄 번호: `TemplateSyntaxError`(if 밖에서 없는 필터를 쓴 `TemplateAssertionError` 포함)는 `error.lineno`다. 렌더링 중 예외는 `traceback.extract_tb(error.__traceback__)`에서 `filename == "<template>"`인 마지막 프레임의 `lineno`다(`UndefinedError`에는 `lineno` 속성이 없다). 찾지 못하면 문구에서 `{lineno}번째 줄: ` 부분만 뺀다.
  - 읽기 `UnicodeDecodeError`(메모장 ANSI·cp949로 저장, PowerShell 5.1의 `>`·`Out-File`이 만드는 UTF-16 파일 등): `보고서 템플릿을 UTF-8로 읽을 수 없습니다: {path}. 파일을 UTF-8로 다시 저장하세요.`
  - 읽기 `OSError`: `보고서 템플릿 파일을 열 수 없습니다: {path} ({error.strerror or error}).`
  - `TemplateSyntaxError`: `보고서 템플릿을 읽지 못했습니다: {path} ({lineno}번째 줄: {message}). 기본 템플릿을 쓰려면 이 파일을 지우거나 이름을 바꾸세요.`
  - 렌더링 중 `UndefinedError`: `보고서 템플릿에 없는 값을 썼습니다: {path} ({lineno}번째 줄: {message}). 쓸 수 있는 값은 README의 '보고서 템플릿' 절을 보세요.`
  - 렌더링 중 그 밖의 `Exception`(if 블록 안의 없는 필터·테스트가 내는 `TemplateRuntimeError`, 로더가 없어 `{% include %}`·`{% extends %}`·`{% import %}`가 내는 `TypeError`, 식 오류의 `TypeError`·`ZeroDivisionError` 등): `보고서 템플릿을 처리하지 못했습니다: {path} ({lineno}번째 줄: {type(error).__name__}: {error}). 템플릿을 고치거나, 기본 템플릿을 쓰려면 이 파일을 지우거나 이름을 바꾸세요.`
  - `{message}`는 Jinja2의 영어 문구 그대로다(예: `'foo' is undefined`).
- **기본 템플릿 출력** (SPEC 7장 형식, `include_commits` 부록은 이번 범위 밖이라 넣지 않음). 절(`##`) 사이와 프로젝트 소절(`###`) 사이에는 빈 줄 하나를 둔다. 목록 줄 사이에는 빈 줄이 없다.
  ```markdown
  # 주간업무보고 (2026-09-28 ~ 2026-10-04)
  작성자: 홍길동

  ## 1. 공수 요약
  총 35h (기록 41건, 완료 태스크 6건)

  | 프로젝트 | 개발 | 코드리뷰 | 회의 | 행정/기타 | 합계 | 비율 |
  |---|---|---|---|---|---|---|
  | payment | 14h | 3h | 2h | - | 19h | 54% |
  | admin | 6h | 1h | 1h | - | 8h | 23% |
  | common | - | - | 5h | 3h | 8h | 23% |

  ## 2. 프로젝트별 실적
  ### payment (19h)
  - [완료] 결제 재시도 로직 구현 (#42) — 실제 8h / 예상 6h
  - [진행] 환불 API 설계 (#43) — 누적 3h / 예상 4h
  - 기타: 개발 3h, 코드리뷰 3h, 회의 2h

  ### admin (8h)
  - [진행] 권한 정리 (#45) — 누적 6h / 예상 10h
  - 기타: 코드리뷰 1h, 회의 1h

  ### common (8h)
  - 기타: 회의 5h, 행정/기타 3h

  ## 3. 특이사항 / 리스크
  (작성하세요)

  ## 4. 다음 주 계획
  ### admin (예상 10h)
  - 권한 정리 (#45) — 예상 10h (이월 후보)

  ### payment (예상 12h)
  - 환불 API 구현 (#44) — 예상 8h
  - 환불 API 설계 (#43) — 예상 4h (이월 후보)
  ```
  - 기록이 없는 주(`matrix`와 `sections`가 빔)는 1절이 표 없이 `총 0m (기록 0건, 완료 태스크 {data.done_task_count}건)` 한 줄이고 완료 수는 `data.done_task_count`를 그대로 출력한다. 계획이 없으면 4절은 `계획된 태스크가 없습니다.` 한 줄이다. 작성자가 비면 `작성자:` 줄을 뺀다. 작성자가 없는 빈 주의 전체 출력(`완료 태스크 0건`일 때):
  ```markdown
  # 주간업무보고 (2026-09-28 ~ 2026-10-04)

  ## 1. 공수 요약
  총 0m (기록 0건, 완료 태스크 0건)

  ## 2. 프로젝트별 실적
  기록이 없습니다.

  ## 3. 특이사항 / 리스크
  (작성하세요)

  ## 4. 다음 주 계획
  계획된 태스크가 없습니다.
  ```

**테스트:**
- 위 예시(세 프로젝트)와 빈 주 예시를 ReportData로 직접 만들어 전체 문자열을 정확히 비교한다.
- 빈 주, 작성자 없음, 계획 없음, 표 칸의 `|` 이스케이프를 확인한다.
- 빈 주인데 `done_task_count == 2`이면 1절이 "총 0m (기록 0건, 완료 태스크 2건)", 2절이 "기록이 없습니다."인지 확인한다.
- 사용자 템플릿 재정의(`{{ data.title }}` 한 줄), BOM 있는 사용자 템플릿, 경로는 있지만 파일이 없을 때 기본 템플릿을 쓰는지 확인한다.
- 문법 오류·없는 변수 문구를 정확히 비교한다(줄 번호 포함).
- 아래를 각각 만들어 한국어 문구와 줄 번호를 확인한다(`{message}`가 Jinja2 영어 문구인 곳은 접두 한국어와 줄 번호는 `==`로, `{message}` 부분은 `in`으로 확인한다). CLI(Task 4-3)에서는 같은 파일로 `오류: …` 한 줄, exit 1, traceback 없음을 확인한다.
  - cp949로 저장한 한글 사용자 템플릿, UTF-16으로 저장한 템플릿
  - `{{ data.titel }}`(오타), `{{ foo }}`
  - `{% if data.author %}{{ data.author | nofilter }}{% endif %}`(if 안의 없는 필터)와 if 밖의 없는 필터(`TemplateAssertionError`)
  - `{{ data.log_count + "건" }}`, `{{ 1 / 0 }}`, `{% include 'x.j2' %}`
- CRLF 사용자 템플릿도 LF로 나오는지 확인한다.
- `importlib.resources` 경로가 실제 파일인지 확인한다.
- 휠 포함 확인(`@pytest.mark.subprocess`):
  - uv는 `os.environ.get("UV") or shutil.which("uv")`로 찾는다. 둘 다 없으면 `pytest.skip("uv가 없어 휠 빌드를 건너뜁니다")`.
  - 빌드: `subprocess.run([uv, "build", "--wheel", "--out-dir", str(tmp_path), str(repo_root)], shell=False, capture_output=True, timeout=300)`. `repo_root = Path(__file__).resolve().parents[2]`. `--out-dir`를 빼면 저장소 `dist/`에 쓰므로 반드시 넣는다. returncode가 0이 아니면 stderr를 붙여 실패시킨다.
  - 첫 실행은 build backend(hatchling)를 내려받으므로 네트워크나 uv 캐시가 필요하다(CI와 `uv sync` 뒤에는 캐시가 있다). 3~6초 걸린다.
  - `zipfile.ZipFile(next(tmp_path.glob("*.whl"))).namelist()`에 `logbook/core/templates/report.md.j2`가 있는지 확인한다.

- [ ] RED → GREEN → 커밋 `feat: 주간보고서 Markdown 렌더링과 기본·사용자 템플릿 추가`

---

## Task 4-3: CLI — lb report

**Files:**
- Create: `src/logbook/cli/commands/report.py`, `tests/cli/test_report.py`
- Modify: `src/logbook/cli/runtime.py`(`OutOpt`, `prepare_output_path`, `write_text_file`), `src/logbook/cli/console.py`(`print_raw`), `src/logbook/core/config.py`(`_expand_home` → `expand_home` 공개. 기존 테스트는 `_expand_home`을 직접 참조하지 않아 이름 변경으로 깨지지 않는다), `src/logbook/cli/main.py`, `tests/cli/test_runtime.py`, `tests/cli/test_console.py`, `tests/cli/test_entry.py`

```python
# runtime.py
OutOpt = Annotated[str | None, typer.Option("--out", "-o", help="저장할 파일 경로")]
def prepare_output_path(path_text: str) -> Path
    """공통 규칙 '파일 쓰기'의 ①~③. DB·설정 없이 하는 검증이라 명령 본문 맨 앞에서 부른다."""
def write_text_file(path: Path, text: str, *, yes: bool) -> None
    """공통 규칙 '파일 쓰기'의 ④~⑤. 확인·거절은 require_confirmation, 오류는 LogbookError."""
```

| 옵션 | 짧은 | 기본값 | 의미 |
|---|---|---|---|
| `--week` | `-w` | `this` | 보고 주차 |
| `--out` | `-o` | 없음 | 파일로 저장 |
| `--copy` | | False | 클립보드에 복사 |
| `--yes` | `-y` | False | 덮어쓰기 확인 생략 |

- `--week`는 `runtime.WeekOpt`(기본 None)로 받고 `week is not None`으로 판정한다(표의 기본값 `this`는 None일 때의 의미다. `-w ""`는 그대로 `parse_week`로 넘어가 한국어 형식 오류가 난다).
- **실행 순서(Phase 2 CLI 공통 규칙):**
  1. `--out`이 있으면 `out_path = runtime.prepare_output_path(out)`(DB·설정 없이 끝나는 검증, 공통 규칙 '파일 쓰기'의 ①~③)
  2. `cfg = runtime.settings()`
  3. 함수 안에서 `from logbook.core.weeks import parse_week` 후 `the_week = parse_week(week if week is not None else "this", today=runtime.today(), week_start=cfg.week_start)`. 주차 형식 오류는 여기서 끝나며 DB·SQLAlchemy·jinja2를 로드하지 않는다.
  4. `from logbook.core import services` 후 `with runtime.session(cfg) as s:` 안에서 `data = services.weekly_report(s, the_week, tz=runtime.now().tzinfo, title_format=cfg.report.title_format, author=cfg.report.author, category_labels=cfg.categories)`
  5. 세션을 닫은 뒤 함수 안에서 `from logbook.core.config import config_path`, `from logbook.core.report import render_markdown, user_template_path` 후 `markdown = render_markdown(data, template_path=user_template_path(config_path()))`
  6. `--out`이면 `runtime.write_text_file(out_path, markdown, yes=yes)` 후 저장 완료 줄(저장 먼저)
  7. `--copy`면 `platform.copy_to_clipboard(markdown)`. 성공 줄과 실패 경고는 아래 '출력' 항목을 따른다.
  8. `--out`과 `--copy`가 모두 없거나, `--copy`가 실패했는데 `--out`이 없으면 `console.print_raw(markdown)`으로 stdout에 쓴다(아래 '출력' 항목의 `print_raw` 설명).
- **출력:**
  - `--out`과 `--copy`가 모두 없으면 `console.print_raw(markdown)`으로 stdout에 쓴다(`console.print_line(Text(markdown))`은 쓰지 않는다. Rich의 기본 `end="\n"`이 붙어 보고서가 `\n\n`으로 끝난다).
    - `print_raw(text: str) -> None`은 `console.py`에 추가하고 `_write_out(out(), Text(text), soft_wrap=True, end="")`로 구현한다. 마크업·이모지를 해석하지 않고 줄을 접지 않으며 text 끝의 줄바꿈을 그대로 쓰고 더하지 않는다. 닫힌 stdout은 `_write_out`이 `OutputClosedError`(조용한 exit 1)로 바꾼다.
    - 직접 `sys.stdout.write`를 쓰지 않는다(CLAUDE.md '콘솔 출력은 Rich를 통해서만', `console.py`가 유일한 통로).
    - Rich `Text`는 탭을 8칸 기준 공백으로 펼치고 `\r`·`\x07`·`\x0b`·`\x0c` 같은 제어 문자를 지운다. 그래서 사용자 템플릿에 직접 쓴 탭·제어 문자만 stdout이 파일·클립보드(원문 그대로)와 다르다. 제목·라벨은 조립 단계에서 정리한다(공통 규칙 '보고서 표기'). stdout 정확 비교 테스트 데이터에는 탭을 넣지 않는다.
  - `--out`: `✔ 보고서를 저장했습니다: {path}`
  - `--copy` 성공: `✔ 보고서를 클립보드에 복사했습니다.`
  - `--copy` 실패: stderr에 `주의: 클립보드에 복사하지 못했습니다. --out으로 파일에 저장하세요.`를 쓴다. `--out`이 없으면 보고서를 stdout에 출력해 내용을 잃지 않게 한다. 종료 코드는 0이다.
  - `--out`을 함께 줬는데 복사에 실패하면(파일은 이미 저장됨): stderr에 `주의: 클립보드에 복사하지 못했습니다. 보고서는 파일로 저장했습니다: {path}`를 쓰고 보고서 본문은 stdout에 출력하지 않는다(저장 완료 줄만 나온다). 종료 코드는 0이다.
  - `--out`과 `--copy`를 함께 주면 둘 다 한다(저장 먼저).
  - 완료 줄의 `✔`와 괄호 안의 `·`는 문자열에 하드코딩하지 않고 `render.ok_mark()`와 `render.info_mark()`로 출력한다(Phase 3 출력 규칙). 대상: `보고서를 저장했습니다`, `보고서를 클립보드에 복사했습니다`, `내보냈습니다`, `가져왔습니다`. 테스트에 `monkeypatch.setattr(platform, "supports_unicode", lambda text="": False)`로 대체 출력(`v`, `-`)을 확인하는 행을 하나 둔다(tests/cli/test_add.py:308 방식).
- **오류:** 주차 형식, 템플릿 오류, 파일 쓰기 오류는 모두 `오류: …` 한 줄이고 exit 1이다.

**단위 테스트:**
- `tests/cli/test_runtime.py`: 폴더(`tmp_path`), `""`(`Path("")`은 `.`), 없는 폴더, 부모가 파일, 기존 파일에 `y`/`n`/EOF/`yes=True`, `Path.write_text`를 `PermissionError(13, "Permission denied")`로 바꾼 경우(`파일을 저장하지 못했습니다: {path} (Permission denied).`), `OSError("x")`(strerror가 None)이면 `(x)`가 나오는지.
- `tests/cli/test_console.py`: `print_raw`는 끝의 `\n` 하나가 유지됨, 빈 줄·끝 공백 보존, 1500자 한 줄과 한글 600자 줄이 접히지 않음, `[bold]x[/bold]`·`:smile:`가 글자 그대로 나옴, 닫힌 stdout에서 `OutputClosedError`.

**테스트 케이스: test_report.py** (`clock`·`today` 고정, `copy_to_clipboard`는 monkeypatch)

상대 경로를 쓰는 CLI 테스트는 모두 먼저 `monkeypatch.chdir(tmp_path)`를 한다(`lb` fixture는 작업 폴더를 바꾸지 않는다). 대상: `report -o out.md`, 같은 경로 재저장, `-o .`, `-o 없는폴더/out.md`, `-o "보고 서/주간.md"`, 경로를 생략한 `export`, `export -o b.jsonl`, `import b.jsonl`. 출력에 나오는 경로의 기대값은 `str(Path("보고 서") / "주간.md")`처럼 Path로 만든다(Windows는 역슬래시). 경로는 `prepare_output_path`·`expand_home`이 돌려준 Path를 그대로 보여 주므로(~만 확장) 기본 이름도 `logbook-export-20261001-093000.jsonl` 그대로 나온다.

- 완료 태스크가 필요한 테스트는 `lb task done`·`set_task_status` 대신 같은 세션에서 `task.done_at = datetime(2026, 9, 30, 3, 0, tzinfo=UTC)`(W40 안, 정오 부근이라 날짜 경계와 멀다)로 직접 넣는다. 기대 출력의 `완료 태스크 N건`은 고정 문자열로 적는다. `report -w last`의 첫 줄은 `# 주간업무보고 (2026-09-21 ~ 2026-09-27)`다.
- 명령(`commands/report.py`, `commands/data.py`)은 모듈 상단에 `from logbook.core import platform`을 두고 `platform.copy_to_clipboard(...)`, `platform.timestamp_for_filename(...)`처럼 모듈 속성으로 부른다(기존 `supports_unicode` monkeypatch와 같은 방식). 테스트는 `monkeypatch.setattr(platform, "copy_to_clipboard", fake)`, `monkeypatch.setattr(platform, "timestamp_for_filename", lambda now=None: "20261001-093000")`로 대신하고, 실제 클립보드를 쓰는 테스트는 서브프로세스를 포함해 두지 않는다.

| 케이스 | 기대 |
|---|---|
| 데이터 준비 후 `report` | stdout이 렌더링 결과와 정확히 같음 |
| `report -w last` | 지난주 제목 |
| 설정 파일에 `week_start = "sunday"`(init 전에 config.toml에 씀), 09-27(일)·10-04(일)에 기록 하나씩 + `report` | 제목 `# 주간업무보고 (2026-09-27 ~ 2026-10-03)`, 1절은 09-27 기록만 집계(기록 1건) |
| `report -w x` | 주차 형식 문구, DB 접근 전 |
| `report -o out.md` | 파일 내용 일치, UTF-8·LF(바이트로 확인), 완료 줄 |
| 같은 경로로 다시 `report -o out.md` + `y` / `n` / 입력 없음 / `--yes` | 덮어씀 / 문구·exit 1·파일 그대로 / 문구·exit 1 / 프롬프트 없음 |
| `-o 없는폴더/out.md` | 폴더 없음 문구 |
| `-o .`(폴더) | 폴더 문구 |
| `-o "~/주간.md"` (HOME·USERPROFILE은 `isolated_home`) | `isolated_home / "주간.md"`에 저장 |
| `-o "~nouser/x.md"` | `오류: 경로가 올바르지 않습니다: --out 값 '~nouser/x.md'. 홈 디렉터리 기준 경로는 '~/'로 시작하세요.` exit 1 |
| `--copy` 성공 | 복사된 텍스트가 보고서와 같음, 성공 줄만 출력 |
| `--copy` 실패 | 주의 문구(stderr) + 보고서 stdout, exit 0 |
| `-o out.md --copy` | 둘 다 |
| `-o out.md --copy`(복사 실패) | stdout에 저장 완료 줄만, stderr에 위 경고, 보고서 본문은 stdout에 없음, exit 0 |
| 설정 폴더의 `report.md.j2` 재정의 | 사용자 템플릿 결과 |
| 문법 오류 템플릿 | 템플릿 문구, exit 1 |
| 설정 `[report] title_format = "주간보고 ({start} ~ {end)"` | `오류: 보고서 제목 형식이 올바르지 않습니다: '주간보고 ({start} ~ {end)'. 사용할 수 있는 이름: {start}, {end}` 한 줄(stderr), exit 1, traceback 없음 |
| 한글 경로·공백 경로 `-o "보고 서/주간.md"`(폴더 미리 생성) | 저장 성공 |
| init 전 | `lb init` 안내 |
| report 성공, report 템플릿 오류 뒤 | 각각 `os.replace(db, db.with_name("moved.db"))`가 성공한다(엔진 dispose 확인) |
| `supports_unicode`가 False일 때 `report -o out.md` | 완료 줄이 대체 출력(`v`)으로 나옴 |

import 가드: `report --help`(rc 0), `report -w x`(rc 1). jinja2가 가드 목록에 이미 있다. 정상 경로에서는 jinja2를 함수 안에서만 로드한다. 경로 오류 케이스도 가드에 추가한다(DB·설정 전에 끝나므로 금지 모듈이 로드되지 않아야 한다).

```python
pytest.param(["report", "-o", "없는폴더/x.md"], 1, "오류: 저장할 폴더가 없습니다", id="report-missing-dir"),
```

- [ ] RED → GREEN → 커밋 `feat: lb report 주간보고서 명령 추가`

---

## Task 4-4: core — 내보내기(export)

**Files:**
- Create: `src/logbook/core/services/backup.py`, `tests/core/test_services_backup.py`
- Modify: `src/logbook/core/services/__init__.py`

**JSONL 형식 (버전 1)**
- 1행 머리글(실제 바이트): `{"exported_at": "2026-10-08T03:00:00+00:00", "format": 1, "schema_version": 1, "type": "logbook-export"}`
- 그다음 행: `{"row": {...}, "table": "projects"}`를 projects → tasks → worklogs → active_timer 순서로, 각 테이블 안에서는 id 순으로 쓴다. `sort_keys=True`라서 `row`가 `table`보다 앞에 오고 `row` 안의 키도 이름순이다.
- 값 형식:
  - 날짜는 `YYYY-MM-DD`이다.
  - 시각은 `value.astimezone(UTC).isoformat()` 그대로다(`timespec`을 지정하지 않는다). 마이크로초가 0이 아니면 `2026-10-08T03:00:00.123456+00:00`처럼 붙는다. 머리글의 `exported_at`도 같은 규칙이다.
  - bool은 JSON bool, 상태는 값 문자열(`todo` …)이다.
  - null 필드도 키를 빠짐없이 쓴다.
- 머리글과 모든 행은 `json.dumps(obj, ensure_ascii=False, sort_keys=True).translate(SEPARATOR_ESCAPES)`로 쓴다. 한 줄 한 레코드라 git diff에 강하다.
  - 모듈 상수: `SEPARATOR_ESCAPES = {cp: json.dumps(chr(cp))[1:-1] for cp in (0x2028, 0x2029, 0x85)}`
  - 이유: `ensure_ascii=False`는 U+2028(LINE SEPARATOR), U+2029(PARAGRAPH SEPARATOR), U+0085(NEXT LINE)를 원문자로 남긴다. `str.splitlines()`와 일부 편집기는 이 문자를 줄 끝으로 본다. 그래서 이 세 문자만 JSON 유니코드 이스케이프(역슬래시, `u`, 16진수 네 자리의 여섯 글자)로 바꾼다. 다른 줄 구분 문자(CR, 0x0B, 0x0C, 0x1C~0x1E)는 `json.dumps`가 이미 이스케이프한다.
  - 이 문자들은 JSON 문자열 안에만 나오므로 값은 그대로이고, 다시 내보내도 바이트가 같다. 한글은 원문자로 남는다.

```python
FORMAT_VERSION = 1
TABLE_ORDER = ("projects", "tasks", "worklogs", "active_timer")

@dataclass(frozen=True)
class BackupCounts:
    projects: int
    tasks: int
    worklogs: int
    timers: int

def export_records(s: Session, *, now: datetime) -> tuple[list[str], BackupCounts]
    """JSONL 줄 목록(줄바꿈 없음)과 개수. now는 머리글 exported_at(aware)."""
```

- `schema_version`은 `db.SCHEMA_VERSION`이다. 테이블별 필드 목록은 모델 컬럼에서 만들지 않고 명시적인 튜플로 둔다. 내보내기 형식은 공개 계약이므로, 컬럼이 늘어날 때 의도적으로 바꾸기 위해서다.
- 테이블별 필드 튜플(모델 컬럼과 같은 순서다. Task 4-5의 `알 수 없는 필드`·`빠진 필드` 검증도 이 튜플을 그대로 쓴다):
  - projects: id, slug, name, description, color, archived, created_at
  - tasks: id, project_id, title, description, status, category, estimate_minutes, planned_week, due_date, external_ref, created_at, updated_at, done_at
  - worklogs: id, project_id, task_id, category, date, minutes, note, started_at, ended_at, created_at
  - active_timer: id, project_id, task_id, category, note, started_at
- **테스트:**
  - 빈 DB(common만)
  - 모든 테이블·모든 필드(null 포함)
  - 한글·따옴표·줄바꿈이 든 메모(JSON 이스케이프 확인)
  - 줄 순서
  - UTC 시각 표기
  - 모든 출력 줄에서 `line.splitlines() == [line]`
  - 정렬된 키
  - 메모, 태스크 제목, 태스크 설명, 타이머 메모의 가운데에 `chr(0x2028)`·`chr(0x2029)`·`chr(0x85)`가 든 데이터: 각 줄에 세 원문자가 없고, 각 줄을 `json.loads`한 값은 원래 문자열과 같다.
  - 필드 목록 고정: 테이블마다 필드 튜플 집합이 `Model.__table__.columns.keys()` 집합과 같고, `set(TABLE_ORDER) == set(Base.metadata.tables) - {"schema_version"}`이다. 실패하면 형식을 의도적으로 바꾸고 `FORMAT_VERSION`을 올린다(tests/cli/test_runtime.py:282의 `MAX_ROUND_MINUTES` 일치 테스트와 같은 방식).
  - 마이크로초 보존: 마이크로초가 있는 시각(예: UTC 03:00:00.123456)이 `"2026-10-08T03:00:00.123456+00:00"`로 나온다. Task 4-5 왕복 테스트에서는 가져온 행의 시각이 원본과 마이크로초까지 같다(export→import→export 바이트 비교만으로는 마이크로초를 자르는 구현을 잡지 못한다).

- [ ] RED → GREEN → 커밋 `feat: 전체 데이터 JSONL 내보내기 서비스 추가`

---

## Task 4-5: core — 가져오기(import)

**Files:** Modify `src/logbook/core/services/backup.py`, `src/logbook/core/services/__init__.py`(`import_records` 공개), `tests/core/test_services_backup.py`

```python
def import_records(s: Session, lines: Iterable[str]) -> BackupCounts
```

**규칙**
- **빈 DB 확인(결정 R3):** projects가 `common` 하나뿐이고 tasks·worklogs·active_timer가 비어 있어야 한다. 그렇지 않으면 `InvalidInputError`를 낸다.
  - 문구: `데이터가 있는 데이터베이스에는 가져올 수 없습니다. 새 데이터베이스에서 실행하세요 (예: LOGBOOK_DB를 새 경로로 바꾸고 'lb init' 후 'lb import').`
- **전체 검증 후 쓰기:** 모든 줄을 먼저 읽고 검증한 뒤에만 쓴다. 검증 실패면 아무것도 바꾸지 않는다(호출자의 세션 롤백).
- **줄과 줄 번호:**
  - `lines`의 각 항목은 한 줄이다(끝에 줄바꿈이 있어도 된다). core는 줄을 다시 나누지 않는다.
  - 오류의 줄 번호 `{n}`은 `lines` 안의 순번(1부터)이다. 빈 줄도 센다(빈 줄을 먼저 거른 뒤 번호를 매기지 않는다).
  - 첫 줄(순번 1) 맨 앞의 U+FEFF(`chr(0xFEFF)`)는 core도 지운다(`lstrip`으로 여러 개여도 모두). `str.strip()`은 U+FEFF를 지우지 않고 `json.loads`는 U+FEFF로 시작하는 문자열을 거부하며 CLI의 `utf-8-sig`는 BOM을 하나만 지운다.
  - `strip()` 결과가 빈 문자열인 줄(공백·`\r`만 있는 줄 포함)은 머리글 앞을 포함해 어디에 있든 건너뛴다.
- **머리글 검증:** 처음 나오는 비어 있지 않은 줄이 머리글이다. 머리글 오류에는 줄 번호를 붙이지 않는다. 문구의 `{값}`은 `echo_input(json.dumps(값, ensure_ascii=False))`(core.duration, 40자 초과는 `...`)이고 키가 없으면 `null`이다. 아래 순서로 검사하고 첫 오류에서 멈춘다.
  1. 비어 있지 않은 줄이 없으면: `logbook 내보내기 파일이 아닙니다 (내용이 없습니다).`
  2. JSON으로 읽을 수 없거나(`ValueError`·`RecursionError` 포함) JSON 객체가 아니거나 `type` 키가 없으면: `logbook 내보내기 파일이 아닙니다 (첫 줄에 type 값이 없습니다).` (예: `lb report -o`로 만든 Markdown 파일)
  3. `type`이 `"logbook-export"`가 아니면: `logbook 내보내기 파일이 아닙니다 (첫 줄의 type 값: {값}).`
  4. `format`이 정수 1이 아니면(`type(v) is int and v == 1`로 확인하므로 `true`, `1.0`, `"1"`, 키 없음은 모두 거부): `지원하지 않는 내보내기 형식 버전입니다: {값}. 이 버전의 logbook이 읽을 수 있는 형식: 1`
  5. `schema_version`이 정수가 아니거나(`type(v) is int`) 1 미만이면: `내보내기 파일의 스키마 버전이 올바르지 않습니다: {값}`
  6. `schema_version`이 `db.SCHEMA_VERSION`보다 크면: `더 새로운 logbook에서 내보낸 파일입니다 (스키마 {n}). logbook을 업데이트한 뒤 가져오세요.`
  7. 머리글의 그 밖의 키(`exported_at` 등)는 검사하지 않는다.
- **행 검증:** 오류 문구에는 줄 번호(1부터)를 붙인다: `{n}번째 줄: …` (정확한 문구는 아래 '행 검사 순서와 오류 문구')
  - JSON 아님, 알 수 없는 table, 알 수 없는 필드, 빠진 필드
  - 타입 오류(int/str/bool/null, 날짜·시각 형식, naive 시각 거부)
  - 테이블 순서 위반
  - 같은 테이블의 id 중복
  - 존재하지 않는 FK 참조(파일 안 기준)
  - slug 형식과 중복, `common` 프로젝트가 파일에 없음
  - status 값, minutes ≥ 1, active_timer 2행 이상
  - 정수 필드(`id`, `project_id`, `task_id`, `estimate_minutes`, `minutes`)는 `type(v) is int`만 받는다(bool·float 거부. JSON `true`는 `isinstance(True, int)`가 참이라 1로 저장된다). 범위는 1 이상 `MAX_SQLITE_INTEGER` 이하다. `MAX_SQLITE_INTEGER = 2**63 - 1`은 backup.py의 상수다(core는 `cli.runtime.MAX_ID`를 import하지 않는다). 넘으면 flush가 `IntegrityError`가 아니라 `OverflowError`를 낸다. `task_id`·`estimate_minutes`는 null도 된다.
  - `worklogs.minutes`는 1 이상 `core.duration.MAX_MINUTES`(1440) 이하이고, `tasks.estimate_minutes`는 null이거나 1 이상이다(상한 없음, `_checked_estimate` 규칙).
  - 문자열 필드는 `type(v) is str`, bool 필드(`archived`)는 `type(v) is bool`이다. 날짜는 `date.fromisoformat(v).isoformat() == v`일 때만 받는다. 시각은 `datetime.fromisoformat(v)`가 되고 `utcoffset()`이 None이 아니어야 하며(naive 거부), `astimezone(UTC)`가 성공해 UTC 날짜가 0001-01-02 이상 9999-12-30 이하여야 한다(이 변환에서 나는 `OverflowError`도 그 줄의 시각 오류로 바꾼다. 하루 여유는 보고서·타이머 표시가 어느 시간대에서도 범위를 넘지 않게 한다). 통과한 값은 int·date·aware datetime 객체로 바꿔 넣는다(문자열을 날짜 컬럼에 넣으면 flush가 `StatementError`를 낸다).
  - `json.loads`의 `ValueError`(`JSONDecodeError`와 4300자리를 넘는 정수)와 `RecursionError`는 모두 `JSON 형식이 올바르지 않습니다`로 바꾼다. 결과가 JSON 객체가 아닌 줄(`[1,2]`, `"x"`, `null`)은 레코드 형식 오류다.
  - `status`가 `done`이면 `done_at`이 있어야 하고, 그 밖의 상태면 `done_at`은 null이다(`set_task_status` 규칙).
  - `worklogs`·`active_timer`에 `task_id`가 있으면 그 태스크의 `project_id`가 행의 `project_id`와 같아야 한다(`target_project` 규칙).
  - slug가 `common`인 프로젝트는 `archived`가 false여야 한다(`archive_project` 규칙. 보관 해제 명령이 없어 CLI로 되돌릴 수 없다).
  - `active_timer.id`는 1이어야 한다.
- **행 검사 순서와 오류 문구:** 가져오기는 `빈 DB 확인 → 파일 전체 검증 → 쓰기` 순서다. 줄마다 아래 순서로 검사하고 첫 오류에서 멈춘다. 문구의 `{값}`은 위 '머리글 검증'과 같이 `echo_input(json.dumps(값, ensure_ascii=False))`이고, 오류는 모두 `InvalidInputError`다.
  1. JSON 해석: `{n}번째 줄: JSON 형식이 올바르지 않습니다.`
  2. 봉투(키가 정확히 `table`과 `row`인 JSON 객체, `table`은 문자열, `row`는 JSON 객체. 머리글 모양의 줄이 다시 나온 경우도 여기): `{n}번째 줄: 레코드 형식이 올바르지 않습니다. {"row": {...}, "table": "..."} 형식이어야 합니다.`
  3. 테이블 이름: `{n}번째 줄: 알 수 없는 테이블입니다: {값}. projects, tasks, worklogs, active_timer 중 하나여야 합니다.`
  4. 테이블 순서(projects → tasks → worklogs → active_timer, 앞 테이블로 돌아가면 위반): `{n}번째 줄: 테이블 순서가 올바르지 않습니다: {table} 행이 {앞서 나온 table} 행 뒤에 있습니다. projects, tasks, worklogs, active_timer 순서여야 합니다.`
  5. 필드 이름: `{n}번째 줄: {table} 행에 알 수 없는 필드가 있습니다: {필드 목록(이름순)}.` 다음에 `{n}번째 줄: {table} 행에 빠진 필드가 있습니다: {필드 목록(필드 튜플 순서)}.`
  6. 필드 값(필드 튜플 순서로 처음 틀린 것): `{n}번째 줄: {table}.{field} 값이 올바르지 않습니다: {값} ({기대}).`
  7. 중복: `active_timer` 행이 둘째면 `{n}번째 줄: active_timer 행은 하나만 있을 수 있습니다.` 그 밖에는 `{n}번째 줄: {table} 행의 id가 중복됩니다: {id}.`, `{n}번째 줄: projects.slug 값이 중복됩니다: {값}.`
  8. 참조(앞서 나온 행만 본다): `{n}번째 줄: {table}.{field} 값이 가리키는 {대상 table} 행이 파일에 없습니다: {id}.`
  9. 불변식:
     - `{n}번째 줄: tasks.done_at 값이 올바르지 않습니다: {값} (status가 done이면 시각, 아니면 null이어야 합니다).`
     - `{n}번째 줄: {table}.task_id 값이 올바르지 않습니다: {id} (그 태스크의 project_id와 같은 프로젝트여야 합니다).`
     - `{n}번째 줄: projects.archived 값이 올바르지 않습니다: true (common 프로젝트는 false여야 합니다).`
  10. 파일 끝에서 `common` 프로젝트가 없으면 줄 번호 없이: `가져올 파일에 common 프로젝트가 없습니다.`
- **{기대} 문구(6단계):**

  | 필드 | 문구 |
  |---|---|
  | `id`, `project_id` | `1 이상 9223372036854775807 이하의 정수` |
  | `task_id`, `tasks.estimate_minutes` | `null 또는 1 이상 9223372036854775807 이하의 정수` |
  | `worklogs.minutes` | `1 이상 1440 이하의 정수` |
  | `active_timer.id` | `1` |
  | `projects.slug` | `영문 소문자나 숫자로 시작하고 영문 소문자·숫자·'-'·'_'만 쓴 32자 이하 문자열` |
  | `tasks.status` | `todo, doing, done, dropped 중 하나` |
  | `projects.archived` | `true 또는 false` |
  | 문자열(null 불가 / 가능) | `문자열` / `null 또는 문자열` |
  | 날짜(`worklogs.date` / `tasks.due_date`) | `YYYY-MM-DD 형식의 날짜` / `null 또는 YYYY-MM-DD 형식의 날짜` |
  | 시각(null 불가 / 가능) | `시간대가 있는 ISO 8601 시각` / `null 또는 시간대가 있는 ISO 8601 시각` |
- **쓰기:**
  - 기존 `common` 프로젝트는 `s.delete(common)` 뒤 바로 `s.flush()`로 먼저 지우고, 그다음 파일의 행을 원래 id로 넣는다(같은 flush에서 처리하면 INSERT가 먼저 실행되어 `common` id가 다를 때 `UNIQUE(slug)` 위반이 난다).
  - flush 중의 `IntegrityError`는 `InvalidInputError("가져온 데이터가 데이터베이스 규칙에 맞지 않습니다: {error.orig}. 'lb export'로 만든 파일인지 확인하세요.")`로 바꾼다. 검증이 정수·시각 범위를 막으므로 `OverflowError`와 `StatementError`는 나오지 않는다. `sqlalchemy.exc.StatementError`나 `DBAPIError`로 넓게 잡지 않는다. 둘은 `OperationalError`의 상위 클래스라서 잠금·읽기 전용·디스크 부족 오류까지 이 문구로 바뀌고 `session_scope`가 `DatabaseBusyError` 등 한국어 오류로 바꾸는 처리(db.py:232-250)가 사라진다.
- **왕복 보장:** `export → 새 DB에 import → export` 결과는 머리글의 `exported_at`을 빼고 바이트까지 같다.

**테스트:**
- 왕복(모든 테이블, 한글, null, 메모·제목 가운데의 U+2028·U+2029·U+0085)
- 왕복에서 가져온 행의 시각이 원본과 마이크로초까지 같다(마이크로초가 있는 시각 포함)
- 데이터가 있는 DB 거부(태스크 하나 / 기록 하나 / 타이머 / 프로젝트 하나 추가 각각)
- `common`만 있는 DB 허용
- 머리글 오류(각각 정확한 문구를 확인한다): 빈 입력, 빈 줄만 있는 입력 / 첫 줄이 JSON 아님(`# 주간업무보고 …`)·`[1]`·`"x"`, `type` 키 없음 / `type` 다름 / `format`이 `true`·`1.0`·`"1"`·없음·2 / `schema_version`이 `"2"`·`0`·`true`·없음 / `schema_version` 2(현재보다 큼)
- 줄 처리: U+FEFF가 앞에 붙은 첫 줄(하나, 둘), 머리글 앞의 빈 줄, 빈 줄 뒤에 있는 오류 줄의 번호(빈 줄도 센 번호), 머리글만 있는 입력(`common` 없음 문구)
- 줄별 오류: 위 '행 검사 순서와 오류 문구'의 단계마다 하나씩 줄 번호 포함 정확한 문구로 확인한다. 한 행에 오류가 둘이면 앞 단계의 문구가 나오는지(예: 알 수 없는 필드와 값 오류가 함께 있으면 알 수 없는 필드)도 한 케이스 둔다.
- 행 값 오류: 항목마다 잘못된 줄이 하나 든 파일을 따로 두고 줄 번호를 포함한 정확한 문구와 DB가 그대로(`common`만)인지를 확인한다. 값: `id` 2**63·0·-1, `minutes` `true`·1.5·1441, `estimate_minutes` -30·0, 5000자리 정수, 날짜 `"20261008"`, 시각 `0001-01-01T00:00:00+09:00`·`0001-01-01T00:00:00+00:00`·naive(`2026-10-08T03:00:00`), `done`인데 `done_at` null, `todo`인데 `done_at` 있음, 다른 프로젝트 태스크를 가리키는 기록 한 줄과 타이머 한 줄, `archived`가 true인 `common`, `active_timer.id` 2, `[1,2]` 줄, 머리글 `"format": true`
- flush가 `OperationalError`(예: `tests/core/test_db_open.py`의 `fake_operational_error("SQLITE_BUSY")` 방식, 또는 다른 연결이 `BEGIN IMMEDIATE`로 쓰기 잠금을 잡고 `db.BUSY_TIMEOUT_SECONDS`를 줄인 상태)를 내면 `import_records`를 `session_scope` 안에서 불렀을 때 `InvalidInputError`가 아니라 `DatabaseBusyError`가 나온다.
- 이스케이프하지 않은 `chr(0x2028)`·`chr(0x85)`가 메모 안에 든 줄을 직접 만들어 넘긴다: 오류 없이 가져오고 저장된 메모가 원래 값과 같다(`json.loads`는 이 문자를 JSON 문자열 안에서 허용한다).
- 파일의 `common` id가 3인 정상 파일 가져오기(성공, 그 뒤 새 기록의 id가 기존 최대 id 다음)
- 검증 실패 뒤 DB가 그대로인지(common만 남음)
- 가져온 뒤 새 기록의 id가 기존 최대 id 다음인지

- [ ] RED → GREEN → 커밋 `feat: JSONL 가져오기 서비스 추가 (빈 데이터베이스에만 복원)`

---

## Task 4-6: CLI — lb export, lb import

**Files:**
- Create: `src/logbook/cli/commands/data.py`, `tests/cli/test_data.py`
- Modify: `src/logbook/cli/main.py`, `tests/cli/test_entry.py`

**lb export [--out/-o PATH] [--yes/-y]**
- 실행 순서: ① `now = runtime.now()`를 한 번만 구한다(기본 파일 이름과 `exported_at`에 같이 쓴다). ② `path = runtime.prepare_output_path(out if out is not None else f"logbook-export-{platform.timestamp_for_filename(now)}.jsonl")` ③ `cfg = runtime.settings()` ④ 세션에서 `services.export_records(s, now=now)` ⑤ 세션을 닫은 뒤 `runtime.write_text_file(path, "\n".join(lines) + "\n", yes=yes)`
- 경로를 생략하면 현재 폴더의 `logbook-export-{timestamp_for_filename(now)}.jsonl`이다.
- 출력: `✔ 내보냈습니다: {path} (프로젝트 2 · 태스크 5 · 기록 41 · 타이머 0)`

**lb import PATH**
- PATH 인자는 `Annotated[str, typer.Argument(metavar="PATH", help="가져올 JSONL 파일 (lb export로 만든 파일)")]`로 받는다. `Path` 타입이나 `exists=True`는 쓰지 않는다(Click이 영어 오류와 exit 2를 낸다).
- 실행 순서(파일을 DB·설정보다 먼저 읽는다. 그래야 파일 오류가 import 가드로 보호된다):
  1. `path = expand_home(path_text, "가져올 파일 경로")` (core.config. `~name`은 `InvalidInputError`)
  2. `path.is_dir()`이면 `파일 경로가 아니라 폴더입니다: {path}. 파일 이름까지 지정하세요.`
  3. `not path.is_file()`이면 `가져올 파일이 없습니다: {path}`
  4. `text = path.read_text(encoding="utf-8-sig")`. 오류: `UnicodeDecodeError`는 `UTF-8 텍스트 파일이 아닙니다: {path}. 'lb export'로 만든 파일을 지정하세요.`, 그 밖의 `OSError`(권한 등)는 `가져올 파일을 읽지 못했습니다: {path} ({error.strerror or error}).` 예외 종류로 폴더를 판정하지 않는다(Windows는 `PermissionError`를 낸다).
  5. `lines = text.split("\n")`. `str.splitlines()`는 쓰지 않는다. U+2028·U+2029·U+0085에서도 줄을 나눠 이 문자가 든 정상 파일을 JSON 오류로 거부한다. 파일 객체를 그대로 `import_records`에 넘기지도 않는다(줄 끝에 줄바꿈이 남고 디코딩 오류가 세션 안에서 늦게 난다).
  6. `cfg = runtime.settings()` 후 `from logbook.core import services`와 `with runtime.session(cfg) as s: counts = services.import_records(s, lines)`. 실패하면 세션 범위가 롤백한다.
- 출력: `✔ 가져왔습니다: {path} (프로젝트 2 · 태스크 5 · 기록 41 · 타이머 0)`
- 확인 프롬프트는 없다. 빈 DB에만 들어가므로 덮어쓸 데이터가 없다.
- 완료 줄의 `✔`와 괄호 안의 `·`는 문자열에 하드코딩하지 않고 `render.ok_mark()`와 `render.info_mark()`로 출력한다(Phase 3 출력 규칙). 대상: `보고서를 저장했습니다`, `보고서를 클립보드에 복사했습니다`, `내보냈습니다`, `가져왔습니다`. 테스트에 `monkeypatch.setattr(platform, "supports_unicode", lambda text="": False)`로 대체 출력(`v`, `-`)을 확인하는 행을 하나 둔다(tests/cli/test_add.py:308 방식).

**테스트 케이스: test_data.py**

상대 경로를 쓰는 CLI 테스트는 모두 먼저 `monkeypatch.chdir(tmp_path)`를 한다(`lb` fixture는 작업 폴더를 바꾸지 않는다). 대상: `report -o out.md`, 같은 경로 재저장, `-o .`, `-o 없는폴더/out.md`, `-o "보고 서/주간.md"`, 경로를 생략한 `export`, `export -o b.jsonl`, `import b.jsonl`. 출력에 나오는 경로의 기대값은 `str(Path("보고 서") / "주간.md")`처럼 Path로 만든다(Windows는 역슬래시). 경로는 `prepare_output_path`·`expand_home`이 돌려준 Path를 그대로 보여 주므로(~만 확장) 기본 이름도 `logbook-export-20261001-093000.jsonl` 그대로 나온다.

- 완료 태스크가 필요한 테스트는 Task 4-3의 테스트 준비 규칙과 같이 `lb task done`·`set_task_status` 대신 같은 세션에서 `task.done_at`을 고정 시각으로 직접 넣는다.
- 명령(`commands/report.py`, `commands/data.py`)은 모듈 상단에 `from logbook.core import platform`을 두고 `platform.copy_to_clipboard(...)`, `platform.timestamp_for_filename(...)`처럼 모듈 속성으로 부른다(기존 `supports_unicode` monkeypatch와 같은 방식). 테스트는 `monkeypatch.setattr(platform, "copy_to_clipboard", fake)`, `monkeypatch.setattr(platform, "timestamp_for_filename", lambda now=None: "20261001-093000")`로 대신하고, 실제 클립보드를 쓰는 테스트는 서브프로세스를 포함해 두지 않는다.

| 케이스 | 기대 |
|---|---|
| 데이터 준비 → `export -o b.jsonl` | 파일 존재, 줄 수 = 1 + 행 수, 완료 줄 |
| `export`(경로 생략, `tmp_path`를 cwd로) | 기본 파일 이름(`timestamp_for_filename`을 monkeypatch해 고정) |
| 기존 파일 + `y`/`n`/`--yes` | Task 4-3과 같은 확인 규칙 |
| 다른 DB(`LOGBOOK_DB` 바꾸고 `init`)에 `import b.jsonl` | 완료 줄, `lb log`·`lb task list -s all` 출력이 원래 DB와 같음 |
| 데이터 있는 DB에 import | 거부 문구, DB 그대로 |
| 없는 파일, 폴더, cp949 파일 | 각 문구 |
| `Path.read_text`를 `PermissionError(13, "Permission denied")`로 바꿈 | `가져올 파일을 읽지 못했습니다: {path} (Permission denied).`(그 밖의 `OSError` 문구) |
| 잘못된 줄이 있는 파일 | `{n}번째 줄: …`, DB 그대로(common만) |
| BOM 있는 파일 | 성공 |
| init 전 import(올바른 JSONL 파일을 먼저 만들어 두고 실행한다. 없는 파일 오류가 먼저 나오지 않게) | `lb init` 안내 |
| 메모·태스크 제목에 `chr(0x2028)`·`chr(0x2029)`·`chr(0x85)`가 든 데이터 → `export -o a.jsonl` | a.jsonl 바이트에 세 원문자가 없음 |
| 위 a.jsonl의 각 줄을 `json.dumps(json.loads(줄), ensure_ascii=False, sort_keys=True)`로 다시 써서 원문자가 든 raw.jsonl을 만든다 → 다른 DB에서 `init` → `import raw.jsonl` → `export -o c.jsonl` | import exit 0과 완료 줄. c.jsonl의 2번째 줄부터가 a.jsonl과 바이트까지 같음. `lb log` 출력으로는 비교하지 않는다(Rich가 메모 칸을 U+2028에서 접고 tests/cli/helpers.py의 `lines()`·`rows()`가 `splitlines()`를 쓴다) |
| export 성공, import 성공, import 검증 실패(롤백 경로), 데이터 있는 DB에 import 거부 뒤 | 각각 `os.replace(db, db.with_name("moved.db"))`가 성공한다(엔진 dispose 확인) |
| `supports_unicode`가 False일 때 `export -o b.jsonl`·`import b.jsonl` | 완료 줄이 대체 출력(`v`, `-`)으로 나옴 |

위 표에서 원문자가 든 raw.jsonl을 만드는 행이 가져오기 쪽 규칙(`lb import`의 `split("\n")`)을 강제한다.

import 가드: `export --help`, `import --help`, `import`(인자 누락, rc 2). 경로 오류·파일 오류 케이스도 가드에 추가한다(DB·설정 전에 끝나므로 금지 모듈이 로드되지 않아야 한다).

```python
pytest.param(["export", "-o", "없는폴더/x.jsonl"], 1, "오류: 저장할 폴더가 없습니다", id="export-missing-dir"),
pytest.param(["import", "없는파일.jsonl"], 1, "오류: 가져올 파일이 없습니다", id="import-missing-file"),
```

**서브프로세스 왕복(test_entry.py, cp949 환경 하나):** 첫 DB에서 `init` → `add` → `export -o b.jsonl`을 하고, 다른 `LOGBOOK_DB`에서 `init` → `import b.jsonl`을 한 뒤 `log`를 실행한다. stdout에 한글 메모가 그대로 나와야 한다.

- [ ] RED → GREEN → 커밋 `feat: lb export·import 백업 명령 추가`

---

## Task 4-7: 문서 마무리와 Phase 4 완료

**Files:** Modify `README.md`, `docs/SPEC.md`, `docs/ROADMAP.md`, `CLAUDE.md`, `AGENTS.md`

- [ ] **README:**
  - "주간보고서" 절: `lb report`, `-w last`, `-o 주간보고.md`, `--copy`, 덮어쓰기 확인
  - "주간보고서" 절에 추가: `PowerShell에서는 lb report > 주간.md 대신 lb report -o 주간.md를 쓰세요. 리디렉션은 PowerShell 버전과 콘솔 인코딩에 따라 한글이 깨질 수 있습니다.`
  - "보고서 템플릿" 절: 설정 파일과 같은 폴더의 `report.md.j2`, `data`의 필드 목록(Task 4-1의 데이터 클래스), 기본 템플릿 위치(패키지 안의 `logbook/core/templates/report.md.j2`)를 적는다. 복사해서 고치는 방법도 PowerShell과 zsh 두 가지로 적는다. PowerShell 복사 예시는 `Copy-Item`만 쓰고, `>`·`Out-File`·`Set-Content`로 옮기면 5.1에서 UTF-16이나 ANSI로 저장되니 쓰지 말라고 적는다.
  - "백업과 복원" 절: export/import, 빈 DB에만 복원하는 이유와 절차
  - "백업과 복원" 절에 추가: `lb export 파일에는 DB 내용(프로젝트·태스크·기록·타이머)만 들어갑니다. 설정 파일(config.toml)과 보고서 템플릿(report.md.j2)은 따로 복사하세요.`
- [ ] **SPEC:**
  - 5장 "집계 / 보고서"와 "데이터 관리"에 옵션, 덮어쓰기 확인(R4), import 빈 DB 규칙(R3), JSONL 형식(머리글·행), `--copy` 실패 동작을 적는다.
  - 7장 첫 문단: `core/services/report.py`의 `weekly_report()`가 한 주의 기록·태스크로 구조화된 데이터(`core/report.py`의 불변 데이터 클래스 `ReportData`)를 만들고, `core/report.py`의 `render_markdown()`이 Jinja2 템플릿으로 Markdown을 렌더링한다. 템플릿은 설정 파일과 같은 폴더의 `report.md.j2`(기본 `~/.logbook/report.md.j2`, `LOGBOOK_CONFIG`를 따름)로 바꿀 수 있다.
  - 7장 예시 블록: Task 4-2의 기본 템플릿 출력 예시로 바꾸고 부록 줄은 지운다. 부록(커밋 내역)은 git-collect를 구현할 때까지 나오지 않는다(`include_commits`는 아직 쓰지 않는다).
  - '실적 그룹핑 규칙'을 다음으로 바꾼다.
    - 공수 요약 표의 열 이름은 설정의 카테고리 라벨이고 기록이 있는 카테고리만 나온다(Phase 2 후속 항목 11 해소). 프로젝트는 합계 내림차순(같으면 slug 순), 비율은 프로젝트 합계 / 주 합계(정수 반올림)다.
    - Task에 연결된 WorkLog는 Task 단위로 묶는다. `(#42)`는 태스크 ID이고 시간은 보고 주 마지막 날까지의 누적이다(완료는 `실제`, 나머지는 `누적`). 순서는 완료 → 진행 → 할 일 → 중단, 같은 상태 안에서는 ID 순이다.
    - Task 미연결 WorkLog는 카테고리 라벨별로 합산해 '기타' 줄에 시간 내림차순(같으면 표의 열 순서)으로 적는다.
    - 1절의 완료 태스크 수는 완료 시각이 그 주 안인 태스크 수다. 2절은 그 주 기록이 있는 태스크만 보여 주므로 두 값은 다를 수 있다.
    - 다음 주 계획 = `planned_week == 다음 주`인 todo·doing 태스크 + `planned_week == 이번 주`인 todo·doing 태스크(끝에 `(이월 후보)`). done·dropped와 보관한 프로젝트의 태스크는 뺀다. 프로젝트 slug 순, 같은 프로젝트 안에서는 다음 주 계획 → 이월 후보, 각각 ID 순이다.
    - 기록이 없는 주는 1절이 `총 0m (기록 0건, 완료 태스크 N건)` 한 줄(표 없음), 2절이 `기록이 없습니다.`다. 계획이 없으면 4절은 `계획된 태스크가 없습니다.`다. `author`가 비면 `작성자:` 줄을 뺀다.
    - 3절은 `(작성하세요)` 자리표시자다(week_notes 저장은 Phase 6).
- [ ] **종료 코드 표:** SPEC 5장 '오류와 종료 코드'와 README '오류와 종료 코드' 표의 1번 행을 `입력·데이터 오류(stderr에 오류: … 한 줄), 삭제·이월·타이머 취소·파일 덮어쓰기 확인을 거절했거나 확인 입력이 없음`으로 고친다.
- [ ] **ROADMAP:** Phase 4의 앞 네 항목을 `[x]`로 바꾼다. git-collect 항목은 그대로 두고 `(후속, R1)`을 덧붙인다.
- [ ] **CLAUDE.md·AGENTS.md(같은 내용):**
  - `report.py` 설명을 "보고서 데이터 클래스 + Markdown 렌더링(조립은 services/report.py)"으로 고친다.
  - `templates/` 줄을 추가한다.
  - services 목록에 `report`, `backup`을 넣는다.
  - commands 예시에 `report`, `data`를 넣는다.
  - 아키텍처 규칙(66행)의 core 공개 진입점 목록에 `core.report`(보고서 렌더링: `render_markdown`·`user_template_path`, DB에 접근하지 않음)와 이미 CLI가 쓰는 `core.taskstatus`(상태 파서)를 추가한다.
- [ ] **수동 확인(이 PC, PowerShell 5.1과 7, 임시 `LOGBOOK_DB`·`LOGBOOK_CONFIG`):**
  - `lb report`: 한글 표 출력
  - `lb report -o 주간.md` 후 메모장으로 열어 한글이 깨지지 않는지
  - `lb report --copy` 후 붙여넣기 확인
  - `lb export` → 새 DB에 `lb import`
- [ ] **전체 검증:** ruff, ruff format, mypy, pytest(전체 80%, core 80%)
- [ ] 커밋 `docs: Phase 4 완료 표시와 주간보고서·백업 사용 안내 추가`
- [ ] 사용자 확인 후 Phase 4 이슈 생성 → push → develop 대상 PR. CI 두 OS가 녹색이어야 한다. macOS 확인 절차는 PR 댓글로 남긴다.

---

## 크로스 플랫폼 체크리스트 (Phase 4 추가분)

- **파일 쓰기:** 보고서와 내보내기 파일 모두 `encoding="utf-8", newline="\n"`이다. 테스트는 바이트(`read_bytes`)로 CR이 없는지 확인한다.
- **파일 읽기:** 사용자 템플릿과 가져오기 파일은 `utf-8-sig`로 읽는다. Windows 메모장이 붙이는 BOM 때문이다.
- **경로:** 한글·공백 경로를 테스트한다. `core.config.expand_home`을 쓰고(`~name`은 거부), 출력은 `Text(str(path))`로 한다.
- **패키지 데이터:** 기본 템플릿은 `importlib.resources`로 읽는다. `__file__` 기준 경로는 쓰지 않는다. 휠 포함 여부를 테스트한다.
- **클립보드:** `platform.copy_to_clipboard`가 False를 돌려주는 경로를 항상 테스트한다. 실제 클립보드 동작은 OS와 러너마다 다르다(macOS 러너는 pbcopy가 동작할 수 있다).
- **JSON:** `ensure_ascii=False`라 한글이 그대로 들어간다. 파일은 UTF-8이다. U+2028·U+2029·U+0085만 이스케이프한다(Task 4-4). 가져오기는 LF로만 줄을 나눈다(Task 4-6).

## 설계 결정 요약 (기술 결정, 계획 승인 시 함께 확정)

1. **조립과 렌더링 분리:** DB 접근은 `services/report.py`, 데이터 클래스와 렌더링은 `core/report.py`에 둔다. Phase 5 Web(`/api/report?format=json|md`)이 같은 `ReportData`를 JSON으로도 쓸 수 있다.
2. **표기는 파이썬에서:** 템플릿에는 완성된 문자열을 넘긴다. 사용자 템플릿이 시간·비율 표기를 다시 구현하지 않아도 된다.
3. **실적 시간:** 태스크 줄의 시간은 SPEC 예시대로 누적이되 보고 주 마지막 날까지의 합이다. 이번 주 시간은 프로젝트 합계와 표에 있다.
4. **기타 줄은 카테고리 라벨로 합산한다:** SPEC 규칙("카테고리별로 묶어")을 따른다. SPEC 예시의 "장애 대응 30m"(메모)는 규칙과 어긋나므로 SPEC 예시를 고친다.
5. **다음 주 계획 대상:** 다음 주 todo·doing과 이번 주 todo·doing(이월 후보)이다. done·dropped와 보관 프로젝트는 뺀다.
6. **템플릿 위치:** 설정 파일과 같은 폴더다. `LOGBOOK_CONFIG`로 설정을 옮긴 사용자(테스트 포함)도 템플릿이 같이 따라간다.
7. **템플릿 오류:** `StrictUndefined`로 오타를 조용히 넘기지 않고, 경로·줄 번호와 함께 한국어로 알린다.
8. **내보내기 형식은 공개 계약이다:** 필드 목록을 명시하고 `format` 버전을 둔다. 스키마가 바뀌면(Phase 6 week_notes) 형식 2와 변환 규칙을 함께 정한다.
9. **가져오기는 전체 검증 후 한 번에:** 줄 번호가 붙은 오류로 실패하고, 실패하면 아무것도 쓰지 않는다.
10. **새 의존성 없음, 스키마 변경 없음.**

## 사용자 결정 (2026-10-08 승인 게이트에서 확정)

- **R1. 범위:** 보고서 + 백업(export/import). git-collect와 LLM 문장 다듬기는 후속 항목이다. 보고서 부록 절은 나오지 않는다.
- **R2. 특이사항 절:** 빈 자리 `(작성하세요)`로 둔다. 저장 기능(week_notes)은 Phase 6에서 첫 마이그레이션과 함께 만든다.
- **R3. lb import:** 빈 DB(`lb init` 직후, common만 있음)에만 ID를 보존해 복원한다. 데이터가 있으면 거부하고 새 DB 경로를 안내한다.
- **R4. 파일 덮어쓰기:** `lb report --out`과 `lb export --out`은 기존 파일이 있으면 `[y/N]`로 확인하고, `--yes`로 생략한다.

## 후속 항목 (Phase 4 범위 밖, 기록만)

1. **git-collect와 보고서 부록(R1):** `gitcollect.py`, `lb git-collect`, `include_commits`
2. **LLM 문장 다듬기(SPEC 7 선택 기능):** 네트워크·API 키·새 의존성이 필요하다. 별도로 승인받는다.
3. **week_notes(R2):** Phase 6에서 다룬다. 그때 내보내기 형식 2와 가져오기 변환도 함께 정한다.
4. **가져오기 병합:** 요청이 있으면 ID 재배정·slug 충돌 규칙을 정해 추가한다.
5. **Phase 3 후속 항목:** 그대로 유지한다(동시 타이머 경합, 태스크 삭제, 밀린 태스크, core 문구의 CLI 문법).
6. **완료 태스크 수의 DST 한계:** 고치려면 `weekly_report`의 `tz`를 `tzinfo | None`으로 바꾸고 None이면 `done_at.astimezone()`(그 시각의 시스템 시간대 규칙, DST 반영)으로 로컬 날짜를 구한다. 요청이 있을 때 다룬다.
