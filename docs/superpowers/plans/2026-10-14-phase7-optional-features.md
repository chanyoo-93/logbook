# Phase 7 구현 계획 (선택 기능)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** ROADMAP Phase 7의 선택 기능 세 가지와 SPEC 후속 항목 `lb git-collect`를 구현한다(결정 S1).
- `lb git-collect`와 보고서 부록(커밋 내역): CLI·웹·API 보고서에 함께 나온다.
- `lb task import-gh owner/repo`: gh CLI로 GitHub 이슈를 태스크로 가져온다(결정 S3).
- 셸 자동완성: `lb --install-completion`, 프로젝트 slug와 태스크 ID 완성(결정 S4).
- LLM 문장 다듬기: Anthropic(Claude)과 OpenAI(ChatGPT) 두 제공자. `lb report --polish`와 웹 `/report`의 "문장 다듬기" 버튼(결정 S2, S2-추가).

**Architecture:**
- **계층:** 기존과 같다. CLI·Web은 `core.services`와 허용된 core 진입점만 쓰고, SQL·ORM 쿼리를 쓰지 않는다.
- **외부 명령:** git·gh는 core의 공용 실행 함수 `core.external.run_tool()` 하나로 부른다. 목록 인자, `shell=False`, UTF-8 디코드, 시간 제한, 한국어 오류.
- **새 core 진입점(허용 목록에 추가):** `core.gitcollect`(커밋 수집), `core.github`(이슈 목록), `core.polish`(LLM 요약), `core.external`. 모두 DB에 접근하지 않는다. 이슈를 태스크로 만드는 일은 `core.services`가 한다.
- **보고서 데이터:** `ReportData`에 `commits`(부록)와 `summary`(자동 생성 요약)를 더한다. `weekly_report()`는 DB만 읽고 그대로 둔다. 호출자(CLI·웹)가 `dataclasses.replace()`로 두 값을 채운다.
- **LLM:** 제공자별 선택 설치(`anthropic`, `openai`) 패키지를 쓸 때만 import한다. 키와 패키지가 모두 있는 제공자만 켜진다. 테스트·CI는 실제 API를 부르지 않는다.
- **외부 실패:** 새 오류 `ExternalServiceError(LogbookError)`. CLI는 다른 LogbookError와 같이 한 줄·종료 1, 웹은 502다.

**Tech Stack:**
- 기존과 같다: Python 3.11+(CI 3.12), uv, Typer 0.27.2, Click 8.5.0, Rich, SQLAlchemy 2.1, Jinja2 3.1, FastAPI 0.143, htmx 2.0.11
- **새 선택 의존성(결정 S2):** `anthropic>=1.13`(2026-10-14 PyPI 최신 1.13.0, Python 3.10+), `openai>=3.29`(최신 3.29.0, Python 3.10+). 둘 다 `[project.optional-dependencies]`와 dev 그룹에 넣는다(테스트·mypy가 SDK 예외 클래스를 쓴다).
- 외부 명령: git, gh(사용자 PC에 있을 때만)

**선행 조건:**
- **브랜치:** `feat/phase7-optional-features`(develop `4d38f2f`에서 분기, 이미 만들어 둠)
- **uv PATH:** 이 PC에서는 uv가 PATH에 없다.
  - Git Bash: `export PATH="/c/Users/User/AppData/Local/Microsoft/WinGet/Packages/astral-sh.uv_Microsoft.Winget.Source_8wekyb3d8bbwe:$PATH"`
  - PowerShell: `$env:Path = "$env:LOCALAPPDATA\Microsoft\WinGet\Packages\astral-sh.uv_Microsoft.Winget.Source_8wekyb3d8bbwe;$env:Path"`
- **사용자 결정:** 문서 끝의 S1~S4는 2026-10-14 승인 게이트에서 확정했다. OpenAI 추가와 기본 모델(`gpt-6.1-sol`)은 게이트 뒤 사용자 요청이다.
- **Task 공통 완료 조건:** 아래 명령을 모두 통과한 뒤 커밋한다.
  - `uv run ruff check .`
  - `uv run ruff format --check .`
  - `uv run mypy src/logbook/core`
  - `uv run pytest` (커버리지: core·web 100% 유지)
- **커밋 메시지:** Conventional Commits 형식이다. type만 영어이고 설명은 한국어로 쓴다.
- **TDD:** 각 Task는 실패하는 테스트를 먼저 쓰고(RED), 최소 구현으로 통과시킨 뒤(GREEN), 정리한다.
- **사용자 문구 규칙(Phase 3에서 정함):**
  - 변수 값 바로 뒤에 조사를 붙이지 않는다. `없습니다: {값}.`처럼 값을 뒤로 보낸다.
  - core 문구에는 `—` 같은 기호를 넣지 않는다. 웹 화면 문구는 `✔`·`—`·`→`를 그대로 쓴다.
  - CLI 출력의 기호는 `render.ok_mark()`·`info_mark()`·`arrow()`로 만든다. 테스트 기대도 같은 함수로 만든다.
  - 식별자(테스트 함수 이름 포함)는 영어다.
- **서브에이전트 실행 규칙(Phase 5부터 이어짐):**
  - 삭제 명령(rm, Remove-Item, rmdir, git clean)을 쓰지 않는다. 임시 파일은 매번 새 임시 폴더를 만들어 쓰고, 정리가 필요하면 보고만 한다.
  - 다른 프로세스를 강제로 끝내지 않는다(taskkill, Stop-Process, kill). 테스트가 자기가 띄운 자식 프로세스를 끄는 것은 괜찮다.
  - 실제 `~/.logbook`, 실제 클립보드, 실제 브라우저를 쓰지 않는다. 실제 DB를 열지 않는다.
  - `lb serve`를 터미널에서 직접 띄우지 않는다.
  - **실제 외부 서비스를 부르지 않는다(Phase 7 추가):** Anthropic·OpenAI API, `gh`(GitHub 네트워크), `--install-completion`(사용자 셸 프로필을 고친다). 테스트는 가짜 클라이언트·가짜 `run_tool`을 쓴다. git은 `tmp_path`에 만든 임시 저장소에만 실행한다(`git init` 후 `-c user.email=… -c user.name=…`로 커밋, 사용자 git 설정을 고치지 않는다).
  - 환경변수 `ANTHROPIC_API_KEY`·`OPENAI_API_KEY`는 테스트에서 `monkeypatch.setenv`/`delenv`로만 다룬다. 실제 키 값을 출력하거나 파일에 쓰지 않는다.

---

## 파일 구조

| 파일 | 구분 | 책임 |
|---|---|---|
| `pyproject.toml`, `uv.lock` | 수정 | 선택 설치 `anthropic`·`openai`, dev 그룹에 두 SDK |
| `src/logbook/core/errors.py` | 수정 | `ExternalServiceError` |
| `src/logbook/core/external.py` | 생성 | `run_tool()`: 외부 명령 실행 공용 함수 |
| `src/logbook/core/config.py` | 수정 | `LlmConfig`(`[llm]`), 기본 설정 파일에 `[llm]` |
| `src/logbook/core/gitcollect.py` | 생성 | `collect_commits()`, `report_commits()`, `RepoCommits` |
| `src/logbook/core/report.py`, `core/templates/report.md.j2` | 수정 | `CommitLine`, `CommitGroup`, `ReportData.commits`·`summary`, 요약 절과 부록 |
| `src/logbook/core/github.py` | 생성 | `parse_repo()`, `list_issues()`, `Issue`, `issue_ref()` |
| `src/logbook/core/services/github_import.py` | 생성 | `plan_issue_import()`, `import_issues()` |
| `src/logbook/core/services/tasks.py`, `services/__init__.py` | 수정 | `existing_external_refs()`, 새 함수 공개 |
| `src/logbook/core/db.py` | 수정 | `open_readonly()`(자동완성 전용 읽기 전용 엔진) |
| `src/logbook/core/polish/__init__.py` | 생성 | 제공자 목록·선택(`available_providers`, `choose_provider`), `polish_report()` |
| `src/logbook/core/polish/prompt.py` | 생성 | 시스템 프롬프트, 보낼 JSON(`report_payload`), 응답 정리, 보낼 범위 요약 |
| `src/logbook/core/polish/sdk_errors.py` | 생성 | 두 SDK 예외 → `ExternalServiceError` 문구 |
| `src/logbook/core/polish/claude.py` | 생성 | Anthropic 호출 |
| `src/logbook/core/polish/chatgpt.py` | 생성 | OpenAI 호출 |
| `src/logbook/cli/commands/gitcollect.py` | 생성 | `lb git-collect` |
| `src/logbook/cli/commands/report.py` | 수정 | 커밋 부록, `--polish`, `--provider` |
| `src/logbook/cli/commands/task.py` | 수정 | `lb task import-gh`, 태스크 ID 자동완성 |
| `src/logbook/cli/completion.py` | 생성 | `complete_project()`, `complete_archived_project()`, `complete_task_id()` |
| `src/logbook/cli/runtime.py`, `commands/project.py`, `commands/timer.py`, `main.py` | 수정 | 옵션에 자동완성 연결, `add_completion=True`, 명령 등록 |
| `src/logbook/web/errors.py` | 수정 | `ExternalServiceError` → 502 `upstream` |
| `src/logbook/web/reporting.py` | 수정 | 커밋 부록 채우기와 경고 |
| `src/logbook/web/pages/report.py` | 수정 | 부록 경고, 다듬기 버튼 정보 |
| `src/logbook/web/pages/report_polish.py` | 생성 | `POST /report/polish` |
| `src/logbook/web/app.py` | 수정 | 라우터 등록 |
| `src/logbook/web/templates/partials/report_body.html`, `report_polish.html`(생성) | 수정·생성 | 버튼, 결과 패널, 경고 |
| `src/logbook/web/static/js/report.js`, `css/report.css` | 수정 | 복사 문구(`data-copy-done`), 결과 패널·진행 표시 |
| `tests/core/test_external.py`, `test_gitcollect.py`, `test_github.py`, `test_services_github_import.py`, `test_db_readonly.py`, `test_polish*.py` | 생성 | |
| `tests/cli/test_gitcollect.py`, `test_import_gh.py`, `test_completion.py`, `test_report_polish.py` | 생성 | |
| `tests/web/test_report_polish.py` | 생성 | |
| `docs/SPEC.md`, `README.md`, `docs/ROADMAP.md`, `CLAUDE.md`, `AGENTS.md` | 수정 | 문서 |

