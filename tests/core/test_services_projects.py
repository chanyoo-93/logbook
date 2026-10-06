"""logbook.core.services.projects 단위 테스트."""

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from logbook.core import services
from logbook.core.errors import InvalidInputError, NotFoundError
from logbook.core.models import Project
from logbook.core.services import projects


def _count_projects(session: Session) -> int:
    return session.scalars(select(func.count()).select_from(Project)).one()


def test_create_then_get_returns_project(session: Session) -> None:
    created = projects.create_project(
        session, "payment", "결제 서버", description="PG 연동", color="#4f46e5"
    )

    found = projects.get_project(session, "payment")

    assert found.id == created.id
    assert found.name == "결제 서버"
    assert found.description == "PG 연동"
    assert found.color == "#4f46e5"
    assert found.archived is False


def test_create_populates_id_and_defaults(session: Session) -> None:
    project = projects.create_project(session, "payment", "결제 서버")

    assert project.id is not None
    assert project.created_at.tzinfo is not None
    assert project.description is None
    assert project.color is None


def test_create_duplicate_slug_raises(session: Session) -> None:
    projects.create_project(session, "payment", "결제 서버")

    with pytest.raises(InvalidInputError, match="이미 존재") as excinfo:
        projects.create_project(session, "payment", "다른 이름")

    assert str(excinfo.value) == (
        "프로젝트 'payment'가 이미 존재합니다. 'lb project list'로 확인하세요."
    )


def test_create_duplicate_of_archived_slug_raises(session: Session) -> None:
    projects.create_project(session, "payment", "결제 서버")
    projects.archive_project(session, "payment")

    with pytest.raises(InvalidInputError, match="이미 존재"):
        projects.create_project(session, "payment", "결제 서버")


