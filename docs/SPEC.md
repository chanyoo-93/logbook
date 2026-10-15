# logbook 상세 명세 (SPEC)

## 1. 목표

1. **업무 정량화**: 프로젝트별·카테고리별·주차별 투입 시간과 처리 건수를 집계한다.
2. **주간 회고와 계획**: 이번 주에 한 일과 다음 주에 할 일을 한 화면/한 명령으로 본다.
3. **주간업무보고서**: 위 데이터를 바탕으로 Markdown 보고서를 자동 생성한다.

지원 플랫폼: **Windows 10/11, macOS** (두 OS에서 동일한 기능과 동작 보장. 세부 규칙은 CLAUDE.md/AGENTS.md의 크로스 플랫폼 규칙).

비목표(초기 버전): 팀 공유, 클라우드 동기화, 인증, 모바일 앱.

---

## 2. 데이터 모델

### projects
| 컬럼 | 타입 | 설명 |
|---|---|---|
| id | int PK | |
| slug | text unique | CLI 입력용 짧은 이름 (`payment`, `admin`, `common`) |
| name | text | 표시 이름 |
| description | text null | |
| color | text null | 대시보드 차트 색상 (hex) |
| archived | bool | 보관 처리 시 목록·입력 후보에서 제외, 과거 집계에는 포함 |
| created_at | datetime | |

`common` 프로젝트는 `lb init` 시 자동 생성 (회의, 교육, 행정 등 프로젝트 무관 업무용).

### tasks
| 컬럼 | 타입 | 설명 |
|---|---|---|
| id | int PK | |
| project_id | FK | |
| title | text | |
| description | text null | |
| status | enum | `todo` / `doing` / `done` / `dropped` |
| category | text null | 기본 카테고리 (WorkLog 입력 시 기본값으로 사용) |
| estimate_minutes | int null | 예상 공수 |
| planned_week | text null | 계획 주차 `YYYY-Www` (예: `2026-W41`) |
| due_date | date null | |
| external_ref | text null | 외부 참조 (GitHub 이슈 URL, `#42`, Jira 키 등) |
| created_at / updated_at | datetime | |
| done_at | datetime null | `done` 전환 시각 |

### worklogs
| 컬럼 | 타입 | 설명 |
|---|---|---|
| id | int PK | |
| project_id | FK | 필수 |
| task_id | FK null | 선택 |
| category | text | 필수 (설정의 카테고리 목록 중 하나) |
| date | date | 업무 수행일 (기본: 오늘) |
| minutes | int | 소요 시간, 1 이상 |
| note | text | 무엇을 했는지 한 줄 |
| started_at / ended_at | datetime null | 타이머로 기록한 경우만 |
| created_at | datetime | |

### active_timer (단일 행)
타이머 기능용. `project_id, task_id, category, note, started_at`. 동시에 하나만 실행.

### week_notes
보고서 3절(특이사항/리스크)의 주차별 입력. `/report` 화면에서만 입력한다(Phase 6).
| 컬럼 | 타입 | 설명 |
|---|---|---|
| week | text PK | `Week.label` (`2026-W41`) |
| risks | text | 리스크 |
| notes | text | 특이사항 |
| updated_at | datetime | |

두 칸이 모두 비면 행을 두지 않는다("행이 있다 = 쓴 내용이 있다"). 줄바꿈은 LF로 저장한다(HTML `textarea`는 CRLF로 보낸다).

### category_colors
카테고리 꼬리표·차트의 색(Phase 8 보완). 카테고리 정의(키·이름)는 설정 파일 `[categories]`에 있고 이 테이블은 사용자가 고른 색만 둔다.
| 컬럼 | 타입 | 설명 |
|---|---|---|
| category | text PK | 카테고리 키(설정 파일의 키 형식: 영문 소문자로 시작하고 영문 소문자·숫자·`_`·`-`만) |
| color | text | `#rrggbb` |
| updated_at | datetime | |

- 행이 없으면 자동이다. 설정의 카테고리 순서 위치로 정한 팔레트 색을 쓴다.
- 색은 웹 설정 화면(6장)에서만 정한다. CLI 명령은 없다(후속 항목).
- 설정 파일에서 지운 카테고리의 행은 DB에 남고, 설정 화면의 표에는 보이지 않는다.
- 백업(`lb export`)에 들어간다(5장).

### schema_version
마이그레이션 버전 관리용 단일 행 테이블. 현재 스키마 버전은 **3**이다(버전 2: `week_notes` 추가, 버전 3: `category_colors` 추가).

- **마이그레이션 전 백업:** 옛 버전 DB를 열어 올려야 하면, 쓰기 잠금 안에서 버전을 다시 읽은 뒤 첫 단계 직전에 한 번만 DB 파일을 sqlite3 백업 API로 같은 폴더에 복사한다. 이름은 `<DB 파일 이름>.v<옛 버전>-YYYYMMDD-HHMMSS.bak`(예: `logbook.db.v1-20261013-153000.bak`)이고 겹치면 `-2`, `-3`을 붙인다. 백업에 실패하면(만들다 만 파일은 지운다) 마이그레이션도 하지 않는다. 오래된 백업은 자동으로 지우지 않는다(후속 항목).
- **업그레이드 안내:** core는 출력하지 않고 `open_database(on_upgrade=…)` 콜백으로 결과를 넘긴다. DB를 여는 CLI 명령과 `lb serve`는 stderr에 `데이터베이스를 업그레이드했습니다: v2 → v3. 이전 데이터베이스 백업: 경로` 한 줄을 쓴다. `lb init`은 업그레이드 줄과 백업 경로를 따로 보여 준다.
- **되돌리기:** `lb serve`와 다른 `lb` 명령을 끈 뒤 백업 파일을 DB 파일 위에 복사한다. 옛 버전 DB가 되므로 옛 버전 logbook으로 써야 하고, 새 버전으로 열면 다시 올라간다.

### 기본 카테고리 (설정으로 변경 가능)
`dev`(개발), `review`(코드리뷰), `meeting`(회의), `docs`(문서), `design`(설계), `ops`(운영/배포/장애), `support`(문의대응), `study`(학습), `admin`(행정/기타)

---

## 3. 설정 파일

경로: `~/.logbook/config.toml` (환경변수 `LOGBOOK_CONFIG`로 변경 가능)
- macOS: `/Users/<user>/.logbook/config.toml`
- Windows: `C:\Users\<user>\.logbook\config.toml`
- 설정 안의 경로 값은 `~` 또는 OS 고유 형식 모두 허용 (Windows 예: `path = 'C:\work\payment-server'` — TOML에서 백슬래시는 작은따옴표 리터럴 문자열로 쓴다)

```toml
db_path = "~/.logbook/logbook.db"
week_start = "monday"          # monday | sunday
default_project = "common"
daily_target_minutes = 480     # 대시보드 일일 목표선

[categories]
dev = "개발"
review = "코드리뷰"
meeting = "회의"
docs = "문서"
design = "설계"
ops = "운영/배포/장애"
support = "문의대응"
study = "학습"
admin = "행정/기타"

[report]
author = "홍길동"
title_format = "주간업무보고 ({start} ~ {end})"
include_commits = true         # 보고서 부록(커밋 내역)을 붙일지. [[git.repos]]가 있을 때만 의미가 있다

[git]
author_email = "me@example.com"   # 비우면 저장소마다 git config user.email을 쓴다

[[git.repos]]
project = "payment"
path = "~/work/payment-server"

[[git.repos]]
project = "admin"
path = "~/work/admin-web"

[web]
host = "127.0.0.1"             # 127.0.0.1 | localhost (표시용 주소)
port = 8765
heading_font = "Bookk Gothic"   # 제목·큰 숫자 글꼴(PC에 설치된 글꼴 이름 하나). ""는 기본 고딕 목록
document_font = "Bookk Gothic"  # 보고서 미리보기·요약 글꼴
body_font = "Bookk Gothic"      # 본문·표·차트 글꼴

[llm]
provider = ""                  # "" | anthropic | openai. ""는 키와 패키지가 있는 제공자를 고른다
anthropic_model = "claude-opus-5-5"
openai_model = "gpt-6.1-sol"
```

- `[web].host`는 `127.0.0.1`과 `localhost`만 받는다. 다른 값(`0.0.0.0` 등)은 설정 오류(종료 코드 1)다. 서버는 값과 무관하게 항상 127.0.0.1에만 열리고, 이 값은 시작 문구와 `--open`이 여는 주소에만 쓴다.
- `[web]` 글꼴(Phase 8): `heading_font`, `document_font`, `body_font`는 이 PC에 설치된 글꼴 이름을 하나씩 받는다. 기본값은 셋 다 `Bookk Gothic`이다. 빈 문자열이면 그 글꼴 변수를 내지 않아 기본 고딕 목록(`app.css`의 `--font-sans`)을 쓴다. 이름은 100자 이하이고 따옴표·역슬래시·세미콜론·쉼표·중괄호·꺾쇠·제어 문자를 넣을 수 없으며 앞뒤 공백이 없어야 한다. 어긋나거나 문자열이 아니면 설정 오류(종료 코드 1)다. 쉼표 목록은 받지 않는다(대체 글꼴은 서버가 기본 고딕 목록을 붙인다). 폰트 파일은 저장소와 패키지에 넣지 않는다. PC에 없는 글꼴이면 브라우저가 다음 글꼴로 넘어가 기본 고딕으로 보인다.
- `[git]`(Phase 7): `author_email`이 비어 있으면 저장소마다 `git -C <경로> config user.email`의 첫 줄을 쓰고, 그것도 없으면 그 저장소는 `작성자 이메일을 알 수 없습니다: 경로. 설정 [git].author_email을 지정하세요.` 오류로 건너뛴다. `[[git.repos]]`의 `project`는 부록에서 묶음 제목으로 쓰는 이름이고, `path`는 저장소 폴더다. `include_commits = false`이거나 `[[git.repos]]`가 없으면 부록을 만들지 않는다.
- `[llm]`(Phase 7): 문장 다듬기(7장)용 설정이다. `provider`는 `""`, `anthropic`, `openai`만 받는다(다른 값은 설정 오류). 모델 이름은 비울 수 없다. `lb init`이 만드는 설정 파일에는 기본값이 들어 있다. API 키는 설정 파일이 아니라 환경변수(`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`)로만 읽는다.
- **설정 자동 반영(`lb serve`):** 요청마다 설정 파일 내용의 해시를 보고(수정 시각에 기대지 않는다), 바뀌었으면 다시 읽어 그 요청부터 새 설정을 쓴다. 카테고리, `default_project`, `week_start`, `daily_target_minutes`, `[report]`, `[web]`의 글꼴 세 키는 바로 반영된다(글꼴은 `/fonts.css`를 새로 받는 새로 고침으로 반영). `db_path`, `web.host`, `web.port`는 서버를 시작할 때 정해지므로 바뀌면 다시 시작해야 하고, 화면 위에 알림(`다시 시작해야 반영되는 설정이 바뀌었습니다: …`)만 보여 준다. 읽기에 실패하면(문법 오류 등) 이전 설정으로 동작하고 오류 알림(`설정 파일을 다시 읽지 못해 이전 설정으로 동작합니다: …`)을 띄운다. CLI 명령은 실행할 때마다 설정을 읽는다.