---

## Phase 7 공통 규칙

### 외부 명령 실행 (`core/external.py`)

```python
DEFAULT_TIMEOUT_SECONDS = 10.0

def run_tool(
    name: str,
    args: Sequence[str],
    *,
    missing_hint: str,
    label: str | None = None,  # 문구에 쓸 이름(예: "git log", "gh issue list"). None이면 name
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> str:
    """name(git, gh)을 shutil.which로 찾아 목록 인자로 실행하고 stdout(UTF-8, 잘못된 바이트는 대체)을 돌려준다.

    shell=False, capture_output, check=False. stdin은 subprocess.DEVNULL(gh가 입력을 기다리지 않게).
    실패는 모두 ExternalServiceError(한 줄 문구)다.
    """
```

| 경우 | 문구 |
|---|---|
| 실행 파일 없음 | `명령을 찾을 수 없습니다: {name}. {missing_hint}` |
| 시간 초과(`TimeoutExpired`) | `명령이 {초}초 안에 끝나지 않았습니다: {label}.` |
| 실행 실패(`OSError`) | `명령을 실행하지 못했습니다: {label} ({strerror}).` |
| 종료 코드 ≠ 0 | `명령이 실패했습니다: {label} (종료 코드 {code}). {stderr 첫 줄}` (stderr가 비면 마지막 문장 없음) |

- `{label}`은 `label or name`이다. git 호출은 `label="git log"`·`"git config"`, gh는 `"gh issue list"`를 넘긴다(git 인자는 `-C <경로>`로 시작해 `args[0]`을 문구에 쓸 수 없다).

- `missing_hint` 예: git은 `git을 설치하세요: https://git-scm.com`, gh는 `GitHub CLI를 설치한 뒤 'gh auth login'을 실행하세요: https://cli.github.com`.
- stderr 첫 줄은 앞뒤 공백을 지우고 200자에서 자른다(core 문구 규칙: 한 줄).
- 환경변수: `GH_PROMPT_DISABLED=1`, `GIT_TERMINAL_PROMPT=0`을 더한 `os.environ` 복사본을 넘긴다(대화형 입력 방지). 원래 `os.environ`은 바꾸지 않는다.

### 새 오류 `ExternalServiceError`

```python
class ExternalServiceError(LogbookError):
    """외부 명령(git, gh)이나 외부 API(Anthropic, OpenAI)가 실패한 경우. Web은 502로 매핑한다."""
```

- `web/errors.py`의 `classify()`에 `ErrorKind(502, "upstream")`을 더한다(`InvalidInputError`보다 먼저 검사할 필요는 없다. 서로 상속 관계가 없다).

### 설정 `[llm]`

```python
@dataclass(frozen=True)
class LlmConfig:
    provider: str = ""  # "" | "anthropic" | "openai". ""는 키가 있는 쪽을 고른다
    anthropic_model: str = "claude-opus-5-5"
    openai_model: str = "gpt-6.1-sol"
```

- `provider`가 `"", "anthropic", "openai"` 밖이면 기존 `_invalid` 문구(`설정할 수 있는 값: '', 'anthropic', 'openai'`)다.
- 모델 이름은 비어 있지 않은 문자열(`non_empty=True`)이다. 존재 여부는 API가 판단한다.
- `_Table.to_llm()`을 만들고 `to_config()`에서 `llm=self.table("llm").to_llm()`으로 부른다. 최상위 키 검사는 `_keys(Config)`가 새 필드를 자동으로 허용한다.
- `_default_document()`에 `"llm": asdict(defaults.llm)`을 더한다. `tests/core/test_config.py`의 `test_write_default_config_document`(문서 dict 전체 비교) 기대에 `"llm": {"provider": "", "anthropic_model": "claude-opus-5-5", "openai_model": "gpt-6.1-sol"}`를 더한다. 기본 설정 파일 끝에 `[llm]` 표가 생긴다. `Config.llm` 필드를 `web` 뒤에 둔다.

### 보고서 데이터 확장 (`core/report.py`)

```python
@dataclass(frozen=True)
class CommitLine:
    date: str  # "2026-10-12" (보고서 시간대의 작성 날짜)
    hash: str  # 앞 7자리
    subject: str  # 한 줄

@dataclass(frozen=True)
class CommitGroup:
    project: str  # 설정의 [[git.repos]].project
    repo: str  # 저장소 폴더 이름(path.name)
    commits: tuple[CommitLine, ...]

# ReportData 끝에 기본값 필드로 더한다(기존 생성 코드는 그대로 동작)
    commits: tuple[CommitGroup, ...] = ()
    summary: str = ""  # LLM 요약 문단(없으면 '')
```

기본 템플릿 변경:
- `작성자:` 줄 다음, `## 1. 공수 요약` 앞:
  ```
  {% if data.summary %}

  ## 요약 (자동 생성)
  {{ data.summary }}
  {% endif %}
  ```
- 4절 끝:
  ```
  {% if data.commits %}

  ## 부록. 커밋 내역
  {% for group in data.commits %}
  {% if not loop.first %}

  {% endif %}
  ### {{ group.project }} ({{ group.repo }})
  {% for commit in group.commits %}
  - {{ commit.date }} {{ commit.hash }} {{ commit.subject }}
  {% endfor %}
  {% endfor %}
  {% endif %}
  ```
- 두 값이 비면 출력은 지금과 바이트 단위로 같다(기존 렌더링 테스트가 그대로 통과해야 한다).
- 사용자 템플릿(`report.md.j2`)은 이 절을 자동으로 얻지 않는다. README에 `data.summary`, `data.commits`를 적는다.
- `/api/report?format=json`의 `dataclasses.asdict(data)`에 `commits`, `summary`가 함께 나온다(API 응답에 필드가 늘어남, SPEC 6장에 적는다).

### 사용자 문구 상수 위치

- core 문구는 각 모듈의 대문자 상수로 둔다. CLI·웹 테스트는 상수를 import해 기대값을 만든다.
- 웹 버튼 이름: `문장 다듬기 (Claude)`, `문장 다듬기 (ChatGPT)`. 제공자 표시 이름은 `core.polish.PROVIDER_LABELS`.

---

## Task 7-0: 계획 문서 저장

- [x] 이 계획서를 커밋한다: `docs: Phase 7 선택 기능 구현 계획 추가`

---

## Task 7-1: 공통 기반 — 외부 명령 실행, ExternalServiceError, [llm] 설정, 선택 의존성

**Files:**
- Modify: `pyproject.toml`, `uv.lock`, `src/logbook/core/errors.py`, `src/logbook/core/config.py`, `src/logbook/web/errors.py`
- Create: `src/logbook/core/external.py`, `tests/core/test_external.py`
- Modify tests: `tests/core/test_config.py`, `tests/core/test_errors.py`, `tests/web/test_errors.py`(`classify` parametrize에 케이스 추가)

**의존성:**
```
uv add --optional anthropic "anthropic>=1.13"
uv add --optional openai "openai>=3.29"
uv add --dev "anthropic>=1.13" "openai>=3.29"
```
- 설치 후 `uv run python -c "import anthropic, openai; print(anthropic.__version__, openai.__version__)"`로 버전을 확인해 커밋 본문에 적는다.
- 두 SDK가 의존하는 HTTP 라이브러리(`httpx2`)가 이미 dev 그룹에 있는 버전과 충돌하면 멈추고 보고한다(버전을 마음대로 낮추지 않는다).

**테스트 케이스**

| 대상 | 케이스 | 기대 |
|---|---|---|
| `run_tool` | `shutil.which`가 None | `ExternalServiceError`, 없음 문구 + hint |
| `run_tool` | 가짜 `subprocess.run`이 stdout `"한글\n".encode()` 반환 | `"한글\n"`. 넘긴 인자가 `[찾은 경로, *args]`, `shell=False`, `stdin=DEVNULL`, `timeout`, env에 `GH_PROMPT_DISABLED=1`·`GIT_TERMINAL_PROMPT=0` |
| `run_tool` | 종료 코드 1, stderr `"fatal: bad\nmore"` / 빈 stderr | 첫 줄만 담은 문구 / 마지막 문장 없음 |
| `run_tool` | 잘못된 UTF-8 바이트 | 대체 문자로 디코드(예외 없음) |
| `run_tool` | `TimeoutExpired`, `OSError` | 각 문구 |
| `run_tool` | 실제 `python -c "print('ok')"`(name=`sys.executable` 경로를 which가 찾게) | `"ok\n"`. 이 테스트 하나만 실제 프로세스를 띄운다 |
| config | `[llm]` 없음 | 기본값(`""`, `claude-opus-5-5`, `gpt-6.1-sol`) |
| config | `provider = "openai"`, 모델 두 개 바꿈 | 그대로 |
| config | `provider = "gemini"`, 모델 `""`, 모르는 키 | 각 기존 문구 |
| config | `write_default_config` 결과를 다시 읽기 | 기본값과 같고 `[llm]` 표가 있다 |
| web `classify` | `ExternalServiceError("x")` | `(502, "upstream")`. HTMX 요청은 알림 영역, JSON API는 봉투 `upstream` |

