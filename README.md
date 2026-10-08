# logbook

개인 소프트웨어 개발자를 위한 업무 기록·공수 집계·주간업무보고서 생성 도구입니다.

- 상세 요구사항: [docs/SPEC.md](docs/SPEC.md)
- 구현 순서: [docs/ROADMAP.md](docs/ROADMAP.md)

## 사용법

아래 예시는 Windows(PowerShell)와 macOS(zsh) 모두에서 그대로 실행할 수 있습니다.

### 처음 설정

```
uv sync
uv run lb init
uv run lb project add payment "결제 서버" --color "#4f46e5"
```

`lb init`은 설정 파일(`~/.logbook/config.toml`)과 DB(`~/.logbook/logbook.db`)를 만들고 공통 업무용 `common` 프로젝트를 준비합니다. 여러 번 실행해도 결과는 같습니다. 가상환경을 활성화했다면 `uv run` 없이 `lb`만 써도 됩니다.

### 명령 예시

```
uv run lb add 2h "결제 재시도 로직 구현" -p payment -c dev -t 42
uv run lb add 1h "스프린트 플래닝" -c meeting
uv run lb add 30m "장애 대응" -p payment -c ops -d yesterday
uv run lb log
uv run lb log -w last
uv run lb log edit 128 --minutes 90 --note "재시도 정책 정리"
uv run lb log edit 128 --no-task
uv run lb log rm 128
uv run lb log rm 128 --yes
uv run lb stats
uv run lb stats --by project
```

| 명령 | 하는 일 |
|---|---|
| `lb add <시간> <메모>` | 기록을 추가하고 그날의 누적 시간을 보여 줍니다. `-p`를 생략하면 설정의 `default_project`에 기록합니다. |
| `lb log` | 이번 주 기록 목록. `-w last`, `-w 2026-W40`, `-d yesterday`, `-p`, `-c`로 거릅니다(`-w`와 `-d`는 함께 쓸 수 없습니다). |
| `lb log edit <ID>` | 지정한 항목만 고칩니다(`-m` 시간, `-n` 메모, `-c`, `-p`, `-d`, `-t`, `--no-task` 태스크 연결 해제). |
| `lb log rm <ID>` | 기록을 보여 주고 `[y/N]`으로 확인한 뒤 삭제합니다. `--yes`(`-y`)로 확인을 생략합니다. |
| `lb stats` | 이번 주 프로젝트 x 카테고리 공수 표. `--by project\|category\|day`로 묶음별 합계, `-w`로 주차를 고릅니다. |

### 태스크·계획·타이머

```
uv run lb task add "환불 API 설계" -p payment -c design --est 4h --week next --ref "#43"
uv run lb task list
uv run lb task list -s all -p payment
uv run lb task edit 43 --est 6h --no-due
uv run lb task start 43
uv run lb task done 43
uv run lb task drop 44
uv run lb plan
uv run lb plan -w next
uv run lb plan carry
uv run lb plan carry -w last --yes
uv run lb start -t 43
uv run lb start "장애 대응" -p payment -c ops
uv run lb status
uv run lb stop --round 15 --note "리뷰 반영"
uv run lb cancel
```