---

## 4. 공통 규칙

### 시간 입력 파싱 (`core/duration.py`)
허용: `2h`, `1.5h`, `90m`, `1h30m`, `1h 30m`, `45` (단위 없으면 분), `1:30` (시:분).
거부: 0 이하, 24h 초과, 잘못된 형식 → 사용자 친화적 한국어 에러.
표시: `90` → `1h 30m`, `60` → `1h`, `30` → `30m`.

### 날짜 입력
`today`(기본), `yesterday`, `mon`~`sun`(이번 주 해당 요일, 미래면 지난주), `2026-10-01`, `10-01`.

### 주차
`YYYY-Www` 형식. `this`, `last`, `next` 별칭 지원. 주차 → (시작일, 종료일) 변환 함수 제공.

---

## 5. CLI 명세 (`lb`)

### 초기화 / 프로젝트
```bash
lb init                                  # 설정 파일·DB 생성, common 프로젝트 생성
lb project add payment "결제 서버" --color "#4f46e5"
lb project list [--all]                  # --all: 보관 포함
lb project edit payment [--name "결제 서버 v2"] [--color "#22c55e" | --no-color] [--description "…" | --no-description]
lb project archive payment
lb project unarchive payment
```
- `lb project edit <slug>`: 이름·색상·설명을 고친다. 하나 이상 지정해야 하고(없으면 오류), 같은 항목의 값 옵션과 `--no-…`를 함께 주면 `{} 옵션과 {} 옵션은 함께 쓸 수 없습니다. 하나만 지정하세요.`로 거절한다. slug는 바꿀 수 없다. 보관한 프로젝트도 고칠 수 있다. 출력: `✔ 프로젝트 수정: payment (결제 서버 v2) #22c55e`.
- `lb project unarchive <slug>`: 보관을 해제한다. 출력 `✔ 프로젝트 보관 해제: payment`. 보관되지 않은 프로젝트면 `· 보관되지 않은 프로젝트입니다: payment` 한 줄을 내고 종료 코드 0이다.

### 업무 기록 (가장 자주 쓰는 명령, 최소 입력으로 동작해야 함)
```bash
lb add 2h "결제 재시도 로직 구현" -p payment -c dev -t 42
lb add 1h "스프린트 플래닝" -c meeting           # -p 생략 시 default_project
lb add 30m "장애 대응" -p payment -c ops -d yesterday
```
- 인자 순서: `lb add <duration> <note> [옵션]`
- 메모는 따옴표로 감싼 한 인자다. `-`로 시작하는 메모는 옵션을 먼저 쓰고 `--` 다음에 쓴다 (`lb add 30m -c dev -- "-5% 개선"`).
- `-t <task_id>` 지정 시 프로젝트·카테고리는 Task의 값으로 기본 설정. `-t 42`와 `-t "#42"` 모두 받는다.
- 성공 시 한 줄 출력: `✔ #128 payment/dev 2h — 결제 재시도 로직 구현 (오늘 누적 5h 30m)`
- 누적은 기록한 날짜의 합계다. 오늘 기록이면 `(오늘 누적 5h 30m)`, 다른 날 기록이면 `(09-30 누적 30m)`.

### 타이머
```bash
lb start "환불 API 설계" -p payment -c design [-t 43]
lb start -t 43                           # 메모 생략 시 태스크 제목 사용
lb status                                # 진행 중 타이머와 경과 시간
lb stop [--note "추가 메모"]             # WorkLog로 저장, 15분 단위 반올림 옵션 --round 15
lb cancel [--yes]
```
- 타이머는 하나만 돌 수 있다. 진행 중인 타이머가 있으면 `lb start`는 거부하고 `lb stop`·`lb cancel`을 안내한다.
- `lb start`: 프로젝트·카테고리 해석은 `lb add`와 같다(`-t` 지정 시 Task의 값이 기본). `-t`를 주고 메모를 생략하면 태스크 제목을 메모로 쓴다. `-t` 태스크가 todo면 doing으로 바꾸고 `· 태스크 #43 상태를 doing으로 바꿨습니다.`를 덧붙인다.
  - 출력: `✔ 타이머 시작: payment/design — 환불 API 설계 [#43] (09:30)`. 시작 시각이 오늘이 아니면 `09-30 (수) 22:10`처럼 날짜를 붙인다.
- `lb status`: `진행 중: payment/design — 환불 API 설계 [#43]`와 `시작 09:30 · 경과 1h 25m`. 타이머가 없으면 `진행 중인 타이머가 없습니다.`를 출력하고 종료 코드 0이다.
- `lb stop` 규칙:
  - 경과 시간은 분 단위로 반올림한다(30초 이상 올림).
  - 1분 미만이거나 24시간(`lb add`와 같은 상한)을 넘으면 저장하지 않고 오류로 끝난다. 타이머는 그대로 남는다(버리려면 `lb cancel`).
  - 기록 날짜는 타이머를 시작한 날(로컬 날짜)이다. 자정을 넘겨도 시작한 날에 기록하며, 누적은 그 날짜의 합계다.
  - `--round N`(1~60분): 경과 시간을 N분 단위로 반올림한다. 결과가 0이면 한 단위(N분)로 올린다. 24시간 상한은 반올림 전 경과로 판단하며, 경과가 24시간 이내인데 반올림 결과만 24시간을 넘으면 24시간(1440분)으로 저장한다. 반올림으로 값이 바뀌면 `· 경과 1h 39m을 15분 단위로 반올림했습니다.`를 덧붙인다.
  - `--note`(`-n`): 시작 메모 뒤에 ` — `로 덧붙인다(`환불 API 설계 — 리뷰 반영`).
  - 시작한 뒤 프로젝트를 보관하거나 카테고리 설정을 바꿔도 저장할 수 있다(재검증하지 않음).
  - 출력은 `lb add`와 같다: `✔ #128 payment/design 1h 45m — 환불 API 설계 — 리뷰 반영 (오늘 누적 5h 30m)`
- `lb cancel`: 버릴 타이머와 경과 시간을 보여 주고 `버릴까요? [y/N]:`로 확인한다. 거절하거나 입력이 없으면 타이머를 남기고 종료 코드 1로 끝난다. `--yes`/`-y`로 확인을 생략한다. 타이머가 없으면 오류(종료 코드 1).

### 기록 조회·수정
```bash
lb log [--week this|last|2026-W40] [--date today] [-p payment] [-c dev]
lb log edit 128 --minutes 90 --note "..."
lb log rm 128 [--yes]
```
- 옵션이 없으면 이번 주 기록을 보여 준다. `--week`(`-w`)와 `--date`(`-d`)는 함께 쓸 수 없다.
- 조회 옵션은 `lb log` 목록에만 쓴다. `lb log edit`·`rm` 같은 하위 명령 앞에 쓰면 거부한다.
- 출력: Rich 테이블 (ID, 날짜, 프로젝트, 카테고리, 시간, 메모, Task) + 하단 합계.
  - 머리줄은 주차와 기간(`2026-W41 (10-05 ~ 10-11)`, `--date`면 `2026-10-08 (목)`), 날짜 열은 `MM-DD (요일)`, 카테고리는 key(`dev`), Task 열은 `#42`(없으면 `-`), 하단은 `합계 5h / 기록 5건`.
  - 터미널 폭이 좁으면 표 대신 한 줄 목록(`#128 10-01 (목) payment/dev 2h — 메모 [#42]`)으로 바꾼다. 파이프·파일 출력은 줄을 접지 않는다.
- `lb log edit <ID>`: 지정한 항목만 바꾼다. 옵션은 `-m/--minutes`, `-n/--note`, `-c/--category`, `-p/--project`, `-d/--date`, `-t/--task`, `--no-task`(태스크 연결 해제). 하나도 없으면 오류.
- `lb log rm <ID>`: 삭제할 기록을 보여 주고 `삭제할까요? [y/N]:`로 확인한다. `y`·`yes`(한글 자판 `ㅛ`·`ㅛㄷㄴ` 포함)만 삭제한다. 거절하거나 입력이 없으면 아무것도 지우지 않고 종료 코드 1로 끝난다. `--yes`/`-y`로 확인을 생략한다.

### 태스크 / 계획
```bash
lb task add "환불 API 설계" -p payment -c design --est 4h --week next --ref "#43"
lb task list [-p payment] [--status todo,doing|all] [--week next]
lb task edit 43 [--title "..."] [--est 6h] [--week next] [--no-due]
lb task start 43                         # status → doing
lb task done 43
lb task drop 43
lb plan [--week next]                    # 해당 주 계획 태스크 + 예상 공수 합계
lb plan carry [--week last] [--yes]      # 해당 주(기본 이번 주) 미완료 태스크를 다음 주로 이월
lb task import-gh chanyoo-93/logbook [--label bug] [--state open|closed|all] [--limit 100] [-p payment] [-c dev] [-w next] [--dry-run]
```
- `lb task add <title>`: `-p`를 생략하면 `default_project`. 옵션은 `-c/--category`, `-e/--est`(예상 공수, 하루를 넘을 수 있으므로 24시간 상한 없음, 예: `40h`), `-w/--week`(계획 주차), `--ref`(외부 참조, `"#43"`·URL·Jira 키), `--due`(마감일, 날짜 입력 규칙과 같음).
  - 출력: `✔ 태스크 추가: #43 payment/design 환불 API 설계 (예상 4h · 2026-W42 · 참조 #43 · 마감 10-15)`. 괄호에는 값이 있는 항목만 쓰고, 하나도 없으면 괄호를 생략한다.
- `lb task list`: 기본은 todo·doing이다. `-s/--status`는 쉼표로 여러 상태를 받고 `all`은 네 상태 전부다. 보관한 프로젝트의 태스크는 `-p`로 그 프로젝트를 지정할 때만 보인다.
  - 출력: 표(ID, 상태, 프로젝트, 카테고리, 제목, 예상, 실적, 주차, 참조) + `태스크 3건 / 예상 10h / 실적 1h 45m`. 상태는 key(`todo`, `doing`, `done`, `dropped`)로 표시해 그대로 `--status`에 쓸 수 있다. 실적은 연결된 WorkLog 합계다.
