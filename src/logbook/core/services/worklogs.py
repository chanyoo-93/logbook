"""업무 기록(WorkLog) 추가·조회·목록·수정·삭제와 하루 합계 유스케이스."""

from collections.abc import Collection
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from logbook.core.duration import MAX_MINUTES
from logbook.core.errors import InvalidInputError, NotFoundError
from logbook.core.models import Project, Task, WorkLog
from logbook.core.services._shared import MISSING_CATEGORY_MESSAGE, check_category, load_task
from logbook.core.services.projects import COMMON_SLUG, get_active_project, get_project
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
    clean_note = _clean_note(note)
    task = load_task(s, task_id) if task_id is not None else None
    slug = _pick_slug(project_slug, task, default_project)
    project = _target_project(s, slug, task, current=None)
    resolved_category = _resolve_category(category, task, allowed_categories)
    if work_date is None:
        work_date = today if today is not None else date.today()
    log = WorkLog(
        project=project,
        task=task,
        category=resolved_category,
        date=work_date,
        minutes=checked_minutes,
        note=clean_note,
    )
    s.add(log)
    s.flush()
    return log


def get_worklog(s: Session, log_id: int) -> WorkLog:
    """id로 기록을 찾는다 (project, task 함께 로드). 없으면 NotFoundError."""
    query = select(WorkLog).where(WorkLog.id == log_id).options(*_WITH_RELATIONS)
    log = s.scalars(query).one_or_none()
    if log is None:
        raise NotFoundError(f"기록 #{log_id}가 없습니다. 'lb log'로 확인하세요.")
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
    allowed_categories: Collection[str] | None = None,
) -> WorkLog:
    """None인 인자는 그대로 두고, 바뀌는 값만 add_worklog와 같은 규칙으로 검증해 고친다.

    태스크만 바꾸면 프로젝트도 태스크의 프로젝트로 옮긴다.
    """
    log = get_worklog(s, log_id)
    new_minutes = log.minutes if minutes is None else _checked_minutes(minutes)
    new_note = log.note if note is None else _clean_note(note)
    new_category = log.category
    if category is not None and category.strip() != log.category:
        new_category = check_category(category, allowed_categories)
    new_task = load_task(s, task_id) if task_id is not None else None
    task = new_task if new_task is not None else log.task
    slug = _pick_slug(project_slug, new_task, log.project.slug)
    project = _target_project(s, slug, task, current=log.project)
    # 모든 검증을 통과한 뒤에만 바꾼다.
    log.minutes, log.note, log.category = new_minutes, new_note, new_category
    log.project, log.task = project, task
    if work_date is not None:
        log.date = work_date
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
    # bool은 int의 하위 타입이지만 소요 시간으로 받지 않는다.
    if isinstance(minutes, bool) or not isinstance(minutes, int):
        raise InvalidInputError(f"소요 시간은 분 단위 정수로 입력하세요: {minutes!r}")
    if minutes < 1:
        raise InvalidInputError("소요 시간은 1분 이상이어야 합니다.")
    if minutes > MAX_MINUTES:
        raise InvalidInputError(
            "소요 시간은 24시간 이하여야 합니다. 하루를 넘는 작업은 날짜별로 나눠 기록하세요."
        )
    return minutes


def _clean_note(note: str) -> str:
    clean = note.strip()
    if not clean:
        raise InvalidInputError("메모를 입력하세요. 무엇을 했는지 한 줄로 적어 주세요.")
    return clean


def _resolve_category(
    category: str | None, task: Task | None, allowed: Collection[str] | None
) -> str:
    """명시한 카테고리 > 태스크의 카테고리. 둘 다 없으면 InvalidInputError."""
    resolved = task.category if category is None and task is not None else category
    if resolved is None:
        raise InvalidInputError(MISSING_CATEGORY_MESSAGE)
    return check_category(resolved, allowed)


def _pick_slug(explicit: str | None, task: Task | None, fallback: str) -> str:
    """명시한 slug > 태스크의 프로젝트 > fallback."""
    if explicit is not None:
        return explicit
    return task.project.slug if task is not None else fallback


def _target_project(
    s: Session, slug: str, task: Task | None, *, current: Project | None
) -> Project:
    """기록이 속할 프로젝트. 연결된 태스크와 프로젝트가 같아야 한다.

    프로젝트가 current와 같으면 보관 여부를 다시 확인하지 않는다 (보관된 프로젝트의
    옛 기록도 시간·메모는 고칠 수 있다).
    """
    if task is not None and task.project.slug != slug:
        owner = task.project.slug
        raise InvalidInputError(
            f"태스크 #{task.id}는 '{owner}' 프로젝트에 속합니다. "
            f"프로젝트를 빼거나 '{owner}'로 지정하세요."
        )
    if current is not None and current.slug == slug:
        return current
    return get_active_project(s, slug)