| 명령 | 하는 일 |
|---|---|
| `lb task add <제목>` | 태스크를 추가합니다(`-p`, `-c`, `--est` 예상 공수, `--week` 계획 주차, `--ref` 외부 참조, `--due` 마감일). `-p`를 생략하면 `default_project`에 추가합니다. |
| `lb task list` | 할 일·진행 중(todo, doing) 태스크 목록과 예상·실적 합계. `-s done,dropped`나 `-s all`로 상태를, `-p`, `-w`로 범위를 고릅니다. 보관한 프로젝트의 태스크는 `-p`로 지정할 때만 보입니다. |
| `lb task edit <ID>` | 지정한 항목만 고칩니다(`--title`, `-c`, `--est`, `--week`, `--ref`, `--due`, 비우려면 `--no-category`, `--no-est`, `--no-week`, `--no-ref`, `--no-due`). 프로젝트는 바꿀 수 없습니다. |
| `lb task start\|done\|drop <ID>` | 상태를 doing, done, dropped로 바꿉니다. `done`은 실적과 예상을 함께 보여 줍니다. |
| `lb plan` | 이번 주에 계획된 태스크(todo, doing, done)와 예상·실적 합계, 프로젝트별 예상. `-w next`처럼 주차를 고릅니다. |
| `lb plan carry` | 이번 주에 계획된 todo·doing 태스크를 보여 주고 `[y/N]`으로 확인한 뒤 다음 주로 옮깁니다. `-w last`로 원본 주를 고르고 `--yes`로 확인을 생략합니다. |
| `lb start [메모]` | 타이머를 시작합니다. `-t`로 태스크를 지정하면 메모를 생략할 수 있고(태스크 제목 사용), todo 태스크는 doing으로 바뀝니다. 타이머는 하나만 돌 수 있습니다. |
| `lb status` | 진행 중인 타이머와 시작 시각, 경과 시간. |
| `lb stop` | 타이머를 멈추고 시작한 날짜의 기록으로 저장합니다. `--round 15`로 15분 단위 반올림, `--note`로 메모를 덧붙입니다. 1분 미만이나 24시간 초과는 저장하지 않고 타이머를 남깁니다. |
| `lb cancel` | 타이머를 보여 주고 `[y/N]`으로 확인한 뒤 기록 없이 버립니다. `--yes`(`-y`)로 확인을 생략합니다. |

### 주간보고서

```
uv run lb report
uv run lb report -w last
uv run lb report -o 주간보고.md
uv run lb report -w last -o 주간보고.md --yes
uv run lb report --copy
```

| 명령 | 하는 일 |
|---|---|
| `lb report` | 이번 주 주간업무보고를 Markdown으로 화면(stdout)에 출력합니다. `-w last`, `-w 2026-W40`처럼 주차를 고릅니다. |
| `lb report -o <파일>` | 보고서를 파일로 저장하고 화면에는 저장한 경로만 보여 줍니다(UTF-8, LF). 파일이 이미 있으면 `덮어쓸까요? [y/N]:`로 확인하고, `--yes`(`-y`)로 확인을 생략합니다. 거절하거나 입력이 없으면 파일을 그대로 두고 종료 코드 1로 끝납니다. |
| `lb report --copy` | 보고서를 클립보드에 복사합니다. 복사하면 화면에는 보고서를 출력하지 않습니다. 클립보드를 쓸 수 없으면 `주의:` 경고를 내고, `-o`를 함께 줬으면 파일로 저장한 것을 안내하고, 주지 않았으면 보고서를 화면에 출력합니다. |

보고서는 공수 요약 표, 프로젝트별 실적, 특이사항 / 리스크, 다음 주 계획 네 절로 이루어집니다. 특이사항 / 리스크는 `(작성하세요)` 자리표시자이고, 저장 기능은 이후 단계에서 추가합니다. 작성자와 제목은 설정 파일의 `[report]`(`author`, `title_format`)에서 바꿉니다. `title_format`에서 쓸 수 있는 이름은 `{start}`와 `{end}`(YYYY-MM-DD)이고, 다른 이름이나 짝이 맞지 않는 중괄호는 오류가 납니다.

PowerShell에서는 `lb report > 주간.md` 대신 `lb report -o 주간.md`를 쓰세요. 리디렉션은 PowerShell 버전과 콘솔 인코딩에 따라 한글이 깨질 수 있습니다.

### 보고서 템플릿