- `lb task edit <ID>`: 지정한 항목만 바꾼다. 옵션은 `--title`, `-c/--category`, `-e/--est`, `-w/--week`, `--ref`, `--due`, 값을 비우는 `--no-category`, `--no-est`, `--no-week`, `--no-ref`, `--no-due`. 하나도 없거나 값과 같은 항목의 `--no-…`를 함께 주면 오류. 프로젝트는 바꿀 수 없다(연결된 기록과 어긋나지 않도록, 필요하면 drop 후 다시 만든다).
- `lb task start|done|drop <ID>`: 상태를 doing·done·dropped로 바꾼다. 출력 `✔ #43 todo → doing: payment/design 환불 API 설계`, `done`은 ` (실적 5h 30m / 예상 4h)`를 덧붙인다. 이미 같은 상태면 `· 태스크 #43 상태는 이미 doing입니다: …`를 출력하고 종료 코드 0이다. 완료·중단된 태스크도 다시 시작할 수 있다.
- `lb task import-gh <OWNER/REPO>`(Phase 7, 선택 기능): GitHub 이슈를 `todo` 태스크로 가져온다. 외부 명령 `gh issue list -R <저장소> --state <상태> --limit <개수> --json number,title,url [--label …]`을 `shell=False`로 실행하므로 GitHub CLI(`gh`)를 설치하고 `gh auth login`을 마쳐야 한다. 새 의존성은 없다.
  - 옵션: `--label`(`-l`, 여러 번 쓸 수 있고 모두 가진 이슈만), `--state`(`open`(기본)·`closed`·`all`), `--limit`(1~1000, 기본 100), `-p`(기본 `default_project`), `-c`, `-w`(계획 주차), `--dry-run`. 저장소는 `owner/repo` 형식의 ASCII만 받는다(앞뒤 공백은 지운다). 형식·상태·개수·주차 검증은 DB와 `gh`를 쓰기 전에 한다.
  - 태스크 제목은 이슈 제목, 외부 참조(`external_ref`)는 `owner/repo#번호`다. 같은 참조의 태스크가 이미 있으면 상태·보관 여부와 상관없이 건너뛴다(다시 가져와도 지운 태스크가 되살아나지 않고, 중복도 생기지 않는다). 이슈 번호 오름차순으로 추가한다.
  - 출력: `✔ 이슈를 태스크로 가져왔습니다: 추가 3건, 건너뜀 1건 (이미 있음)`과 추가한 태스크 줄. 이슈가 없으면 `· 가져올 이슈가 없습니다: owner/repo`. `--dry-run`은 `· 가져올 이슈: 3건, 건너뛸 이슈: 1건 (이미 있음). --dry-run이라 추가하지 않았습니다.`와 `  #번호 제목` 줄만 보이고 DB를 바꾸지 않는다.
  - 오류(`오류: …` 한 줄, 종료 코드 1): `gh`가 없으면 `명령을 찾을 수 없습니다: gh. GitHub CLI를 설치한 뒤 'gh auth login'을 실행하세요: https://cli.github.com`, 실패하거나 30초 안에 끝나지 않으면 `명령이 실패했습니다: gh issue list (종료 코드 1). …`(stderr 첫 줄 포함)·`명령이 30초 안에 끝나지 않았습니다: gh issue list.`, 출력을 읽을 수 없으면 `gh 출력을 읽지 못했습니다. gh를 최신 버전으로 업데이트하세요.`
- `lb plan`: 기본은 이번 주다. 그 주에 계획된 todo·doing·done 태스크를 프로젝트, ID 순으로 보여 주고 dropped와 보관한 프로젝트의 태스크는 뺀다.
  - 머리줄: `2026-W41 (10-05 ~ 10-11) 계획   예상 6h / 실적 1h 45m / 태스크 2건 (완료 1건)`, 표(ID, 상태, 프로젝트, 제목, 예상, 실적), 하단 `프로젝트별 예상: admin 4h · payment 8h`와 `예상이 없는 태스크 N건`.
- `lb plan carry`: `-w`로 고른 원본 주(기본 이번 주)에 계획된 todo·doing 태스크를 다음 주로 옮긴다. 더 이전 주에 밀린 태스크와 보관한 프로젝트의 태스크는 옮기지 않는다.
  - 옮길 목록(`이월할 태스크 (2026-W41 → 2026-W42):`)을 보여 주고 `옮길까요? [y/N]:`로 확인한다. 거절하거나 입력이 없으면 아무것도 옮기지 않고 종료 코드 1로 끝난다. `--yes`/`-y`로 확인을 생략한다.
  - 출력: `✔ 2건을 옮겼습니다: 2026-W41 → 2026-W42`와 옮긴 태스크 줄. 확인하는 동안 상태·주차가 바뀐 태스크는 건너뛰고 경고한다.
  - 월요일에 지난주 태스크를 옮기려면 `lb plan carry -w last`.
- `--week`는 `lb plan` 목록에만 쓴다. `lb plan -w last carry`처럼 하위 명령 앞에 쓰면 거부한다.

### 집계 / 보고서
```bash
lb stats [--week this] [--by project|category|day]
lb report [--week this] [--out report.md] [--copy] [--yes] [--polish] [--provider anthropic|openai]
```
- `lb report`: 주간업무보고(7장 형식)를 Markdown으로 만든다. 기본은 이번 주를 stdout에 출력한다. `--week`(`-w`)는 `lb stats`와 같다(`this`, `last`, `next`, `2026-W40`).
- `--out`(`-o`): 파일로 저장한다(UTF-8, LF). 저장하면 보고서는 stdout에 출력하지 않고 `✔ 보고서를 저장했습니다: 경로` 한 줄만 보여 준다. 경로는 `~`로 시작할 수 있고 상대 경로는 현재 폴더 기준이다. 폴더이거나 부모 폴더가 없으면 오류(종료 코드 1)다.
  - 덮어쓰기 확인(R4): 파일이 이미 있으면 `파일이 이미 있습니다: 경로`와 `덮어쓸까요? [y/N]:`로 확인한다. 거절하거나 입력이 없으면 파일을 그대로 두고 종료 코드 1로 끝난다. `--yes`/`-y`로 확인을 생략한다.
- `--copy`: `pyperclip`으로 클립보드에 복사하고 `✔ 보고서를 클립보드에 복사했습니다.`를 출력한다(이때 stdout에는 보고서를 쓰지 않는다). 복사에 실패하면 오류로 끝내지 않고(종료 코드 0) stderr에 `주의: 클립보드에 복사하지 못했습니다. …` 경고를 쓴다. `--out`을 함께 줬으면 파일로 저장했다고 안내하고, 주지 않았으면 `--out` 사용을 안내하며 보고서를 stdout에 출력한다.
- `--out`과 `--copy`는 함께 쓸 수 있다.
- **커밋 부록(Phase 7):** 설정의 `[[git.repos]]`가 있고 `[report].include_commits`가 켜져 있으면(기본) 보고서 끝에 `## 부록. 커밋 내역`을 붙인다(7장). 커밋 수집에 실패한 저장소는 stderr에 `주의: 커밋을 모으지 못했습니다: payment (사유)` 경고를 쓰고 그 저장소만 뺀 채 보고서를 만든다(종료 코드 0).
- `--polish`(Phase 7, 선택 기능): 보고서 데이터를 외부 AI 서비스(Claude 또는 ChatGPT)로 보내 요약 문단을 받아 보고서 맨 위(제목·작성자 아래)에 `## 요약 (자동 생성)`으로 넣는다. 7장의 "선택 기능"을 본다.
  - `--provider`(`anthropic`·`openai`)는 이번 한 번만 제공자를 고른다. `--polish` 없이 쓰면 `--provider 옵션은 --polish와 함께 쓰세요.`, 모르는 이름이면 `제공자 이름이 올바르지 않습니다: '이름'. anthropic 또는 openai를 쓰세요.`(종료 코드 1). 이 검증은 DB·설정을 읽기 전에 한다.
  - 보내기 전에 확인한다: `보낼 내용: 2026-W41 보고서 데이터(프로젝트 2개, 태스크 3건, 특이사항·리스크 포함). 커밋 내역과 작성자는 보내지 않습니다.`와 `Claude(claude-opus-5-5)로 보낼까요? [y/N]:`. 거절하면 `문장 다듬기를 취소했습니다. 보고서를 만들지 않았습니다.`(종료 코드 1), 입력이 없으면(파이프 등) `확인 입력이 없습니다. 보내려면 --yes를 붙이세요.`다. `--yes`(`-y`)는 이 확인과 `--out` 덮어쓰기 확인을 함께 생략한다. `--out` 덮어쓰기 확인은 비용이 드는 요청 전에 미리 받는다.
  - 요청하는 동안 stderr에 ` Claude에 요약을 요청하는 중입니다…`를 보인다. 요청이 실패하면(키 없음, 패키지 없음, 한도 초과, 네트워크 등) 한국어 `오류: …` 한 줄(종료 코드 1)로 끝나고 요약 없는 보고서를 대신 내보내지 않는다.
- 템플릿 오류(문법, 없는 값, UTF-8이 아닌 파일 등)는 `오류: …` 한 줄(종료 코드 1)로 파일 경로와 줄 번호를 알린다.
`lb stats` 예시 출력 (열 이름은 설정의 카테고리 라벨, 기록이 있는 카테고리만 표시):
```
2026-W40 (09-28 ~ 10-04)   총 35h / 기록 41건
프로젝트  개발  코드리뷰  회의  행정/기타  합계
payment    14h        3h    2h          -   19h
admin       6h        1h    1h          -    8h
common       -         -    5h         3h    8h
```
`--by` 출력 열 (머리줄은 같다):
- `--by project`: 프로젝트(slug), 이름, 시간, 건수, 비율
- `--by category`: 카테고리(key), 이름(라벨), 시간, 건수, 비율
- `--by day`: 날짜(`MM-DD (요일)`, 기록 없는 날도 표시), 시간, 건수, 비율

### 데이터 관리
```bash
lb export [--out backup.jsonl] [--yes]  # 전 테이블 JSONL 내보내기 (git 백업용)
lb import backup.jsonl                   # 빈 DB(lb init 직후)에만 복원
lb git-collect [--week this]             # 설정된 레포에서 본인 커밋 수집 (보고서 부록과 같은 수집, DB 저장 안 함)
lb serve [--port 8765] [--open]          # 웹 대시보드 실행
```
- `lb export`: 프로젝트·태스크·기록·진행 중 타이머·주차별 특이사항·카테고리 색을 JSONL 한 파일로 내보낸다. `--out`(`-o`)을 생략하면 현재 폴더에 `logbook-export-20261008-153000.jsonl`처럼 만든다. 기존 파일은 `lb report --out`과 같은 덮어쓰기 확인을 거치고 `--yes`로 생략한다(R4). 출력: `✔ 내보냈습니다: 경로 (프로젝트 3 · 태스크 1 · 기록 2 · 타이머 0 · 특이사항 0 · 카테고리 색 0)`.
  - 설정 파일(`config.toml`)과 보고서 템플릿(`report.md.j2`)은 들어 있지 않다. 따로 복사한다.
  - **JSONL 형식(버전 3, 공개 계약):** 파일은 UTF-8이고 한 줄이 JSON 객체 하나다. 첫 줄은 머리글 `{"type": "logbook-export", "format": 3, "schema_version": 3, "exported_at": "…"}`이고 (`schema_version`은 내보낸 DB의 스키마 버전, `exported_at`은 UTC 시각), 그 뒤는 `{"table": "tasks", "row": {…}}` 형태의 행이다. 행은 `projects`, `tasks`, `worklogs`, `active_timer`, `week_notes`, `category_colors` 순서이고 각 테이블 안에서는 id 순이다(`week_notes`는 `week` 순, `category_colors`는 `category` 순). `row`의 필드는 2장 데이터 모델의 컬럼과 같다. 시각은 UTC ISO 8601, 날짜는 `YYYY-MM-DD`, 상태는 `todo`·`doing`·`done`·`dropped`다. 한글은 이스케이프하지 않는다. 형식 1(`week_notes`, `category_colors` 없음)과 형식 2(`category_colors` 없음)도 계속 가져온다.
