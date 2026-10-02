# AGENTS.md — logbook

이 파일은 AI 코딩 에이전트(Codex, Claude Code 등)가 이 저장소에서 작업할 때 항상 참고하는 프로젝트 컨텍스트다.
상세 요구사항은 `docs/SPEC.md`, 구현 순서는 `docs/ROADMAP.md`를 따른다.

## 프로젝트 개요

개인 소프트웨어 개발자의 업무 기록·공수 집계·주간업무보고서 생성 도구.

- 여러 프로젝트를 동시에 관리한다 (프로젝트별 분리 집계).
- 개발 외 업무(회의, 리뷰, 문서, 운영, 문의 대응 등)도 기록한다.
- 하나의 공통 코어(도메인 + SQLite) 위에 두 가지 인터페이스를 제공한다.
  1. **CLI** (`lb`): 터미널에서 10초 안에 기록하는 것이 최우선 목표
  2. **Web 대시보드** (`lb serve`): 로컬 브라우저에서 조회·집계·계획·보고서 확인

## 핵심 개념 (반드시 구분할 것)

- **Project**: 업무가 속한 프로젝트. 비개발 공통 업무용 `common` 프로젝트가 기본 존재.
- **Task**: 할 일(계획 단위). 상태, 예상 공수, 계획 주차를 가진다. "다음 주 계획"의 원천.
- **WorkLog**: 실제로 한 일(실적 단위). 날짜, 소요 시간(분), 카테고리, 메모. Task 연결은 선택.
- 주간 실적·공수는 **WorkLog를 집계**해서 만든다. Task 목록을 실적으로 쓰지 않는다.

## 기술 스택

- Python 3.11+, 패키지/가상환경 관리: `uv`
- CLI: Typer + Rich
- DB: SQLite (SQLAlchemy 2.0 ORM, typed `Mapped[]` 스타일)
- Web: FastAPI + Jinja2 템플릿 + HTMX + Chart.js (프론트 빌드 단계 없음, JS 번들러 금지)
- 설정: TOML (`tomllib` 읽기, `tomli-w` 쓰기)
- 테스트: pytest, 린트/포맷: ruff, 타입체크: mypy (strict는 core 패키지만)

## 디렉터리 구조

```
src/logbook/
  core/          # 도메인 로직. CLI/Web에 의존하지 않는다.
    models.py    # SQLAlchemy 모델
    db.py        # 엔진/세션, 스키마 생성 및 마이그레이션
    services.py  # 기록 추가, 집계, 계획 등 유스케이스 함수
    duration.py  # "1h30m", "1.5h", "90m" 파싱/포맷
    weeks.py     # ISO 주차 계산 (YYYY-Www)
    report.py    # 주간보고서 데이터 조립 + Markdown 렌더링
    config.py    # 설정 로드
    platform.py  # OS별 처리 (콘솔 인코딩, 클립보드, 데이터 디렉터리)
    gitcollect.py# git 커밋 수집 (선택 기능)
  cli/
    main.py      # Typer 앱, 엔트리포인트 `lb`
  web/
    app.py       # FastAPI 앱
    templates/   # Jinja2 + HTMX
    static/      # 최소한의 CSS, Chart.js는 CDN 또는 로컬 파일
tests/
docs/
```

## 아키텍처 규칙

- CLI와 Web은 반드시 `core.services`의 함수만 호출한다. SQL/ORM 쿼리를 CLI·Web 레이어에 직접 쓰지 않는다.
- 시간은 내부적으로 항상 **정수 분(minutes)** 으로 저장한다. 표시할 때만 `1h 30m` 형태로 변환.
- 날짜는 `date`(로컬 기준)로 저장, 타임스탬프는 ISO 8601 문자열 또는 timezone-aware datetime.
- 주차는 ISO 8601 주차(월요일 시작)를 기본으로 하되 설정으로 시작 요일 변경 가능하게 설계.
- 프로젝트는 사용자 입력 시 `slug`(예: `payment`)로 지정한다. 존재하지 않는 slug면 친절한 에러 + 생성 안내.
- DB 경로 기본값: `~/.logbook/logbook.db`, 환경변수 `LOGBOOK_DB`로 덮어쓰기 가능. 테스트는 항상 임시 DB 사용. (OS별 처리는 아래 크로스 플랫폼 규칙 참고)
- 네트워크가 필요한 기능(LLM 요약 등)은 전부 선택 사항이며, 없어도 모든 핵심 기능이 동작해야 한다.

