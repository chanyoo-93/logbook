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
ops = "운영/장애"
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
- `-t <task_id>` 지정 시 프로젝트·카테고리는 Task의 값으로 기본 설정
- 성공 시 한 줄 출력: `✔ #128 payment/dev 2h — 결제 재시도 로직 구현 (오늘 누적 5h 30m)`

### 타이머
```bash
lb start "환불 API 설계" -p payment -c design [-t 43]
lb status                                # 진행 중 타이머와 경과 시간
lb stop [--note "추가 메모"]             # WorkLog로 저장, 15분 단위 반올림 옵션 --round 15
lb cancel
```

### 기록 조회·수정
```bash
lb log [--week this|last|2026-W40] [--date today] [-p payment] [-c dev]
lb log edit 128 --minutes 90 --note "..."
lb log rm 128
```
출력: Rich 테이블 (ID, 날짜, 프로젝트, 카테고리, 시간, 메모, Task) + 하단 합계.

### 태스크 / 계획
```bash
lb task add "환불 API 설계" -p payment -c design --est 4h --week next --ref "#43"
lb task list [-p payment] [--status todo,doing] [--week next]
lb task start 43                         # status → doing
lb task done 43
lb task drop 43
lb plan [--week next]                    # 해당 주 계획 태스크 + 예상 공수 합계
lb plan carry                            # 이번 주 미완료 태스크를 다음 주로 이월
```

### 집계 / 보고서
```bash
lb stats [--week this] [--by project|category|day]
lb report [--week this] [--out report.md] [--copy]
```
`--copy`는 `pyperclip`으로 클립보드에 복사한다. 실패하면 경고를 출력하고 `--out` 사용을 안내한다.
`lb stats` 예시 출력:
```
2026-W40 (09-28 ~ 10-04)   총 35h 00m / 기록 41건
프로젝트      개발    리뷰   회의   기타    합계
payment     14h     3h     2h     -      19h
admin        6h     1h     1h     -       8h
common       -      -      5h     3h      8h
```

### 데이터 관리
```bash
lb export --out backup.jsonl             # 전 테이블 JSONL 내보내기 (git 백업용)
lb import backup.jsonl
lb git-collect [--week this]             # 설정된 레포에서 본인 커밋 수집 (보고서 첨부용, DB 저장 안 함)
lb serve [--port 8765] [--open]          # 웹 대시보드 실행
```

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

`core/report.py`는 먼저 **구조화된 데이터(dict)** 를 만들고, Jinja2 템플릿으로 Markdown을 렌더링한다. (템플릿은 `~/.logbook/report.md.j2`로 사용자 교체 가능)

```markdown
# 주간업무보고 (2026-09-28 ~ 2026-10-04)
작성자: 홍길동

## 1. 공수 요약
총 35h 00m (기록 41건, 완료 태스크 6건)

| 프로젝트 | 개발 | 리뷰 | 회의 | 기타 | 합계 | 비율 |
|---|---|---|---|---|---|---|
| payment | 14h | 3h | 2h | - | 19h | 54% |
| ...

## 2. 프로젝트별 실적
### payment (19h)
- [완료] 결제 재시도 로직 구현 (#42) — 실제 8h / 예상 6h
- [진행] 환불 API 설계 (#43) — 누적 3h / 예상 4h
- 기타: 장애 대응 30m, 코드리뷰 3h

## 3. 특이사항 / 리스크
(week_notes 내용)

## 4. 다음 주 계획
### payment (예상 12h)
- 환불 API 구현 (#44) — 예상 8h
- ...

## 부록. 커밋 내역 (include_commits = true 일 때)
```

실적 그룹핑 규칙:
- Task에 연결된 WorkLog는 Task 단위로 묶어 상태와 누적 시간을 보여준다.
- Task 미연결 WorkLog는 카테고리별로 묶어 "기타" 줄에 요약한다.
- 다음 주 계획 = `planned_week == 다음 주` 태스크 + 상태가 `todo`/`doing`인 이번 주 계획 태스크(이월 후보 표시).

### 선택 기능: LLM 문장 다듬기
`lb report --polish` 또는 웹 보고서의 "문장 다듬기" 버튼. 환경변수 `ANTHROPIC_API_KEY`가 있을 때만 활성화. 구조화 데이터를 보내 실적 요약 문단을 생성하고, 원본 Markdown과 나란히 보여준다. 키가 없으면 기능을 숨긴다.

---

## 8. 품질 기준

- `core` 테스트 커버리지 80% 이상 (duration, weeks, services 집계, report 조립은 필수)
- Windows·macOS 양쪽 CI에서 전체 테스트 통과 (경로, 인코딩, 한글 출력, 클립보드 실패 처리 테스트 포함)
- 한글 메모·프로젝트명이 Windows Terminal, PowerShell, macOS Terminal/iTerm2에서 깨지지 않을 것
- `--help`, `--version`, 사용법 오류, 입력 형식 오류는 SQLAlchemy와 웹 스택을 로드하지 않는다(서브프로세스 테스트로 강제). `lb add` 응답 시간은 CI 보고서(`scripts/bench_cli.py`)로 추적한다(파이썬 내부 처리 시간 참고값: Windows 약 500 ms, macOS 약 350 ms). CLI에서 FastAPI를 import하지 않는다.
- 모든 에러 메시지는 한국어로, 다음 행동을 안내 (예: "프로젝트 'paymnt'가 없습니다. `lb project list`로 확인하세요.")
- 데이터 손실 방지: 삭제 명령은 확인 프롬프트(`--yes`로 생략), `export`로 언제든 전체 백업 가능