- `lb import <파일>`(R3): `lb export`로 만든 파일을 **빈 DB**(`lb init` 직후, `common` 프로젝트만 있음)에만 원래 id 그대로 복원한다. 기록·태스크가 id로 서로를 가리키므로 id를 바꾸지 않고, 병합은 id 충돌 규칙이 필요해 하지 않는다. 데이터가 있는 DB에는 가져오지 않고 새 DB를 쓰라고 안내한다(종료 코드 1). 복원 절차: `LOGBOOK_DB`를 새 경로로 바꾸고 `lb init` 후 `lb import`.
  - 파일 전체를 먼저 검증하고(머리글 형식·버전, 필드 이름·값, 참조 무결성 등) 통과했을 때만 한 번에 쓴다. 검증에 실패하면 `오류: N번째 줄: …` 한 줄로 알리고 DB는 바뀌지 않는다. 더 새로운 스키마로 내보낸 파일은 거부한다. 성공 출력: `✔ 가져왔습니다: 경로 (프로젝트 2 · 태스크 5 · 기록 41 · 타이머 0 · 특이사항 0 · 카테고리 색 0)`. 형식 1 파일은 특이사항과 카테고리 색이 0이고, 형식 2 파일은 카테고리 색이 0이다.
  - 가져오기는 줄을 LF로만 나눈다. 파일 앞의 BOM은 허용한다.
  - `week_notes` 행은 쓴 내용이 있는 행만 허용한다. `risks`와 `notes`가 모두 빈 행, 그리고 저장할 때 정리한 모양이 아닌 값(CRLF, 줄 끝 공백, 앞뒤 빈 줄)은 거부한다.
  - `category_colors` 행은 `category`가 설정 파일의 카테고리 키 형식이고 `color`가 `#rrggbb`여야 한다. 키가 설정 파일에 있는지는 보지 않는다. 형식 2 이하 파일에 `category_colors` 줄이 있으면 `알 수 없는 테이블입니다` 오류다(그 형식에는 없는 테이블이라서).
  - `projects.color`는 `null`이거나 문자열이면 받는다. `#rrggbb` 형식은 보지 않는다(후속 항목). 형식이 틀린 색은 화면에서 자동 색으로 보인다.
- `lb git-collect`(Phase 7): `[[git.repos]]`의 저장소마다 `--week`(`-w`, 기본 이번 주) 동안의 본인 커밋을 `git log`로 모아 보여 준다. DB에는 저장하지 않는다.
  - 수집 규칙: 외부 명령 `git`을 `shell=False`·목록 인자로 실행한다. 모든 브랜치(`--all`)의 병합 아닌 커밋(`--no-merges`) 중 작성자 이메일이 설정 `[git].author_email`(비면 저장소의 `git config user.email`)과 같은 것(대소문자 무시, `--author=<이메일>`로 정확히 일치)만 오래된 순으로 모은다. 날짜는 작성 날짜를 로컬 시간대로 바꾼 값이고, `--since/--until`이 커미터 날짜를 기준으로 하므로 작성 날짜가 그 주 밖인 커밋은 걸러 낸다. 한계: 같은 이유로 다른 주에 rebase·amend해 커미터 날짜가 그 주 밖이 된 커밋은 작성 날짜가 그 주여도 빠질 수 있다. 출력은 UTF-8로 읽는다(Windows 콘솔 코드 페이지와 무관).
  - 출력: 저장소마다 `payment (payment-server) 2건`과 그 아래 `  2026-10-05 a1b2c3d 결제 재시도 로직 구현`(날짜, 해시 7자리, 제목) 줄. 커밋이 없는 저장소는 `0건`이다.
  - 저장소 하나가 실패해도(폴더 없음 `저장소 폴더가 없습니다: 경로. 설정의 [[git.repos]] path를 확인하세요.`, 이메일을 알 수 없음, `git` 없음 `명령을 찾을 수 없습니다: git. git을 설치하세요: https://git-scm.com`, 10초 안에 끝나지 않음 등) 나머지를 계속 모으고, 실패한 저장소마다 stderr에 `주의: 커밋을 모으지 못했습니다: payment (사유)` 한 줄을 쓴다(보고서 경고와 같은 문구). 하나라도 실패했으면 마지막에 `오류: 저장소 N곳에서 커밋을 읽지 못했습니다.`로 종료 코드 1이다.
  - `[[git.repos]]`가 없으면 `오류: 설정된 저장소가 없습니다. 설정 파일에 [[git.repos]]를 추가하세요.`(종료 코드 1)다.
- `lb serve`: 웹 대시보드(6장)를 실행한다. `--port`(기본은 설정 `web.port`, 8765)는 1~65535의 ASCII 숫자만 받는다. 값은 설정·DB를 읽기 전에 검사한다.
  - 시작: `✔ 웹 대시보드: http://127.0.0.1:8765 (끄려면 Ctrl+C)`. `--open`이면 `webbrowser.open()`으로 브라우저를 연다. 열지 못하면 `주의: 브라우저를 열지 못했습니다. 주소를 직접 여세요: 주소` 경고만 내고 서버는 계속 돈다.
  - 종료: Ctrl+C로 `웹 대시보드를 종료했습니다.`를 출력하고 종료 코드 0으로 끝난다.
  - 오류(`오류: …` 한 줄, 종료 코드 1): 잘못된 `--port`, 설정 `host`가 허용 값이 아님, `lb init` 전(DB가 없거나 초기화되지 않음, `lb init`을 안내), 포트를 열 수 없음(이미 사용 중 등, `--port`로 다른 포트를 안내). DB를 연 뒤 포트 소켓을 먼저 열고 나서 서버를 띄우므로, 실패하면 서버는 뜨지 않는다.
  - 서버를 돌리는 동안에도 CLI(`lb add` 등)를 함께 쓸 수 있다. 화면은 요청할 때마다 DB를 읽는다.

### 셸 자동완성
```bash
lb --install-completion                  # 현재 셸에 자동완성 설치 (bash, zsh, fish, PowerShell)
lb --show-completion                     # 설치하지 않고 스크립트만 출력
```
- Typer의 자동완성을 쓴다. 설치하면 셸 설정 파일(PowerShell은 프로필)에 줄을 더하므로 **새 셸(PowerShell은 새 창)을 열어야 반영된다**. Windows·macOS 모두 지원한다(`lb.exe`여도 완성 변수 이름은 `_LB_COMPLETE`).
- 후보: 프로젝트 `-p/--project` 값과 `lb project edit|archive`의 slug는 보관하지 않은 프로젝트(설명에 프로젝트 이름), `lb project unarchive`의 slug는 보관한 프로젝트다. 조회용 `lb task list -p`는 보관한 프로젝트까지 포함한다. 태스크 ID(`-t/--task`, `lb task edit|start|done|drop`의 ID)는 todo·doing 태스크이고 설명에 제목(60자까지)이 붙는다. `#`으로 시작하면 `#42` 형태로 완성한다.
- 탭 한 번이 DB를 바꾸지 않도록 **읽기 전용**(`core.db.open_readonly`)으로만 연다. DB가 없거나, 현재 스키마 버전과 다르거나(옛 버전 DB), 어떤 오류가 나도 후보 없이 조용히 끝난다.

### 오류와 종료 코드
| 코드 | 의미 |
|---|---|
| 0 | 성공 |
| 1 | 입력·데이터 오류(stderr에 `오류: …` 한 줄), 외부 명령·API 실패(`git`·`gh`·AI 서비스), 삭제·이월·타이머 취소·파일 덮어쓰기·문장 다듬기 전송 확인을 거절했거나 확인 입력이 없음 |
| 2 | 명령 문법 오류(없는 옵션, 인자 누락·초과 등) |
| 130 | Ctrl+C로 중단 |

예외: `lb serve`는 Ctrl+C가 서버를 끄는 정상 방법이라 `웹 대시보드를 종료했습니다.`를 출력하고 종료 코드 0으로 끝난다.

---

## 6. 웹 대시보드 명세 (`lb serve`)

FastAPI + Jinja2 서버 렌더링, 상호작용은 HTMX, 차트는 Chart.js. 로컬 전용(127.0.0.1 바인딩), 인증 없음. htmx·Chart.js는 `static/vendor/`의 로컬 파일이라 인터넷 없이 동작한다.

Phase 5에서 대시보드(`/`)와 기록(`/logs`) 화면, JSON API를 구현했고, Phase 6에서 태스크(`/tasks`)·보고서(`/report`)·설정(`/settings`) 화면, 타이머 시작·취소, 다크모드, 설정 자동 반영을 더했다. 머리 메뉴는 대시보드, 기록, 태스크, 보고서, 설정이다. Phase 7에서 보고서 화면에 커밋 부록과 문장 다듬기(선택 기능)를 더했다. Phase 8에서 화면 구조는 그대로 두고 디자인 시스템(설정 글꼴, 디자인 토큰, 꼬리표, 프로젝트 색 점, 프로젝트 색 규칙)을 더했고, 보완으로 사용자 지정 색(설정 화면의 카테고리 색 표, 프로젝트 색 고르기)을 더했다.

### 실행과 보안
- 서버는 항상 127.0.0.1에만 연다. `[web].host`는 표시용 주소이고 `127.0.0.1`, `localhost`만 받는다(3장). 같은 PC의 다른 사용자나 다른 PC에서는 접속할 수 없다. 인증이 없으므로 LAN에 공개하지 않는다.
- 설정 파일은 요청마다 바뀌었는지 확인해 자동으로 반영한다(3장). `db_path`·`web.host`·`web.port`만 서버를 다시 시작해야 한다.
- **Host 검사:** `Host` 헤더가 하나이고 호스트 이름이 `127.0.0.1` 또는 `localhost`(대소문자 무시)일 때만 받는다. 포트가 있으면 ASCII 숫자여야 한다(`127.0.0.1:`, `localhost:abc`는 거부). 헤더가 없거나 여러 개이면 거부한다. 다른 사이트의 도메인이 127.0.0.1로 연결되는 DNS 리바인딩을 막는다. `[::1]` 같은 IPv6 주소는 받지 않는다. 거부하면 403이다.
- **교차 출처 쓰기 차단:** GET·HEAD·OPTIONS가 아닌 요청은 다음 규칙으로 가린다. 어긋나면 403이다.
  1. `Sec-Fetch-Site`가 있으면 `same-origin`이나 `none`일 때만 받는다.
  2. 없고 `Origin`이 있으면 `http`이고 `host:port`가 `Host`와 같을 때만 받는다(`null`은 거부, `Origin`이 여러 개여도 거부).
  3. 둘 다 없으면 브라우저가 아닌 클라이언트(curl, 스크립트)로 보고 받는다.
- **보안 헤더(모든 응답):** `Content-Security-Policy`(모든 출처를 `'self'`로 좁힘, 인라인 스크립트·스타일 없음, `frame-ancestors 'none'`), `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: same-origin`. `/static/`이 아닌 응답(`/fonts.css`, `/colors.css` 포함)에는 `Cache-Control: no-store`도 붙인다. `/static/` 응답은 `Cache-Control: no-cache`와 ETag(재요청은 304)라서 새로 고침만으로 최신 CSS·JS를 받는다.
- `/docs`, `/redoc`, `/openapi.json`은 열지 않는다(CDN 스크립트가 CSP와 맞지 않는다). API 계약은 이 문서가 기준이다.

