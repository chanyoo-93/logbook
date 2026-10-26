# Phase 9 보완: 최근 기록 날짜 순 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 대시보드 최근 기록을 업무 날짜 순으로 보여 준다. 2026-10-26 디자인 평가의 P2이고, 방향(날짜 순)은 평가 직후 정했다.
- 지금은 `core/services/worklogs.py`의 `recent_worklogs`가 ID 내림차순(입력 순)이다. 지난 날짜를 오늘 입력하면 맨 위에 와서 날짜가 뒤섞인다.

**범위 밖(SPEC 후속 항목에 그대로 둔다):** 오류 페이지 h1, 밝은 테마 주 이동 링크 대비, 320px 타이머 안내 글자. 주 이동 링크 대비는 나중에 할 때 밝은 테마 `--accent`를 조금 진하게 하는 방향으로 정했다(2026-10-26).

**기준:** develop f3bfff7(PR #27 병합)에서 갈라진 브랜치 `feat/recent-by-date`

**진행:**
1. 계획서 승인 → Task 1 구현(테스트 먼저 RED) → 전후 스크린샷 → 사용자 승인 → Task 2.
2. 변경이 작아 메인 세션이 직접 구현한다. 서브에이전트는 끝의 최종 리뷰 1회(`final-reviewer`, Sonnet high)만 쓴다.

**Tech Stack:** 기존과 같다. 새 의존성, 스키마 변경, JS 변경 없음(`work_logs.date`에는 이미 인덱스가 있다).

---

## 결정 (2026-10-26 결정 게이트, 사용자 확정)

| ID | 결정 |
|---|---|
| E1 | 최근 기록 10건은 **업무 날짜가 최신인 10건**이다. 정렬은 업무 날짜 내림차순, 같은 날은 나중에 입력한 것(ID 큰 것)이 위다. 오늘 지난 날짜로 넣은 기록은 목록에 안 보일 수 있다(기록 화면에서 본다). |
| E2 | 브랜치는 PR #27 병합 뒤 develop에서 갈라진다. |

---

## Task 1: 최근 기록 정렬 (E1)

**파일:** `src/logbook/core/services/worklogs.py`(`recent_worklogs`), `tests/core/test_services_worklogs_recent.py`, 필요하면 `tests/web/test_dashboard.py`

- `recent_worklogs`의 정렬을 `WorkLog.date.desc(), WorkLog.id.desc()`로 바꾸고 docstring을 고친다(함수 이름과 시그니처는 그대로, 호출하는 곳은 `web/pages/dashboard.py`와 `web/pages/panels.py` 두 곳뿐이고 고칠 것 없음).
- 영향: 빠른 기록·타이머 정지 뒤 최근 기록 갱신(OOB)도 같은 함수라 함께 바뀐다. 오늘 기록은 늘 맨 위라 저장 직후 보이는 동작은 같다.

**테스트 먼저(RED):**
- 기존 `test_recent_worklogs_returns_latest_ids_first_with_relations`를 날짜 순 기준으로 고친다: 날짜가 섞인 기록 12건에서 (날짜 내림차순, 같은 날 ID 내림차순) 10건인지, 관계(project·task) 로드가 그대로인지.
- 새 테스트: 나중에 입력한 지난 날짜 기록이 더 최근 날짜 기록보다 아래에 오는지. 최신 날짜 10건에 들지 못하면 빠지는지.
- 웹: 대시보드 최근 기록 표의 행 순서가 날짜 순인지 1건(지난 날짜를 나중에 입력한 경우).

**확인:** 지난 날짜 기록을 섞은 임시 DB로 대시보드 전후 스크린샷(1280·375·320px × 밝은·어두운).

## Task 2: 문서와 마무리

- `docs/SPEC.md`: 대시보드 페이지 목록의 "최근 기록 10건"에 정렬 규칙(E1)을 적고, 후속 항목 줄에서 "최근 기록을 날짜 순으로 정렬"을 뺀다.
- `README.md`: 대시보드 행의 "최근 기록 10건"에 "업무 날짜 순"을 붙인다.
- `docs/ROADMAP.md`: 항목 체크.
- 전체 검증: `uv run pytest`(timeout 600000으로 1회), `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy src/logbook/core`.
- `final-reviewer` 1회 → 지적 반영 → PR(develop 대상) → 사용자 Windows·macOS 확인.
- 사용자에게 알릴 것: 저장소 밖 `SCREENS.md`의 대시보드 최근 기록 설명(정렬)이 바뀐다.

## 위험과 대응

| 위험 | 대응 |
|---|---|
| 오늘 지난 날짜로 넣은 기록이 최근 기록에 안 보여 저장됐는지 헷갈림 | 빠른 기록은 날짜가 항상 오늘이라 대시보드에서 넣은 것은 늘 보인다. CLI `lb add -d`로 지난 날짜를 넣은 경우만 해당하고 결과 줄로 확인된다. E1에서 받아들였다. |
| 미래 날짜 기록이 늘 맨 위를 차지함 | `lb add`는 미래 날짜를 받을 수 있다. 드문 경우라 그대로 두고 SPEC에 적는다. |
