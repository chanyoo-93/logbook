"""services.github_import와 services.existing_external_refs 테스트."""

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from logbook.core import services
from logbook.core.errors import InvalidInputError, NotFoundError
from logbook.core.github import Issue
from logbook.core.models import Task
from logbook.core.services.github_import import IssueImport, plan_issue_import
from logbook.core.taskstatus import TaskStatus
from logbook.core.weeks import Week

CATEGORIES = ("dev", "docs")
W42 = Week(2026, 42)


def issue(number: int, title: str = "") -> Issue:
    return Issue(number, title or f"이슈 {number}", f"https://github.com/a/b/issues/{number}")


@pytest.fixture
def seeded(session: Session) -> Session:
    services.ensure_common_project(session)
    services.create_project(session, "payment", "결제 서버")
    return session


def task_count(s: Session) -> int:
    return s.scalar(select(func.count()).select_from(Task)) or 0


def do_import(s: Session, issues: list[Issue], **overrides: object) -> services.IssueImportResult:
    params: dict[str, object] = {
        "project_slug": "payment",
        "category": "dev",
        "planned_week": W42,
        "allowed_categories": CATEGORIES,
    }
    return services.import_issues(s, "a/b", issues, **{**params, **overrides})  # type: ignore[arg-type]


def test_existing_external_refs_includes_every_status_and_archived_projects(
    seeded: Session,
) -> None:
    services.create_project(seeded, "old", "옛")
    done = services.create_task(seeded, title="a", project_slug="payment", external_ref="a/b#1")
    dropped = services.create_task(seeded, title="b", project_slug="payment", external_ref="a/b#2")
    services.create_task(seeded, title="c", project_slug="old", external_ref="a/b#3")
    services.create_task(seeded, title="d", project_slug="payment", external_ref="a/b#4")
    services.set_task_status(seeded, done.id, TaskStatus.DONE)
    services.set_task_status(seeded, dropped.id, TaskStatus.DROPPED)
    services.archive_project(seeded, "old")

    found = services.existing_external_refs(seeded, ["a/b#1", "a/b#2", "a/b#3", "a/b#9"])

    assert found == {"a/b#1", "a/b#2", "a/b#3"}


def test_existing_external_refs_empty_input_returns_empty(seeded: Session) -> None:
    assert services.existing_external_refs(seeded, []) == set()


def test_plan_issue_import_splits_new_and_skipped(seeded: Session) -> None:
    services.create_task(seeded, title="a", project_slug="payment", external_ref="a/b#2")

    plan = plan_issue_import(seeded, "a/b", [issue(3), issue(2), issue(1)])

    assert plan == IssueImport(new=(issue(1), issue(3)), skipped=(issue(2),))


def test_plan_issue_import_drops_duplicate_numbers(seeded: Session) -> None:
    plan = plan_issue_import(seeded, "a/b", [issue(2), issue(1), issue(2)])

    assert plan.new == (issue(1), issue(2))
    assert plan.skipped == ()


def test_import_issues_creates_tasks_in_number_order(seeded: Session) -> None:
    services.create_task(seeded, title="이미", project_slug="payment", external_ref="a/b#5")

    result = do_import(seeded, [issue(7), issue(5), issue(6), issue(7)])

    assert [t.external_ref for t in result.created] == ["a/b#6", "a/b#7"]
    assert [t.title for t in result.created] == ["이슈 6", "이슈 7"]
    assert result.skipped == (issue(5),)
    for task in result.created:
        assert task.status == TaskStatus.TODO
        assert task.project.slug == "payment"
        assert task.category == "dev"
        assert task.planned_week == "2026-W42"


def test_import_issues_without_category_and_week(seeded: Session) -> None:
    result = do_import(seeded, [issue(1)], category=None, planned_week=None)

    assert result.created[0].category is None
    assert result.created[0].planned_week is None


def test_import_issues_archived_project_creates_nothing(seeded: Session) -> None:
    services.archive_project(seeded, "payment")
    before = task_count(seeded)

    with pytest.raises(InvalidInputError):
        do_import(seeded, [issue(1), issue(2)])

    assert task_count(seeded) == before


def test_import_issues_unknown_project_creates_nothing(seeded: Session) -> None:
    before = task_count(seeded)

    with pytest.raises(NotFoundError):
        do_import(seeded, [issue(1)], project_slug="nope")

    assert task_count(seeded) == before


def test_import_issues_unknown_category_creates_nothing(seeded: Session) -> None:
    before = task_count(seeded)

    with pytest.raises(InvalidInputError):
        do_import(seeded, [issue(1), issue(2)], category="zzz")

    assert task_count(seeded) == before


def test_import_issues_blank_title_stops_with_core_message(seeded: Session) -> None:
    before = task_count(seeded)

    with pytest.raises(InvalidInputError):
        do_import(seeded, [Issue(1, "   ", "u")])

    seeded.rollback()
    assert task_count(seeded) == before