## 크로스 플랫폼 규칙 (Windows / macOS)

최종 제품은 **Windows 10/11과 macOS 모두에서 동일하게 동작**해야 한다. 모든 기능은 두 OS에서 테스트한다.

- **경로**: 항상 `pathlib.Path`를 사용한다. 문자열 결합, `/` 하드코딩, `os.path` 문자열 조작 금지. `~`는 `Path.expanduser()`로 확장한다.
- **데이터 디렉터리**: 두 OS 모두 `Path.home() / ".logbook"` (Windows: `C:\Users\<user>\.logbook`). 환경변수 `LOGBOOK_DB`, `LOGBOOK_CONFIG`로 덮어쓰기 가능.
- **파일 인코딩**: 모든 파일 읽기·쓰기에 `encoding="utf-8"`을 명시한다. 한국어 Windows의 기본 인코딩은 cp949이므로 생략하면 한글이 깨진다.
- **콘솔 출력**: Rich를 통해서만 출력한다. 시작 시 `sys.stdout`/`sys.stderr`가 UTF-8이 아니면 `reconfigure(encoding="utf-8")`을 시도한다. `✔` 같은 기호는 출력 실패 시 ASCII 대체 문자로 대신한다.
- **시간대**: `zoneinfo`를 쓰는 경우 Windows에는 IANA 시간대 DB가 없으므로 `tzdata` 패키지를 의존성에 포함한다.
- **날짜 포맷**: `strftime`의 `%-d`, `%-m`(Unix 전용) 사용 금지. 앞자리 0 제거는 직접 포맷한다 (`f"{d.month}/{d.day}"`).
- **외부 명령 실행**: `subprocess.run([...], shell=False)`로 리스트 인자만 사용한다. bash 전용 문법, 파이프, `which` 금지 (실행 파일 탐색은 `shutil.which`).
- **클립보드**: `pyperclip`으로 처리한다 (macOS는 pbcopy, Windows는 Win32 API를 내부적으로 사용). 실패 시 에러 대신 "클립보드 복사 실패, 파일로 저장하세요" 안내.
- **파일명**: 생성하는 파일명에 `: * ? " < > |` 금지 (Windows 금지 문자). 타임스탬프는 `20261002-153000` 형식.
- **SQLite**: 연결은 사용 후 반드시 닫고, 테스트 종료 시 `engine.dispose()`를 호출한다. Windows는 열린 파일을 삭제할 수 없어 임시 DB 정리가 실패한다.
- **줄바꿈**: 저장소는 LF로 통일한다 (`.gitattributes`에 `* text=auto eol=lf`). 생성하는 파일도 `newline="\n"`으로 쓴다.
- **브라우저 열기**: `webbrowser.open()`만 사용한다.
- **CI**: GitHub Actions에서 `windows-latest`, `macos-latest` 매트릭스로 테스트·린트·타입체크를 모두 통과해야 한다.
- 문서와 예시 명령은 두 OS에서 모두 실행 가능한 형태로 쓴다 (`uv run ...` 위주, bash 전용 명령은 PowerShell 대안을 함께 적는다).

## 자주 쓰는 명령

```
uv sync                      # 의존성 설치
uv run lb --help             # CLI 실행
uv run lb serve              # 웹 대시보드 (기본 http://127.0.0.1:8765)
uv run pytest                # 테스트
uv run ruff check .
uv run ruff format .
uv run mypy src/logbook/core
```

## 작업 방식

- 기능 하나를 구현할 때마다 `core`에 대한 단위 테스트를 함께 작성한다.
- `docs/ROADMAP.md`의 단계 순서를 지키고, 단계가 끝나면 체크박스를 갱신한다.
- 사용자 메시지·CLI 출력·웹 UI 문구는 **한국어**, 코드·식별자·커밋 메시지는 영어.
- 스키마를 변경하면 `db.py`의 마이그레이션(버전 테이블 기반)을 추가하고 기존 데이터가 보존되는지 테스트한다.
- 새 의존성을 추가하기 전에 이유를 설명하고 확인을 받는다.