### 화면 동작 (Phase 5)
- **공통:** 모든 오류는 한국어 문구로 보여 준다(core 오류 문구를 그대로 쓴다). 서버 내부 오류는 화면에 상세를 내지 않고 `lb serve`를 실행한 터미널을 안내한다.
- **빠른 기록:** 시간, 메모, 프로젝트, 카테고리, 태스크를 입력하고 Enter 또는 `기록` 버튼으로 저장한다. 저장하면 요약 카드·차트·최근 기록을 함께 갱신하고 결과 줄(`✔ #128 payment/dev 2h — 메모 (오늘 누적 5h 30m)`)을 보여 준다. 저장 뒤에는 시간·메모만 비우고 프로젝트·카테고리·태스크 선택은 유지한다. 처리하는 동안 버튼을 잠그고 같은 폼의 중복 요청은 버려서 Enter를 빠르게 두 번 눌러도 한 건만 저장한다.
  - 날짜는 항상 오늘이다. 다른 날짜는 기록 페이지에서 고친다.
  - '자동' 규칙은 `lb add`와 같다. 프로젝트를 비우면 태스크의 프로젝트, 태스크도 없으면 설정의 `default_project`를 쓴다. 카테고리를 비우면 태스크의 카테고리를 쓴다. 태스크도 카테고리도 없으면 `카테고리를 고르세요. …` 오류다. 태스크 후보는 보관하지 않은 프로젝트의 todo·doing 태스크다.
  - 오류는 폼 아래 알림에 보여 주고 입력한 값은 그대로 둔다.
- **타이머:** 진행 중인 타이머(`payment/design`, 메모, 태스크, 시작 시각, 경과)와 `정지` 버튼을 보여 준다. 경과는 60초마다 갱신한다. `정지`는 `lb stop`과 같이 저장하고(반올림 없음, 메모 덧붙이지 않음), 요약·최근 기록을 갱신한다. CLI에서 타이머가 이미 멈췄으면 다음 갱신에서 패널이 비워진다. 타이머 시작·취소는 아래 Phase 6 동작을 본다.
- **기록 페이지(`/logs`):** 주차(기본 이번 주)·프로젝트·카테고리 필터를 바꾸면 표만 다시 그리고 주소(`?week=&project=&category=`)를 갱신한다. 합계와 건수를 함께 보여 준다. 잘못된 주차·없는 프로젝트는 알림으로 알린다.
- **인라인 수정:** 행의 `수정`을 누르면 그 행이 시간·메모·날짜·프로젝트·카테고리·태스크 입력으로 바뀌고 시간 입력에 포커스가 간다. 저장하면 바뀐 항목만 반영한다(`lb log edit`과 같다). 바뀐 것이 없으면 `바뀐 내용이 없습니다.`를 알린다. 날짜를 다른 주로 옮겨도 표는 보고 있던 주 그대로 남고 그 기록만 빠진다. 입력 오류는 알림으로 보여 주고, 편집 행은 입력한 값 그대로 둔다(포커스는 시간 입력).
- **삭제:** 브라우저 확인 창에 연도를 포함한 기록 한 줄을 보여 주고 `확인`해야 삭제한다.
- **버전 확인(기록):** 화면의 각 행은 기록 버전(id·날짜·시간·메모·프로젝트·카테고리·태스크·생성 시각의 해시)을 들고 있고 수정·삭제 요청에 함께 보낸다. 그사이 CLI 등으로 기록이 바뀌었으면 409(`다른 곳에서 기록이 바뀌었습니다: #128. 목록을 새로 고친 뒤 다시 시도하세요.`)로 거부한다. 수정·삭제 모두 알림으로 오류를 보여 준다. 수정이면 편집 행을 입력한 값 그대로 둔다. 검사와 변경 사이의 밀리초 단위 경쟁 구간은 막지 않는다(로컬 단일 사용자라 허용, 후속 항목).

### 화면 동작 (Phase 6)
- **타이머(대시보드):** 타이머가 없으면 시작 폼(메모, 프로젝트, 카테고리, 태스크)을 보여 주고, 있으면 `정지`와 `취소`를 보여 준다. 시작은 `lb start`와 같은 규칙(태스크만 골라도 시작, todo 태스크는 doing으로)이다. `취소`는 브라우저 확인 창을 거쳐 기록 없이 버린다. 타이머가 없을 때 패널은 스스로 갱신하지 않으므로 CLI에서 시작한 타이머는 화면을 새로 고쳐야 보인다.
- **태스크(`/tasks`):** 칸반 3열(할 일, 진행 중, 이번 주 완료)이다. 완료 열은 이번 주에 완료한 것만이고 중단한 태스크는 보이지 않는다. 720px 미만에서는 한 열이다.
  - 상태는 카드의 버튼으로 바꾼다(`lb task start|done|drop`과 같다). 추가 폼은 `lb task add`와 같은 항목이다. 상태 이름은 보고서와 같은 한국어(할 일·진행·완료·중단)다.
  - 카드 `수정`은 제목·카테고리·예상·주차를 고친다(Enter 저장, Esc 취소). 바뀐 항목만 반영하고 바뀐 것이 없으면 `바뀐 내용이 없습니다.`를 알린다.
  - 프로젝트 필터는 보드와 다음 주 계획 패널에 함께 적용된다. 카드에는 실적(연결된 기록 합계)이 늘 보이고(없으면 `실적 0m`), 예상이 있을 때만 `/ 예상 Y`가 붙는다. 실적이 예상보다 크면 `예상 초과` 꼬리표가, 계획 주차 옆에는 이번 주·다음 주·지난 주 꼬리표가 붙는다.
  - **다음 주 계획 패널:** 보고서 4절과 같은 함수로 만든 계획(다음 주 계획 + 이월 후보)과 예상 합계를 보여 준다. `다음 주로 이월` 버튼은 이번 주의 할 일·진행 중 태스크를 다음 주로 옮기고(`lb plan carry`와 같다) 확인 창을 거친다. 일부만 옮기면 성공 줄 뒤에 `N건은 그사이 바뀌어 옮기지 않았습니다.`가 붙는다. 하나도 옮기지 못하면(0건) 409(`옮긴 태스크가 없습니다. 그사이 상태나 계획 주차가 바뀌었습니다. 패널을 지금 상태로 다시 표시했습니다.`)로 알리고 패널을 현재 상태로 다시 그린다.
- **보고서(`/report?week=`):** 주 이동, Markdown 원문 미리보기(`lb report`와 같은 템플릿), `복사`(Clipboard API, 실패하면 선택 후 `execCommand("copy")`), `.md` 내려받기(`weekly-report-2026-W40.md`, ASCII 이름, UTF-8·LF)가 있다. 아래 입력란에 그 주의 특이사항·리스크를 저장하면 `week_notes`에 쓰고 미리보기를 갱신한다. 두 칸을 모두 비우면 행을 지운다.
- **설정(`/settings`):** 프로젝트 표(보관 포함)와 색 견본(형식을 확인한 색만), `lb project add`와 같은 추가 폼(slug·이름·색, 색을 비우면 색 없음), 행 수정(이름·색·설명), 보관·보관 해제(`common`은 보관할 수 없다)가 있다. 카테고리 색 표(Phase 8 보완, 아래 Phase 8 절)가 있다. 설정 정보(설정 파일 경로, 실제로 연 DB 경로, 기본값, 글꼴)는 읽기 전용이다(카테고리 목록은 색 표로 옮겼다). 설정 파일 편집은 웹에서 하지 않는다.
- **다크모드:** OS·브라우저 설정(`prefers-color-scheme`)을 따르고 토글은 없다. 색 값은 `static/css/app.css`의 `:root` 토큰 두 벌(밝은·어두운)에만 있고, 다른 스타일 파일은 토큰만 쓴다(`web/assets.py`의 `STYLESHEETS`가 `app.css`, `dashboard.css`, `logs.css`, `components.css`, `tasks.css`, `report.css`, `settings.css`, `responsive.css` 순서를 정하고 `base.html`과 오류 페이지가 그대로 링크한다. 그 뒤에 `/fonts.css`를 링크한다. `components.css`는 타이머·버튼·알림처럼 여러 화면이 함께 쓰는 부품이다). 어두운 테마는 `screen`에만 적용되고 인쇄는 밝은 색이다. 테마가 바뀌면 차트를 다시 그린다.
- **버전 확인(409) 대상:** 기록 수정·삭제(Phase 5)에 더해 태스크 상태 변경·수정, 특이사항 저장, 프로젝트 수정·보관·보관 해제, 타이머 취소다. 화면이 들고 있는 대상의 버전(내용 해시)을 요청에 함께 보내고, 그사이 CLI 등으로 바뀌었으면 409로 거부하고 새로 고치라고 안내한다. 타이머 정지는 버전을 보지 않는다. 검사와 변경 사이의 경쟁 구간은 막지 않는다(후속 항목). JSON API는 버전을 보지 않는다.
- 화면 라우트(HTMX 조각 포함, `POST /report/polish` 포함)는 브라우저용이고 계약이 아니다. 연동에는 아래 JSON API를 쓴다.

### 화면 동작 (Phase 7)
- **커밋 부록(`/report`):** 설정에 `[[git.repos]]`가 있고 `include_commits`가 켜져 있으면 미리보기·복사·`.md` 내려받기·`GET /api/report`에 7장의 부록이 들어간다. 화면을 열 때마다 `git`을 실행한다(DB 세션은 이미 닫은 뒤라 DB를 잡고 있지 않다). 수집에 실패한 저장소는 미리보기 위의 경고 목록(`커밋을 모으지 못했습니다: payment (사유)`)으로 알리고 보고서는 그대로 만든다. API 응답에는 경고를 넣지 않는다.
- **문장 다듬기(`/report`):** 키와 패키지가 모두 준비된 제공자마다 `문장 다듬기 (Claude)`·`문장 다듬기 (ChatGPT)` 버튼을 보여 준다(`ANTHROPIC_API_KEY`·`anthropic` 패키지, `OPENAI_API_KEY`·`openai` 패키지). 둘 다 없으면 문장 다듬기 영역 전체를 숨긴다. 이 판정은 화면을 열 때 한다.
  - 버튼을 누르면 브라우저 확인 창이 `2026-W41 보고서 데이터(태스크 제목·특이사항·리스크 포함)를 외부 AI 서비스로 보냅니다. 커밋 내역과 작성자는 보내지 않습니다. 계속할까요?`를 보여 주고, `확인`해야 `POST /report/polish`(`week`, `provider`)를 보낸다. 요청하는 동안 버튼을 잠그고 `요약을 만드는 중입니다…`를 보여 준다.
  - 서버는 그 주의 보고서 데이터를 DB에서 만든 뒤 세션을 닫고 나서 외부에 요청한다(커밋 부록은 수집하지 않는다). 성공하면 미리보기 위의 결과 패널에 `요약 (자동 생성 · Claude claude-opus-5-5)`와 요약 문단, `요약 복사` 버튼을 보여 준다. 요약은 **저장하지 않는다**: 미리보기 Markdown·내려받기 파일·`lb report`에는 들어가지 않고, 주나 본문이 바뀌면 패널은 사라진다. 필요하면 `요약 복사`로 가져가 붙인다.
  - 잘못된 주차·제공자 이름, 키·패키지 없음은 400, 외부 서비스 실패(한도 초과·네트워크·모델 없음 등)는 502(`upstream`)로 화면 알림에 한국어 문구를 보여 준다. 교차 출처 요청은 다른 쓰기 요청처럼 403이다.

