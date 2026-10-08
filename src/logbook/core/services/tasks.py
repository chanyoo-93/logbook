"""태스크(할 일) 생성·조회·목록·수정·상태 변경과 실제 공수 집계 유스케이스."""

from collections.abc import Callable, Collection
from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from logbook.core.errors import InvalidInputError
from logbook.core.models import Project, Task, TaskStatus, WorkLog, utcnow
from logbook.core.services._shared import (
    check_category,
    check_date,
    check_positive_minutes,
    load_task,
    strip_or_none,
)
from logbook.core.services.projects import get_active_project, get_project
from logbook.core.taskstatus import OPEN_STATUSES
from logbook.core.weeks import Week


def create_task(
    s: Session,
    *,
    title: str,
    project_slug: str,
    category: str | None = None,
    estimate_minutes: int | None = None,
    planned_week: Week | None = None,
    due_date: date | None = None,
    external_ref: str | None = None,
    description: str | None = None,
    allowed_categories: Collection[str] | None = None,
) -> Task:
    """새 태스크를 TODO 상태로 만든다. 카테고리는 지정했을 때만 allowed_categories로 검사한다."""
    task = Task(
        project=get_active_project(s, project_slug),
        title=_clean_title(title),
        category=_checked_category(category, allowed_categories),
        estimate_minutes=_checked_estimate(estimate_minutes),
        planned_week=_week_label(planned_week),
        due_date=_checked_due_date(due_date),
        external_ref=strip_or_none(external_ref),
        description=strip_or_none(description),
        status=TaskStatus.TODO,
    )
    s.add(task)
    s.flush()
    return task


def get_task(s: Session, task_id: int) -> Task:
    """id로 태스크를 찾는다 (project 함께 로드). 없으면 NotFoundError."""
    return load_task(s, task_id)


def list_tasks(
    s: Session,
    *,
    project_slug: str | None = None,
    statuses: Collection[TaskStatus] | None = None,
    week: Week | None = None,
    include_archived: bool = False,
) -> list[Task]:
    """모든 조건을 만족하는 태스크를 계획 주차(없으면 마지막), id 순으로 반환한다.

    기본값은 보관된 프로젝트의 태스크를 뺀다. project_slug를 주면 보관 여부와 상관없이
    그 프로젝트의 태스크를 돌려준다.
    """
    query = (
        select(Task)
        .options(joinedload(Task.project))
        # NULLS LAST 문법 대신 IS NULL 정렬을 써서 SQLite 버전에 기대지 않는다.
        .order_by(Task.planned_week.is_(None), Task.planned_week, Task.id)
    )
    if project_slug is not None:
        query = query.where(Task.project_id == get_project(s, project_slug).id)
    elif not include_archived:
        query = query.where(Task.project.has(Project.archived.is_(False)))
    if statuses is not None:
        if isinstance(statuses, str):
            # 'todo' 같은 문자열은 글자 단위 컬렉션으로 오인되므로 막는다.
            raise TypeError("statuses must be a collection of TaskStatus, not str")
        if not statuses:
            return []
        query = query.where(Task.status.in_(list(statuses)))
    if week is not None:
        query = query.where(Task.planned_week == week.label)
    return list(s.scalars(query))


def update_task(
    s: Session,
    task_id: int,
    *,
    allowed_categories: Collection[str] | None = None,
    **fields: Any,
) -> Task:
    """넘긴 필드만 create_task와 같은 규칙으로 검증해 고친다. None은 선택 필드를 비운다.

    필드: title, category, estimate_minutes, planned_week, due_date, external_ref,
    description. 그 밖의 이름은 TypeError.
    """
    validators = _field_validators(allowed_categories)
    unknown = sorted(set(fields) - set(validators))
    if unknown:
        raise TypeError(f"update_task() got unexpected field(s): {', '.join(unknown)}")
    task = load_task(s, task_id)
    # 모든 값을 검증한 뒤에만 바꾼다.
    changes = {name: validators[name](value) for name, value in fields.items()}
    for name, value in changes.items():
        setattr(task, name, value)
    # 바뀐 값이 없어도 수정 시각을 남긴다 (onupdate는 실제 변경이 있을 때만 동작).
    task.updated_at = utcnow()
    s.flush()
    return task


