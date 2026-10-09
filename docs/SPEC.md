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

### schema_version
마이그레이션 버전 관리용 단일 행 테이블.

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
include_commits = true

[git]
author_email = "me@example.com"

[[git.repos]]
project = "payment"
path = "~/work/payment-server"

[[git.repos]]
project = "admin"
path = "~/work/admin-web"

[web]
host = "127.0.0.1"             # 127.0.0.1 | localhost (표시용 주소)
port = 8765
```

- `[web].host`는 `127.0.0.1`과 `localhost`만 받는다. 다른 값(`0.0.0.0` 등)은 설정 오류(종료 코드 1)다. 서버는 값과 무관하게 항상 127.0.0.1에만 열리고, 이 값은 시작 문구와 `--open`이 여는 주소에만 쓴다.
- 설정은 서버를 시작할 때 한 번 읽는다. 바꾸면 `lb serve`를 다시 시작한다.

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
lb project archive payment
```

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
```
- `lb task add <title>`: `-p`를 생략하면 `default_project`. 옵션은 `-c/--category`, `-e/--est`(예상 공수, 하루를 넘을 수 있으므로 24시간 상한 없음, 예: `40h`), `-w/--week`(계획 주차), `--ref`(외부 참조, `"#43"`·URL·Jira 키), `--due`(마감일, 날짜 입력 규칙과 같음).
  - 출력: `✔ 태스크 추가: #43 payment/design 환불 API 설계 (예상 4h · 2026-W42 · 참조 #43 · 마감 10-15)`. 괄호에는 값이 있는 항목만 쓰고, 하나도 없으면 괄호를 생략한다.
- `lb task list`: 기본은 todo·doing이다. `-s/--status`는 쉼표로 여러 상태를 받고 `all`은 네 상태 전부다. 보관한 프로젝트의 태스크는 `-p`로 그 프로젝트를 지정할 때만 보인다.
  - 출력: 표(ID, 상태, 프로젝트, 카테고리, 제목, 예상, 실적, 주차, 참조) + `태스크 3건 / 예상 10h / 실적 1h 45m`. 상태는 key(`todo`, `doing`, `done`, `dropped`)로 표시해 그대로 `--status`에 쓸 수 있다. 실적은 연결된 WorkLog 합계다.