- [x] RED → GREEN → 커밋 `feat: 외부 명령 실행 함수와 외부 오류, [llm] 설정, LLM 선택 설치 추가`

---

## Task 7-2: core — 커밋 수집과 보고서 부록·요약 절

**Files:**
- Create: `src/logbook/core/gitcollect.py`, `tests/core/test_gitcollect.py`
- Modify: `src/logbook/core/report.py`, `src/logbook/core/templates/report.md.j2`
- Modify tests: `tests/core/test_report_render.py`

```python
# core/gitcollect.py
@dataclass(frozen=True)
class RepoCommits:
    project: str
    path: Path
    commits: tuple[CommitLine, ...]
    error: str = ""  # 이 저장소에서 실패했으면 한국어 한 줄, 아니면 ''

def collect_commits(git: GitConfig, week: Week, *, tz: tzinfo, run: RunTool = run_tool) -> tuple[RepoCommits, ...]:
    """설정의 저장소마다 week 동안의 본인 커밋을 모은다. 저장소 하나의 실패는 error에 담고 계속한다."""

def to_commit_groups(results: Sequence[RepoCommits]) -> tuple[CommitGroup, ...]:
    """커밋이 있는 저장소만 설정 순서대로 CommitGroup으로 바꾼다."""

def report_commits(cfg: Config, week: Week, *, tz: tzinfo, run: RunTool = run_tool) -> tuple[tuple[CommitGroup, ...], tuple[str, ...]]:
    """보고서 부록용: (커밋 묶음, 경고 문구들). include_commits가 false거나 저장소가 없으면 ((), ())."""
```
- `RunTool`은 `run_tool`과 같은 시그니처의 `Callable` 별칭(`core.external`에 둔다). 테스트가 가짜를 넘긴다.

**저장소 하나의 처리 순서**
1. `path.is_dir()`가 아니면 `error = 저장소 폴더가 없습니다: {path}. 설정의 [[git.repos]] path를 확인하세요.`
2. 이메일: `git.author_email`이 비면 `run("git", ["-C", path, "config", "user.email"], label="git config")`의 첫 줄. 이 명령이 실패하거나(설정 없음은 종료 코드 1) 비면 `error = 작성자 이메일을 알 수 없습니다: {path}. 설정 [git].author_email을 지정하세요.`
3. 기록:
   ```
   git -C <path> -c i18n.logOutputEncoding=UTF-8 log --all --no-merges --reverse
       --fixed-strings --regexp-ignore-case --author=<이메일>
       --since=<주 시작 00:00, tz의 ISO 8601> --until=<주 끝 다음 날 00:00, ISO 8601>
       --format=%H%x1f%aI%x1f%s
   ```
   - 시각은 `week.start`와 `week.end` 다음 날의 tz 자정(`datetime.combine(day, time(), tzinfo=tz)`)을 `isoformat()`으로 쓴다.
   - 지원 범위 끝의 주(0001-W01, 9999-W52)에서 날짜 계산이 `OverflowError`·`ValueError`를 내면 모든 저장소의 `error`를 `이 주의 커밋은 모을 수 없습니다: {주차}.`로 하고 git을 실행하지 않는다.
   - 각 줄을 `\x1f`로 3칸 나눈다. 칸 수가 다르면 그 줄을 건너뛴다.
   - 날짜는 `datetime.fromisoformat(aI).astimezone(tz).date().isoformat()`, 해시는 앞 7자, 제목은 `strip()`.
   - `--since`/`--until`은 커미터 날짜 기준이라 범위 밖 작성 날짜의 커밋이 섞일 수 있다. 작성 날짜가 `week.start..week.end` 밖인 줄은 버린다.
4. `ExternalServiceError`는 `error = str(error)`로 담는다. 그 밖의 예외는 잡지 않는다.

**테스트 케이스**

| 대상 | 케이스 | 기대 |
|---|---|---|
| `collect_commits` | 가짜 run: 두 저장소, 각 2줄 | 순서·날짜·7자 해시·제목, 넘긴 인자(위 형식 그대로) |
| `collect_commits` | author_email 비어 있음 → config 조회 결과 사용 / 조회 실패 | 이메일 반영 / 이메일 문구 |
| `collect_commits` | 없는 폴더, run이 `ExternalServiceError` | 각 `error`, 다른 저장소는 계속 |
| `collect_commits` | 칸이 모자란 줄, 주 밖 날짜 | 버림 |
| `collect_commits` | KST(+09:00) tz, 2026-W42 | `--since=2026-10-12T00:00:00+09:00`, `--until=2026-10-19T00:00:00+09:00` |
| `collect_commits` | **실제 git**: `tmp_path`에 `git init`, `-c user.email=me@example.com -c user.name=me commit`(날짜는 `GIT_AUTHOR_DATE`·`GIT_COMMITTER_DATE`). **지난주 커밋을 먼저, 이번 주 커밋을 나중에** 만든다(git은 `--since`보다 오래된 커밋을 만나면 탐색을 멈춘다). 다음 주 월요일 00:00 커밋(끝 경계, git `--until`이 포함한다)과 다른 이메일 커밋도 하나씩 | 이번 주 본인 커밋 1건, 한글 제목 그대로(경계 커밋은 Python 필터가 버린다). git이 없으면 `pytest.skip` |
| `to_commit_groups` | 커밋 0건 저장소, 오류 저장소 섞임 | 커밋 있는 저장소만 |
| `report_commits` | include_commits false / 저장소 없음 / 정상 + 오류 하나 | `((), ())` / `((), ())` / (묶음, (오류 문구,)) |
| 렌더링 | summary·commits 비어 있음 | 기존 기대 출력과 같다 |
| 렌더링 | summary `"요약 문단"` | 작성자 줄 다음 빈 줄, `## 요약 (자동 생성)`, 문단, 빈 줄, `## 1.` |
| 렌더링 | author 없음 + summary | 제목 다음 빈 줄, 요약 절 |
| 렌더링 | commits 두 묶음 | 4절 끝 빈 줄, `## 부록. 커밋 내역`, 묶음 사이 빈 줄, `- 2026-10-12 a1b2c3d 제목` |

- [x] RED → GREEN → 커밋 `feat: git 커밋 수집과 보고서 요약 절·커밋 부록 추가`

---

## Task 7-3: CLI·웹 — `lb git-collect`와 보고서 부록 연결

**Files:**
- Create: `src/logbook/cli/commands/gitcollect.py`, `tests/cli/test_gitcollect.py`
- Modify: `src/logbook/cli/main.py`(등록), `src/logbook/cli/commands/report.py`, `src/logbook/web/reporting.py`, `src/logbook/web/pages/report.py`, `src/logbook/web/api/report.py`, `src/logbook/web/templates/partials/report_body.html`
- Modify tests: `tests/cli/test_report.py`, `tests/cli/test_entry.py`(가드 parametrize에 `git-collect-help`), `tests/web/test_report_page.py`(이름은 보고서 화면 테스트 파일), `tests/web/test_api_report.py`

**`lb git-collect [--week]`**
- 순서: 주차 검증(DB·설정 없이 가능한 것 먼저) → 설정 → `collect_commits(cfg.git, week, tz=runtime.now().tzinfo)`. DB를 열지 않는다(SQLAlchemy를 로드하지 않는다. 가드 테스트로 확인).
- 저장소가 없으면 `InvalidInputError`: `설정된 저장소가 없습니다. 설정 파일에 [[git.repos]]를 추가하세요.`
- 출력(저장소마다):
  ```
  payment (payment-server) 2건
    2026-10-12 a1b2c3d 재시도 백오프 구현
    2026-10-13 b2c3d4e 환불 API 초안
  admin (admin-web) 0건
  ```
  - 머리 줄은 `render`에 `commit_heading()`을 두지 말고 이 모듈 안에서 Rich `Text`로 만든다(마크업 해석 안 함).
  - 오류 저장소는 `console.print_warning(error)` 한 줄.
- 오류 저장소가 하나라도 있으면 모두 출력한 뒤 `LogbookError(f"저장소 {n}곳에서 커밋을 읽지 못했습니다.")`로 종료 1.
- help: `설정한 git 저장소에서 이번 주 본인 커밋을 모아 보여 줍니다. DB에는 저장하지 않습니다.`
- `main.py`의 `COMMAND_MODULES`에서 `report` 다음에 둔다.

**`lb report`**
- `_build_markdown`을 `_build_data(week) -> ReportBuild`(NamedTuple: `cfg`, `week`, `tz`, `data`)와 `_render(data: ReportData) -> str`(기존 사용자 템플릿 처리)로 나눈다. `report()`는 `_build_data` → `replace(data, commits=…)` → `_render` → `_deliver` 순서다. Task 7-8은 `_render` 앞에 요약 `replace`를 끼운다.
- 세션을 닫은 뒤 `report_commits(cfg, week, tz=tz)`로 부록을 채우고(`dataclasses.replace`), 경고는 `console.print_warning` 각 한 줄(stderr). 보고서는 그대로 나온다.

**웹**
- `web/reporting.py`에 `report_with_commits(ctx, data, week, now) -> tuple[ReportData, tuple[str, ...]]`를 더한다. `report_data`는 그대로 둔다.
- `report_page`, `_conflict_response`, `report_download`, `_save`의 응답(특이사항 저장 뒤 미리보기), `api/report.get_report` 다섯 곳이 모두 세션을 닫은 뒤 이 함수를 부른다(git 실행 동안 DB 세션을 잡지 않는다). `_load`는 지금처럼 data와 note만 돌려준다. `_week_error_response`(데이터 없음)와 `/report/polish`는 부르지 않는다.
- 화면: 경고가 있으면 미리보기 위에 `<ul class="report__warnings" role="status">`로 한 줄씩. API는 경고를 응답에 넣지 않는다(JSON 데이터에는 commits만).
- `ReportBodyView`에 `warnings: tuple[str, ...] = ()`.

