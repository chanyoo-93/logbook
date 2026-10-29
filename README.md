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

### 프로젝트

```
uv run lb project add payment "결제 서버" --color "#4f46e5"
uv run lb project list --all
uv run lb project edit payment --name "결제 서버 v2"
uv run lb project edit payment --color "#22c55e"
uv run lb project edit payment --no-color --description "결제 관련 서버"
uv run lb project archive payment
uv run lb project unarchive payment
```

| 명령 | 하는 일 |
|---|---|
| `lb project add <slug> <이름>` | 프로젝트를 추가합니다(`--color`). |
| `lb project list` | 보관하지 않은 프로젝트 목록. `--all`(`-a`)이면 보관한 것도 보여 줍니다. |
| `lb project edit <slug>` | 이름·색상·설명을 고칩니다(`--name`, `--color`, `--description`, 비우려면 `--no-color`, `--no-description`). 하나 이상 지정해야 합니다. 같은 항목의 값 옵션과 `--no-…`를 함께 주면 `--color 옵션과 --no-color 옵션은 함께 쓸 수 없습니다. 하나만 지정하세요.`로 거절합니다. slug는 바꿀 수 없고, 보관한 프로젝트도 고칠 수 있습니다. |
| `lb project archive <slug>` | 프로젝트를 보관합니다. 과거 기록은 집계에 계속 포함됩니다. |
| `lb project unarchive <slug>` | 보관을 해제합니다. 보관하지 않은 프로젝트면 안내 한 줄만 내고 종료 코드 0으로 끝납니다. |

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
| `lb report --polish` | AI(Claude·ChatGPT)로 요약 문단을 만들어 보고서 맨 위에 넣습니다. 외부로 데이터를 보내고 비용이 듭니다. 아래 "AI 문장 다듬기"를 보세요. |
| `lb report --copy` | 보고서를 클립보드에 복사합니다. 복사하면 화면에는 보고서를 출력하지 않습니다. 클립보드를 쓸 수 없으면 `주의:` 경고를 내고, `-o`를 함께 줬으면 파일로 저장한 것을 안내하고, 주지 않았으면 보고서를 화면에 출력합니다. |

보고서는 공수 요약 표, 프로젝트별 실적, 특이사항 / 리스크, 다음 주 계획 네 절로 이루어집니다. 특이사항 / 리스크는 웹 대시보드의 `/report` 화면에서 주차별로 입력해 저장합니다(CLI 입력은 없습니다). 저장한 내용은 `lb report` 출력에도 들어가고, 3절이 `### 특이사항`과 `### 리스크`로 나뉩니다(비어 있는 칸은 뺍니다). 둘 다 비어 있으면 `(작성하세요)`가 나옵니다. 작성자와 제목은 설정 파일의 `[report]`(`author`, `title_format`)에서 바꿉니다. `title_format`에서 쓸 수 있는 이름은 `{start}`와 `{end}`(YYYY-MM-DD)이고, 다른 이름이나 짝이 맞지 않는 중괄호는 오류가 납니다.

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
| `data.notes`, `data.risks` | 그 주의 특이사항, 리스크 텍스트(웹에서 저장, 없으면 빈 문자열) |
| `data.summary` | AI가 만든 요약 문단(`--polish`를 쓴 때만, 없으면 빈 문자열). 기본 템플릿은 제목 아래에 `## 요약 (자동 생성)`으로 넣습니다. 사용자 템플릿에는 `data.summary`를 직접 넣어야 요약이 나옵니다(없으면 `--polish`가 미리 경고합니다). |
| `data.commits` | 커밋 부록. 각 묶음: `project`, `repo`(저장소 폴더 이름), `commits`(각 커밋: `date`, `hash`, `subject`). 없으면 빈 목록 |

3절의 기본 템플릿 출력은 다음과 같습니다(빈 칸은 빠지고, 둘 다 비면 `(작성하세요)` 한 줄입니다).

```markdown
## 3. 특이사항 / 리스크
### 특이사항
결제 서버 점검 일정이 10/9로 확정됨

### 리스크
외부 PG 응답 지연이 계속되면 일정이 밀릴 수 있음
```