def test_create_duplicate_converts_integrity_error_on_race(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    projects.create_project(session, "payment", "결제 서버")
    # 확인과 삽입 사이에 다른 프로세스가 같은 slug를 넣은 상황을 흉내 낸다.
    monkeypatch.setattr(projects, "_find_project", lambda s, slug: None)

    with pytest.raises(InvalidInputError, match="이미 존재"):
        projects.create_project(session, "payment", "결제 서버")


@pytest.mark.parametrize(
    "slug",
    [
        "Pay ment",
        "결제",
        "",
        "Payment",
        "-payment",
        "_payment",
        "pay.ment",
        "payment\n",
        "a" * 33,
    ],
)
def test_create_invalid_slug_raises(session: Session, slug: str) -> None:
    with pytest.raises(InvalidInputError, match="slug가 올바르지 않습니다") as excinfo:
        projects.create_project(session, slug, "이름")

    assert f"'{slug}'" in str(excinfo.value)
    assert "최대 32자" in str(excinfo.value)
    assert _count_projects(session) == 0


@pytest.mark.parametrize("slug", ["a", "0day", "pay-ment_2", "a" * 32])
def test_create_valid_slug_accepted(session: Session, slug: str) -> None:
    project = projects.create_project(session, slug, "이름")

    assert project.slug == slug


@pytest.mark.parametrize("name", ["", "   ", "\t\n"])
def test_create_blank_name_raises(session: Session, name: str) -> None:
    with pytest.raises(InvalidInputError, match="이름"):
        projects.create_project(session, "payment", name)

    assert _count_projects(session) == 0


def test_create_stores_stripped_name_and_description(session: Session) -> None:
    project = projects.create_project(session, "payment", "  결제 서버 ", description="  PG 연동  ")

    assert project.name == "결제 서버"
    assert project.description == "PG 연동"


def test_create_blank_description_becomes_none(session: Session) -> None:
    project = projects.create_project(session, "payment", "결제 서버", description="   ")

    assert project.description is None


@pytest.mark.parametrize("color", ["#4f46e5", "#ABCDEF", "#00ff00"])
def test_create_valid_color_stored_as_given(session: Session, color: str) -> None:
    project = projects.create_project(session, "payment", "결제 서버", color=color)

    assert project.color == color


@pytest.mark.parametrize(
    "color", ["blue", "#abc", "4f46e5", "#4f46e5 ", "#4f46e", "#gggggg", "#4f46e5\n", ""]
)
def test_create_invalid_color_raises(session: Session, color: str) -> None:
    with pytest.raises(InvalidInputError, match="#4f46e5"):
        projects.create_project(session, "payment", "결제 서버", color=color)

    assert _count_projects(session) == 0


def test_get_missing_slug_raises_not_found(session: Session) -> None:
    with pytest.raises(NotFoundError, match="lb project list") as excinfo:
        projects.get_project(session, "paymnt")

    assert str(excinfo.value) == (
        "프로젝트 'paymnt'가 없습니다. 'lb project list'로 확인하거나, "
        "새 프로젝트라면 'lb project add paymnt <이름>'으로 만드세요."
    )


def test_get_missing_invalid_slug_hints_placeholder(session: Session) -> None:
    with pytest.raises(NotFoundError) as excinfo:
        projects.get_project(session, "Pay Ment")

    assert str(excinfo.value) == (
        "프로젝트 'Pay Ment'가 없습니다. 'lb project list'로 확인하거나, "
        "새 프로젝트라면 'lb project add <slug> <이름>'으로 만드세요."
    )


def test_get_returns_archived_project(session: Session) -> None:
    projects.create_project(session, "payment", "결제 서버")
    projects.archive_project(session, "payment")

    project = projects.get_project(session, "payment")

    assert project.archived is True


def test_get_active_returns_active_project(session: Session) -> None:
    created = projects.create_project(session, "payment", "결제 서버")

    assert projects.get_active_project(session, "payment").id == created.id


def test_get_active_rejects_archived_project(session: Session) -> None:
    projects.create_project(session, "payment", "결제 서버")
    projects.archive_project(session, "payment")

    with pytest.raises(InvalidInputError, match="보관된 프로젝트") as excinfo:
        projects.get_active_project(session, "payment")

    assert "'payment'" in str(excinfo.value)


def test_get_active_missing_slug_raises_not_found(session: Session) -> None:
    with pytest.raises(NotFoundError, match="lb project list"):
        projects.get_active_project(session, "paymnt")


def _slugs(items: list[Project]) -> list[str]:
    return [project.slug for project in items]


def _create_mixed_projects(session: Session) -> None:
    for slug in ["search", "payment", "admin", "billing"]:
        projects.create_project(session, slug, slug.upper())
    projects.archive_project(session, "billing")
    projects.archive_project(session, "search")


def test_list_excludes_archived_by_default_and_sorts_by_slug(session: Session) -> None:
    _create_mixed_projects(session)

    assert _slugs(projects.list_projects(session)) == ["admin", "payment"]


def test_list_include_archived_sorts_by_slug(session: Session) -> None:
    _create_mixed_projects(session)

    result = projects.list_projects(session, include_archived=True)

    assert _slugs(result) == ["admin", "billing", "payment", "search"]


def test_list_empty_returns_empty_list(session: Session) -> None:
    assert projects.list_projects(session) == []


def test_archive_sets_archived_and_is_idempotent(session: Session) -> None:
    projects.create_project(session, "payment", "결제 서버")

    first = projects.archive_project(session, "payment")
    second = projects.archive_project(session, "payment")

    assert first.archived is True
    assert second.archived is True
    assert second.id == first.id
    stored = session.scalar(select(Project.archived).where(Project.slug == "payment"))
    assert stored is True


def test_archive_missing_slug_raises_not_found(session: Session) -> None:
    with pytest.raises(NotFoundError, match="lb project list"):
        projects.archive_project(session, "paymnt")


def test_archive_common_raises(session: Session) -> None:
    projects.ensure_common_project(session)

    with pytest.raises(InvalidInputError, match="common 프로젝트는 보관할 수 없습니다"):
        projects.archive_project(session, projects.COMMON_SLUG)

    assert projects.get_project(session, "common").archived is False


def test_ensure_common_creates_once(session: Session) -> None:
    first = projects.ensure_common_project(session)
    second = projects.ensure_common_project(session)

    assert first.id == second.id
    assert _count_projects(session) == 1


def test_ensure_common_sets_name_and_description(session: Session) -> None:
    project = projects.ensure_common_project(session)

    assert project.slug == projects.COMMON_SLUG == "common"
    assert project.name == "공통"
    assert project.description == "프로젝트와 무관한 업무 (회의, 교육, 행정 등)"
    assert project.archived is False


def test_ensure_common_returns_existing_unchanged(session: Session) -> None:
    existing = projects.create_project(session, "common", "공통 업무", color="#123456")

    project = projects.ensure_common_project(session)

    assert project.id == existing.id
    assert project.name == "공통 업무"
    assert project.description is None
    assert project.color == "#123456"


def test_slug_pattern_constant() -> None:
    assert projects.SLUG_PATTERN == r"^[a-z0-9][a-z0-9_-]{0,31}$"


def test_package_reexports_project_services() -> None:
    assert services.create_project is projects.create_project
    assert services.get_project is projects.get_project
    assert services.get_active_project is projects.get_active_project
    assert services.list_projects is projects.list_projects
    assert services.archive_project is projects.archive_project
    assert services.ensure_common_project is projects.ensure_common_project
    assert services.COMMON_SLUG == projects.COMMON_SLUG
    assert services.SLUG_PATTERN == projects.SLUG_PATTERN
    assert set(services.__all__) >= {
        "COMMON_SLUG",
        "SLUG_PATTERN",
        "archive_project",
        "create_project",
        "ensure_common_project",
        "get_active_project",
        "get_project",
        "list_projects",
    }
