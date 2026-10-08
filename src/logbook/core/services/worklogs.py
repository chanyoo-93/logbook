"""업무 기록(WorkLog) 추가·조회·목록·수정·삭제와 하루 합계 유스케이스."""

from collections.abc import Collection
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from logbook.core.duration import MAX_MINUTES
from logbook.core.errors import InvalidInputError, NotFoundError
from logbook.core.models import Task, WorkLog
from logbook.core.services._resolve import (
    clean_note,
    pick_slug,
    resolve_category,
    target_project,
)
from logbook.core.services._shared import (
    check_category,
    check_date,
    check_positive_minutes,
    load_task,
)
from logbook.core.services.projects import COMMON_SLUG, get_project
from logbook.core.weeks import Week

# CLI는 세션이 닫힌 뒤 결과를 출력하므로 다대일 관계를 함께 로드한다.
_WITH_RELATIONS = (
    joinedload(WorkLog.project),
    joinedload(WorkLog.task).joinedload(Task.project),
)


def add_worklog(
    s: Session,
    *,
    minutes: int,
    note: str,
    project_slug: str | None = None,
    category: str | None = None,
    work_date: date | None = None,
    task_id: int | None = None,
    allowed_categories: Collection[str] | None = None,
    default_project: str = COMMON_SLUG,
    today: date | None = None,
) -> WorkLog:
    """업무 기록을 추가한다. 프로젝트·카테고리는 명시 인자 > 태스크 값 > 기본값 순으로 정한다."""
    checked_minutes = _checked_minutes(minutes)
    checked_note = clean_note(note)
    task = load_task(s, task_id) if task_id is not None else None
    slug = pick_slug(project_slug, task, default_project)
    project = target_project(s, slug, task, current=None)
    resolved_category = resolve_category(category, task, allowed_categories)
    if work_date is None:
        work_date = today if today is not None else date.today()
    checked_date = _checked_work_date(work_date)
    log = WorkLog(
        project=project,
        task=task,
        category=resolved_category,
        date=checked_date,
        minutes=checked_minutes,
        note=checked_note,
    )
    s.add(log)
    s.flush()
    return log


def get_worklog(s: Session, log_id: int) -> WorkLog:
    """id로 기록을 찾는다 (project, task 함께 로드). 없으면 NotFoundError."""
    query = select(WorkLog).where(WorkLog.id == log_id).options(*_WITH_RELATIONS)
    log = s.scalars(query).one_or_none()
    if log is None:
        raise NotFoundError(f"기록을 찾을 수 없습니다: #{log_id}. 'lb log'로 확인하세요.")
    return log


def list_worklogs(
    s: Session,
    *,
    week: Week | None = None,
    on: date | None = None,
    project_slug: str | None = None,
    category: str | None = None,
) -> list[WorkLog]:
    """모든 조건을 만족하는 기록을 날짜, id 순으로 반환한다. 보관된 프로젝트도 조회할 수 있다."""
    query = select(WorkLog).options(*_WITH_RELATIONS).order_by(WorkLog.date, WorkLog.id)
    if week is not None:
        query = query.where(WorkLog.date.between(week.start, week.end))
    if on is not None:
        query = query.where(WorkLog.date == on)
    if project_slug is not None:
        query = query.where(WorkLog.project_id == get_project(s, project_slug).id)
    if category is not None:
        query = query.where(WorkLog.category == category)
    return list(s.scalars(query))


def update_worklog(
    s: Session,
    log_id: int,
    *,
    minutes: int | None = None,
    note: str | None = None,
    category: str | None = None,
    project_slug: str | None = None,
    work_date: date | None = None,
    task_id: int | None = None,
    clear_task: bool = False,
    allowed_categories: Collection[str] | None = None,
) -> WorkLog:
    """None인 인자는 그대로 두고, 바뀌는 값만 add_worklog와 같은 규칙으로 검증해 고친다.

    태스크만 바꾸면 프로젝트도 태스크의 프로젝트로 옮긴다. clear_task=True면 태스크
    연결을 끊는다 (task_id와 함께 줄 수 없다).
    """
    if clear_task and task_id is not None:
        raise InvalidInputError(
            "태스크를 지정하면서 연결을 해제할 수는 없습니다. 둘 중 하나만 지정하세요."
        )
    log = get_worklog(s, log_id)
    new_minutes = log.minutes if minutes is None else _checked_minutes(minutes)
    new_note = log.note if note is None else clean_note(note)
    new_date = log.date if work_date is None else _checked_work_date(work_date)
    new_category = log.category
    if category is not None and category.strip() != log.category:
        new_category = check_category(category, allowed_categories)
    new_task = load_task(s, task_id) if task_id is not None else None
    task = None if clear_task else (new_task if new_task is not None else log.task)
    slug = pick_slug(project_slug, new_task, log.project.slug)
    project = target_project(s, slug, task, current=log.project, task_is_new=new_task is not None)
    # 모든 검증을 통과한 뒤에만 바꾼다.
    log.minutes, log.note, log.category = new_minutes, new_note, new_category
    log.project, log.task, log.date = project, task, new_date
    s.flush()
    return log


def delete_worklog(s: Session, log_id: int) -> None:
    """기록을 삭제한다. 없으면 NotFoundError."""
    s.delete(get_worklog(s, log_id))
    s.flush()


def day_total_minutes(s: Session, on: date) -> int:
    """그날 모든 프로젝트(보관 포함) 기록의 소요 시간 합계(분). 기록이 없으면 0."""
    total = s.scalar(select(func.sum(WorkLog.minutes)).where(WorkLog.date == on))
    return total or 0


def _checked_minutes(minutes: int) -> int:
    minutes = check_positive_minutes(minutes, "소요 시간은")
    if minutes > MAX_MINUTES:
        raise InvalidInputError(
            "소요 시간은 24시간 이하여야 합니다. 하루를 넘는 작업은 날짜별로 나눠 기록하세요."
        )
    return minutes


def _checked_work_date(work_date: date) -> date:
    return check_date(work_date, "작업 날짜는")