- `lb task edit <ID>`: 지정한 항목만 바꾼다. 옵션은 `--title`, `-c/--category`, `-e/--est`, `-w/--week`, `--ref`, `--due`, 값을 비우는 `--no-category`, `--no-est`, `--no-week`, `--no-ref`, `--no-due`. 하나도 없거나 값과 같은 항목의 `--no-…`를 함께 주면 오류. 프로젝트는 바꿀 수 없다(연결된 기록과 어긋나지 않도록, 필요하면 drop 후 다시 만든다).
- `lb task start|done|drop <ID>`: 상태를 doing·done·dropped로 바꾼다. 출력 `✔ #43 todo → doing: payment/design 환불 API 설계`, `done`은 ` (실적 5h 30m / 예상 4h)`를 덧붙인다. 이미 같은 상태면 `· 태스크 #43 상태는 이미 doing입니다: …`를 출력하고 종료 코드 0이다. 완료·중단된 태스크도 다시 시작할 수 있다.
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
lb report [--week this] [--out report.md] [--copy] [--yes]
```
- `lb report`: 주간업무보고(7장 형식)를 Markdown으로 만든다. 기본은 이번 주를 stdout에 출력한다. `--week`(`-w`)는 `lb stats`와 같다(`this`, `last`, `next`, `2026-W40`).
- `--out`(`-o`): 파일로 저장한다(UTF-8, LF). 저장하면 보고서는 stdout에 출력하지 않고 `✔ 보고서를 저장했습니다: 경로` 한 줄만 보여 준다. 경로는 `~`로 시작할 수 있고 상대 경로는 현재 폴더 기준이다. 폴더이거나 부모 폴더가 없으면 오류(종료 코드 1)다.
  - 덮어쓰기 확인(R4): 파일이 이미 있으면 `파일이 이미 있습니다: 경로`와 `덮어쓸까요? [y/N]:`로 확인한다. 거절하거나 입력이 없으면 파일을 그대로 두고 종료 코드 1로 끝난다. `--yes`/`-y`로 확인을 생략한다.
- `--copy`: `pyperclip`으로 클립보드에 복사하고 `✔ 보고서를 클립보드에 복사했습니다.`를 출력한다(이때 stdout에는 보고서를 쓰지 않는다). 복사에 실패하면 오류로 끝내지 않고(종료 코드 0) stderr에 `주의: 클립보드에 복사하지 못했습니다. …` 경고를 쓴다. `--out`을 함께 줬으면 파일로 저장했다고 안내하고, 주지 않았으면 `--out` 사용을 안내하며 보고서를 stdout에 출력한다.
- `--out`과 `--copy`는 함께 쓸 수 있다.
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
lb git-collect [--week this]             # 설정된 레포에서 본인 커밋 수집 (보고서 첨부용, DB 저장 안 함)
lb serve [--port 8765] [--open]          # 웹 대시보드 실행
```
- `lb export`: 프로젝트·태스크·기록·진행 중 타이머를 JSONL 한 파일로 내보낸다. `--out`(`-o`)을 생략하면 현재 폴더에 `logbook-export-20261008-153000.jsonl`처럼 만든다. 기존 파일은 `lb report --out`과 같은 덮어쓰기 확인을 거치고 `--yes`로 생략한다(R4). 출력: `✔ 내보냈습니다: 경로 (프로젝트 2 · 태스크 5 · 기록 41 · 타이머 0)`.
  - 설정 파일(`config.toml`)과 보고서 템플릿(`report.md.j2`)은 들어 있지 않다. 따로 복사한다.
  - **JSONL 형식(버전 1, 공개 계약):** 파일은 UTF-8이고 한 줄이 JSON 객체 하나다. 첫 줄은 머리글 `{"type": "logbook-export", "format": 1, "schema_version": 1, "exported_at": "…"}`이고 (`schema_version`은 내보낸 DB의 스키마 버전, `exported_at`은 UTC 시각), 그 뒤는 `{"table": "tasks", "row": {…}}` 형태의 행이다. 행은 `projects`, `tasks`, `worklogs`, `active_timer` 순서이고 각 테이블 안에서는 id 순이다. `row`의 필드는 2장 데이터 모델의 컬럼과 같다. 시각은 UTC ISO 8601, 날짜는 `YYYY-MM-DD`, 상태는 `todo`·`doing`·`done`·`dropped`다. 한글은 이스케이프하지 않는다.
- `lb import <파일>`(R3): `lb export`로 만든 파일을 **빈 DB**(`lb init` 직후, `common` 프로젝트만 있음)에만 원래 id 그대로 복원한다. 기록·태스크가 id로 서로를 가리키므로 id를 바꾸지 않고, 병합은 id 충돌 규칙이 필요해 하지 않는다. 데이터가 있는 DB에는 가져오지 않고 새 DB를 쓰라고 안내한다(종료 코드 1). 복원 절차: `LOGBOOK_DB`를 새 경로로 바꾸고 `lb init` 후 `lb import`.
  - 파일 전체를 먼저 검증하고(머리글 형식·버전, 필드 이름·값, 참조 무결성 등) 통과했을 때만 한 번에 쓴다. 검증에 실패하면 `오류: N번째 줄: …` 한 줄로 알리고 DB는 바뀌지 않는다. 더 새로운 스키마로 내보낸 파일은 거부한다. 성공 출력: `✔ 가져왔습니다: 경로 (프로젝트 2 · 태스크 5 · 기록 41 · 타이머 0)`.
  - 가져오기는 줄을 LF로만 나눈다. 파일 앞의 BOM은 허용한다.
- `lb serve`: 웹 대시보드(6장)를 실행한다. `--port`(기본은 설정 `web.port`, 8765)는 1~65535의 ASCII 숫자만 받는다. 값은 설정·DB를 읽기 전에 검사한다.
  - 시작: `✔ 웹 대시보드: http://127.0.0.1:8765 (끄려면 Ctrl+C)`. `--open`이면 `webbrowser.open()`으로 브라우저를 연다. 열지 못하면 `주의: 브라우저를 열지 못했습니다. 주소를 직접 여세요: 주소` 경고만 내고 서버는 계속 돈다.
  - 종료: Ctrl+C로 `웹 대시보드를 종료했습니다.`를 출력하고 종료 코드 0으로 끝난다.
  - 오류(`오류: …` 한 줄, 종료 코드 1): 잘못된 `--port`, 설정 `host`가 허용 값이 아님, `lb init` 전(DB가 없거나 초기화되지 않음, `lb init`을 안내), 포트를 열 수 없음(이미 사용 중 등, `--port`로 다른 포트를 안내). DB를 연 뒤 포트 소켓을 먼저 열고 나서 서버를 띄우므로, 실패하면 서버는 뜨지 않는다.
  - 서버를 돌리는 동안에도 CLI(`lb add` 등)를 함께 쓸 수 있다. 화면은 요청할 때마다 DB를 읽는다.