def set_task_status(s: Session, task_id: int, status: TaskStatus) -> Task:
    """상태를 바꾼다. DONE이 되면 완료 시각을 기록하고 (이미 DONE이면 유지), 그 밖에는 지운다."""
    task = load_task(s, task_id)
    if status != TaskStatus.DONE:
        task.done_at = None
    elif task.status != TaskStatus.DONE or task.done_at is None:
        task.done_at = utcnow()
    task.status = status
    # 상태가 같아도 바꾼 시각을 남긴다 (onupdate는 실제 변경이 있을 때만 동작).
    task.updated_at = utcnow()
    s.flush()
    return task


def task_actual_minutes(s: Session, task_id: int) -> int:
    """태스크에 연결된 기록의 소요 시간 합계(분). 기록이 없으면 0, 태스크가 없으면 NotFoundError."""
    load_task(s, task_id)
    total = s.scalar(select(func.sum(WorkLog.minutes)).where(WorkLog.task_id == task_id))
    return total or 0


def actual_minutes_by_task(s: Session, task_ids: Collection[int]) -> dict[int, int]:
    """태스크별 연결 기록 합계(분)를 GROUP BY 쿼리 한 번으로 구한다.

    기록이 없는 태스크 id는 결과에 없다. 빈 입력은 쿼리 없이 빈 dict.
    """
    if not task_ids:
        return {}
    rows = s.execute(
        select(WorkLog.task_id, func.sum(WorkLog.minutes))
        .where(WorkLog.task_id.in_(list(task_ids)))
        .group_by(WorkLog.task_id)
    )
    return {task_id: int(total) for task_id, total in rows if task_id is not None}


def carry_candidates(s: Session, week: Week) -> list[Task]:
    """week에 계획된 할 일·진행 중 태스크(보관 프로젝트 제외)를 id 순으로 반환한다."""
    query = (
        select(Task)
        .options(joinedload(Task.project))
        .where(
            Task.planned_week == week.label,
            Task.status.in_(OPEN_STATUSES),
            Task.project.has(Project.archived.is_(False)),
        )
        .order_by(Task.id)
    )
    return list(s.scalars(query))


def carry_tasks(s: Session, week: Week, task_ids: Collection[int]) -> list[Task]:
    """carry_candidates(week) 중 task_ids에 든 태스크의 계획 주차를 다음 주로 옮긴다.

    옮긴 태스크를 id 순으로 반환한다. 그 사이 상태·주차가 바뀌었거나 보관된 태스크,
    없는 id는 건너뛴다.
    """
    wanted = set(task_ids)
    moved = [task for task in carry_candidates(s, week) if task.id in wanted]
    next_label = week.next().label
    now = utcnow()
    for task in moved:
        task.planned_week = next_label
        task.updated_at = now
    s.flush()
    return moved


def _field_validators(
    allowed_categories: Collection[str] | None,
) -> dict[str, Callable[[Any], object]]:
    """update_task가 받는 필드 이름과, create_task와 같은 규칙의 검증 함수."""
    return {
        "title": _clean_title,
        "category": lambda value: _checked_category(value, allowed_categories),
        "estimate_minutes": _checked_estimate,
        "planned_week": _week_label,
        "due_date": _checked_due_date,
        "external_ref": strip_or_none,
        "description": strip_or_none,
    }


def _clean_title(title: str | None) -> str:
    clean = title.strip() if title is not None else ""
    if not clean:
        raise InvalidInputError("태스크 제목을 입력하세요. 무엇을 할지 한 줄로 적어 주세요.")
    return clean


def _checked_category(category: str | None, allowed: Collection[str] | None) -> str | None:
    return None if category is None else check_category(category, allowed)


def _checked_estimate(estimate_minutes: int | None) -> int | None:
    # 태스크는 여러 날에 걸칠 수 있으므로 상한은 두지 않는다.
    if estimate_minutes is None:
        return None
    return check_positive_minutes(estimate_minutes, "예상 공수는")


def _week_label(week: Week | None) -> str | None:
    if week is None:
        return None
    if not isinstance(week, Week):
        raise InvalidInputError(f"계획 주차는 Week 값이어야 합니다 (예: 2026-W41): {week!r}")
    return week.label


def _checked_due_date(due_date: date | None) -> date | None:
    return None if due_date is None else check_date(due_date, "마감일은")
