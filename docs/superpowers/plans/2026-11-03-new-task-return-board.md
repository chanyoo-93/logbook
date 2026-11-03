# Phase 9 보완: 새 태스크를 저장한 뒤 돌아갈 보드 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 거른 보드에서 새 태스크를 다른 프로젝트로 저장해도, 돌아간 보드에 방금 만든 카드가 보인다.

SPEC 후속 항목 "새 태스크를 다른 프로젝트로 저장한 뒤 돌아갈 보드"(PR #36 최종 리뷰 L4, QA 참고)를 다룬다. 지금은 저장 뒤 숨은 칸 `project`(원래 필터)의 보드로 돌아간다. 그래서 payment로 거른 채 열고 billing으로 저장하거나, 보관 프로젝트 old로 거른 보드에서 `자동`(common)으로 저장하면 새 카드가 돌아간 보드에 없다(결과 줄에는 나온다).

**기준:** develop d95274d(PR #36 병합)에서 갈라진 브랜치 `feat/new-task-return-board`.

**진행:** 계획서 승인 → Task 순서대로, 테스트 먼저(RED). 서버 응답 주소만 바뀌고 화면 모양은 바뀌지 않으므로 Task 1은 전후 스크린샷 대신 돌아간 보드의 전후 화면(새 카드가 보이는지) 한 쌍을 비교 HTML로 보여 드리고 승인을 받는다. 끝에 문서·전체 검증·최종 리뷰 1회(`final-reviewer`, Sonnet high) → PR(develop) → "logbook QA" 세션 점검. 새 의존성 없음.

---

## 결정 (2026-11-03 결정 게이트, 사용자 확정)

| ID | 결정 |
|---|---|
| B1 | **필터가 있었으면 저장한 태스크의 프로젝트로 거른 보드로 돌아간다.** payment로 거른 채 열고 billing으로 저장하면 `/tasks?added=ID&project=billing`. 같은 프로젝트로 저장하면 지금과 같다. 필터가 없었으면(전체 보드) 지금처럼 `/tasks?added=ID`. |

## 설계

- `pages/tasks.py`의 `_add_task`가 저장한 태스크의 ID와 프로젝트 slug를 함께 돌려준다(`tuple[int, str]`, `task.project.slug`). 세션 안에서 읽는다.
- `add_task`는 `board_url(saved_slug if selected else "", added=task_id)`로 보낸다.
- 취소 링크, 오류 뒤 다시 그리기의 숨은 칸은 그대로 원래 필터다(저장이 일어나지 않았으므로).
- 수정 화면은 프로젝트를 바꿀 수 없으므로 바꾸지 않는다.

## Task 1: 저장한 프로젝트 보드로 돌아가기(B1)

**Files:** `src/logbook/web/pages/tasks.py`, 테스트 `tests/web/test_tasks_add.py`

- [ ] RED: 테스트를 쓰고 실패를 확인한다.
  - `project=payment`(필터)로 `task_project=billing`을 저장하면 `HX-Redirect`가 `/tasks?added=ID&project=billing`.
  - 보관 프로젝트 `old`로 거른 채 `task_project`를 비워(자동) 저장하면 `/tasks?added=ID&project=common`.
  - 필터 없이 다른 프로젝트로 저장하면 `/tasks?added=ID`(기존과 같음).
  - 같은 프로젝트로 저장하면 `&project=payment`(기존 테스트 `test_add_redirect_keeps_the_filter_project` 그대로 통과).
- [ ] 구현 → GREEN
- [ ] 돌아간 보드 전후 화면(1280px 밝음): 전 = payment 보드(새 카드 없음), 후 = billing 보드(새 카드와 결과 줄)
- [ ] 비교 HTML → 사용자 승인 → 커밋 `feat: 새 태스크를 다른 프로젝트로 저장하면 그 프로젝트 보드로 돌아간다`

## Task 2: 문서와 PR

- [ ] SPEC 새 태스크 화면 절의 성공 뒤 주소 규칙을 고치고, 후속 항목에서 이 줄을 뺀다
- [ ] ROADMAP Phase 9에 보완 줄을 더하고 체크한다
- [ ] 전체 검증: `ruff check`, `ruff format --check`, `mypy src/logbook/core`, 전체 `pytest`
- [ ] 최종 리뷰 1회(`final-reviewer`) → 지적 반영
- [ ] PR(develop) 생성, "logbook QA" 세션에 점검 요청
