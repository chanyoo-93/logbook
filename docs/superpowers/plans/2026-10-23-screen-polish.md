# Phase 9 보완: 화면 다듬기 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 2026-10-23 사용자 확인에서 나온 화면 수정 다섯 가지를 반영한다.
1. 대시보드: 진행 중 타이머의 왼쪽 초록 선("손톱 모양")을 없앤다. "이번 주 요약"을 "주간 요약"으로 바꾼다.
2. 기록: 표 컬럼명을 화면에서 숨긴다. 행의 "수정"·"삭제" 버튼을 ⋮ 버튼 하나와 컨텍스트 메뉴로 바꾼다.
3. 태스크: 보드 열 머리(할 일·진행 중·완료·중단) 왼쪽의 점을 없앤다.
4. 보고서: "복사" 버튼을 없애고 보고서 Markdown 영역 오른쪽 위에 복사 아이콘을 둔다. "내려받기" 버튼을 내려받기 아이콘으로 바꾼다.
5. 설정: 프로젝트 행의 동작 버튼을 ⋮ 컨텍스트 메뉴로 바꾼다(common은 메뉴의 "보관"이 비활성). 프로젝트 표와 카테고리 색 표의 컬럼명을 화면에서 숨긴다.

**기준:** develop 4212b4d(PR #23 병합)에서 갈라진 브랜치 `feat/screen-polish`

**진행:**
1. 이 계획서를 사용자가 승인하면 Task 순서대로 구현한다. Task마다 구현 1명 + 검토 1명(Sonnet medium)이다.
2. 화면마다 메인 세션이 전후 스크린샷(1280·375·320px × 밝은·어두운)과 비교 페이지를 만들어 사용자 승인을 받은 뒤 다음 화면으로 넘어간다.
3. 끝에 문서 → 전체 검증 → PR(develop 대상) → 사용자 Windows·macOS 확인

**Tech Stack:** 기존과 같다. 새 의존성은 없다(아이콘은 인라인 SVG, 메뉴는 기존 `app.js`).

**승인:** 사용자가 이 계획서를 승인했다(2026-10-23, e163bc4).

---

## 결정 (2026-10-23 결정 게이트, 사용자 확정)

| # | 결정할 것 | 결정 |
|---|---|---|
| H1 | 표 컬럼명 | 화면에서만 숨긴다. 표 머리(`thead`)는 남겨 화면 낭독기가 읽게 한다(`visually-hidden`) |
| H2 | 메뉴 버튼 모양 | 세로 점 세 개 ⋮(사용자가 보낸 스크린샷과 같은 모양) |
| H3 | 진행 | Phase 9 보완으로 Phase 10 전에 한다. 화면마다 전후 비교로 승인받는다 |

**메인 세션이 정한 세부(승인 대상):**
- "손톱 모양 카드"는 진행 중 타이머 패널의 왼쪽 4px 초록 선(`.timer--running`의 `border-left`)으로 이해했다. 없애면 패널은 다른 패널과 같아지고, 진행 중 표시는 "진행 중" 꼬리표와 점이 맡는다.
- 아이콘은 `templates/partials/icons.html`의 매크로(인라인 SVG, `aria-hidden`, `currentColor`)로 둔다. 아이콘 버튼은 글자 대신 `aria-label`과 `title`(마우스를 올리면 보이는 설명)을 가진다: 복사 "Markdown 복사", 내려받기 "Markdown 내려받기", 메뉴 "동작".
- 컨텍스트 메뉴(기록·설정이 같은 부품):
  - ⋮ 버튼(`aria-haspopup="menu"`, `aria-expanded`)과 그 아래 펼쳐지는 메뉴(`role="menu"`, 항목 `role="menuitem"`). 항목은 지금 버튼의 htmx 속성을 그대로 가진다.
  - 기록: "수정", "삭제"(삭제는 지금처럼 브라우저 확인 창, 위험색 글자).
  - 프로젝트: "수정", "보관" 또는 "보관 해제". common의 "보관"은 비활성(`disabled`, 설명 "common 프로젝트는 보관할 수 없습니다").
  - 키보드: ⋮에서 Enter·Space로 열고 첫 항목에 포커스, 위·아래 화살표로 이동, Esc는 닫고 ⋮로 포커스를 돌린다. 바깥을 누르거나 Tab으로 나가면 닫힌다. 한 번에 메뉴 하나만 열린다.
  - 인라인 코드 없이 `app.js`의 이벤트 위임으로 동작한다(htmx로 다시 그려진 행에도 동작). 위치는 CSS로 ⋮ 아래 오른쪽 정렬, 좁은 화면에서 화면 밖으로 나가지 않게 한다.
- 보고서 복사 아이콘은 Markdown 영역(`#report-markdown`을 감싼 상자)의 오른쪽 위에 겹쳐 둔다. 복사 결과 줄(`#copy-status`)은 그대로다. 내려받기 아이콘은 지금 "내려받기" 자리(머리 오른쪽)에 둔다.

---

## Task 1: 공용 부품(아이콘·컨텍스트 메뉴)

**Files:** 새 `templates/partials/icons.html`, 새 `templates/partials/menu.html`(⋮ 버튼과 메뉴 틀 매크로), `static/js/app.js`(메뉴 동작), `static/css/components.css`(메뉴·아이콘 버튼), 테스트

| 대상 | 케이스 | 기대 |
|---|---|---|
| 아이콘 매크로 | 복사·내려받기·⋮ | 인라인 SVG, `aria-hidden="true"`, `style=` 없음 |
| 메뉴 매크로 | 렌더 | ⋮ 버튼 `aria-haspopup="menu"`·`aria-expanded="false"`·`aria-label`, 메뉴 `role="menu"`·`hidden` |
| `app.js` | 문자열 | 메뉴 열기·닫기, 화살표, Esc, 바깥 클릭 처리 |
| CSS | 규칙 | 메뉴·아이콘 버튼 규칙, 색은 토큰만 |

- 이 Task만으로는 화면이 바뀌지 않는다(쓰는 곳은 Task 3·6).
- [ ] RED → GREEN → 커밋 `feat: 아이콘 매크로와 컨텍스트 메뉴 부품`

## Task 2: 대시보드

**Files:** `static/css/components.css`(`.timer--running`), `templates/partials/summary.html`, 테스트(`test_css_layout.py`, `test_dashboard.py`)

- `.timer--running`의 `border-left`를 없앤다(다른 패널과 같은 모양).
- 요약 패널 제목 "이번 주 요약" → "주간 요약".
- [ ] RED → GREEN → 커밋 `feat: 대시보드 타이머 초록 선 제거와 주간 요약 제목`
- [ ] 메인 세션: 전후 비교 → 사용자 승인

## Task 3: 기록

**Files:** `templates/partials/log_table.html`(thead `visually-hidden`), `log_row.html`(⋮ 메뉴), `static/css/logs.css`, 테스트(`test_logs_page.py`, `test_logs_edit.py`)

- 표 머리는 남기되 화면에서 숨긴다.
- 행의 "수정"·"삭제"를 ⋮ 메뉴로. 동작(편집 행, 삭제 확인 창, 버전 409, 결과 줄, 포커스 규칙)은 그대로다.
- [ ] RED → GREEN → 커밋 `feat: 기록 표 컬럼명 숨김과 행 동작을 컨텍스트 메뉴로`
- [ ] 메인 세션: 전후 비교(메뉴를 연 상태 포함) → 사용자 승인

## Task 4: 태스크

**Files:** `templates/partials/task_board.html`, `static/css/tasks.css`(`.board__dot` 삭제), 테스트

- 열 머리의 점을 없앤다. 열 머리 색 바탕·제목·건수는 그대로다.
- [ ] RED → GREEN → 커밋 `feat: 태스크 보드 열 머리의 점 제거`
- [ ] 메인 세션: 전후 비교 → 사용자 승인

## Task 5: 보고서

**Files:** `templates/partials/report_body.html`, `static/css/report.css`, `static/js/report.js`(복사 대상 그대로), 테스트(`test_report_page.py` 등)

- "복사" 버튼을 없애고 Markdown 영역 오른쪽 위에 복사 아이콘 버튼(`data-copy-target="report-markdown"`, `aria-label="Markdown 복사"`).
- "내려받기" 링크를 내려받기 아이콘 링크로(`download`, `aria-label="Markdown 내려받기"`). "문장 다듬기" 버튼은 그대로다.
- [ ] RED → GREEN → 커밋 `feat: 보고서 복사·내려받기를 아이콘으로`
- [ ] 메인 세션: 전후 비교 → 사용자 승인

## Task 6: 설정

**Files:** `templates/partials/project_section.html`·`project_row.html`(⋮ 메뉴, thead 숨김), `category_section.html`(thead 숨김), `static/css/settings.css`, 테스트(`test_settings*.py`)

- 프로젝트 행 동작을 ⋮ 메뉴로("수정", "보관"/"보관 해제", common은 "보관" 비활성). 버전 409·결과 줄·포커스는 그대로다.
- 프로젝트 표와 카테고리 색 표의 머리를 화면에서 숨긴다. 카테고리 행의 저장 등 기존 조작은 그대로다.
- [ ] RED → GREEN → 커밋 `feat: 설정 표 컬럼명 숨김과 프로젝트 동작을 컨텍스트 메뉴로`
- [ ] 메인 세션: 전후 비교(메뉴를 연 상태, common 메뉴 포함) → 사용자 승인

## Task 7: 문서, 검증, PR

- [ ] SPEC 6장(타이머 모양, 주간 요약, 표 머리 숨김, 컨텍스트 메뉴와 키보드, 보고서 아이콘, 열 머리 점), README(화면 설명), ROADMAP 체크
- [ ] 전체 검증: ruff, format, mypy(core strict, 전체), pytest. 화면: 메뉴 키보드 조작과 CSP 위반 0건(Edge 헤드리스)
- [ ] PR(develop 대상), CI, 확인 절차 댓글
- [ ] 사용자 Windows·macOS 확인

---

## 범위 밖

- 좌측 내비게이션(Phase 10)
- 대시보드 최근 기록 표(컬럼명 요청 대상이 아니다. 필요하면 따로 정한다)
