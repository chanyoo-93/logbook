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
| 1 | 입력·데이터 오류(stderr에 `오류: …` 한 줄), 삭제·이월·타이머 취소 확인을 거절했거나 확인 입력이 없음 |
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
