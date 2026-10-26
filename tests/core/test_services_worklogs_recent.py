"""logbook.core.services.worklogs.recent_worklogs 단위 테스트."""

from datetime import date
from typing import Any

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from logbook.core import services
from logbook.core.db import session_scope
from logbook.core.models import Task, WorkLog

THU = date(2026, 10, 1)


@pytest.fixture
def seeded(session: Session) -> Session:
    """common, payment, search 프로젝트가 있는 세션."""
    services.ensure_common_project(session)
    services.create_project(session, "payment", "결제 서버")
    services.create_project(session, "search", "검색")
    return session


def _add(s: Session, **overrides: Any) -> WorkLog:
    params: dict[str, Any] = {"minutes": 60, "note": "작업", "category": "dev", "today": THU}
    return services.add_worklog(s, **{**params, **overrides})


def _make_task(s: Session) -> Task:
    task = Task(project=services.get_project(s, "payment"), title="결제 재시도", category="dev")
    s.add(task)
    s.flush()
    return task


def test_recent_worklogs_orders_by_work_date_then_newest_entry_with_relations(
    seeded: Session, engine: Engine
) -> None:
    task = _make_task(seeded)
    for index in range(12):
        _add(
            seeded,
            work_date=date(2026, 9, 20 + index % 5),
            task_id=task.id if index == 9 else None,
            project_slug="payment",
        )
    seeded.commit()

    with session_scope(engine) as s:
        logs = services.recent_worklogs(s, limit=10)

    keys = [(log.date, log.id) for log in logs]
    assert keys == sorted(keys, reverse=True)
    assert len(keys) == 10
    # 9월 24일(index 4, 9)이 가장 최신 날짜이고, 같은 날은 나중에 넣은 index 9(태스크 연결)가 위다.
    assert logs[0].date == date(2026, 9, 24)
    assert logs[0].project.slug == "payment"
    assert logs[0].task is not None


def test_recent_worklogs_puts_backdated_entry_below_newer_dates(seeded: Session) -> None:
    today = _add(seeded, work_date=THU)
    backdated = _add(seeded, work_date=date(2026, 9, 28))

    ids = [log.id for log in services.recent_worklogs(seeded, limit=10)]

    assert ids == [today.id, backdated.id]


def test_recent_worklogs_drops_backdated_entry_outside_latest_dates(seeded: Session) -> None:
    newer = [_add(seeded, work_date=THU) for _ in range(10)]
    backdated = _add(seeded, work_date=date(2026, 9, 28))

    ids = [log.id for log in services.recent_worklogs(seeded, limit=10)]

    assert backdated.id not in ids
    assert ids == [log.id for log in reversed(newer)]


def test_recent_worklogs_returns_all_when_fewer_than_limit(seeded: Session) -> None:
    _add(seeded)

    assert len(services.recent_worklogs(seeded, limit=10)) == 1


@pytest.mark.parametrize("limit", [0, -1])
def test_recent_worklogs_rejects_limit_below_one(seeded: Session, limit: int) -> None:
    with pytest.raises(ValueError, match="limit"):
        services.recent_worklogs(seeded, limit=limit)