**테스트 케이스**

| 대상 | 케이스 | 기대 |
|---|---|---|
| `lb git-collect` | 가짜 `collect_commits`(monkeypatch `logbook.core.gitcollect.collect_commits`) 두 저장소 | 위 출력 |
| `lb git-collect` | 저장소 없음 | 종료 1, 문구 |
| `lb git-collect` | 저장소 하나 오류 | 경고 줄, 마지막 문구, 종료 1 |
| `lb git-collect --week 2026-W99` | 잘못된 주차 | 종료 1, SQLAlchemy 로드 안 함 |
| `lb report` | include_commits true, 가짜 수집 결과 | 부록이 붙는다 |
| `lb report` | 수집 경고 | stderr에 경고, stdout 보고서는 그대로 |
| 웹 `/report` | 가짜 수집(커밋·경고) | 미리보기에 부록, 경고 목록 |
| 웹 `/report/download`, `/api/report?format=json` | 가짜 수집 | 부록 포함 / `commits` 배열 |
| 웹 | 특이사항 저장 응답, 409 응답 | 부록이 남아 있다 |
| 웹 | 저장소 설정 없음 | 경고 목록 없음, 부록 없음 |

- [x] RED → GREEN → 커밋 `feat: lb git-collect와 보고서 커밋 부록(CLI·웹·API) 추가`

---

## Task 7-4: GitHub 이슈 가져오기 `lb task import-gh`

**Files:**
- Create: `src/logbook/core/github.py`, `src/logbook/core/services/github_import.py`, `tests/core/test_github.py`, `tests/core/test_services_github_import.py`, `tests/cli/test_import_gh.py`
- Modify: `src/logbook/core/services/tasks.py`, `src/logbook/core/services/__init__.py`, `src/logbook/cli/commands/task.py`
- Modify tests: `tests/cli/test_entry.py`(가드: `task-import-gh-help`, `task-import-gh-bad-repo`, `task-import-gh-bad-state`)

```python
# core/github.py (DB 없음)
@dataclass(frozen=True)
class Issue:
    number: int
    title: str
    url: str

ISSUE_STATES = ("open", "closed", "all")
MAX_ISSUE_LIMIT = 1000
DEFAULT_ISSUE_LIMIT = 100

def parse_repo(text: str) -> str:
    """'owner/repo'만 받는다(앞뒤 공백 제거). 형식이 다르면 InvalidInputError."""
def check_state(text: str) -> str
def check_limit(value: int) -> int
def list_issues(repo: str, *, labels: Sequence[str], state: str, limit: int, run: RunTool = run_tool) -> tuple[Issue, ...]:
    """gh issue list -R repo --state state --limit limit --json number,title,url [--label L ...]"""
def issue_ref(repo: str, number: int) -> str:
    return f"{repo}#{number}"
```
- 저장소 형식: `^[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9._-]+$`(ASCII). 문구 `저장소 형식이 올바르지 않습니다: '{echo}'. owner/repo 형식으로 쓰세요 (예: chanyoo-93/logbook).`
- 상태 문구 `이슈 상태가 올바르지 않습니다: '{echo}'. open, closed, all 중 하나를 쓰세요.`, 개수 문구 `가져올 개수는 1~1000 사이의 정수여야 합니다: {값}`.
- gh 출력은 JSON 배열이어야 하고 각 원소에 정수 `number`, 문자열 `title`·`url`이 있어야 한다. 아니면 `ExternalServiceError`: `gh 출력을 읽지 못했습니다. gh를 최신 버전으로 업데이트하세요.`
- gh 시간 제한은 30초(`run_tool(..., timeout=30.0)`).

```python
# core/services/tasks.py
def existing_external_refs(s: Session, refs: Collection[str]) -> set[str]:
    """refs 가운데 이미 어떤 태스크(상태·보관 무관)의 external_ref인 것."""

# core/services/github_import.py
@dataclass(frozen=True)
class IssueImport:
    new: tuple[Issue, ...]
    skipped: tuple[Issue, ...]  # 같은 external_ref의 태스크가 이미 있음

@dataclass(frozen=True)
class IssueImportResult:
    created: tuple[Task, ...]
    skipped: tuple[Issue, ...]

def plan_issue_import(s: Session, repo: str, issues: Sequence[Issue]) -> IssueImport
def import_issues(
    s: Session, repo: str, issues: Sequence[Issue], *, project_slug: str,
    category: str | None, planned_week: Week | None, allowed_categories: Collection[str],
) -> IssueImportResult:
    """새 이슈마다 create_task(title=이슈 제목, external_ref=issue_ref(...)). 이슈 번호 오름차순."""
```
- 같은 응답에 같은 번호가 두 번 오면 한 번만 만든다.
- 제목이 공백뿐인 이슈는 GitHub가 허용하지 않으므로 따로 처리하지 않는다. 생기면 `create_task`의 core 문구로 끝나고 세션이 롤백되어 아무것도 추가되지 않는다(테스트 하나로 확인).

**CLI**
```
lb task import-gh OWNER/REPO [--label/-l 라벨 …] [--state open] [--limit 100]
                  [-p 프로젝트] [-c 카테고리] [-w 주차] [--dry-run]
```
- 순서: `parse_repo`·`check_state`·`check_limit`·주차 형식(설정 필요 시 설정 먼저) → `list_issues` → DB.
- 출력:
  - 추가: `{ok_mark} 이슈를 태스크로 가져왔습니다: 추가 {n}건, 건너뜀 {m}건 (이미 있음)` 다음 줄마다 `  ` + `render.task_line(task)`.
  - `--dry-run`: `{info_mark} 가져올 이슈: {n}건, 건너뛸 이슈: {m}건 (이미 있음). --dry-run이라 추가하지 않았습니다.` 다음 줄마다 `  #{번호} {제목}`.
  - 이슈가 0건: `{info_mark} 가져올 이슈가 없습니다: {repo}`.
- help: `GitHub 이슈를 할 일 태스크로 가져옵니다. gh CLI가 필요합니다. 이미 가져온 이슈는 건너뜁니다.`

**테스트 케이스**

| 대상 | 케이스 | 기대 |
|---|---|---|
| `parse_repo` | `"a/b"`, `" a-1/b.c_d "`, `"a"`, `"a/b/c"`, `"https://github.com/a/b"`, `"한/글"` | 통과 2 / 거부 4 |
| `list_issues` | 가짜 run, 라벨 2개 | 인자 `["issue","list","-R","a/b","--state","open","--limit","100","--json","number,title,url","--label","bug","--label","ui"]`, timeout 30 |
| `list_issues` | JSON 아님, 객체, 필드 타입 틀림 | 각 `ExternalServiceError` 문구 |
| `existing_external_refs` | done·dropped·보관 프로젝트 태스크 포함 | 모두 포함 |
| `import_issues` | 새 2 + 기존 1 + 중복 번호 | 2건 생성(번호순, todo, ref `a/b#N`, 프로젝트·카테고리·주차), skipped 1 |
| `import_issues` | 보관 프로젝트, 모르는 카테고리 | 기존 core 문구, 아무것도 만들지 않음 |
| CLI | 가짜 `list_issues`(monkeypatch `logbook.core.github.list_issues`) | 출력·DB |
| CLI | `--dry-run` | DB 변화 없음, 출력 |
| CLI | 두 번 실행 | 두 번째는 추가 0, 건너뜀 n |
| CLI | gh 없음(가짜가 `ExternalServiceError`) | 종료 1, 문구 |
| 가드 | `--help`, 잘못된 저장소, 잘못된 상태 | SQLAlchemy 로드 안 함 |

- [x] RED → GREEN → 커밋 `feat: lb task import-gh로 GitHub 이슈를 태스크로 가져오기`

---

## Task 7-5: 셸 자동완성

**Files:**
- Create: `src/logbook/cli/completion.py`, `tests/cli/test_completion.py`, `tests/core/test_db_readonly.py`
- Modify: `src/logbook/core/db.py`, `src/logbook/cli/main.py`, `src/logbook/cli/runtime.py`, `src/logbook/cli/commands/task.py`, `src/logbook/cli/commands/project.py`, `src/logbook/cli/commands/timer.py`(`-t` 쓰는 곳이 runtime.TaskOpt면 수정 불필요)

```python
# core/db.py
def open_readonly(path: Path | str) -> Engine | None:
    """자동완성 전용. 파일이 있고 스키마 버전이 SCHEMA_VERSION과 같을 때만 읽기 전용 엔진을 준다.

    sqlite3.connect(Path(path).absolute().as_uri() + "?mode=ro", uri=True)를 creator로 쓴다.
    파일을 만들거나 마이그레이션하지 않는다. 없거나 버전이 다르거나 열 수 없으면 None(엔진은 dispose).
    """
```