### 화면 동작 (Phase 8)
- **`GET /fonts.css`:** 설정 `[web]`의 글꼴을 CSS 변수(`--font-heading`, `--font-document`, `--font-body`)로 내는 스타일시트다. 응답은 `Content-Type: text/css; charset=utf-8`이고 `/static/`이 아니라서 `Cache-Control: no-store`가 붙는다. 값은 `"글꼴 이름", var(--font-sans)` 꼴이고 빈 값인 키는 줄을 내지 않아 `app.css`의 기본값(`var(--font-sans)`)이 남는다. 요청마다 현재 설정으로 만들기 때문에 설정 파일을 고친 뒤 서버를 다시 시작하지 않고 새로 고침만 하면 반영된다(3장). `base.html`과 오류 페이지가 `STYLESHEETS`의 모든 파일 뒤에 이 주소를 링크한다(`STYLESHEETS`에는 넣지 않는다). `base.html`은 그 다음에 `/colors.css`도 링크한다(오류 페이지는 링크하지 않는다). 글꼴을 인라인 스타일이 아닌 별도 스타일시트로 내므로 CSP(인라인 스타일 없음)와 맞는다.
- **글꼴이 쓰이는 곳:** `heading_font`는 제목과 큰 숫자(머리 로고, 패널·보드·보고서 제목, 요약 카드 숫자), `document_font`는 보고서 미리보기와 문장 다듬기 결과 글, 설정 화면의 문서 글꼴 미리보기, `body_font`는 본문·표·입력칸과 대시보드 차트 글자(`static/js/dashboard.js`가 `--font-body`를 읽는다)다.
- **설정 화면 글꼴 줄:** `/settings`의 설정 정보에 제목 글꼴·문서 글꼴·본문 글꼴 세 줄을 보여 준다. 각 줄은 설정 값(빈 값이면 `기본 글꼴`)과 그 글꼴로 그린 미리보기 문장(`가나다 ABC 123 · 8h 55m`)이다. 아래 안내 문장은 설치된 글꼴 이름으로 정하며 설치되지 않았으면 기본 글꼴로 보인다고 알린다. 글꼴 설정은 웹에서 저장하지 않는다.
- **디자인 토큰:** 색 값은 `app.css`의 `:root` 두 벌(밝은·어두운)에만 있고 다른 CSS는 토큰만 쓴다. 색은 데이터(프로젝트·카테고리)와 상태(`--ok`, `--danger`)에만 쓰고, 강조색 `--accent`는 링크·포커스·주 버튼 전용이다. 모서리는 `--radius-xs`(4px, 입력칸)·`--radius-sm`(8px, 버튼·태스크 카드)·`--radius-md`(12px, 패널·보드 열)·`--radius-full`(꼬리표), 입력칸 테두리는 배경과 3:1 이상 대비인 `--control-border`(옅은 `--rule`은 장식용), 그림자는 `--shadow-soft`·`--shadow-raised`, 글자 크기(`--text-*`)와 간격(`--space-*`)도 토큰이다.
- **꼬리표(pill):** `templates/partials/marks.html`의 `pill` 매크로와 `.pill`(`.pill--ok`, `.pill--danger`)로 카테고리(색은 아래 카테고리 꼬리표 색), 계획 주차(이번 주·다음 주·지난 주), `예상 초과`, `이월 후보`, 타이머의 `진행 중`, 프로젝트의 `보관`·`사용 중`을 같은 모양으로 보여 준다. `ok`와 `danger`는 상태에만 쓴다.
- **프로젝트 색 점:** 같은 파일의 `project_mark` 매크로가 프로젝트 이름 앞에 색 점(SVG, `aria-hidden`)을 붙인다. CSP 때문에 `style` 속성 대신 SVG `fill` 속성으로 칠한다. 태스크 카드, 기록 표, 대시보드 최근 기록에 쓴다.
- **프로젝트 색 규칙(`web/pages/views.py`의 `project_color`):** 프로젝트에 지정한 색(`#rrggbb`)이 있으면 그 색, 없거나 형식이 틀리면 프로젝트 ID로 고른 `CHART_PALETTE` 색이다. 대시보드 프로젝트 차트(`pages/summary.py`)도 같은 규칙이라 같은 프로젝트는 어느 화면·어느 주에서나 같은 색이다. 바뀐 점: 전에는 차트 색이 그 주에 나타난 순서로 정해졌다.
- **카테고리 색 규칙(`web/pages/views.py`의 `category_color_map`):** 저장한 색(`category_colors`, 2장)이 있으면 그 색, 없으면 설정의 카테고리 순서 위치로 고른 `CHART_PALETTE` 색이다. 설정에 없는 카테고리(설정에서 지운 뒤 남은 기록)는 설정 개수 뒤의 위치를 이름 순으로 받는다. 꼬리표와 대시보드 카테고리 차트(`pages/summary.py`)가 같은 규칙을 써서 같은 카테고리는 어느 화면·어느 주에서나 같은 색이다.
- **카테고리 색 표(`/settings`, `partials/category_section.html`):** 설정의 카테고리마다 한 줄(키, 이름, 색, 저장)이다. 색 칸은 색 고르기(`input type="color"`)와 `자동` 체크다. 색을 고르면 `자동` 체크가 풀리고(`static/js/app.js`, `data-color-field`), `자동`을 켜고 저장하면 저장한 색을 지워 자동으로 되돌린다. `저장`은 `POST /settings/categories/{key}/color`(폼 `color`·`auto`·`version`)이고 표만 다시 그린다. 결과 줄은 `✔ dev 색을 저장했습니다.`, `✔ dev 색을 자동으로 되돌렸습니다.`, 바뀐 것이 없으면 `바뀐 내용이 없습니다.`다. 그사이 다른 곳에서 바뀌었으면 409(버전은 키와 저장 색의 해시), 설정에 없는 키는 404(`설정에 없는 카테고리입니다: …`), 색 형식이 틀리면 400이고 오류는 `#flash`로 알린다. 표 아래에 카테고리 추가와 이름은 설정 파일 `[categories]`에서 바꾼다는 안내가 있다. 색 비교는 대소문자를 무시한다.
- **`GET /colors.css`:** 카테고리 꼬리표 색을 `.pill--cat-<키>` 규칙으로 내는 스타일시트다(`web/colors.py`의 `colors_css`, 라우트는 `web/pages/colors.py`). 응답은 `text/css; charset=utf-8`이고 `Cache-Control: no-store`라 저장한 뒤 새로 고침만으로 반영된다. 설정 카테고리 전부(설정 순서)와 색이 저장된 그 밖의 키(이름 순)의 규칙을 내고, 키가 형식에 맞지 않거나 색이 `#rrggbb`가 아니면 그 줄을 내지 않는다(CSS 주입 방지). 인라인 스타일을 쓰지 않으므로 CSP와 맞는다.
- **카테고리 꼬리표 색:** `partials/marks.html`의 `category_pill` 매크로가 `pill--cat-<키>` class를 붙이고(`templating.py`의 `category_class` 필터는 형식이 맞는 키에만 class를 준다), 형식이 틀린 키는 class 없이 기본 꼬리표로 보인다. 칠은 옅은 바탕이다: 카테고리 색을 `--pill-tint`(20%)만큼 표면색에 섞고 글자는 `--ink`다.
- **프로젝트 색 고르기:** 설정 화면의 프로젝트 추가 폼과 행 수정에서 색은 색 고르기(`input type="color"`)와 `자동` 체크(`color_auto`)다. `자동`이면 색을 비워 저장한다(색 없음). 추가 폼은 `자동`이 켜진 채 색 고르기에 팔레트 첫 색을 처음 값으로 보여 준다. 프로젝트 표의 색 칸은 지정한 색이면 견본과 `#rrggbb` 글자, 지정하지 않았으면(형식이 틀린 값 포함) 자동 팔레트 색 견본과 `자동`을 보여 준다. 이름 칸은 줄바꿈하지 않는다(`nowrap`). 수정할 때 색 비교는 대소문자를 무시해 같은 색을 다시 저장해도 바뀐 것으로 치지 않는다.

### 페이지
1. **대시보드** (`/`) — Phase 5, 타이머 시작·취소는 Phase 6
   - 이번 주 총 공수, 기록 건수, 완료 태스크 수 카드
   - 요일별 누적 막대 차트 (프로젝트별 색상 스택) + 일일 목표선
   - 프로젝트별·카테고리별 도넛 차트
   - 최근 기록 10건, 진행 중 타이머 표시(정지 버튼)
   - 상단 **빠른 기록 폼**: 시간 / 메모 / 프로젝트 / 카테고리 / Task (Enter로 저장, HTMX로 목록 갱신)
2. **기록** (`/logs`) — Phase 5
   - 주차·프로젝트·카테고리 필터, 인라인 수정·삭제
3. **태스크·계획** (`/tasks`) — Phase 6
   - 칸반 뷰 (todo / doing / 이번 주 done), 프로젝트 필터, 카드 수정
   - "다음 주 계획" 패널: 계획 태스크와 예상 공수 합계, 이월 버튼
   - 태스크별 예상 대비 실제 공수(연결된 WorkLog 합계) 표시
4. **보고서** (`/report?week=2026-W40`) — Phase 6
   - 주차 선택, Markdown 미리보기, 원문 복사 버튼, `.md` 다운로드
   - 보고서 하단 "특이사항/리스크" 입력란 (해당 주차에 저장)
   - 커밋 부록과 수집 경고, 문장 다듬기 버튼과 결과 패널 — Phase 7
5. **설정** (`/settings`): 프로젝트 관리(추가·수정·보관·보관 해제), 카테고리 색 표, 설정 정보(설정 파일·DB 경로·기본값·글꼴) 확인 — Phase 6, 색은 Phase 8 보완

### JSON API (CLI 이외의 연동·테스트용)
```
GET    /api/logs?week=&project=&category=
POST   /api/logs
PATCH  /api/logs/{id}
DELETE /api/logs/{id}
GET    /api/tasks?status=&week=&project=
POST   /api/tasks
PATCH  /api/tasks/{id}
GET    /api/stats?week=&by=project|category|day
GET    /api/report?week=&format=md|json
GET    /api/timer
POST   /api/timer/start | /api/timer/stop | /api/timer/cancel
```

Phase 5에서 구현했고, Phase 6에서 `GET /api/timer`와 `POST /api/timer/cancel`을 더했다. 화면과 같은 서비스를 부르므로 CLI와 규칙이 같다(보안 규칙도 같다).

**응답 봉투:** 모든 응답은 JSON이고 UTF-8이다(한글은 이스케이프하지 않는다).
```json
{"ok": true,  "data": {...}, "error": null}
{"ok": false, "data": null,  "error": {"code": "invalid_input", "message": "한국어 문구"}}
```
- 목록 응답(`GET /api/logs`, `GET /api/tasks`)은 최상위에 `meta`를 더한다. `/api/logs`는 `{week, start, end, count, total_minutes}`, `/api/tasks`는 `{count}`다.
- `message`는 사용자에게 보여 줄 한국어 문구다. 분기는 `code`로 한다.