### 오류와 종료 코드
| 코드 | 의미 |
|---|---|
| 0 | 성공 |
| 1 | 입력·데이터 오류(stderr에 `오류: …` 한 줄), 삭제·이월·타이머 취소·파일 덮어쓰기 확인을 거절했거나 확인 입력이 없음 |
| 2 | 명령 문법 오류(없는 옵션, 인자 누락·초과 등) |
| 130 | Ctrl+C로 중단 |

예외: `lb serve`는 Ctrl+C가 서버를 끄는 정상 방법이라 `웹 대시보드를 종료했습니다.`를 출력하고 종료 코드 0으로 끝난다.

---

## 6. 웹 대시보드 명세 (`lb serve`)

FastAPI + Jinja2 서버 렌더링, 상호작용은 HTMX, 차트는 Chart.js. 로컬 전용(127.0.0.1 바인딩), 인증 없음. htmx·Chart.js는 `static/vendor/`의 로컬 파일이라 인터넷 없이 동작한다.

Phase 5에서 구현한 것은 대시보드(`/`)와 기록(`/logs`) 화면, JSON API 전부다. 태스크·보고서·설정 화면은 Phase 6이다.

### 실행과 보안
- 서버는 항상 127.0.0.1에만 연다. `[web].host`는 표시용 주소이고 `127.0.0.1`, `localhost`만 받는다(3장). 같은 PC의 다른 사용자나 다른 PC에서는 접속할 수 없다. 인증이 없으므로 LAN에 공개하지 않는다.
- 설정은 시작할 때 한 번 읽는다. 설정을 바꾸면 서버를 다시 시작한다.
- **Host 검사:** `Host` 헤더가 하나이고 호스트 이름이 `127.0.0.1` 또는 `localhost`(대소문자 무시)일 때만 받는다. 포트가 있으면 ASCII 숫자여야 한다(`127.0.0.1:`, `localhost:abc`는 거부). 헤더가 없거나 여러 개이면 거부한다. 다른 사이트의 도메인이 127.0.0.1로 연결되는 DNS 리바인딩을 막는다. `[::1]` 같은 IPv6 주소는 받지 않는다. 거부하면 403이다.
- **교차 출처 쓰기 차단:** GET·HEAD·OPTIONS가 아닌 요청은 다음 규칙으로 가린다. 어긋나면 403이다.
  1. `Sec-Fetch-Site`가 있으면 `same-origin`이나 `none`일 때만 받는다.
  2. 없고 `Origin`이 있으면 `http`이고 `host:port`가 `Host`와 같을 때만 받는다(`null`은 거부, `Origin`이 여러 개여도 거부).
  3. 둘 다 없으면 브라우저가 아닌 클라이언트(curl, 스크립트)로 보고 받는다.
- **보안 헤더(모든 응답):** `Content-Security-Policy`(모든 출처를 `'self'`로 좁힘, 인라인 스크립트·스타일 없음, `frame-ancestors 'none'`), `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: same-origin`. `/static/`이 아닌 응답에는 `Cache-Control: no-store`도 붙인다.
- `/docs`, `/redoc`, `/openapi.json`은 열지 않는다(CDN 스크립트가 CSP와 맞지 않는다). API 계약은 이 문서가 기준이다.