보고서 모양은 템플릿으로 바꿀 수 있습니다. 설정 파일(`config.toml`)과 같은 폴더에 `report.md.j2`를 두면 기본 템플릿 대신 그 파일을 씁니다(기본은 `~/.logbook/report.md.j2`이고 `LOGBOOK_CONFIG`로 설정 위치를 옮겼다면 그 옆입니다). 파일이 없으면 기본 템플릿을 씁니다. 기본 템플릿은 패키지 안의 `logbook/core/templates/report.md.j2`입니다. [Jinja2](https://jinja.palletsprojects.com/) 문법이고 파일은 UTF-8로 저장해야 합니다(BOM은 허용).

기본 템플릿을 복사해서 고치려면 다음처럼 합니다. 저장소 폴더에서 실행합니다.

```
# PowerShell
Copy-Item (uv run python -c "import importlib.resources as r; print(r.files('logbook.core').joinpath('templates', 'report.md.j2'))") "$HOME\.logbook\report.md.j2"

# macOS (zsh)
cp "$(uv run python -c "import importlib.resources as r; print(r.files('logbook.core').joinpath('templates', 'report.md.j2'))")" ~/.logbook/report.md.j2
```

PowerShell에서는 `Copy-Item`으로만 복사하세요. `>`, `Out-File`, `Set-Content`로 옮기면 PowerShell 5.1에서 UTF-16이나 ANSI로 저장되어 템플릿을 읽을 수 없습니다.

템플릿에는 `data` 하나가 넘어옵니다. 시간과 비율은 `1h 30m`, `54%`처럼 이미 표기가 끝난 문자열입니다. 쓸 수 있는 값은 다음과 같고, 없는 값을 쓰면 오류로 알려 줍니다.

| 값 | 내용 |
|---|---|
| `data.title`, `data.author` | 제목, 작성자(설정이 비면 빈 문자열) |
| `data.week_label`, `data.start`, `data.end` | `2026-W40`, `2026-09-28`, `2026-10-04` |
| `data.total`, `data.log_count`, `data.done_task_count` | 주 합계 시간, 기록 건수, 그 주에 완료한 태스크 수 |
| `data.categories` | 표 머리글(카테고리 라벨, 기록이 있는 것만) |
| `data.matrix` | 표의 행. 각 행: `project`, `cells`(카테고리별 시간), `total`, `percent` |
| `data.sections` | 프로젝트별 실적. 각 항목: `project`, `total`, `tasks`, `others` |
| `data.sections[].tasks` | 각 태스크: `status`, `title`, `task_id`, `actual`, `actual_label`(`실제` 또는 `누적`), `estimate`(없으면 `None`) |
| `data.sections[].others` | 태스크에 연결되지 않은 기록의 (카테고리 라벨, 시간) 쌍 |
| `data.plan` | 다음 주 계획. 각 항목: `project`, `estimate_total`, `items` |
| `data.plan[].items` | 각 태스크: `title`, `task_id`, `estimate`(없으면 `None`), `carried`(이번 주에서 넘어온 후보면 참) |

표 칸에 넣을 값은 `{{ 값 | cell }}`로 `|`를 이스케이프합니다. 템플릿에 문법 오류가 있으면 `오류: …` 한 줄로 파일 경로와 줄 번호를 알려 줍니다. 기본 템플릿으로 돌아가려면 파일을 지우거나 이름을 바꾸세요.

### 백업과 복원

```
uv run lb export
uv run lb export -o 백업.jsonl
uv run lb export -o 백업.jsonl --yes
uv run lb import 백업.jsonl
```

| 명령 | 하는 일 |
|---|---|
| `lb export` | 프로젝트·태스크·기록·타이머를 JSONL 파일 하나로 내보냅니다. `-o`를 생략하면 현재 폴더에 `logbook-export-20261008-153000.jsonl`처럼 만듭니다. 파일이 이미 있으면 `lb report -o`와 같이 덮어쓰기를 확인하고 `--yes`로 생략합니다. |
| `lb import <파일>` | `lb export`로 만든 파일을 **빈 데이터베이스**(`lb init` 직후)에만 복원합니다. |

`lb export` 파일에는 DB 내용(프로젝트·태스크·기록·타이머)만 들어갑니다. 설정 파일(config.toml)과 보고서 템플릿(report.md.j2)은 따로 복사하세요.

`lb import`는 데이터가 있는 DB에는 쓰지 않습니다. 기록과 태스크가 ID로 서로를 가리키므로 ID를 그대로 복원해야 하고, 이미 있는 데이터와 합치려면 ID가 겹칠 때의 규칙이 필요하기 때문입니다. 데이터가 있는 DB에서 실행하면 새 DB를 쓰라고 안내하고 종료 코드 1로 끝납니다. 다른 PC로 옮기거나 백업에서 되살리는 절차는 다음과 같습니다.

```
# PowerShell
$env:LOGBOOK_DB = "$HOME\.logbook\restored.db"
uv run lb init
uv run lb import 백업.jsonl

# macOS (zsh)
export LOGBOOK_DB=~/.logbook/restored.db
uv run lb init
uv run lb import 백업.jsonl
```

복원한 DB를 계속 쓰려면 `LOGBOOK_DB`를 그대로 두거나 설정 파일의 `db_path`를 그 경로로 바꾸세요. 파일을 먼저 전부 검사하고 문제가 없을 때만 한 번에 쓰므로, 검사에 실패하면(예: `오류: 12번째 줄: …`) DB는 바뀌지 않습니다.

### 셸별 주의

- 메모는 따옴표로 감싼 한 인자입니다. 따옴표 없이 여러 단어를 쓰면 `Got unexpected extra argument` 오류(종료 코드 2)가 납니다.
- `#`로 시작하는 값은 따옴표로 감쌉니다(`--color "#4f46e5"`, `-t "#42"`, `--ref "#43"`). PowerShell과 bash에서 `#` 뒤는 주석이 됩니다.
- `-`로 시작하는 메모는 옵션을 먼저 쓰고 `--` 뒤에 씁니다: `lb add 30m -c dev -- "-5% 개선"`
- PowerShell에서 `$`가 든 메모는 작은따옴표로 감쌉니다: `lb add 1h 'API $limit 조정' -c dev`
- PowerShell에서 lb 출력을 파이프나 파일로 넘길 때(`lb log | Select-String payment`)는 먼저 `[Console]::OutputEncoding = [System.Text.Encoding]::UTF8`을 실행합니다. 프로필에 넣으면 매번 적용됩니다(5.1과 7은 프로필 파일이 따로라 각각 넣어야 합니다). 설정하지 않으면 한국어 Windows 기본값(cp949)에서 한글이 깨지고 `Select-String`도 한글을 찾지 못합니다. PowerShell 5.1과 7 모두 같습니다.
- 파이프나 파일로 넘긴 `lb log`·`lb stats`는 줄을 접지 않습니다. 기록 한 건이 한 줄이라 줄 단위로 걸러낼 수 있습니다.

### 오류와 종료 코드

| 코드 | 의미 |
|---|---|
| 0 | 성공 |
| 1 | 입력·데이터 오류(stderr에 `오류: …` 한 줄), 삭제·이월·타이머 취소·파일 덮어쓰기 확인을 거절했거나 확인 입력이 없음 |
| 2 | 명령 문법 오류(없는 옵션, 인자 누락·초과 등). Typer/Click 기본 영어 문구로 안내합니다. |
| 130 | Ctrl+C로 중단 |

## 개발

[uv](https://docs.astral.sh/uv/)가 필요합니다. 아래 명령은 Windows(PowerShell)와 macOS(zsh) 모두에서 그대로 실행할 수 있습니다.

| 명령 | 용도 |
|---|---|
| `uv sync` | 의존성 설치 (Phase 2 이후 처음 받으면 진입점이 바뀌었으므로 다시 실행) |
| `uv run lb --help` | CLI 실행 |
| `uv run pytest` | 테스트 |
| `uv run pytest -m "not subprocess"` | 빠른 테스트 (서브프로세스 테스트 제외) |
| `uv run python scripts/bench_cli.py` | CLI 응답 시간 측정 |
| `uv run ruff check .` | 린트 |
| `uv run ruff format .` | 포맷 |
| `uv run mypy src/logbook/core` | 타입 체크 |
