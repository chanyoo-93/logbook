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
host = "127.0.0.1"
port = 8765
```

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

FastAPI + Jinja2 서버 렌더링, 상호작용은 HTMX, 차트는 Chart.js. 로컬 전용(127.0.0.1 바인딩), 인증 없음.

### 페이지
1. **대시보드** (`/`)
   - 이번 주 총 공수, 기록 건수, 완료 태스크 수 카드
   - 요일별 누적 막대 차트 (프로젝트별 색상 스택) + 일일 목표선
   - 프로젝트별·카테고리별 도넛 차트
   - 최근 기록 10건, 진행 중 타이머 표시(정지 버튼)
   - 상단 **빠른 기록 폼**: 시간 / 메모 / 프로젝트 / 카테고리 / Task (Enter로 저장, HTMX로 목록 갱신)
2. **기록** (`/logs`)
   - 주차·프로젝트·카테고리 필터, 인라인 수정·삭제
3. **태스크·계획** (`/tasks`)
   - 칸반 뷰 (todo / doing / done), 프로젝트 필터
   - "다음 주 계획" 패널: 계획 태스크와 예상 공수 합계, 이월 버튼
   - 태스크별 예상 대비 실제 공수(연결된 WorkLog 합계) 표시
4. **보고서** (`/report?week=2026-W40`)
   - 주차 선택, Markdown 미리보기, 원문 복사 버튼, `.md` 다운로드
   - 보고서 하단 "특이사항/리스크" 입력란 (해당 주차에 저장)
5. **설정** (`/settings`): 프로젝트 관리(추가·보관·색상), 카테고리 확인

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

### 추가 데이터
보고서의 "특이사항/리스크"를 저장하기 위해 `week_notes(week text PK, risks text, notes text, updated_at)` 테이블을 추가한다.

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
- `--help`, `--version`, 사용법 오류, 입력 형식 오류는 SQLAlchemy와 웹 스택을 로드하지 않는다(서브프로세스 테스트로 강제). `lb add` 응답 시간은 CI 보고서(`scripts/bench_cli.py`)로 추적한다(파이썬 내부 처리 시간 참고값: Windows 약 500 ms, macOS 약 350 ms). CLI에서 FastAPI를 import하지 않는다.
- 모든 에러 메시지는 한국어로, 다음 행동을 안내 (예: "프로젝트를 찾을 수 없습니다: 'paymnt'. `lb project list`로 확인하세요.") 단, 명령 문법 오류(없는 옵션, 인자 누락 등, 종료 코드 2)와 --help의 틀(Usage, Options 등)은 Typer/Click 기본 영어 문구를 쓴다.
- 데이터 손실 방지: 삭제 명령은 확인 프롬프트(`--yes`로 생략), `export`로 언제든 전체 백업 가능