**상태 코드와 `error.code`:**

| 상태 | code | 때문에 |
|---|---|---|
| 200 / 201 | | 성공 (추가는 201: `POST /api/logs`, `/api/tasks`, `/api/timer/start`) |
| 400 | `invalid_input` | 입력 값 오류(시간·날짜·주차 형식, 없는 키, 타입 오류, 본문이 JSON 객체가 아님, 이미 진행 중인 타이머 등) |
| 400 | `error` | 위로 분류되지 않는 도메인 오류 |
| 403 | `forbidden` | Host 검사·교차 출처 쓰기 차단에 걸림 |
| 404 | `not_found` | 없는 기록·태스크·프로젝트 ID나 slug, 진행 중인 타이머가 없을 때의 정지·취소, 없는 API 주소 |
| 405 | `method_not_allowed` | 그 주소가 받지 않는 메서드 |
| 502 | `upstream` | 외부 명령이나 외부 API가 실패함(`git`·`gh` 실행 실패, Claude·ChatGPT 요청 실패). 문장 다듬기(`POST /report/polish`)와 같은 화면 라우트에서 나온다 |
| 503 | `busy` | DB가 다른 프로세스에 잠겨 있음(잠시 후 다시 시도) |
| 503 | `not_initialized` | DB가 없거나 초기화되지 않음(`lb init`) |
| 500 | `internal` | 예상하지 못한 서버 오류(상세는 `lb serve`를 실행한 터미널에 남는다) |

409 `conflict`(버전 불일치)는 화면의 변경 요청에만 쓴다(대상은 위 "버전 확인(409) 대상"). API의 PATCH·DELETE는 버전을 보지 않는다.

**쿼리(GET):** 값은 앞뒤 공백을 지우고, 비어 있으면 생략한 것으로 본다.

| 엔드포인트 | 쿼리 | 기본값·규칙 |
|---|---|---|
| `GET /api/logs` | `week`, `project`(slug), `category` | `week`는 `this`(4장 주차 규칙). 없는 프로젝트는 404 |
| `GET /api/tasks` | `status`, `week`, `project` | `status`는 쉼표로 여러 개나 `all`(기본 `todo,doing`). `week`를 생략하면 주차로 거르지 않는다 |
| `GET /api/stats` | `week`, `by` | `by`는 `project`(기본)·`category`·`day`. `lb stats --by`와 같다 |
| `GET /api/report` | `week`, `format` | `format`은 `md`(기본)·`json` |

**요청 본문(POST·PATCH):** `Content-Type: application/json`의 UTF-8 JSON 객체. 정해진 필드만 받는다(알 수 없는 키는 400). 타입을 바꿔 받지 않는다(숫자 `2`를 문자열 시간으로 받지 않음). 시간·날짜·주차는 CLI와 같은 문자열 규칙(4장)이다.

| 엔드포인트 | 필드 (필수는 굵게) |
|---|---|
| `POST /api/logs` | **`duration`**, **`note`**, `project`, `category`, `date`, `task_id`. `project`를 생략하면 태스크의 프로젝트, 태스크도 없으면 설정 `default_project`를 쓴다. `category`를 생략하면 태스크의 카테고리를 쓰고, 태스크도 없으면 400(카테고리 필요)이다. 카테고리에는 설정 기본값이 없다. `date` 기본은 오늘 |
| `PATCH /api/logs/{id}` | `duration`, `note`, `category`, `project`, `date`, `task_id` |
| `POST /api/tasks` | **`title`**, `project`(기본 `default_project`), `category`, `estimate`(24시간 상한 없음), `week`, `due`, `ref`, `description` |
| `PATCH /api/tasks/{id}` | `title`, `category`, `estimate`, `week`, `due`, `ref`, `description`, `status`(`todo`·`doing`·`done`·`dropped`) |
| `POST /api/timer/start` | `note`, `project`, `category`, `task_id` (`task_id`만 줘도 시작한다. 메모는 태스크 제목, 카테고리는 태스크의 것을 쓴다. 태스크 없이 시작하려면 `note`와 `category`를 함께 줘야 한다) |
| `POST /api/timer/stop` | `note`(` — `로 덧붙임), `round`(1~60, 15분 단위 반올림) (본문 전체를 생략할 수 있다) |
| `GET /api/timer`, `POST /api/timer/cancel` | 본문 없음 |

**PATCH 규칙:**
- 보낸 키만 바꾼다. 하나도 보내지 않으면 400(`바꿀 항목을 하나 이상 지정하세요: …`).
- `null`은 값을 비우는 뜻이다. 비울 수 있는 필드는 기록의 `task_id`(태스크 연결 해제), 태스크의 `category`·`estimate`·`week`·`due`·`ref`·`description`뿐이다. 그 밖의 필드에 `null`을 보내면 400이다(`'duration' 값은 비울 수 없습니다.`).
- 태스크의 `status`를 보내면 `lb task start|done|drop`과 같이 `done_at`도 갱신한다. 프로젝트는 바꿀 수 없다(태스크 PATCH에 `project` 없음).

**응답 `data`:**
- 기록: `{id, date, minutes, duration, note, project, category, task_id, started_at, ended_at, created_at}`. `minutes`는 정수 분, `duration`은 `1h 30m` 표기, 시각은 UTC ISO 8601이다.
  - `POST /api/logs`는 `{log, day_total_minutes}`, `PATCH`는 `{log}`, `DELETE`는 `{id}`, `GET`은 기록의 배열이다.
- 태스크: `{id, project, title, description, status, category, estimate_minutes, planned_week, due_date, external_ref, created_at, updated_at, done_at, actual_minutes}`. `actual_minutes`는 연결된 기록의 합계다. `POST`·`PATCH`는 태스크 하나, `GET`은 배열이다.
- 타이머: `POST /api/timer/start`는 `{timer: {project, category, note, task_id, started_at, elapsed_minutes}, task_started}`(`task_started`는 todo 태스크가 doing으로 바뀌었는지)다. `POST /api/timer/stop`은 `{log, elapsed_minutes, day_total_minutes}`다. `GET /api/timer`는 `{timer}`이고 타이머가 없으면 `timer`가 `null`이다. `POST /api/timer/cancel`은 버린 타이머를 `{timer}`로 돌려주고, 타이머가 없으면 404다.
- 통계: `{week, start, end, by, total_minutes, count, rows: [{key, label, minutes, count}]}`.
- 보고서: `format=md`는 `{week, markdown}`, `format=json`은 보고서 데이터(7장의 `ReportData`를 그대로 직렬화한 구조)다. Phase 7부터 `commits`(커밋 부록, `[{project, repo, commits: [{date, hash, subject}]}]`, 없으면 `[]`)와 `summary`(문장 다듬기 요약, API는 만들지 않으므로 늘 `""`)가 들어 있고, `format=md`는 부록을 포함한다. 커밋 수집 경고는 응답에 없다.

### 후속 항목 (Phase 6·7·8 범위 밖)
- **웹 전용 오류 문구:** core 문구의 CLI 안내가 웹에도 보인다(예: 타이머 시작 실패의 `'lb stop'으로 저장하거나`).
- **브라우저 E2E 테스트:** 새 dev 의존성이 필요하다.
- **버전 확인과 변경 사이의 경쟁 구간:** 기록·태스크·프로젝트·특이사항·타이머 취소 모두 해당한다.
- **차트 팔레트:** 사용자가 색을 정할 수 있게 했다(카테고리 색 표, 프로젝트 색 고르기). 정하지 않은 항목이 쓰는 자동 팔레트의 어두운 바탕 대비(마지막 회색이 약하고 짙은 색 점의 대비가 낮다)는 그대로다.
- **카테고리 색 CLI와 JSON API:** 카테고리 색은 웹 설정 화면에서만 정한다. `lb`에 명령(예: `lb category color`)과 `/api`에 엔드포인트가 없다. 서비스 함수(`category_colors`, `set_category_color`, `clear_category_color`)는 이미 있다.
- **백업 가져오기의 `projects.color` 검증:** 가져올 때 `projects.color`가 문자열인지만 보고 `#rrggbb`인지는 보지 않는다. `category_colors.color`는 검사한다.
- **설정에서 지운 카테고리의 색 행 정리:** 행이 DB에 남고 화면에는 보이지 않는다. 같은 키를 다시 만들면 그 색이 되살아난다. 정리하는 방법이 없다.
- **카테고리 키 길이 제한:** 저장 컬럼은 32자(`String(32)`)로 선언했지만 설정과 서비스가 길이를 검사하지 않는다(SQLite는 길이를 강제하지 않는다). 설정과 서비스에 같은 제한을 둘 수 있다.
- **글꼴 고르기:** 설치된 글꼴 목록에서 고르기와 웹에서 글꼴 설정 저장. 지금은 설정 파일에 이름을 적는다.
- **수정 중인 태스크 카드의 프로젝트 색 점:** 수정 폼이 열린 카드에는 프로젝트가 글자만 나온다.
- **타이머 정지의 버전 확인**
- **태스크 화면 확장:** 끌어 놓기, 설명·마감일·외부 참조 수정, 중단 태스크 보기·복원
- **웹에서 설정 파일 편집:** 지금은 읽기만 한다.
- **특이사항 CLI 입력**(`lb report note` 등)
- **다크모드 수동 토글**
- **오래된 마이그레이션 백업 정리:** 자동으로 지우지 않는다. 정리 명령이나 안내를 더할 수 있다.
- **Phase 4 후속 항목:** 가져오기 병합, DST, 템플릿 샌드박스, 오프라인 휠 테스트.
- **Phase 7 후속 항목:** 웹에서 GitHub 이슈 가져오기, 요약 저장(주차별)과 보고서 3절 자동 채우기, 커밋 수집 결과 캐시(웹 보고서를 열 때마다 `git`을 실행한다), 제공자 추가(Gemini 등)와 사용자 정의 프롬프트, Jira 등 다른 이슈 추적기.
- LAN 공개는 비목표다(1장).

---

## 7. 주간보고서 형식

`core/services/report.py`의 `weekly_report()`가 한 주의 기록·태스크로 **구조화된 데이터**(`core/report.py`의 불변 데이터 클래스 `ReportData`)를 만들고, `core/report.py`의 `render_markdown()`이 Jinja2 템플릿으로 Markdown을 렌더링한다. 템플릿은 설정 파일과 같은 폴더의 `report.md.j2`(기본 `~/.logbook/report.md.j2`, `LOGBOOK_CONFIG`를 따름)로 바꿀 수 있다. 파일이 없으면 패키지 안의 기본 템플릿(`logbook/core/templates/report.md.j2`)을 쓴다.

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
### 특이사항
결제 서버 점검 일정이 10/9로 확정됨

### 리스크
외부 PG 응답 지연이 계속되면 일정이 밀릴 수 있음