### 화면 동작 (Phase 5)
- **공통:** 모든 오류는 한국어 문구로 보여 준다(core 오류 문구를 그대로 쓴다). 서버 내부 오류는 화면에 상세를 내지 않고 `lb serve`를 실행한 터미널을 안내한다.
- **빠른 기록:** 시간, 메모, 프로젝트, 카테고리, 태스크를 입력하고 Enter 또는 `기록` 버튼으로 저장한다. 저장하면 요약 카드·차트·최근 기록을 함께 갱신하고 결과 줄(`✔ #128 payment/dev 2h — 메모 (오늘 누적 5h 30m)`)을 보여 준다. 저장 뒤에는 시간·메모만 비우고 프로젝트·카테고리·태스크 선택은 유지한다. 처리하는 동안 버튼을 잠그고 같은 폼의 중복 요청은 버려서 Enter를 빠르게 두 번 눌러도 한 건만 저장한다.
  - 날짜는 항상 오늘이다. 다른 날짜는 기록 페이지에서 고친다.
  - '자동' 규칙은 `lb add`와 같다. 프로젝트를 비우면 태스크의 프로젝트, 태스크도 없으면 설정의 `default_project`를 쓴다. 카테고리를 비우면 태스크의 카테고리를 쓴다. 태스크도 카테고리도 없으면 `카테고리를 고르세요. …` 오류다. 태스크 후보는 보관하지 않은 프로젝트의 todo·doing 태스크다.
  - 오류는 폼 아래 알림에 보여 주고 입력한 값은 그대로 둔다.
- **타이머:** 진행 중인 타이머(`payment/design`, 메모, 태스크, 시작 시각, 경과)와 `정지` 버튼을 보여 준다. 경과는 60초마다 갱신한다. `정지`는 `lb stop`과 같이 저장하고(반올림 없음, 메모 덧붙이지 않음), 요약·최근 기록을 갱신한다. 시작·취소는 화면에 없고 CLI로 한다(`lb start`, `lb cancel`). CLI에서 타이머가 이미 멈췄으면 다음 갱신에서 패널이 비워진다.
- **기록 페이지(`/logs`):** 주차(기본 이번 주)·프로젝트·카테고리 필터를 바꾸면 표만 다시 그리고 주소(`?week=&project=&category=`)를 갱신한다. 합계와 건수를 함께 보여 준다. 잘못된 주차·없는 프로젝트는 알림으로 알린다.
- **인라인 수정:** 행의 `수정`을 누르면 그 행이 시간·메모·날짜·프로젝트·카테고리·태스크 입력으로 바뀌고 시간 입력에 포커스가 간다. 저장하면 바뀐 항목만 반영한다(`lb log edit`과 같다). 바뀐 것이 없으면 `바뀐 내용이 없습니다.`를 알린다. 날짜를 다른 주로 옮겨도 표는 보고 있던 주 그대로 남고 그 기록만 빠진다. 입력 오류는 그 행에 오류 줄로 보여 주고 편집 상태를 유지한다.
- **삭제:** 브라우저 확인 창에 연도를 포함한 기록 한 줄을 보여 주고 `확인`해야 삭제한다.
- **버전 확인:** 화면의 각 행은 기록 버전(id·날짜·시간·메모·프로젝트·카테고리·태스크·생성 시각의 해시)을 들고 있고 수정·삭제 요청에 함께 보낸다. 그사이 CLI 등으로 기록이 바뀌었으면 409(`다른 곳에서 기록이 바뀌었습니다: #128. 목록을 새로 고친 뒤 다시 시도하세요.`)로 거부한다. 수정은 그 행에, 삭제는 알림에 오류를 보여 준다. 검사와 변경 사이의 밀리초 단위 경쟁 구간은 막지 않는다(로컬 단일 사용자라 허용, 후속 항목).
- 화면 라우트(HTMX 조각 포함)는 브라우저용이고 계약이 아니다. 연동에는 아래 JSON API를 쓴다.

### 페이지
1. **대시보드** (`/`) — Phase 5
   - 이번 주 총 공수, 기록 건수, 완료 태스크 수 카드
   - 요일별 누적 막대 차트 (프로젝트별 색상 스택) + 일일 목표선
   - 프로젝트별·카테고리별 도넛 차트
   - 최근 기록 10건, 진행 중 타이머 표시(정지 버튼)
   - 상단 **빠른 기록 폼**: 시간 / 메모 / 프로젝트 / 카테고리 / Task (Enter로 저장, HTMX로 목록 갱신)
2. **기록** (`/logs`) — Phase 5
   - 주차·프로젝트·카테고리 필터, 인라인 수정·삭제
