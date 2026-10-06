"""logbook.core.models 단위 테스트."""

import datetime as dt

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, StatementError
from sqlalchemy.orm import Session

from logbook.core.models import ActiveTimer, Project, Task, TaskStatus, WorkLog, utcnow

KST = dt.timezone(dt.timedelta(hours=9))
UTC_OFFSET = dt.timedelta(0)


def add_project(session: Session, slug: str = "payment") -> Project:
    project = Project(slug=slug, name="결제 시스템")
    session.add(project)
    session.flush()
    return project


def add_task(session: Session, project: Project) -> Task:
    task = Task(project=project, title="환불 API 설계")
    session.add(task)
    session.flush()
    return task


def add_worklog(
    session: Session,
    project: Project,
    *,
    task: Task | None = None,
    minutes: int = 30,
    started_at: dt.datetime | None = None,
) -> WorkLog:
    log = WorkLog(
        project=project,
        task=task,
        category="dev",
        date=dt.date(2026, 10, 1),
        minutes=minutes,
        note="결제 재시도 로직 구현",
        started_at=started_at,
    )
    session.add(log)
    session.flush()
    return log


def assert_aware_utc(value: dt.datetime | None) -> None:
    assert value is not None
    assert value.tzinfo is not None
    assert value.utcoffset() == UTC_OFFSET


def test_utcnow_is_aware_utc() -> None:
    assert_aware_utc(utcnow())


def test_task_status_values() -> None:
    assert [status.value for status in TaskStatus] == ["todo", "doing", "done", "dropped"]
    assert TaskStatus("doing") is TaskStatus.DOING


def test_project_created_at_is_aware_after_reload(session: Session) -> None:
    project = add_project(session)
    session.commit()

    session.expire_all()
    loaded = session.get(Project, project.id)

    assert loaded is not None
    assert_aware_utc(loaded.created_at)


def test_defaults_are_applied(session: Session) -> None:
    project = add_project(session)
    task = add_task(session, project)
    log = add_worklog(session, project)
    session.expire_all()

    assert project.archived is False
    assert_aware_utc(project.created_at)
    assert task.status is TaskStatus.TODO
    assert_aware_utc(task.created_at)
    assert_aware_utc(task.updated_at)
    assert task.done_at is None
    assert_aware_utc(log.created_at)
    assert log.task_id is None
    assert log.started_at is None
    assert log.ended_at is None


def test_relationships_point_to_parents(session: Session) -> None:
    project = add_project(session)
    task = add_task(session, project)
    log = add_worklog(session, project, task=task)
    session.expire_all()

    assert task.project is project
    assert log.project is project
    assert log.task is task
    assert (log.project_id, log.task_id) == (project.id, task.id)


def test_worklog_minutes_must_be_at_least_one(session: Session) -> None:
    project = add_project(session)

    with pytest.raises(IntegrityError):
        add_worklog(session, project, minutes=0)


def test_duplicate_slug_is_rejected(session: Session) -> None:
    add_project(session, "payment")

    with pytest.raises(IntegrityError):
        add_project(session, "payment")


def test_deleting_task_sets_worklog_task_id_to_null(session: Session) -> None:
    project = add_project(session)
    task = add_task(session, project)
    log = add_worklog(session, project, task=task)

    session.delete(task)
    session.flush()
    session.refresh(log)

    assert log.task_id is None
    assert log.task is None


def test_deleting_project_with_worklogs_fails(session: Session) -> None:
    project = add_project(session)
    add_worklog(session, project)

    session.delete(project)

    with pytest.raises(IntegrityError):
        session.flush()


def test_utc_datetime_stores_aware_value_as_utc(session: Session) -> None:
    project = add_project(session)
    log = add_worklog(session, project, started_at=dt.datetime(2026, 10, 1, 9, 0, tzinfo=KST))

    raw = session.execute(text("SELECT started_at FROM worklogs")).scalar_one()
    session.refresh(log)

    assert raw.startswith("2026-10-01 00:00:00")
    assert log.started_at is not None
    assert_aware_utc(log.started_at)
    assert log.started_at.replace(tzinfo=None) == dt.datetime(2026, 10, 1, 0, 0)


def test_utc_datetime_rejects_naive_value(session: Session) -> None:
    project = add_project(session)

    with pytest.raises(StatementError) as excinfo:
        add_worklog(session, project, started_at=dt.datetime(2026, 10, 1, 9, 0))

    assert isinstance(excinfo.value.orig, ValueError)


def test_task_status_is_stored_as_value_string(session: Session) -> None:
    project = add_project(session)
    task = add_task(session, project)

    raw = session.execute(text("SELECT status FROM tasks")).scalar_one()
    session.expire_all()

    assert raw == "todo"
    assert task.status is TaskStatus.TODO


def test_task_status_rejects_unknown_value_in_db(session: Session) -> None:
    project = add_project(session)
    add_task(session, project)

    with pytest.raises(IntegrityError):
        session.execute(text("UPDATE tasks SET status = 'paused'"))


def test_project_archived_has_server_default(session: Session) -> None:
    session.execute(
        text("INSERT INTO projects (slug, name, created_at) VALUES ('raw', 'r', '2026-10-01')")
    )

    assert session.execute(text("SELECT archived FROM projects")).scalar_one() == 0


def test_task_updated_at_changes_on_update(session: Session) -> None:
    project = add_project(session)
    old = dt.datetime(2026, 1, 1, tzinfo=dt.UTC)
    task = Task(project=project, title="환불 API 설계", created_at=old, updated_at=old)
    session.add(task)
    session.flush()

    task.title = "환불 API 상세 설계"
    session.flush()
    session.refresh(task)

    assert task.updated_at > old
    assert task.created_at == old


def new_timer(project: Project, **kwargs: object) -> ActiveTimer:
    return ActiveTimer(
        project=project, category="design", note="환불 API 설계", started_at=utcnow(), **kwargs
    )


def test_active_timer_id_defaults_to_one(session: Session) -> None:
    project = add_project(session)
    timer = new_timer(project)
    session.add(timer)
    session.flush()

    assert timer.id == 1
    assert timer.task_id is None


def test_active_timer_rejects_second_row_id(session: Session) -> None:
    project = add_project(session)
    session.add(new_timer(project, id=2))

    with pytest.raises(IntegrityError):
        session.flush()


def test_deleting_task_clears_active_timer_task(session: Session) -> None:
    project = add_project(session)
    task = add_task(session, project)
    timer = new_timer(project, task=task)
    session.add(timer)
    session.flush()

    session.delete(task)
    session.flush()
    session.refresh(timer)

    assert timer.task_id is None