```python
# cli/completion.py (상단에서 typer·core를 import하지 않는다. 모두 함수 안에서 지연 import)
def complete_project(incomplete: str) -> list[tuple[str, str]]:
    """보관하지 않은 프로젝트: (slug, 이름). slug 순."""
def complete_archived_project(incomplete: str) -> list[tuple[str, str]]:
    """보관한 프로젝트(lb project unarchive용)."""
def complete_any_project(incomplete: str) -> list[tuple[str, str]]:
    """보관 포함 모든 프로젝트(조회 옵션용, 예: lb task list -p)."""
def complete_task_id(incomplete: str) -> list[tuple[str, str]]:
    """todo·doing 태스크: (ID 문자열, 제목). ID 순. '#'으로 시작하면 '#'을 붙인 값."""
```
- 공통: `load_config()` → `open_readonly(cfg.db_path)` → `session_scope(engine)`에서 `services.list_projects(s, include_archived=True)`/`list_tasks(s, statuses=OPEN_STATUSES)`(`OPEN_STATUSES`는 `core.taskstatus`). 모든 예외(설정 오류 포함)를 잡아 `[]`. 엔진은 항상 dispose. 앞부분 거르기는 Typer가 한다(그래도 `incomplete`로 먼저 걸러 DB 결과를 줄인다).
- 제목은 한 줄로(줄바꿈을 공백으로) 60자에서 자른다(셸 표시용).
- 연결:
  - `runtime.ProjectOpt`: `autocompletion=completion.complete_project`
  - `runtime.TaskOpt`, `task.TaskIdArg`: `complete_task_id`
  - `lb project edit|archive SLUG`: `complete_project`, `lb project unarchive SLUG`: `complete_archived_project`
  - `runtime.ProjectOpt`가 아닌 따로 정의한 프로젝트 옵션도 연결한다(`grep -rn '"--project"' src/logbook/cli`로 찾는다). 보관한 프로젝트도 받는 조회 옵션(예: `lb task list -p`, task.py 100행대)은 `complete_any_project`를 쓴다.
- `main.py`: `add_completion=True`로 바꾸고 주석을 지운다. `--install-completion`, `--show-completion`은 Typer 기본 영어 help다(SPEC 8의 예외 범위: 프레임워크 기본 문구).
- `runtime.py`가 `cli.completion`을 import해도 `--help`에서 SQLAlchemy가 로드되지 않아야 한다(기존 가드 테스트가 지킨다).

**테스트 케이스**

| 대상 | 케이스 | 기대 |
|---|---|---|
| `open_readonly` | 파일 없음 / v1 DB(`tests/core`의 v1 DB 헬퍼) / 현재 DB | None(파일을 만들지 않음) / None(버전 그대로, 백업 없음) / 엔진 |
| `open_readonly` | 엔진으로 쓰기 시도 | `OperationalError`(읽기 전용) |
| `open_readonly` | 경로에 한글·공백·`#` | 열린다 |
| `complete_project` | 활성 2 + 보관 1, `incomplete="pa"` | 활성 중 `pa`로 시작하는 것만 |
| `complete_archived_project` | 같은 DB | 보관 1 |
| `complete_any_project` | 같은 DB | 3개 |
| `complete_task_id` | todo·doing·done, `"#"` 시작 | 열린 것만, `#` 붙임, 긴 제목 자름 |
| 공통 | DB 없음, 설정 TOML 오류 | `[]`, 예외 없음 |
| 통합 | `CliRunner().invoke(app, [], prog_name="lb", env={"_LB_COMPLETE": "complete_bash", "COMP_WORDS": "lb add 1h x -p ", "COMP_CWORD": "5"})` | 출력에 활성 slug. `prog_name`을 빼면 변수 이름이 `_ROOT_COMPLETE`가 되어 실패한다. PowerShell 형식은 `COMP_WORDS`를 쓰지 않으므로 테스트는 bash 형식만 쓴다 |
| 통합 | `lb --help` | `--install-completion`, `--show-completion`이 보인다 |
| 가드 | `lb --help`, `lb task start --help` | SQLAlchemy 로드 안 함 |

- 실제 `--install-completion`은 실행하지 않는다(사용자 셸 프로필을 고친다). `--show-completion`도 셸 감지를 하므로 테스트하지 않는다.

- [x] RED → GREEN → 커밋 `feat: 셸 자동완성과 프로젝트·태스크 ID 완성 추가`

---

## Task 7-6: LLM 공통 core와 Anthropic(Claude)

effort high: 공용 인터페이스·오류 매핑·SDK 사용을 처음 정하는 Task라 설계 판단이 필요하다.

**Files:**
- Create: `src/logbook/core/polish/__init__.py`, `prompt.py`, `sdk_errors.py`, `claude.py`, `tests/core/test_polish.py`, `tests/core/test_polish_claude.py`

```python
# core/polish/__init__.py
PROVIDERS = ("anthropic", "openai")
PROVIDER_LABELS = MappingProxyType({"anthropic": "Claude", "openai": "ChatGPT"})
KEY_ENV = MappingProxyType({"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY"})
EXTRA = MappingProxyType({"anthropic": "anthropic", "openai": "openai"})  # 패키지·extra 이름

@dataclass(frozen=True)
class PolishResult:
    provider: str
    model: str
    summary: str

def available_providers() -> tuple[str, ...]:
    """키(비어 있지 않은 환경변수)와 패키지(importlib.util.find_spec)가 모두 있는 제공자. PROVIDERS 순."""
def choose_provider(llm: LlmConfig, requested: str | None) -> str:
    """requested > llm.provider > 사용 가능한 첫 제공자. 고른 제공자를 못 쓰면 InvalidInputError."""
def model_for(llm: LlmConfig, provider: str) -> str
def polish_report(data: ReportData, llm: LlmConfig, provider: str, *, client: Any = None) -> PolishResult:
    """보고서 데이터로 요약 문단을 받는다. client는 테스트용(SDK 클라이언트 대역)."""
```

| 경우 | 문구(InvalidInputError) |
|---|---|
| 모르는 제공자 | `제공자 이름이 올바르지 않습니다: '{echo}'. anthropic 또는 openai를 쓰세요.` |
| 쓸 수 있는 제공자 없음 | `문장 다듬기를 쓸 수 있는 제공자가 없습니다. ANTHROPIC_API_KEY나 OPENAI_API_KEY를 설정하고 'uv sync --extra anthropic'이나 'uv sync --extra openai'로 패키지를 설치하세요.` |
| 키 없음 | `환경변수가 없습니다: {env}. {label} 문장 다듬기를 쓰려면 API 키를 설정하세요.` |
| 패키지 없음 | `패키지가 설치되어 있지 않습니다: {extra}. 'uv sync --extra {extra}'로 설치하세요.` |

```python
# core/polish/prompt.py
SYSTEM_PROMPT = (
    "당신은 소프트웨어 개발자의 주간업무보고서에 넣을 실적 요약을 쓰는 도우미입니다. "
    "사용자가 보내는 JSON(한 주의 공수 표, 프로젝트별 태스크, 특이사항·리스크, 다음 주 계획)만 근거로 "
    "한국어 문단 하나를 3~5문장으로 쓰세요. 시간·건수는 데이터의 값을 그대로 쓰고, 데이터에 없는 "
    "사실이나 평가를 지어내지 마세요. 제목·목록·Markdown 서식 없이 '~했습니다' 체의 평문만 쓰세요."
)
def report_payload(data: ReportData) -> str:
    """보낼 JSON: asdict(data)에서 summary·commits·author를 뺀 것. ensure_ascii=False, sort_keys=True, indent=None."""
def send_scope(data: ReportData) -> str:
    """확인 문구용: '2026-W42 보고서 데이터(프로젝트 3개, 태스크 7건, 특이사항·리스크 포함)'.
    특이사항·리스크가 둘 다 비면 '(…, 특이사항·리스크 없음)'. 커밋 내역과 작성자는 보내지 않는다."""
def clean_summary(text: str) -> str:
    """앞뒤 공백 제거, 줄바꿈 여러 개는 한 줄로 합친다(문단 하나). 비면 ''."""
```
- 커밋 제목과 작성자 이름은 보내지 않는다(외부 전송 최소화). README·확인 문구에 적는다.
- 프로젝트 개수는 `len(data.matrix)`, 태스크 건수는 `sum(len(section.tasks))`이다.

```python
# core/polish/sdk_errors.py
def to_external_error(
    error: Exception, sdk: ModuleType, *, provider: str, model: str, timeout: float
) -> ExternalServiceError | None:
    """두 SDK 공통 예외 이름으로 판정한다. 해당하지 않으면 None(호출자가 다시 던진다).

    timeout은 호출한 제공자 모듈(claude.py·chatgpt.py)의 TIMEOUT_SECONDS다. 이 모듈은 그 상수를 import하지 않는다.
    """
```

| SDK 예외(검사 순서) | 문구(ExternalServiceError) |
|---|---|
| `AuthenticationError`, `PermissionDeniedError` | `{label} API 키가 올바르지 않거나 권한이 없습니다. 환경변수 {env}를 확인하세요.` |
| `NotFoundError` | `{label} 모델을 쓸 수 없습니다: {model}. 설정 [llm].{provider}_model을 확인하세요.` |
| `RateLimitError` | `{label} 요청 한도를 넘었습니다. 잠시 후 다시 시도하세요.` |
| `APITimeoutError`(APIConnectionError보다 먼저) | `{label} 응답이 {timeout:.0f}초 안에 오지 않았습니다. 잠시 후 다시 시도하세요.` |
| `APIConnectionError` | `{label} 서버에 연결하지 못했습니다. 인터넷 연결을 확인하세요.` |
| `APIStatusError` | `{label} 요청이 실패했습니다 (HTTP {status_code}). 잠시 후 다시 시도하세요.` |

공용 문구(`prompt.py`의 상수): 거절 `{label} 모델이 요약을 거절했습니다. 다른 제공자로 다시 시도하세요.`, 빈 응답 `{label} 응답에 요약 문장이 없습니다. 다시 시도하세요.`, 길이 초과 `{label} 응답이 길이 제한에 걸려 끝까지 오지 않았습니다. 다시 시도하세요.`