표 칸에 넣을 값은 `{{ 값 | cell }}`로 `|`를 이스케이프합니다. 템플릿에 문법 오류가 있으면 `오류: …` 한 줄로 파일 경로와 줄 번호를 알려 줍니다. 기본 템플릿으로 돌아가려면 파일을 지우거나 이름을 바꾸세요.

### 커밋 부록 (`lb git-collect`)

설정 파일에 본인 커밋을 모을 저장소를 적어 두면 보고서 끝에 `## 부록. 커밋 내역`이 붙습니다. `git`이 설치되어 있어야 합니다.

```toml
[report]
include_commits = true             # false로 하면 부록을 붙이지 않습니다

[git]
author_email = "me@example.com"    # 비워 두면 저장소마다 git config user.email을 씁니다

[[git.repos]]
project = "payment"
path = "~/work/payment-server"

[[git.repos]]
project = "admin"
path = 'C:\work\admin-web'         # Windows 경로는 작은따옴표로 씁니다
```

```
uv run lb git-collect
uv run lb git-collect -w last
```

`lb git-collect`는 저장소마다 그 주의 커밋(모든 브랜치, 병합 커밋 제외, 작성자 이메일이 같은 것)을 날짜·해시·제목으로 보여 줍니다. DB에는 저장하지 않습니다. 저장소 폴더가 없는 등 하나가 실패해도 나머지를 계속 모으고, 실패한 곳마다 `주의: …`를 보여 준 뒤 종료 코드 1로 끝납니다. `lb report`와 웹 보고서는 수집에 실패한 저장소를 경고만 하고 부록에서 빼고 보고서를 만듭니다. 웹 보고서는 화면을 열 때마다 `git`을 실행합니다.

### AI 문장 다듬기 (선택, 비용·외부 전송 주의)

`lb report --polish`와 웹 보고서의 `문장 다듬기` 버튼은 그 주의 보고서 데이터로 요약 문단 하나를 만들어 `## 요약 (자동 생성)`으로 넣습니다. Claude(Anthropic)와 ChatGPT(OpenAI)를 쓸 수 있고, **기본으로는 꺼져 있습니다.** 쓰려면 제공자별 패키지 설치와 API 키 설정이 모두 필요합니다.

1. 패키지를 설치합니다(쓸 제공자만).

```
uv sync --extra anthropic
uv sync --extra openai
```

   두 제공자를 모두 쓰려면 `uv sync --extra anthropic --extra openai`로 한 번에 설치합니다. 여러 번에 나눠 실행하면 앞에 설치한 패키지가 빠질 수 있습니다.

2. API 키를 환경변수로 설정합니다. 키는 설정 파일이 아니라 환경변수로만 읽습니다. 아래는 현재 터미널에서만 유효하며, 계속 쓰려면 사용자 환경변수나 셸 프로필에 넣으세요.

```
# PowerShell
$env:ANTHROPIC_API_KEY = "sk-ant-..."
$env:OPENAI_API_KEY = "sk-..."

# macOS (zsh)
export ANTHROPIC_API_KEY="sk-ant-..."
export OPENAI_API_KEY="sk-..."
```

3. 실행합니다.

```
uv run lb report --polish
uv run lb report -w last --polish --provider openai -o 주간보고.md
```

- **외부로 보내는 데이터:** 그 주의 보고서 데이터(공수 표, 프로젝트별 태스크 제목과 시간, 특이사항·리스크, 다음 주 계획)를 Anthropic 또는 OpenAI 서버로 보냅니다. **커밋 부록(커밋 제목)과 작성자 이름은 보내지 않습니다.** 민감한 내용이 태스크 제목이나 특이사항에 있다면 쓰지 마세요.
- **비용:** 요청마다 제공자의 API 요금이 듭니다. 그래서 보내기 전에 항상 `보낼 내용: …` 범위를 보여 주고 `[y/N]`으로 확인합니다(`--yes`로 생략). 웹은 확인 창을 띄웁니다. 확인 입력이 없는 환경(파이프 등)에서는 `--yes`를 붙여야 합니다.
- **제공자 선택:** `--provider anthropic|openai`, 없으면 설정 `[llm].provider`, 그것도 비었으면 키와 패키지가 모두 있는 제공자를 고릅니다(둘 다면 anthropic). 웹은 쓸 수 있는 제공자마다 버튼을 보여 주고, 하나도 없으면 숨깁니다.
- **모델:** 설정 파일의 `[llm]`에서 바꿉니다(기본 `claude-opus-5-5`, `gpt-6.1-sol`).