3. **태스크·계획** (`/tasks`) — Phase 6
   - 칸반 뷰 (todo / doing / done), 프로젝트 필터
   - "다음 주 계획" 패널: 계획 태스크와 예상 공수 합계, 이월 버튼
   - 태스크별 예상 대비 실제 공수(연결된 WorkLog 합계) 표시
4. **보고서** (`/report?week=2026-W40`) — Phase 6
   - 주차 선택, Markdown 미리보기, 원문 복사 버튼, `.md` 다운로드
   - 보고서 하단 "특이사항/리스크" 입력란 (해당 주차에 저장)
5. **설정** (`/settings`): 프로젝트 관리(추가·보관·색상), 카테고리 확인 — Phase 6

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
POST   /api/timer/start | /api/timer/stop
```

Phase 5에서 모두 구현했다. 화면과 같은 서비스를 부르므로 CLI와 규칙이 같다(보안 규칙도 같다).

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
| 404 | `not_found` | 없는 기록·태스크·프로젝트 ID나 slug, 진행 중인 타이머가 없을 때의 정지, 없는 API 주소 |
| 405 | `method_not_allowed` | 그 주소가 받지 않는 메서드 |
| 503 | `busy` | DB가 다른 프로세스에 잠겨 있음(잠시 후 다시 시도) |
| 503 | `not_initialized` | DB가 없거나 초기화되지 않음(`lb init`) |
| 500 | `internal` | 예상하지 못한 서버 오류(상세는 `lb serve`를 실행한 터미널에 남는다) |

409 `conflict`(기록 버전 불일치)는 화면의 수정·삭제 요청에만 쓴다. API의 PATCH·DELETE는 버전을 보지 않는다.

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
| `POST /api/timer/stop` | `note`(` — `로 덧붙임), `round`(1~60, 15분 단위 반올림) (본문 전체를 생략할 수 있다. 본문을 통째로 생략할 수 있는 것은 `stop`뿐이다) |

**PATCH 규칙:**
- 보낸 키만 바꾼다. 하나도 보내지 않으면 400(`바꿀 항목을 하나 이상 지정하세요: …`).
- `null`은 값을 비우는 뜻이다. 비울 수 있는 필드는 기록의 `task_id`(태스크 연결 해제), 태스크의 `category`·`estimate`·`week`·`due`·`ref`·`description`뿐이다. 그 밖의 필드에 `null`을 보내면 400이다(`'duration' 값은 비울 수 없습니다.`).
- 태스크의 `status`를 보내면 `lb task start|done|drop`과 같이 `done_at`도 갱신한다. 프로젝트는 바꿀 수 없다(태스크 PATCH에 `project` 없음).

**응답 `data`:**
- 기록: `{id, date, minutes, duration, note, project, category, task_id, started_at, ended_at, created_at}`. `minutes`는 정수 분, `duration`은 `1h 30m` 표기, 시각은 UTC ISO 8601이다.
  - `POST /api/logs`는 `{log, day_total_minutes}`, `PATCH`는 `{log}`, `DELETE`는 `{id}`, `GET`은 기록의 배열이다.
- 태스크: `{id, project, title, description, status, category, estimate_minutes, planned_week, due_date, external_ref, created_at, updated_at, done_at, actual_minutes}`. `actual_minutes`는 연결된 기록의 합계다. `POST`·`PATCH`는 태스크 하나, `GET`은 배열이다.
- 타이머: `POST /api/timer/start`는 `{timer: {project, category, note, task_id, started_at, elapsed_minutes}, task_started}`(`task_started`는 todo 태스크가 doing으로 바뀌었는지)다. `POST /api/timer/stop`은 `{log, elapsed_minutes, day_total_minutes}`다.
- 통계: `{week, start, end, by, total_minutes, count, rows: [{key, label, minutes, count}]}`.
- 보고서: `format=md`는 `{week, markdown}`, `format=json`은 보고서 데이터(7장의 `ReportData`를 그대로 직렬화한 구조)다.

### 추가 데이터
보고서의 "특이사항/리스크"를 저장하기 위해 `week_notes(week text PK, risks text, notes text, updated_at)` 테이블을 추가한다(Phase 6).

### Phase 6에 남은 것
- `/tasks` 칸반과 다음 주 계획 패널, `/report` 미리보기·복사·다운로드와 `week_notes`, `/settings` 화면
- 다크모드
- 웹에서의 타이머 시작·취소(API에도 상태 조회·취소가 없다)
- 설정 변경 자동 반영(지금은 서버 재시작)

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
(작성하세요)

## 4. 다음 주 계획
### admin (예상 10h)
- 권한 정리 (#45) — 예상 10h (이월 후보)

### payment (예상 12h)
- 환불 API 구현 (#44) — 예상 8h
- 환불 API 설계 (#43) — 예상 4h (이월 후보)
```