## 4. 다음 주 계획
### admin (예상 10h)
- 권한 정리 (#45) — 예상 10h (이월 후보)

### payment (예상 12h)
- 환불 API 구현 (#44) — 예상 8h
- 환불 API 설계 (#43) — 예상 4h (이월 후보)
```

**부록(커밋 내역, Phase 7):** 설정의 `[[git.repos]]`에서 모은 본인 커밋이 있으면 4절 뒤에 다음 부록을 붙인다. `report.include_commits`를 `false`로 하거나 `[[git.repos]]`가 없거나 커밋이 하나도 없으면 부록 전체를 생략한다.

```markdown
## 부록. 커밋 내역
### payment (payment-server)
- 2026-09-29 a1b2c3d 결제 재시도 로직 구현
- 2026-10-02 e4f5a6b 재시도 횟수 설정 추가

### admin (admin-web)
- 2026-09-30 1234abc 권한 화면 정리
```

- 저장소는 설정 순서대로이고 커밋이 있는 저장소만 나온다. 제목은 `### <project> (<저장소 폴더 이름>)`, 줄은 `- 작성 날짜 해시 7자리 제목`이며 오래된 커밋부터다. 수집 규칙은 5장 `lb git-collect`와 같다.
- 커밋 제목은 보고서 데이터(`ReportData.commits`)와 Markdown에만 들어간다. 문장 다듬기로는 보내지 않는다.

**요약 절(Phase 7, 선택):** `lb report --polish`나 웹 문장 다듬기로 요약을 만들면 제목·작성자 바로 아래, 1절 앞에 `## 요약 (자동 생성)` 절과 문단 하나가 붙는다. 요약이 없으면(기본) 이 절은 나오지 않는다. 절 번호(1~4)는 바뀌지 않는다. 사용자 템플릿(`report.md.j2`)을 쓰면 템플릿에 `data.summary`를 넣어야 요약이 나온다. 템플릿 소스에 `summary`가 없으면 `--polish`는 확인 전에 `주의: 사용자 보고서 템플릿에 data.summary가 없어 요약이 출력에 나오지 않습니다: 경로. 템플릿에 data.summary를 넣으세요.`를 stderr에 쓰고(진행은 막지 않는다) 그대로 요청한다.

실적 그룹핑 규칙:
- 공수 요약 표의 열 이름은 설정의 카테고리 라벨이고 기록이 있는 카테고리만 나온다. 프로젝트는 합계 내림차순(같으면 slug 순), 비율은 프로젝트 합계 / 주 합계(정수 반올림)다.
- Task에 연결된 WorkLog는 Task 단위로 묶는다. `(#42)`는 태스크 ID이고 시간은 보고 주 마지막 날까지의 누적이다(완료는 `실제`, 나머지는 `누적`). 순서는 완료 → 진행 → 할 일 → 중단, 같은 상태 안에서는 ID 순이다.
- Task 미연결 WorkLog는 카테고리 라벨별로 합산해 "기타" 줄에 시간 내림차순(같으면 표의 열 순서)으로 적는다.
- 1절의 완료 태스크 수는 완료 시각이 그 주 안인 태스크 수다. 2절은 그 주 기록이 있는 태스크만 보여 주므로 두 값은 다를 수 있다.
- 다음 주 계획 = `planned_week == 다음 주`인 todo·doing 태스크 + `planned_week == 이번 주`인 todo·doing 태스크(끝에 `(이월 후보)`). done·dropped와 보관한 프로젝트의 태스크는 뺀다. 프로젝트 slug 순, 같은 프로젝트 안에서는 다음 주 계획 → 이월 후보, 각각 ID 순이다.
- 기록이 없는 주는 1절이 `총 0m (기록 0건, 완료 태스크 N건)` 한 줄(표 없음), 2절이 `기록이 없습니다.`다. 계획이 없으면 4절은 `계획된 태스크가 없습니다.`다. `author`가 비면 `작성자:` 줄을 뺀다.
- 3절은 `week_notes`의 두 칸을 `### 특이사항`, `### 리스크`로 나누어 싣고(템플릿 값 `data.notes`, `data.risks`), 비어 있는 칸은 뺀다. 둘 다 비면 `(작성하세요)` 한 줄이다. 입력은 웹 `/report`에서만 하고, `lb report` 출력에도 같은 내용이 들어간다.

### 선택 기능: LLM 문장 다듬기 (Phase 7)
`lb report --polish` 또는 웹 보고서의 "문장 다듬기" 버튼. 보고서 데이터로 실적 요약 문단을 생성해 Markdown에 `## 요약 (자동 생성)`으로 넣는다. 네트워크가 필요한 선택 기능이라 없어도 다른 기능은 모두 동작한다.

- **제공자:** Anthropic(Claude)과 OpenAI(ChatGPT)를 공식 SDK로 부른다. SDK는 선택 설치다: `uv sync --extra anthropic`, `uv sync --extra openai`. 제공자는 **API 키 환경변수와 패키지가 모두 있을 때만** 쓸 수 있다(키는 `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`이고 비어 있지 않아야 한다).
- **제공자 선택:** `--provider`(CLI)나 누른 버튼(웹) > 설정 `[llm].provider` > 쓸 수 있는 제공자 중 첫째(anthropic, openai 순). 설정이나 `--provider`로 고른 제공자의 키나 패키지가 없으면 오류다.
  - 쓸 수 있는 제공자가 없으면: `문장 다듬기를 쓸 수 있는 제공자가 없습니다. ANTHROPIC_API_KEY나 OPENAI_API_KEY를 설정하고 'uv sync --extra anthropic'이나 'uv sync --extra openai'로 패키지를 설치하세요.`
  - 키가 없으면: `환경변수가 없습니다: ANTHROPIC_API_KEY. Claude 문장 다듬기를 쓰려면 API 키를 설정하세요.` 패키지가 없으면: `패키지가 설치되어 있지 않습니다: anthropic. 'uv sync --extra anthropic'로 설치하세요.`
  - 웹은 쓸 수 있는 제공자마다 버튼을 보여 주고 하나도 없으면 영역을 숨긴다(6장).
- **모델:** 설정 `[llm].anthropic_model`(기본 `claude-opus-5-5`), `[llm].openai_model`(기본 `gpt-6.1-sol`). 둘 다 추론 강도(effort)는 `low`로 고정한다(요약에는 깊은 추론이 필요 없다). Claude는 모델이 거절하면 서버가 대체 모델로 다시 시도하는 기능(beta)을 지원하는 모델에서 켠다. 요청 제한 시간은 60초, 자동 재시도는 2회다.
- **보내는 데이터(외부 전송):** 그 주의 보고서 데이터(공수 표, 프로젝트별 태스크 제목·시간, 특이사항·리스크, 다음 주 계획)를 JSON으로 보낸다. **커밋 부록(커밋 제목)과 작성자 이름은 보내지 않는다.** API 키와 DB 파일은 보내지 않는다. 시스템 프롬프트는 데이터에 없는 사실을 지어내지 말고 3~5문장의 평문 한 문단만 쓰도록 요구한다. 응답은 줄바꿈을 한 칸 공백으로 합쳐 문단 하나로 정리한다.
- **확인과 비용:** 외부 AI 서비스 사용에는 제공자의 API 요금이 든다. 그래서 보내기 전에 항상 확인한다(CLI는 `[y/N]` 프롬프트, `--yes`로 생략. 웹은 브라우저 확인 창). 확인 문구는 보내는 범위(주차, 프로젝트·태스크 수, 특이사항·리스크 포함 여부)와 커밋·작성자를 보내지 않는다는 점을 알린다(5장, 6장).
- **실패:** 키 거부(`Claude API 키가 올바르지 않거나 권한이 없습니다. 확인할 환경변수: ANTHROPIC_API_KEY.`), 모델 없음(`Claude 모델을 쓸 수 없습니다: 모델. 설정 [llm].anthropic_model을 확인하세요.`), 한도 초과(`Claude 요청 한도를 넘었습니다. 잠시 후 다시 시도하세요.`), 시간 초과(`Claude 응답이 60초 안에 오지 않았습니다. 잠시 후 다시 시도하세요.`), 연결 실패(`Claude 서버에 연결하지 못했습니다. 인터넷 연결을 확인하세요.`), 그 밖의 HTTP 오류(`Claude 요청이 실패했습니다 (HTTP 500). 잠시 후 다시 시도하세요.`), 모델 거절(`Claude 모델이 요약을 거절했습니다. 다른 제공자로 다시 시도하세요.`), 길이 제한(`… 응답이 길이 제한에 걸려 끝까지 오지 않았습니다. 다시 시도하세요.`), 빈 응답(`… 응답에 요약 문장이 없습니다. 다시 시도하세요.`). ChatGPT는 이름과 환경변수만 다르다. CLI는 요약 없는 보고서를 대신 내보내지 않고 종료 코드 1로 끝나며, 웹은 502 알림이다.
- 요약 문단은 만들 때마다 다를 수 있고 저장하지 않는다.

---

## 8. 품질 기준

- `core` 테스트 커버리지 80% 이상 (duration, weeks, services 집계, report 조립은 필수)
- Windows·macOS 양쪽 CI에서 전체 테스트 통과 (경로, 인코딩, 한글 출력, 클립보드 실패 처리 테스트 포함)
- 한글 메모·프로젝트명이 Windows Terminal, PowerShell, macOS Terminal/iTerm2에서 깨지지 않을 것
- `--help`, `--version`, 사용법 오류, 입력 형식 오류는 SQLAlchemy와 웹 스택을 로드하지 않는다(서브프로세스 테스트로 강제). `lb add` 응답 시간은 CI 보고서(`scripts/bench_cli.py`)로 추적한다(파이썬 내부 처리 시간 참고값: Windows 약 500 ms, macOS 약 350 ms). `lb serve`를 실행할 때만 FastAPI·uvicorn을 import한다(서브프로세스 테스트로 강제).
- 모든 에러 메시지는 한국어로, 다음 행동을 안내 (예: "프로젝트를 찾을 수 없습니다: 'paymnt'. `lb project list`로 확인하세요.") 단, 명령 문법 오류(없는 옵션, 인자 누락 등, 종료 코드 2)와 --help의 틀(Usage, Options 등)은 Typer/Click 기본 영어 문구를 쓴다.
- 외부 명령·API 실패는 한국어 한 줄이다. 공통 형식: `명령을 찾을 수 없습니다: 이름. 설치 안내`, `명령이 N초 안에 끝나지 않았습니다: 이름.`, `명령이 실패했습니다: 이름 (종료 코드 N). stderr 첫 줄`. `git`·`gh`는 `shutil.which`로 찾아 `shell=False`·목록 인자로 실행하고 대화형 입력을 기다리지 않게 한다(`GIT_TERMINAL_PROMPT=0`, `GH_PROMPT_DISABLED=1`). 커밋 수집 실패는 보고서를 막지 않고 경고가 되며(CLI 보고서·웹), `lb git-collect`·`lb task import-gh`·`--polish`는 오류(종료 코드 1)로 끝난다.
- 자동 테스트는 외부 서비스를 부르지 않는다. `git`·`gh`·Claude·ChatGPT는 가짜 실행 함수·SDK 클라이언트 대역으로 대신하고(임시 git 저장소를 만드는 테스트만 실제 `git`을 쓴다), 실제 키·`gh` 로그인이 필요한 확인은 사람이 두 OS에서 따로 한다.
- 데이터 손실 방지: 삭제 명령은 확인 프롬프트(`--yes`로 생략), `export`로 언제든 전체 백업 가능
