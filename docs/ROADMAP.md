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
- [x] (선택) `gitcollect.py` + `lb git-collect`, 보고서 부록 (후속, R1 → Phase 7에서 구현)

## Phase 5. 웹 대시보드 — 기본
- [x] 의존성 추가: fastapi, uvicorn (CLI에서는 `lb serve` 실행 시에만 lazy import)
- [x] `/api/*` JSON 엔드포인트 + 테스트 (`TestClient`)
- [x] 레이아웃 템플릿, 대시보드 페이지(요약 카드, 차트), 빠른 기록 폼(HTMX)
- [x] `/logs` 필터·인라인 수정

## Phase 6. 웹 대시보드 — 계획·보고서
- [x] `/tasks` 칸반 + 다음 주 계획 패널 + 예상 대비 실제
- [x] `week_notes` 테이블 + `/report` 미리보기·복사·다운로드
- [x] `/settings` 프로젝트 관리
- [x] 다크모드 대응 CSS

## Phase 7. 선택 기능
- [x] LLM 문장 다듬기 (`lb report --polish`와 웹 버튼, Claude·ChatGPT, 키와 선택 설치 패키지가 있을 때만)
- [x] GitHub 이슈 가져오기: `lb task import-gh owner/repo --label ...` (gh CLI)
- [x] 셸 자동완성(`lb --install-completion`), 프로젝트·태스크 ID 자동완성
- [x] `lb git-collect`와 보고서 커밋 부록

## Phase 8. 웹 대시보드 — 디자인 시스템
기존 컨셉(Swiss 계열 기록 우선 업무 도구, 색은 데이터·상태에만, 상단 내비)을 유지한다. Notion 디자인 분석 문서와 업무 보드 레퍼런스 2장을 참고한다.
진행: 결정 게이트에서 승인받고 계획서를 쓴 뒤, 계획서도 승인받고 구현한다. 항목은 아래 순서대로 하나씩 바꾸고, 항목마다 바꾸기 전후 스크린샷(1280·375·320px, 밝은·어두운)을 보여 승인받은 뒤 다음 항목으로 넘어간다.
- [x] 색·표면 토큰: 따뜻한 종이색 바탕, 웜 차콜 글자, 강조색은 파랑 하나, 옅은 경계선과 여러 겹의 옅은 그림자, 다크모드도 같은 방향
- [x] 모서리·버튼 체계: 입력칸 4px, 버튼·태스크 카드 8px, 패널 12px, 누를 때 살짝 작아지는 효과
- [x] 글꼴 설정: 폰트 파일은 저장소에 넣지 않고 PC에 설치된 글꼴을 이름으로 쓴다. 설정 `[web]`의 `heading_font`·`document_font`·`body_font`(기본은 셋 다 `Bookk Gothic`, 빈 값이면 기본 고딕 목록, 설치되지 않았으면 기존 OS 글꼴로 대체), 서버가 글꼴 스타일시트를 따로 내보냄(CSP), `/settings`에 현재 글꼴과 미리보기
- [x] 타이포그래피: 큰 숫자·제목에 부크크 고딕 Bold, 큰 글자일수록 자간을 좁힘. 보고서 미리보기와 요약 패널은 문서 글꼴(`document_font`)이다. 명조는 쓰지 않기로 했다(2026-10-14 사용자 결정, 제목·문서·본문·차트 모두 부크크 고딕으로 통일)
- [x] 꼬리표·상태 표기 통일: 주차·예상 초과·상태·카테고리를 같은 pill 부품으로, 프로젝트는 색 점
- [x] 사용자 지정 색: 설정 화면의 카테고리 색 표에서 색을 고르고 DB에 저장(스키마 3, `category_colors`, 백업 형식 3), 카테고리 꼬리표는 그 색을 옅게 깐 바탕(`/colors.css`), 대시보드 카테고리 차트가 같은 색을 따름, 프로젝트도 색 고르기와 `자동` 체크로 정함(2026-10-15 사용자 결정)
- [ ] 문서(SPEC 설정·화면, README, CLAUDE.md)와 Windows·macOS 화면 확인 — 문서·Windows 화면 확인 완료, macOS는 사용자 확인 대기

## Phase 9. 웹 대시보드 — 화면 고도화
Phase 8의 토큰·꼬리표·글꼴 위에 쌓는다. 진행 방식은 Phase 8과 같다(결정 게이트 → 계획서 승인 → 항목별 승인). 결정 게이트 D1~D9는 2026-10-15에 정했다.
- [ ] 중단 시각 기록: 태스크에 중단 시각을 저장해(스키마 4, 백업 형식 4) 중단 열이 이번 주에 중단한 것을 정확히 고르게 한다. 기존 중단 태스크는 마지막 수정 시각으로 채운다
- [ ] 칸반 고도화: 상태 색을 옅게 깐 열 머리와 건수, 둥근 흰 카드, 실적/예상 진행 막대(예상 초과는 빨강)
- [ ] 태스크 등록·수정 화면 분리: 보드에서 추가 폼과 카드 수정 폼을 빼고 등록·수정을 별도 화면에서 한다. 카드를 누르면 수정 화면으로 간다. 항목은 CLI 범위에 설명을 더하고, 수정 화면의 상태 선택이 끌 수 없는 사용자(키보드 등)의 상태 변경 경로다. 저장하면 보드로 돌아가 결과 줄을 보여 준다
- [ ] 끌어 놓기로 상태 변경: 카드의 버튼을 모두 없애고 SortableJS(로컬 포함)로 카드를 열 사이에 끌어 놓아 상태를 바꾼다. 보드에 중단 열(이번 주에 중단한 것, 열 제목은 "중단")을 더해 중단도 끌어 놓기로 한다(확인 창 없음, 버전 확인 409 포함, 열 안 순서는 바꾸지 않음). 열 배치는 폭에 따라 4열·2×2·1열
- [ ] 대시보드 위계: 이번 주 공수 칸에 오늘 공수 / 하루 목표 진행 막대. 진행 중 타이머의 색 뒤집기 강조 띠는 화면 확인 뒤 취소했다(다른 패널과 같은 색, 왼쪽 초록 선 유지)
- [ ] 문서(SPEC 화면·데이터 모델·의존성, README, CLAUDE.md)와 Windows·macOS 화면 확인

## Phase 10. 웹 대시보드 — 좌측 내비게이션
Phase 9 다음에 한다(2026-10-15 사용자 요청, Phase 9에서는 고려하지 않기로 함). 진행 방식은 Phase 8·9와 같다(결정 게이트 → 계획서 승인 → 항목별 승인). Phase 8의 "상단 내비 유지" 컨셉을 바꾼다.
- [ ] 좌측 내비게이션: 위쪽 탭 메뉴(대시보드·기록·태스크·보고서·설정)를 왼쪽 사이드바로 옮긴다. 좁은 화면(720px 미만)에서는 지금처럼 위쪽 메뉴로 바뀐다(2026-10-15 결정). 메뉴 모양(아이콘 여부), 접기, 사이드바 폭만큼 좁아지는 본문에 맞춘 보드 열 기준은 결정 게이트에서 정한다
- [ ] 문서와 Windows·macOS 화면 확인

## 남은 확인 (사용자)
- [ ] Phase 5 웹 대시보드 macOS 브라우저 확인 (PR #12)
- [ ] Phase 6 웹 대시보드 macOS 브라우저 확인 (PR #14)
- [ ] Phase 7 실제 API 키로 Claude·ChatGPT 문장 다듬기 확인 (PR #16)

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