```python
# core/polish/claude.py
TIMEOUT_SECONDS = 60.0
MAX_TOKENS = 4000
EFFORT = "low"
# 거절 시 서버가 다른 모델로 다시 시도하는 기능(beta)을 받는 모델
FALLBACK_MODELS = frozenset({"claude-fable-5-1", "claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5"})
FALLBACK_BETA = "server-side-fallback-2026-07-01"

def summarize(system: str, user: str, *, model: str, client: Any = None) -> str:
    import anthropic
    api = client if client is not None else anthropic.Anthropic(timeout=TIMEOUT_SECONDS, max_retries=2)
    request = {
        "model": model,
        "max_tokens": MAX_TOKENS,
        "system": system,
        "messages": [{"role": "user", "content": user}],
        "output_config": {"effort": EFFORT},
    }
    if model in FALLBACK_MODELS:
        response = api.beta.messages.create(**request, betas=[FALLBACK_BETA], fallbacks="default")
    else:
        response = api.messages.create(**request)
    # stop_reason: "refusal" → 거절 문구, "max_tokens" → 길이 초과 문구
    return "".join(block.text for block in response.content if block.type == "text")
```
- `thinking` 인자를 보내지 않는다(Opus 5.5는 thinking을 끌 수 없고 effort로만 조절한다. `budget_tokens`는 400).
- SDK 예외는 `to_external_error(error, anthropic, …)`로 바꾼다. None이면 그대로 다시 던진다.
- `polish_report`의 흐름: `prompt.report_payload` → 제공자 모듈의 `summarize` → `clean_summary` → 비면 빈 응답 문구.
- 클라이언트 대역은 `SimpleNamespace`로 `messages.create`·`beta.messages.create`를 흉내 낸다. 넘긴 인자를 기록해 확인한다. SDK 예외 객체는 실제 클래스로 만든다(예: `anthropic.RateLimitError("x", response=httpx2.Response(429, request=httpx2.Request("POST", "https://api.anthropic.com/v1/messages")), body=None)`. 생성자 시그니처가 다르면 설치된 SDK의 `_exceptions.py`를 읽고 맞춘다).

**테스트 케이스**

| 대상 | 케이스 | 기대 |
|---|---|---|
| `available_providers` | 키·패키지 조합 4가지(monkeypatch env·`find_spec`) | 각 결과 |
| `choose_provider` | requested 있음 / 설정 있음 / 둘 다 없고 openai만 가능 / 둘 다 가능 | 각각 / `openai` / `anthropic` |
| `choose_provider` | 모르는 이름, 키 없음, 패키지 없음, 아무것도 없음 | 각 문구 |
| `report_payload` | summary·commits·author가 채워진 데이터 | 세 키 없음, 한글 그대로, 정렬된 키 |
| `send_scope` | 특이사항 있음 / 없음 | 두 문구 |
| `clean_summary` | `"  첫 줄\n\n둘째 줄 \n"` | `"첫 줄 둘째 줄"` |
| `claude.summarize` | 기본 모델 | beta 경로, `betas`·`fallbacks="default"`, `output_config`, `thinking` 없음, 텍스트 블록만 합침 |
| `claude.summarize` | `claude-haiku-5-5` | 일반 경로, fallbacks 없음 |
| `claude.summarize` | client None | `anthropic.Anthropic(timeout=60.0, max_retries=2)` 생성(monkeypatch로 가짜 클래스) |
| `claude.summarize` | stop_reason refusal / max_tokens | 각 문구 |
| `claude.summarize` | SDK 예외 6종 + 그 밖의 예외 | 표의 문구 / 그대로 전파 |
| `polish_report` | 가짜 클라이언트 응답 `"  요약\n"` / `""` | `PolishResult("anthropic", 모델, "요약")` / 빈 응답 문구 |

- [x] RED → GREEN → 커밋 `feat: LLM 문장 다듬기 공통 core와 Claude(Anthropic) 제공자 추가`

---

## Task 7-7: OpenAI(ChatGPT) 제공자

**Files:**
- Create: `src/logbook/core/polish/chatgpt.py`, `tests/core/test_polish_chatgpt.py`
- Modify: `src/logbook/core/polish/__init__.py`(제공자 연결), `tests/core/test_polish.py`

```python
# core/polish/chatgpt.py
TIMEOUT_SECONDS = 60.0
MAX_OUTPUT_TOKENS = 4000
EFFORT = "low"

def summarize(system: str, user: str, *, model: str, client: Any = None) -> str:
    import openai
    api = client if client is not None else openai.OpenAI(timeout=TIMEOUT_SECONDS, max_retries=2)
    response = api.responses.create(
        model=model,
        instructions=system,
        input=user,
        reasoning={"effort": EFFORT},
        max_output_tokens=MAX_OUTPUT_TOKENS,
    )
    # response.status == "incomplete" → 길이 초과 문구
    # response.output 안의 message 항목 content에 type == "refusal"이 있고 output_text가 비면 거절 문구
    return response.output_text
```
- 근거(2026-10-14 확인): openai-python README의 Responses API 예(`client.responses.create(model=…, instructions=…, input=…)`, `response.output_text`), OpenAI 추론 가이드의 `reasoning={"effort": "low"}`, 모델 페이지의 `gpt-6.1-sol`(지능·비용 균형, effort `low`~`max`). 사용자가 `gpt-6-astra`는 크다고 해서 `gpt-6.1-sol`을 기본으로 했다.
- 예외는 `to_external_error(error, openai, …)`(같은 예외 이름: `AuthenticationError`, `PermissionDeniedError`, `NotFoundError`, `RateLimitError`, `APITimeoutError`, `APIConnectionError`, `APIStatusError`).
- 설치된 SDK에서 `responses.create`의 인자 이름이 다르면(예: `max_output_tokens`) 설치본의 `resources/responses` 시그니처를 읽고 맞춘 뒤 계획과 다른 점을 보고한다.

**테스트 케이스**

| 대상 | 케이스 | 기대 |
|---|---|---|
| `chatgpt.summarize` | 정상 | 넘긴 인자(위 그대로), `output_text` |
| `chatgpt.summarize` | client None | `openai.OpenAI(timeout=60.0, max_retries=2)` |
| `chatgpt.summarize` | status incomplete / 거절 항목 | 각 문구 |
| `chatgpt.summarize` | SDK 예외 6종(실제 클래스) + 그 밖의 예외 | 표의 문구 / 그대로 전파 |
| `polish_report` | provider `openai` | `PolishResult("openai", "gpt-6.1-sol", …)` |

- [x] RED → GREEN → 커밋 `feat: LLM 문장 다듬기에 ChatGPT(OpenAI) 제공자 추가`

---

## Task 7-8: CLI `lb report --polish`

**Files:**
- Modify: `src/logbook/cli/commands/report.py`, `tests/cli/test_report.py`(또는 새 `tests/cli/test_report_polish.py`), `tests/cli/test_entry.py`(가드: `report-provider-without-polish`, `report-bad-provider`)

```
lb report [--week] [--out] [--copy] [--yes] [--polish] [--provider anthropic|openai]
```
- `--provider`만 주고 `--polish`가 없으면 `InvalidInputError`: `--provider 옵션은 --polish와 함께 쓰세요.` DB·설정 없이 끝난다.
- 모르는 제공자 이름도 DB 없이 끝난다(`choose_provider` 전에 `PROVIDERS`로 검사. 문구는 core 상수를 쓴다).
- 순서: 옵션 검사 → 출력 경로 검사 → `_build_data` → 커밋 부록 → (`--polish`면) `choose_provider(build.cfg.llm, provider)` → 확인 → 요청 → `replace(data, summary=…)` → `_render` → `_deliver`.
- 함수 안에서 `from logbook.core import polish`로 지연 import하고 `polish.choose_provider`·`polish.polish_report`를 속성으로 부른다(테스트 monkeypatch 대상 `logbook.core.polish.polish_report`).
- 확인(`--yes`가 없을 때 `runtime.require_confirmation`):
  ```
  보낼 내용: 2026-W42 보고서 데이터(프로젝트 3개, 태스크 7건, 특이사항·리스크 포함). 커밋 내역과 작성자는 보내지 않습니다.
  Claude(claude-opus-5-5)로 보낼까요?
  ```
  - 거절: `문장 다듬기를 취소했습니다. 보고서를 만들지 않았습니다.` / 입력 없음: `확인 입력이 없습니다. 보내려면 --yes를 붙이세요.` (종료 1. 기존 `require_confirmation` 동작)
- 요청 전에 stderr에 `{info_mark} Claude에 요약을 요청하는 중입니다…`(`console.print_notice`). 요청 중 Ctrl+C는 기존 오류 경계 처리에 맡긴다.
- 실패(`ExternalServiceError`)면 보고서를 만들지 않고 종료 1(사용자가 요약을 원했으므로 요약 없는 보고서로 조용히 대신하지 않는다). 문구 끝에 덧붙이지 않는다. README에 "요약 없이 받으려면 --polish 없이 다시 실행" 안내.
- `--out`이 이미 있는 파일이면 덮어쓰기 확인은 요청 **뒤**(기존 `write_text_file`)가 아니라 요청 **전**에 한다: 요약에 비용이 드니 사용자가 거절할 수 있는 확인을 먼저 다 받는다. `runtime.prepare_output_path` 다음에 파일이 있고 `--yes`가 없으면 기존 덮어쓰기 질문을 먼저 하고, `_deliver(..., overwrite_confirmed=True)`로 넘겨 `write_text_file(..., yes=True)`로 쓴다. `_deliver`에 키워드 인자 `overwrite_confirmed: bool = False`를 더한다.

**테스트 케이스**(`logbook.core.polish.polish_report`를 monkeypatch, 실제 SDK 호출 없음)

