# Phase 9 보완: 새 태스크 화면의 프로젝트 기본값 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 보드를 프로젝트로 거른 채 `새 태스크`를 열면 그 프로젝트가 프로젝트 칸에 골라져 있다.

SPEC "후속 항목"의 "새 태스크 화면의 프로젝트 기본값"(PR #32 QA 참고)을 다룬다. 지금은 `?project=` 값이 저장 뒤 돌아갈 보드 주소(숨은 칸 `project`, 취소 링크)에만 쓰이고, 프로젝트 칸(`task_project`)은 늘 `자동 (default_project)`로 나온다.

**기준:** develop e41bb98(PR #35 병합)에서 갈라진 브랜치 `feat/new-task-default-project`.

**진행:**
- 계획서 승인 → Task 순서대로. 테스트를 먼저 써서 실패를 확인(RED)한다.
- Task 1은 전후 스크린샷 비교 HTML로 사용자 승인을 받은 뒤 커밋한다.
- 끝에 문서·전체 검증·최종 리뷰 1회(`final-reviewer`, Sonnet high) → PR(develop) → "logbook QA" 세션 점검.
- 구현은 메인 세션이 직접 한다. 새 의존성은 없다.

---

## 결정 (2026-11-03 결정 게이트, 사용자 확정)

| ID | 결정 |
|---|---|
| N1 | **거른 프로젝트를 프로젝트 칸에 골라 둔다.** `GET /tasks/new?project=<slug>`에서 slug가 등록 칸 선택지(보관하지 않은 프로젝트)에 있으면 그 프로젝트를 고른다. |
| N2 | **고를 수 없으면 자동으로 둔다.** 보관 프로젝트이거나 없는 slug면 지금처럼 `자동 (default_project)`이고 따로 안내하지 않는다. 저장 뒤에는 원래 거른 보드로 돌아간다(지금과 같다). |

## 설계

- `pages/task_views.py`에 순수 함수 `new_task_values(projects, filter_project) -> TaskFormValues`를 둔다. 선택지 값 가운데 `filter_project`가 있으면 `TaskFormValues(task_project=filter_project)`, 없으면 `TaskFormValues()`.
- `pages/tasks.py`의 `task_new_page`가 `project_choices(s, archived=False)` 대신 `task_form_view`가 만든 선택지를 쓰도록, 폼 뷰를 만든 뒤 값만 바꾼다(`dataclasses.replace(form, values=new_task_values(form.projects, selected))`). 선택지를 두 번 조회하지 않는다.
- 저장(`POST /tasks`)과 오류 뒤 다시 그리기는 바꾸지 않는다. 오류 뒤에는 사용자가 고른 값(`task_project`)이 그대로 남는다(기존 동작). 사용자가 `자동`으로 바꿔 저장하면 `default_project`로 저장된다(기존 동작).
- 보드 머리·빈 열·계획 패널의 `새 태스크` 링크는 이미 `?project=`를 잇므로 템플릿은 바꾸지 않는다.

## Task 1: 프로젝트 기본값(N1·N2)

**Files:** `src/logbook/web/pages/task_views.py`, `src/logbook/web/pages/tasks.py`, 테스트 `tests/web/test_tasks_add.py`

- [ ] RED: 테스트를 쓰고 실패를 확인한다.
  - `?project=payment`(보관 아님)면 `task_project`에서 `payment`가 골라져 있고 `자동` 항목은 골라져 있지 않다.
  - 필터가 없으면 `자동`이 골라져 있다(기존과 같음, 회귀 확인).
  - 보관 프로젝트 slug, 없는 slug면 `자동`이 골라져 있고 숨은 칸 `project`는 그 slug를 그대로 싣는다.
  - 거른 채 연 화면에서 그대로 저장하면 그 프로젝트로 저장되고 거른 보드로 돌아간다.
- [ ] 구현 → GREEN
- [ ] 전후 스크린샷: `/tasks/new?project=payment` 1280px·320px, 밝은·어두운 테마
- [ ] 전후 비교 HTML → 사용자 승인 → 커밋 `feat: 보드에서 거른 프로젝트를 새 태스크의 프로젝트 칸에 골라 둔다`

## Task 2: 문서와 PR

- [ ] SPEC 새 태스크 화면 절에 기본값 규칙(N1·N2)을 적고, 후속 항목에서 이 줄을 뺀다
- [ ] ROADMAP Phase 9에 보완 줄을 더하고 체크한다
- [ ] 전체 검증: `ruff check`, `ruff format --check`, `mypy src/logbook/core`, 전체 `pytest`
- [ ] 최종 리뷰 1회(`final-reviewer`) → 지적 반영
- [ ] PR(develop) 생성, "logbook QA" 세션에 점검 요청