부록(커밋 내역)은 `lb git-collect`를 구현할 때까지 나오지 않는다(`report.include_commits` 설정은 아직 쓰지 않는다).

실적 그룹핑 규칙:
- 공수 요약 표의 열 이름은 설정의 카테고리 라벨이고 기록이 있는 카테고리만 나온다. 프로젝트는 합계 내림차순(같으면 slug 순), 비율은 프로젝트 합계 / 주 합계(정수 반올림)다.
- Task에 연결된 WorkLog는 Task 단위로 묶는다. `(#42)`는 태스크 ID이고 시간은 보고 주 마지막 날까지의 누적이다(완료는 `실제`, 나머지는 `누적`). 순서는 완료 → 진행 → 할 일 → 중단, 같은 상태 안에서는 ID 순이다.
- Task 미연결 WorkLog는 카테고리 라벨별로 합산해 "기타" 줄에 시간 내림차순(같으면 표의 열 순서)으로 적는다.
- 1절의 완료 태스크 수는 완료 시각이 그 주 안인 태스크 수다. 2절은 그 주 기록이 있는 태스크만 보여 주므로 두 값은 다를 수 있다.
- 다음 주 계획 = `planned_week == 다음 주`인 todo·doing 태스크 + `planned_week == 이번 주`인 todo·doing 태스크(끝에 `(이월 후보)`). done·dropped와 보관한 프로젝트의 태스크는 뺀다. 프로젝트 slug 순, 같은 프로젝트 안에서는 다음 주 계획 → 이월 후보, 각각 ID 순이다.
- 기록이 없는 주는 1절이 `총 0m (기록 0건, 완료 태스크 N건)` 한 줄(표 없음), 2절이 `기록이 없습니다.`다. 계획이 없으면 4절은 `계획된 태스크가 없습니다.`다. `author`가 비면 `작성자:` 줄을 뺀다.
- 3절은 `(작성하세요)` 자리표시자다(`week_notes` 저장은 Phase 6).

### 선택 기능: LLM 문장 다듬기
`lb report --polish` 또는 웹 보고서의 "문장 다듬기" 버튼. 환경변수 `ANTHROPIC_API_KEY`가 있을 때만 활성화. 구조화 데이터를 보내 실적 요약 문단을 생성하고, 원본 Markdown과 나란히 보여준다. 키가 없으면 기능을 숨긴다.

---

## 8. 품질 기준

- `core` 테스트 커버리지 80% 이상 (duration, weeks, services 집계, report 조립은 필수)
- Windows·macOS 양쪽 CI에서 전체 테스트 통과 (경로, 인코딩, 한글 출력, 클립보드 실패 처리 테스트 포함)
- 한글 메모·프로젝트명이 Windows Terminal, PowerShell, macOS Terminal/iTerm2에서 깨지지 않을 것
- `--help`, `--version`, 사용법 오류, 입력 형식 오류는 SQLAlchemy와 웹 스택을 로드하지 않는다(서브프로세스 테스트로 강제). `lb add` 응답 시간은 CI 보고서(`scripts/bench_cli.py`)로 추적한다(파이썬 내부 처리 시간 참고값: Windows 약 500 ms, macOS 약 350 ms). `lb serve`를 실행할 때만 FastAPI·uvicorn을 import한다(서브프로세스 테스트로 강제).
- 모든 에러 메시지는 한국어로, 다음 행동을 안내 (예: "프로젝트를 찾을 수 없습니다: 'paymnt'. `lb project list`로 확인하세요.") 단, 명령 문법 오류(없는 옵션, 인자 누락 등, 종료 코드 2)와 --help의 틀(Usage, Options 등)은 Typer/Click 기본 영어 문구를 쓴다.
- 데이터 손실 방지: 삭제 명령은 확인 프롬프트(`--yes`로 생략), `export`로 언제든 전체 백업 가능