| 케이스 | 기대 |
|---|---|
| `--polish --yes`, 가짜 결과 `"요약 문단"` | stdout 보고서에 `## 요약 (자동 생성)`과 문단, stderr에 요청 중 줄 |
| `--polish`, 입력 `y` / `n` / EOF | 진행 / 취소 문구 종료 1 / 입력 없음 문구 종료 1. 거절·EOF면 가짜가 불리지 않는다 |
| 확인 문구 | 위 두 줄(제공자·모델 반영) |
| `--polish --provider openai --yes` | 가짜에 provider `openai` |
| 제공자 없음(env 없음) | 종료 1, core 문구, 가짜가 불리지 않는다 |
| 가짜가 `ExternalServiceError` | 종료 1, 문구, stdout에 보고서 없음, `--out` 파일 안 만듦 |
| `--polish --out 있는파일` 입력 `n` | 요청하지 않음 |
| `--polish --copy --yes` | 클립보드(가짜)에 요약 포함 |
| `--provider openai`만 | 종료 1, 문구, SQLAlchemy 로드 안 함 |
| `--polish` 없이 | 기존 출력과 같다(요약 절 없음) |

- [x] RED → GREEN → 커밋 `feat: lb report --polish로 보고서 요약 문단 생성`

---

## Task 7-9: 웹 — 보고서 "문장 다듬기"

**Files:**
- Create: `src/logbook/web/pages/report_polish.py`, `src/logbook/web/templates/partials/report_polish.html`, `tests/web/test_report_polish.py`
- Modify: `src/logbook/web/app.py`, `src/logbook/web/pages/report.py`, `src/logbook/web/templates/partials/report_body.html`, `src/logbook/web/static/js/report.js`, `src/logbook/web/static/css/report.css`, `tests/web/test_static_*.py`(JS 문구 테스트가 있으면)

**화면**
- `ReportBodyView`에 `polish: tuple[PolishButton, ...] = ()`(`PolishButton(provider, label)`. 기본값 필수: `_week_error_response`가 직접 만든다). 페이지는 `from logbook.core import polish`로 가져와 `polish.available_providers()`를 속성으로 부른다(테스트 monkeypatch 대상 `logbook.core.polish.available_providers`). `available_providers()`가 비면 빈 튜플이고 버튼 영역이 나오지 않는다(SPEC: 키가 없으면 기능을 숨긴다). 설정 `[llm].provider`가 있어도 웹은 가능한 제공자 버튼을 모두 보여 준다(결정 S2-추가).
- `report_body.html`: 미리보기 오류가 없을 때 `report__actions` 안에
  ```html
  <form class="report__polish-form" hx-post="/report/polish" hx-target="#report-polish" hx-swap="outerHTML"
        hx-sync="this:drop" hx-disabled-elt="find button" hx-indicator="#polish-progress"
        hx-confirm="{{ polish_confirm }}">
    <input type="hidden" name="week" value="{{ body.week }}">
    {% for button in body.polish %}
    <button type="submit" class="btn btn--small" name="provider" value="{{ button.provider }}">문장 다듬기 ({{ button.label }})</button>
    {% endfor %}
  </form>
  ```
  - `polish_confirm`(웹 문구 상수 `POLISH_CONFIRM`): `{week} 보고서 데이터(태스크 제목·특이사항·리스크 포함)를 외부 AI 서비스로 보냅니다. 커밋 내역과 작성자는 보내지 않습니다. 계속할까요?`
  - 미리보기 위에 빈 결과 자리 `<section id="report-polish" class="report-polish" hidden></section>`와 진행 표시 `<p id="polish-progress" class="report-polish__progress htmx-indicator" role="status">요약을 만드는 중입니다…</p>`.
- 주 이동이나 특이사항 저장으로 본문이 바뀌면 결과 패널도 사라진다(저장하지 않는 값, 설계상 동작).

**`POST /report/polish`** (`web/pages/report_polish.py`)
- 폼: `week`, `provider`. 주차 오류·제공자 오류는 `InvalidInputError` → 기존 공통 처리(400, 알림 영역).
- `choose_provider(ctx.cfg.llm, provider)` → 세션 안에서 `report_data` → 세션 밖에서 `polish_report(data, ctx.cfg.llm, provider)` → `report_polish.html`. 이 모듈은 `from logbook.core.polish import choose_provider, polish_report`로 모듈 수준 import한다(테스트 monkeypatch 대상 `logbook.web.pages.report_polish.polish_report`).
- 커밋 부록은 보내지 않으므로 수집하지 않는다(`report_with_commits`를 부르지 않는다).
- `ExternalServiceError`는 공통 처리(502, 알림 영역에 문구). 결과 자리는 그대로.
- 라우트는 동기 함수(`def`)로 둔다. 외부 요청 동안 이벤트 루프를 막지 않도록 FastAPI가 스레드풀에서 실행한다.

```html
{# partials/report_polish.html #}
<section id="report-polish" class="report-polish" aria-labelledby="report-polish-heading">
  <div class="report-polish__head">
    <h3 id="report-polish-heading">요약 (자동 생성 · {{ polish.label }} {{ polish.model }})</h3>
    <button type="button" class="btn btn--small" data-copy-target="report-polish-text" data-copy-done="요약을 클립보드에 복사했습니다.">요약 복사</button>
  </div>
  <p id="report-polish-text" class="report-polish__text">{{ polish.summary }}</p>
</section>
```

**JS·CSS**
- `report.js`: 버튼의 `data-copy-done`이 있으면 그 문구를, 없으면 기존 `COPIED`를 보여 준다.
- `report.css`: `.report-polish`(패널 안쪽 여백, 테두리는 기존 토큰), `.report-polish__text`(줄 간격), `.report__polish-form`(버튼 줄바꿈 허용), `.htmx-indicator { display: none; }`, `.htmx-request.htmx-indicator, .htmx-request .htmx-indicator { display: block; }`. 색 값은 토큰만 쓴다(색 하드코딩 금지 테스트).
- 320px에서 버튼 줄이 넘치지 않게 `flex-wrap: wrap`.

**테스트 케이스**(`logbook.web.pages.report_polish.polish_report`와 `logbook.core.polish.available_providers`를 monkeypatch)

| 케이스 | 기대 |
|---|---|
| 제공자 없음 | 버튼 영역·결과 자리 없음 |
| anthropic만 / 둘 다 | 버튼 1개 / 2개(Claude, ChatGPT 순) |
| 확인 문구 | `hx-confirm`에 주차와 보내는 범위 |
| POST 정상 | 200, 패널에 제공자·모델·요약, `data-copy-done` |
| POST 잘못된 주차·제공자 | 400 알림 |
| POST 가짜가 `ExternalServiceError` | 502, 알림 문구 |
| POST 교차 출처 | 기존 보안 규칙대로 거부(403) |
| JS 문구 | `data-copy-done` 처리 코드가 있다(정적 파일 문자열 테스트) |
| CSS | `.report-polish`가 report.css에 있고 색 리터럴 없음 |

- 화면 모양(1280·375·320px, 밝은·어두운)은 메인 세션이 Edge 헤드리스로 확인한다.

- [x] RED → GREEN → 커밋 `feat: 보고서 화면에 문장 다듬기(Claude·ChatGPT) 추가`

---

## Task 7-10: 문서 마무리와 Phase 7 완료

- [x] **SPEC.md**
  - 3장(설정): `[llm]` 표와 설명, `[git]` 이메일 기본값(저장소의 `git config user.email`)
  - 5장(CLI): `lb git-collect`, `lb task import-gh`, `lb report --polish --provider`, 자동완성(`lb --install-completion`)
  - 6장(웹·API): 문장 다듬기 버튼·`POST /report/polish`, `/api/report` JSON의 `commits`·`summary`, 502 `upstream`
  - 7장(보고서): 요약 절과 부록 형식, "부록은 git-collect를 구현할 때까지 나오지 않는다" 문장 삭제, 선택 기능 절을 실제 동작(두 제공자, 확인, 보내는 범위)으로 고침
  - 8장: 외부 명령·API 실패 문구, 테스트가 외부 서비스를 부르지 않는다
  - 후속 항목: Phase 4 후속의 `git-collect`·LLM 다듬기 제거
- [x] **README.md**: 선택 설치(`uv sync --extra anthropic`/`openai`), 키 설정(PowerShell·zsh), 보내는 데이터, `lb git-collect`, `lb task import-gh`(gh 설치·로그인), 자동완성 설치(PowerShell은 프로필 다시 열기), 템플릿 값 `data.summary`·`data.commits`
- [x] **ROADMAP.md**: Phase 7 체크
- [x] **CLAUDE.md, AGENTS.md**: 디렉터리 구조(`core/external.py`, `core/github.py`, `core/polish/`, `cli/completion.py`, `web/pages/report_polish.py`), 허용 core 진입점 목록에 `core.gitcollect`·`core.github`·`core.polish`·`core.external`·`core.db.open_readonly`
- [x] **자동 확인(메인 세션, 임시 `LOGBOOK_DB`·`LOGBOOK_CONFIG`)**
  - `lb git-collect`: 임시 git 저장소 두 개(하나는 없는 경로)로 출력과 종료 코드
  - `lb report`: 부록, 경고
  - `lb task import-gh`: 실제 gh로 이 저장소(`chanyoo-93/logbook`)의 `--state all --limit 5 --dry-run`(읽기 전용, 사용자 PC에 gh 로그인이 되어 있을 때만). 실제 추가는 임시 DB에서만
  - 자동완성: `_LB_COMPLETE=complete_bash`, `COMP_WORDS`, `COMP_CWORD` 환경으로 실제 `lb`의 후보 출력 확인(설치는 하지 않음. PowerShell 형식은 COMP_WORDS를 쓰지 않는다)
  - `lb report --polish`: 키 없는 상태의 안내 문구만(실제 API 호출은 사용자 확인 항목)
