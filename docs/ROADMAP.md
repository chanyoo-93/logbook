# 구현 로드맵

각 단계는 독립적으로 동작 가능한 상태로 끝낸다. 단계 완료 시 체크박스를 갱신한다.
CLI만 필요하면 Phase 4까지, 웹 대시보드까지 원하면 Phase 6까지 진행한다.

## Phase 0. 프로젝트 골격
- [x] `uv init --package logbook`, `src/` 레이아웃, `[project.scripts] lb = "logbook.cli.main:app"` (Phase 2에서 `:run`으로 변경)
- [x] 의존성: typer, rich, sqlalchemy, tomli-w, jinja2, pyperclip, tzdata / dev: pytest, ruff, mypy
- [x] ruff·mypy·pytest 설정 (`pyproject.toml`)
- [x] `tests/conftest.py`: 임시 DB fixture (`LOGBOOK_DB`를 tmp_path로, 종료 시 `engine.dispose()`)
- [x] `.gitattributes` (`* text=auto eol=lf`), `.editorconfig`
- [x] GitHub Actions: `windows-latest` + `macos-latest` 매트릭스에서 pytest·ruff·mypy 실행
- [x] `core/platform.py`: 콘솔 UTF-8 설정, 클립보드 래퍼, 데이터 디렉터리 해석 + 테스트

## Phase 1. Core 도메인
- [x] `duration.py` 파싱/포맷 + 테스트 (SPEC 4장 모든 케이스)
- [x] `weeks.py` 주차 ↔ 날짜 범위, `this/last/next` 별칭 + 연말 경계 테스트 (2026-W53 등)
- [x] `config.py` 설정 로드, 기본값, `~` 확장
- [x] `models.py`, `db.py` (스키마 생성 + schema_version 기반 마이그레이션)
- [x] `services/`: project / worklog / task CRUD, 집계 함수(`stats_by(week, by)`)

## Phase 2. CLI — 기록 중심
- [x] `lb init`, `lb project add|list|archive`
- [x] `lb add` (기록 후 오늘 누적 시간 출력)
- [x] `lb log` 조회 + `edit` / `rm`
- [x] `lb stats`
- [x] CLI 테스트 (`typer.testing.CliRunner`)

## Phase 3. CLI — 태스크·계획·타이머
- [x] `lb task add|list|edit|start|done|drop`
- [x] `lb plan`, `lb plan carry`
- [x] `lb start|status|stop|cancel` 타이머

## Phase 4. 주간보고서
- [x] `report.py`: 구조화 데이터 조립 (SPEC 7장 그룹핑 규칙)
- [x] 기본 Jinja2 템플릿 + 사용자 템플릿 오버라이드
- [x] `lb report [--week] [--out] [--copy]`
- [x] `lb export|import` (JSONL)
- [ ] (선택) `gitcollect.py` + `lb git-collect`, 보고서 부록 (후속, R1)

## Phase 5. 웹 대시보드 — 기본
- [x] 의존성 추가: fastapi, uvicorn (CLI에서는 `lb serve` 실행 시에만 lazy import)
- [x] `/api/*` JSON 엔드포인트 + 테스트 (`TestClient`)
- [x] 레이아웃 템플릿, 대시보드 페이지(요약 카드, 차트), 빠른 기록 폼(HTMX)
- [x] `/logs` 필터·인라인 수정

## Phase 6. 웹 대시보드 — 계획·보고서
- [ ] `/tasks` 칸반 + 다음 주 계획 패널 + 예상 대비 실제
- [ ] `week_notes` 테이블 + `/report` 미리보기·복사·다운로드
- [ ] `/settings` 프로젝트 관리
- [ ] 다크모드 대응 CSS

## Phase 7. 선택 기능
- [ ] LLM 문장 다듬기 (`--polish`, `ANTHROPIC_API_KEY` 있을 때만)
- [ ] GitHub 이슈 가져오기: `lb task import-gh owner/repo --label ...` (gh CLI 또는 API)
- [ ] 셸 자동완성(`lb --install-completion`), 프로젝트·태스크 ID 자동완성

---

## Claude Code에 줄 프롬프트 예시

처음 시작할 때:
> CLAUDE.md와 docs/SPEC.md, docs/ROADMAP.md를 읽고, Phase 0과 Phase 1의 구현 계획을 먼저 세워줘. 파일별로 무엇을 만들지와 테스트 케이스 목록을 보여주고, 내가 승인하면 구현해.

단계 진행:
> ROADMAP의 Phase 2를 구현해. 각 명령마다 테스트를 먼저 작성하고, 끝나면 `uv run pytest`와 ruff, mypy를 통과시킨 뒤 체크박스를 갱신해. Windows에서 깨질 수 있는 부분(경로, 인코딩, 한글 출력)이 없는지도 점검해.

웹 시작:
> Phase 5를 시작해. CLI의 `lb add` 응답 속도가 느려지지 않도록 FastAPI는 `lb serve`에서만 import되게 해줘. 대시보드는 SPEC 6장의 구성을 따르고, 프론트엔드 빌드 도구 없이 HTMX와 Chart.js만 써.

리뷰 요청:
> 지금까지 구현된 core/services.py를 SPEC과 비교해서 빠진 요구사항이나 집계 오류 가능성이 있는 부분을 찾아줘. 수정은 하지 말고 목록만.

크로스 플랫폼 점검:
> 지금까지의 코드를 CLAUDE.md(AGENTS.md)의 크로스 플랫폼 규칙과 대조해서 Windows나 macOS 한쪽에서만 동작할 수 있는 부분을 찾아 고쳐줘. 인코딩 명시 누락, 경로 문자열 결합, Unix 전용 strftime, shell=True 사용을 중점적으로 봐.