```toml
[llm]
provider = ""                      # "" | anthropic | openai
anthropic_model = "claude-opus-5-5"
openai_model = "gpt-6.1-sol"
```

- 실패하면(키 거부, 한도 초과, 네트워크 등) 한국어 오류 한 줄로 끝나고 요약 없는 보고서를 대신 내보내지 않습니다. 웹의 요약은 저장하지 않으며 결과 패널의 `요약 복사`로 가져갑니다.

### GitHub 이슈 가져오기 (`lb task import-gh`)

GitHub 이슈를 할 일 태스크로 가져옵니다. [GitHub CLI(`gh`)](https://cli.github.com)를 설치하고 로그인해 두어야 합니다.

```
gh auth login
uv run lb task import-gh chanyoo-93/logbook --dry-run
uv run lb task import-gh chanyoo-93/logbook --label bug -p payment -c dev -w next
uv run lb task import-gh chanyoo-93/logbook --state all --limit 50
```

- 저장소는 `owner/repo` 형식입니다. `--label`(여러 번 가능), `--state open|closed|all`(기본 open), `--limit`(1~1000, 기본 100), `-p`(기본은 `default_project`), `-c`, `-w`를 쓸 수 있습니다.
- `--dry-run`은 추가하지 않고 가져올 이슈와 건너뛸 이슈 건수만 보여 줍니다.
- 태스크 제목은 이슈 제목이고 외부 참조(`--ref`)에 `owner/repo#번호`가 들어갑니다. 같은 참조의 태스크가 이미 있으면(상태와 상관없이) 건너뛰므로 여러 번 실행해도 중복되지 않습니다.
- `gh`가 없으면 `명령을 찾을 수 없습니다: gh. GitHub CLI를 설치한 뒤 'gh auth login'을 실행하세요: https://cli.github.com`로 안내합니다.

### 셸 자동완성

```
uv run lb --install-completion
```

현재 셸(PowerShell, zsh, bash, fish)에 자동완성을 설치합니다. 설치 뒤 **새 셸을 열어야 반영됩니다. PowerShell은 새 창을 여세요**(프로필을 다시 읽어야 합니다). 설치하지 않고 스크립트만 보려면 `lb --show-completion`입니다. 자동완성을 쓰려면 `uv run` 없이 `lb`를 직접 실행할 수 있어야 하므로 가상환경을 활성화하거나 `lb`를 PATH에 설치해 두세요.

명령 이름·옵션에 더해 `-p`의 프로젝트 slug와 태스크 ID(`-t`, `lb task start 4<Tab>`)가 완성됩니다. 탭을 눌러도 DB를 만들거나 올리지 않도록 읽기 전용으로만 열고, DB가 없거나 옛 버전이면 후보 없이 조용히 넘어갑니다.

### 백업과 복원

```
uv run lb export
uv run lb export -o 백업.jsonl
uv run lb export -o 백업.jsonl --yes
uv run lb import 백업.jsonl
```

| 명령 | 하는 일 |
|---|---|
| `lb export` | 프로젝트·태스크·기록·타이머·특이사항·카테고리 색을 JSONL 파일 하나로 내보냅니다. `-o`를 생략하면 현재 폴더에 `logbook-export-20261008-153000.jsonl`처럼 만듭니다. 파일이 이미 있으면 `lb report -o`와 같이 덮어쓰기를 확인하고 `--yes`로 생략합니다. |
| `lb import <파일>` | `lb export`로 만든 파일을 **빈 데이터베이스**(`lb init` 직후)에만 복원합니다. |

`lb export` 파일에는 DB 내용(프로젝트·태스크·기록·타이머·보고서 특이사항·카테고리 색)만 들어갑니다. 파일 형식은 4이고(머리글의 `format`), 태스크마다 중단 시각(`dropped_at`)이 들어 있습니다. 이전 버전이 만든 형식 1~3 파일도 `lb import`로 가져오며, 형식 1~3의 중단 태스크는 중단 시각을 마지막 수정 시각으로 채웁니다. 성공 줄은 `✔ 내보냈습니다: 경로 (프로젝트 3 · 태스크 1 · 기록 2 · 타이머 0 · 특이사항 0 · 카테고리 색 0)`처럼 끝에 특이사항과 카테고리 색 건수가 붙습니다. 설정 파일(config.toml)과 보고서 템플릿(report.md.j2)은 따로 복사하세요.

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

### 업데이트와 DB 업그레이드

logbook을 업데이트했는데 DB 구조가 바뀌었으면, DB를 여는 첫 명령(`lb add`, `lb log`, `lb serve` 등)이 DB를 자동으로 업그레이드합니다. 업그레이드하기 직전에 DB와 같은 폴더에 백업을 먼저 만들고, 백업에 실패하면 업그레이드하지 않습니다. 안내는 stderr에 한 줄로 나옵니다(`lb init`은 백업 경로를 따로 한 줄로 보여 줍니다).

```
데이터베이스를 업그레이드했습니다: v3 → v4. 이전 데이터베이스 백업: C:\Users\me\.logbook\logbook.db.v3-20261015-153000.bak
```

- **파일 이름:** `<DB 파일 이름>.v<옛 버전>-YYYYMMDD-HHMMSS.bak` (예: 버전 3 DB를 올릴 때 `logbook.db.v3-20261015-153000.bak`). 이름이 겹치면 `-2`, `-3`을 붙입니다.
- **자동완성:** 업그레이드하기 전에는 셸 자동완성 후보(프로젝트 slug·태스크 ID)가 비어 있습니다. DB를 여는 명령을 한 번 실행하면 채워집니다.
- **정리:** 오래된 백업은 자동으로 지우지 않습니다. 필요 없으면 직접 지우세요.
- **프로젝트 자동 색(2026-10-23 변경):** 색을 지정하지 않은 프로젝트는 이 버전부터 다른 자동 색으로 보입니다(예: `common`이 파랑에서 회색). 데이터는 바뀌지 않습니다. 예전 색을 쓰고 싶으면 설정 화면에서 그 색을 직접 고르세요.
- **되돌리기:** `lb serve`와 다른 `lb` 명령을 모두 끈 뒤, 백업 파일을 DB 파일 위에 복사합니다. 그러면 옛 버전 DB가 되므로 옛 버전 logbook으로 쓰세요. 새 버전 logbook으로 열면 다시 업그레이드합니다.

```
# PowerShell
Copy-Item "$HOME\.logbook\logbook.db.v3-20261015-153000.bak" "$HOME\.logbook\logbook.db" -Force

# macOS (zsh)
cp ~/.logbook/logbook.db.v3-20261015-153000.bak ~/.logbook/logbook.db
```

### 웹 대시보드

```
uv run lb serve
uv run lb serve --port 9000
uv run lb serve --open
```

`lb serve`는 로컬 웹 대시보드를 실행하고 `✔ 웹 대시보드: http://127.0.0.1:8765 (끄려면 Ctrl+C)`를 보여 줍니다. 브라우저에서 그 주소를 엽니다. `--open`을 주면 브라우저를 자동으로 엽니다. 포트는 `--port`나 설정 파일의 `[web].port`(기본 8765)로 정합니다. Ctrl+C로 끄면 `웹 대시보드를 종료했습니다.`를 보여 주고 종료 코드 0으로 끝납니다. 서버가 도는 동안에도 다른 터미널에서 `lb add` 등을 그대로 쓸 수 있습니다.

| 화면 | 주소 | 하는 일 |
|---|---|---|
| 대시보드 | `/` | 위에서부터 `작업 기록` 패널(빠른 기록 폼, 타이머: 시작 폼, 진행 중이면 정지·취소), 최근 기록 10건(업무 날짜 순), 주간 요약(이번 주 공수(오늘 공수 / 목표 진행 막대)·기록 건수·완료 태스크 카드, 요일별 막대 차트(일일 목표선), 프로젝트별·카테고리별 도넛 차트) |
| 기록 | `/logs` | 주차·프로젝트·카테고리 필터, 행의 ⋮ 메뉴로 수정(행 안에서 바로)·삭제(확인 창) |
| 태스크 | `/tasks` | 칸반 4열(할 일, 진행 중, 완료, 중단 — 완료·중단은 이번 주에 바뀐 것), 카드를 끌어 놓아 상태 변경, `새 태스크` 화면, 카드를 눌러 수정 화면, 다음 주 계획 패널과 이월 |
| 보고서 | `/report` | 주 이동, 표 보기(기본)와 원문 탭(커밋 부록과 수집 경고 포함), 절별·전체 복사, `Markdown 복사`, `.md` 내려받기, 특이사항·리스크 입력, 문장 다듬기(키와 패키지가 있을 때만, 확인 창 뒤 외부 전송) |
| 설정 | `/settings` | 프로젝트 표(보관 포함)와 추가, 행의 ⋮ 메뉴로 수정·보관·보관 해제, 프로젝트·카테고리 색 고르기, 카테고리 색 표, 설정 정보(읽기 전용) |

- 빠른 기록은 시간(`2h`, `90m`, `1:30`)과 메모를 입력하고 Enter를 누르면 저장합니다. 프로젝트와 카테고리를 `프로젝트 자동`·`카테고리 자동`으로 두면 태스크 또는 설정의 `default_project`를 쓰고(선택 상자에 마우스를 올리면 규칙이 말풍선으로 보입니다), 태스크도 카테고리도 없으면 카테고리를 고르라고 안내합니다. 날짜는 항상 오늘이고, 다른 날짜는 기록 페이지에서 고칩니다.
- 그사이 다른 곳(CLI 등)에서 바뀐 기록·태스크·프로젝트·특이사항을 수정·삭제하려 하면 거부하고 화면을 새로 고치라고 안내합니다(타이머 정지는 확인하지 않습니다).
- 대시보드의 타이머는 시작 폼(메모, 프로젝트, 카테고리, 태스크)으로 시작하고, 진행 중이면 정지와 취소(확인 창)를 보여 줍니다. 타이머가 없을 때 패널은 스스로 갱신하지 않으므로, CLI에서 시작한 타이머는 화면을 새로 고쳐야 보입니다.
- 태스크 화면: 카드를 다른 열로 끌어 놓으면 그 열의 상태로 바뀝니다(마우스·터치패드는 바로 끌고, 터치는 잠깐 누른 뒤 끕니다). 중단 열로 끌 때도 확인 창은 없습니다. 끌다가 마음이 바뀌면 열 밖(예: 페이지 위쪽)에서 놓으세요. 카드가 원래 자리로 돌아가고 상태는 그대로입니다. 열 안에서 순서는 바꿀 수 없습니다. 끌어 놓기가 실패하면(예: 그사이 다른 곳에서 태스크가 바뀜) 알림에 이유가 나오고 카드는 원래 자리로 돌아갑니다. 완료·중단 열은 이번 주에 완료·중단한 태스크만 보여 줍니다.
- 태스크 등록·수정: 보드 위의 `새 태스크`는 등록 화면으로, 카드(카드 전체가 링크입니다)는 그 태스크의 수정 화면으로 갑니다. 항목은 제목, 프로젝트(등록할 때만), 카테고리, 예상, 계획 주차, 마감일, 외부 참조, 설명(여러 줄), 상태(수정할 때만)입니다. 저장하면 보드로 돌아와 위에 결과 줄(`✔ 태스크 추가: …`, `✔ 수정했습니다: …`)을 보여 줍니다. 바뀐 것이 없으면 수정 화면에 머물며 `바뀐 내용이 없습니다.`를 알립니다. Esc는 취소이고 제목 칸에 처음부터 커서가 있습니다.
- 키보드로 상태 바꾸기: 끌 수 없으면 카드에 Tab으로 가서 Enter를 눌러 수정 화면을 열고, 상태 선택을 바꿔 저장합니다.
- 태스크 카드: 카드에는 실적(연결된 기록 합계)이 늘 보이고(없으면 `실적 0m`), 예상이 있으면 `/ 예상 Y`가 붙으며, 실적이 예상보다 크면 `예상 초과` 꼬리표가 붙습니다. 계획 주차 옆에는 이번 주·다음 주·지난 주 꼬리표가 붙습니다. 프로젝트 필터는 보드와 다음 주 계획 패널에 함께 적용됩니다. `다음 주로 이월` 버튼은 이번 주의 할 일·진행 중 태스크를 다음 주로 옮기고 확인 창을 거칩니다. 일부가 그사이 바뀌었으면 성공 줄 뒤에 `N건은 그사이 바뀌어 옮기지 않았습니다.`가 붙고, 하나도 옮기지 못하면 409(`옮긴 태스크가 없습니다. 그사이 상태나 계획 주차가 바뀌었습니다. 패널을 지금 상태로 다시 표시했습니다.`)입니다.
- 기록·설정의 행 동작은 ⋮ 버튼의 메뉴에 있습니다. 키보드로는 ⋮에서 Enter(또는 아래 화살표)로 열고, 위·아래 화살표로 고르고, Esc로 닫습니다. common 프로젝트의 `보관`은 비활성입니다. 표의 컬럼명은 화면에 보이지 않습니다(화면 낭독기는 읽습니다).
- 보고서 화면: 주를 이동하며 장부 모양의 표 보기로 보고서를 봅니다. `전체 복사`나 절 제목 옆의 `복사`를 누르면 서식 있는 표와 글이 함께 복사되어, 엑셀·한글에 붙이면 표가 셀로 나뉩니다(빈 절의 `(작성하세요)` 같은 문구는 빠집니다). `원문` 탭에서는 `lb report`와 같은 Markdown을 보고 `Markdown 복사`로 복사하며, 머리 오른쪽의 `내려받기`로 `weekly-report-2026-W40.md`를 받습니다. 표 보기는 보고서 템플릿과 상관없이 같은 구조이고, 템플릿은 원문·내려받기·`lb report`에만 적용됩니다. 아래 입력란에 그 주의 특이사항·리스크를 저장하면 `lb report`에도 반영됩니다. 저장하지 않은 내용이 있으면 저장 버튼 옆에 안내가 나오고, 그 상태로 복사하면 결과 줄에 경고가 붙습니다.
- 설정 화면: `common`은 보관할 수 없습니다. 설정 정보(설정 파일, 실제로 연 DB 경로, 기본값, 글꼴)는 읽기 전용이라 고치려면 설정 파일을 편집하세요.
- 카테고리 색: 설정 화면의 `카테고리 색` 표에서 카테고리마다 색 고르기로 색을 정하고 `저장`을 누릅니다. 색을 고르면 `자동` 체크가 풀리고, `자동`을 켜고 저장하면 정한 색을 지워 자동 색으로 되돌립니다. 카테고리를 더하거나 이름을 바꾸는 것은 설정 파일 `[categories]`에서 합니다. 고른 색은 DB에 저장되어 `lb export` 백업에 들어갑니다.
- 프로젝트 색: 프로젝트 추가 폼과 행 수정에서도 색 고르기와 `자동` 체크로 색을 정합니다. `자동`이면 색을 지정하지 않은 것이고, 표에는 자동 색 견본과 `자동`이 보입니다. 자동 색은 카테고리 색과 겹치지 않게 팔레트를 끝에서부터 씁니다(기본 `common`은 회색). 어두운 테마에서는 색 점에 옅은 테두리가 보입니다.
- 카테고리·계획 주차·`예상 초과`·`진행 중`·`보관` 같은 표시는 모두 같은 모양의 꼬리표입니다. 프로젝트 이름 앞에는 색 점이 붙습니다(태스크 카드, 기록 표, 최근 기록). 프로젝트 색은 지정한 색이 있으면 그 색이고, 없으면 프로젝트마다 정해진 색이라 대시보드 차트를 포함해 어느 화면·어느 주에서나 같은 프로젝트는 같은 색입니다. 카테고리 꼬리표는 카테고리 색을 옅게 깐 모양이고, 대시보드의 카테고리 차트도 같은 색을 따릅니다(정하지 않은 카테고리는 설정 순서대로 자동 색).
- 다크모드는 OS·브라우저 설정(`prefers-color-scheme`)을 따르고 토글은 없습니다. 인쇄는 항상 밝은 색입니다.
- 정적 파일(CSS·JS)은 `no-cache`와 ETag로 매번 확인하므로 새로 고침만 해도 최신 파일을 받습니다.
- 인터넷 연결이 필요 없습니다(htmx, Chart.js, SortableJS는 패키지에 들어 있습니다).

이 컴퓨터에서만 열립니다. 서버는 `127.0.0.1`에만 연결하므로 다른 PC에서는 접속할 수 없고, 인증이 없어서 공개하지 않습니다. `localhost`나 `127.0.0.1` 이외의 주소(PC 이름, 다른 도메인)로 열면 `허용되지 않은 Host 헤더입니다` 오류(403)가 납니다. 다른 사이트에서 보낸 변경 요청도 거부합니다.

설정 파일의 `[web]`:

```toml
[web]
host = "127.0.0.1"   # 127.0.0.1 또는 localhost (표시용 주소). 다른 값은 오류
port = 8765
heading_font = "Bookk Gothic"    # 제목·큰 숫자 글꼴
document_font = "Bookk Gothic"   # 보고서 표 보기·원문·요약 글꼴
body_font = "Bookk Gothic"       # 본문·표·차트 글꼴
```

#### 글꼴

기본 글꼴은 부크크 고딕(Bookk Gothic)입니다. 글꼴 파일은 이 프로그램에 들어 있지 않습니다. 부크크에서 글꼴을 받아 PC에 설치해 쓰고, 사용 조건은 부크크의 약관을 따릅니다. 설치하지 않으면 기본 고딕 목록(Pretendard, Apple SD Gothic Neo, Malgun Gothic, Noto Sans KR 중 PC에 있는 것)으로 보입니다.

- `heading_font`는 제목과 큰 숫자, `document_font`는 보고서 표 보기·원문과 문장 다듬기 결과 글, `body_font`는 본문·표·차트에 쓰입니다.
- 이 PC에 설치된 다른 글꼴로 바꾸려면 이름을 하나만 적습니다. 예: `body_font = "나눔고딕"`. 쉼표로 여러 개를 적거나 따옴표·세미콜론·중괄호 등을 넣으면 설정 오류입니다. PC에 없는 글꼴 이름이면 기본 고딕으로 보입니다.
- 빈 값(`body_font = ""`)이면 그 글꼴은 정하지 않고 기본 고딕을 씁니다.
- 설치 방법. Windows: 글꼴 파일을 두 번 클릭해 열리는 창에서 `설치`를 누릅니다. macOS: 글꼴 파일을 두 번 클릭해 열리는 서체 관리자 창에서 설치 버튼을 누릅니다.
- 설정 파일을 고친 뒤 브라우저를 새로 고치면 반영됩니다(서버를 다시 시작하지 않아도 됩니다). `/settings`에서 지금 글꼴과 미리보기 문장을 확인합니다.

설정 파일을 고치면 서버를 끄지 않아도 다음 요청부터 반영합니다(요청마다 파일 내용이 바뀌었는지 확인해 바뀌었으면 다시 읽습니다). 카테고리, `default_project`, `week_start`, `daily_target_minutes`, `[report]` 등이 그렇습니다. 다음 세 값만 서버를 다시 시작해야 반영되고, 바꾸면 화면 위에 `다시 시작해야 반영되는 설정이 바뀌었습니다: …` 알림이 나옵니다.

- `db_path`
- `web.host`
- `web.port`

설정 파일을 읽지 못하면(문법 오류 등) 이전 설정으로 계속 동작하고 `설정 파일을 다시 읽지 못해 이전 설정으로 동작합니다: …` 오류 알림을 띄웁니다. 파일을 고치면 다시 읽습니다.

오류는 `오류: …` 한 줄과 종료 코드 1입니다(잘못된 `--port`, `lb init` 전, 이미 쓰는 포트 등). 포트가 사용 중이면 `--port`로 다른 포트를 지정하세요.

### JSON API

대시보드와 같은 서버가 JSON API(`/api/*`)도 제공합니다. 스크립트나 다른 도구에서 기록을 읽고 쓸 때 씁니다. `lb serve`를 먼저 실행해 두세요. 계약의 자세한 내용은 [docs/SPEC.md](docs/SPEC.md) 6장에 있습니다.

모든 응답은 같은 봉투입니다. 실패하면 `ok`가 `false`이고 `error.message`에 한국어 문구가 있습니다.

```json
{"ok": true, "data": {...}, "error": null}
{"ok": false, "data": null, "error": {"code": "invalid_input", "message": "소요 시간은 1분 이상이어야 합니다: '0m'. 예: 30m, 1h"}}
```

| 엔드포인트 | 하는 일 |
|---|---|
| `GET /api/logs?week=&project=&category=` | 기록 목록(기본 이번 주)과 합계 |
| `POST /api/logs` | 기록 추가 (`duration`, `note` 필수. `project`, `category`, `date`, `task_id`. `project`는 생략하면 태스크의 프로젝트, 없으면 `default_project`. `category`는 생략하면 태스크의 카테고리이고, 태스크도 없으면 400) |
| `PATCH /api/logs/{id}` | 보낸 항목만 수정 (`task_id`에 `null`이면 태스크 연결 해제) |
| `DELETE /api/logs/{id}` | 기록 삭제 |
| `GET /api/tasks?status=&week=&project=` | 태스크 목록(기본 todo, doing)과 실적 시간 |
| `POST /api/tasks` | 태스크 추가 (`title` 필수. `project`, `category`, `estimate`, `week`, `due`, `ref`, `description`) |
| `PATCH /api/tasks/{id}` | 보낸 항목만 수정 (`status` 포함, 비울 수 있는 항목은 `null`) |
| `GET /api/stats?week=&by=project\|category\|day` | 주간 공수 집계 |
| `GET /api/report?week=&format=md\|json` | 주간보고서(Markdown 문자열 또는 구조화 데이터. 커밋 부록이 있으면 `commits`에 들어갑니다) |
| `GET /api/timer` | 진행 중인 타이머 조회(본문 없음. 없으면 `data.timer`가 `null`) |
| `POST /api/timer/start` | 타이머 시작 (`task_id`만 주거나, `note`와 `category`를 함께 준다. `project`도 받는다. 본문을 생략하면 400) |
| `POST /api/timer/stop` | 타이머 정지 (`note`, `round`. 본문 전체를 생략할 수 있다) |
| `POST /api/timer/cancel` | 타이머를 기록 없이 버림(본문 없음. 진행 중인 타이머가 없으면 404) |

본문은 `Content-Type: application/json`의 UTF-8 JSON 객체입니다. 시간(`"1h30m"`)·날짜(`"yesterday"`)·주차(`"last"`)는 CLI와 같은 문자열을 받습니다. 모르는 키는 400으로 거부합니다.

```
# macOS (zsh)
curl -s http://127.0.0.1:8765/api/logs
curl -s -X POST http://127.0.0.1:8765/api/logs \
  -H "Content-Type: application/json" \
  -d '{"duration": "1h30m", "note": "결제 재시도 정리", "project": "payment", "category": "dev"}'
curl -s -X PATCH http://127.0.0.1:8765/api/logs/128 \
  -H "Content-Type: application/json" -d '{"duration": "90m"}'
```

PowerShell에서는 `curl`이 `Invoke-WebRequest`의 별칭이라 `Invoke-RestMethod`를 씁니다. 본문은 UTF-8 바이트로 보내야 한글이 깨지지 않습니다. Windows PowerShell 5.1은 문자열 본문을 UTF-8로 보내지 않습니다.

```
# PowerShell
Invoke-RestMethod http://127.0.0.1:8765/api/logs

$json = '{"duration": "1h30m", "note": "결제 재시도 정리", "project": "payment", "category": "dev"}'
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8765/api/logs `
  -ContentType 'application/json; charset=utf-8' -Body ([Text.Encoding]::UTF8.GetBytes($json))
```

연습할 때는 임시 DB를 쓰면 실제 기록이 섞이지 않습니다. 같은 터미널에서 `lb init`부터 `lb serve`까지 실행하세요.

```
# PowerShell
$env:LOGBOOK_DB = "$HOME\.logbook\try.db"
$env:LOGBOOK_CONFIG = "$HOME\.logbook\try-config.toml"
uv run lb init
uv run lb serve

# macOS (zsh)
export LOGBOOK_DB=~/.logbook/try.db
export LOGBOOK_CONFIG=~/.logbook/try-config.toml
uv run lb init
uv run lb serve
```

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
| 130 | Ctrl+C로 중단 (`lb serve`는 Ctrl+C가 서버를 끄는 정상 방법이라 0) |

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