- [x] **화면 확인(메인 세션, Edge 헤드리스)**: `/report`에 가짜 제공자(확인 스크립트의 앱 래퍼에서 `available_providers`·`polish_report` 대역)로 버튼·결과 패널·경고 목록, 1280·375·320px × 밝은·어두운
- [ ] **브라우저·실제 서비스 확인(사용자, Windows·macOS, 절차는 PR 댓글)**: 실제 키로 Claude·ChatGPT 다듬기 각 1회(비용 발생 안내), 자동완성 설치(PowerShell·zsh), gh 이슈 가져오기, git-collect
  - 2026-10-14: 실제 키 다듬기를 뺀 전 항목을 사용자가 확인했다. 실제 키 다듬기는 키를 발급받은 뒤 사용자가 확인한다.
- [x] **전체 검증:** ruff, ruff format --check, mypy(core strict, 전체), pytest(커버리지 core·web 100%), GitHub Actions 두 OS
- [x] **PR:** develop 대상, `Closes #15` (#16)

---

## 크로스 플랫폼 체크리스트 (Phase 7 추가분)

- git·gh 실행: `shutil.which`로 찾고 목록 인자, `shell=False`. Windows의 `gh.exe`·`git.exe`도 which가 찾는다.
- git 출력 인코딩: `-c i18n.logOutputEncoding=UTF-8`과 UTF-8 디코드(`errors="replace"`). 한국어 Windows의 cp949와 무관하다.
- git 시각: `--since`/`--until`에 시간대를 붙인 ISO 8601. 날짜 비교는 Python에서 한다.
- 자동완성: Typer가 PowerShell(`pwsh`·`powershell`)·zsh·bash를 지원한다. `lb.exe`여도 `prog_name="lb"`라 변수 이름은 `_LB_COMPLETE`다.
- 읽기 전용 SQLite URI: `Path.absolute().as_uri()`(Windows `file:///C:/…`, 한글·공백 퍼센트 인코딩) + `?mode=ro`, `uri=True`.
- API 키 안내는 PowerShell(`$env:ANTHROPIC_API_KEY = "…"`)과 zsh(`export …`)를 함께 적는다.

---

## 설계 결정 요약 (기술 결정, 계획 승인 시 함께 확정)

1. **보고서 조립은 DB만:** `weekly_report()`는 바꾸지 않고, 커밋·요약은 호출자가 `replace()`로 채운다. 외부 명령·API가 DB 세션 안에서 돌지 않는다.
2. **외부 명령 공용 함수:** git·gh의 실행·시간 제한·오류 문구를 `run_tool` 한 곳에 둔다.
3. **커밋 수집 실패는 보고서를 막지 않는다:** 저장소별 오류를 경고로 보여 주고 보고서는 만든다. `lb git-collect`만 종료 1로 알린다.
4. **이슈 중복 기준:** `external_ref = owner/repo#번호`. 상태·보관과 상관없이 이미 있으면 건너뛴다(다시 가져오기로 지운 태스크가 되살아나지 않게).
5. **자동완성은 읽기 전용·현재 스키마만:** 탭 한 번에 DB가 업그레이드되거나 만들어지지 않는다.
6. **요약 실패는 보고서를 만들지 않는다(CLI):** 요약을 요청한 사용자에게 요약 없는 보고서를 조용히 주지 않는다.
7. **외부 전송 최소화:** 커밋 제목·작성자는 보내지 않는다. 보내기 전에 범위를 보여 주고 확인을 받는다(CLI 프롬프트, 웹 확인 창).
8. **모델 기본값:** Claude는 `claude-opus-5-5`·effort `low`(요약은 깊은 추론이 필요 없다), 거절 시 서버 대체 모델(beta) 사용. ChatGPT는 `gpt-6.1-sol`·effort `low`. 둘 다 설정으로 바꾼다.
9. **웹 요약은 저장하지 않는다:** 결과 패널은 본문이 바뀌면 사라진다. 복사 버튼만 준다.

---

## 사용자 결정 (2026-10-14 승인 게이트에서 확정)

- **S1 범위:** ROADMAP 3개(LLM 문장 다듬기, GitHub 이슈 가져오기, 셸 자동완성) + `lb git-collect`와 보고서 커밋 부록
- **S2 LLM 호출:** 공식 SDK, 선택 설치. 키와 패키지가 모두 있을 때만 켠다. 보내기 전에 보낼 내용을 확인한다.
  - **추가(게이트 뒤 요청):** OpenAI(ChatGPT)도 지원한다. 제공자는 `[llm].provider` 설정, 비면 키가 있는 쪽(둘 다면 anthropic), `--provider`로 한 번만 바꾼다. 웹은 가능한 제공자마다 버튼. 선택 설치는 제공자별(`--extra anthropic`, `--extra openai`).
  - **OpenAI 기본 모델:** `gpt-6.1-sol`(사용자: `gpt-6-astra`는 너무 크다)
- **S3 GitHub:** gh CLI(`gh issue list --json`), 새 의존성 없음. 중복은 `external_ref`(owner/repo#번호)로 건너뛴다.
- **S4 자동완성:** `lb --install-completion` + `-p` slug·태스크 ID 완성. 읽기 전용, 옛 버전 DB면 후보 없음.

---

## 계획 검토 (2026-10-14)

사실 확인 에이전트 1명(Sonnet)이 코드·Typer·git·SQLite를 실험으로 확인했다. 반영한 것:
- `run_tool` 문구는 `label`(예: `git log`)을 쓴다. `args[0]`은 `-C`라 쓸 수 없다.
- 타임아웃 문구 값은 제공자 모듈이 `to_external_error(..., timeout=)`로 넘긴다.
- CLI 보고서는 `_build_data`(cfg 포함)와 `_render`로 나눈다. `_deliver`에 `overwrite_confirmed`.
- 웹 부록은 특이사항 저장·409 응답 경로까지 다섯 곳에서 채운다.
- git 실제 테스트는 지난주 커밋을 먼저 만든다(`--since` 탐색 중단). `--until`은 경계를 포함하므로 Python 필터가 필요하다.
- 자동완성 테스트는 `prog_name="lb"`와 bash 형식만 쓴다. 조회용 `-p`는 보관 포함 후보(`complete_any_project`).
- `_Table.to_llm()`, 기본 설정 문서 테스트 기대 수정, `ReportBodyView.polish` 기본값, monkeypatch 대상에 맞춘 import 방식.
- SDK(anthropic·openai) 세부는 미설치라 확인하지 못했다. Task 7-1에서 설치한 뒤 7-6·7-7 구현자가 설치본으로 확인한다.

---

## 구현 기록 (2026-10-14)

- **진행 규모:** 서브에이전트 22명(모두 Sonnet)
  - 워크플로: Task 7-1~7-9마다 구현 1명 + 통합 검토 1명(18명). 수정이 필요한 Task는 없었다. effort는 7-6만 high.
  - 문서 1명, 최종 리뷰 1명(high), 최종 리뷰 수정 1명
- **환경:** 구현 중 사용자 `lb serve`가 포트 8765와 `lb.exe`를 잡고 있어 에이전트들은 `uv run --no-sync`로 돌렸고 `test_serve.py` 3건이 실패했다. 포트가 빈 뒤 메인 세션에서 `uv sync`와 전체 검증을 다시 해 모두 통과했다.
- **계획과 달라진 것**
  - SDK 오류 문구는 조사 규칙 때문에 `확인할 환경변수: {env}.`로 썼다.
  - 커밋 수집 경고는 `커밋을 모으지 못했습니다: {project} ({message})`이고 `lb report`와 `lb git-collect`가 같이 쓴다.
  - 확인 프롬프트 기대값은 시드 데이터 기준이다. `--out` 덮어쓰기 확인을 요청 전에 하려고 `runtime.confirm_overwrite()`를 뽑았다.
  - 웹 Task 7-9는 테스트를 구현 뒤에 썼다(RED 미확인, 검토에서 테스트 충분성 확인).
- **최종 리뷰로 고친 것(major 4건)**
  - git `--author`가 부분 일치라 `some@example.com` 커밋이 `me@example.com`에 섞였다. `--author=<email>`로 정확히 맞춘다.
  - `--polish`는 제공자 확인을 커밋 수집보다 먼저 한다(제공자가 없으면 git을 실행하지 않는다).
  - 사용자 템플릿에 `data.summary`가 없으면 요청 전에 경고한다(비용만 들고 요약이 사라지는 일 방지).
  - `lb git-collect` 경고에 프로젝트 이름을 넣었다.
  - minor: git 미설치 원인 표시(`ToolNotFoundError`), import-gh `--dry-run`의 프로젝트·카테고리 검증(`check_import_target`), ChatGPT `content_filter`는 거절 문구, 실제 git 테스트의 전역 설정 격리, 자동완성 테스트 강화
- **화면 확인:** 보고서 화면(버튼, 결과 패널, 경고, 부록)을 1280·375·320px × 밝은·어두운으로 찍었다. 가로 넘침 없음. 확인 스크립트는 프로세스 안에서만 제공자·다듬기·커밋 수집을 대역으로 바꿨다.

---

## 후속 항목 (Phase 7 범위 밖, 기록만)

1. 웹에서 GitHub 이슈 가져오기
2. 요약 저장(주차별)과 보고서 3절 자동 채우기
3. 커밋 수집 결과 캐시(웹 보고서를 열 때마다 git을 실행한다)
4. 제공자 추가(Gemini 등), 사용자 정의 프롬프트
5. Jira 등 다른 이슈 추적기
6. gh가 이슈 0건을 돌려줄 때는 DB를 열지 않아 프로젝트·카테고리를 검증하지 않는다
7. GitHub 저장소 이름 대소문자(`A/B#1`과 `a/b#1`)를 같은 이슈로 보지 않는다
8. `--install-completion`·`--show-completion` 도움말은 Typer 기본 영어 문구다
