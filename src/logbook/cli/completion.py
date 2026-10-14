"""셸 자동완성 후보: 프로젝트 slug와 태스크 ID.

탭 한 번에 DB를 만들거나 올리지 않도록 읽기 전용 엔진만 쓰고, 어떤 오류도 빈 후보로 돌린다.
이 모듈은 --help 시작 시간을 지키려고 최상위에서 typer·core를 import하지 않는다.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    from sqlalchemy.orm import Session

MAX_TITLE_LENGTH = 60  # 셸 후보 설명으로 보여 줄 제목 길이

Candidates = list[tuple[str, str]]


def _one_line(title: str) -> str:
    return " ".join(title.split())[:MAX_TITLE_LENGTH]


def _collect(query: "Callable[[Session], Candidates]") -> Candidates:
    """읽기 전용 세션에서 query를 실행한다. DB가 없거나 옛 버전이거나 오류면 []."""
    try:
        from logbook.core import db
        from logbook.core.config import load_config

        engine = db.open_readonly(load_config().db_path)
        if engine is None:
            return []
        try:
            with db.session_scope(engine) as s:
                return query(s)
        finally:
            engine.dispose()
    except Exception:  # noqa: BLE001 - 자동완성은 어떤 오류에도 셸을 어지럽히지 않는다.
        return []


def _projects(incomplete: str, *, archived: bool | None) -> Candidates:
    def query(s: "Session") -> Candidates:
        from logbook.core import services

        return [
            (p.slug, p.name)
            for p in services.list_projects(s, include_archived=True)
            if p.slug.startswith(incomplete) and (archived is None or p.archived == archived)
        ]

    return _collect(query)


def complete_project(incomplete: str) -> Candidates:
    """보관하지 않은 프로젝트: (slug, 이름). slug 순."""
    return _projects(incomplete, archived=False)


def complete_archived_project(incomplete: str) -> Candidates:
    """보관한 프로젝트(lb project unarchive용)."""
    return _projects(incomplete, archived=True)


def complete_any_project(incomplete: str) -> Candidates:
    """보관 포함 모든 프로젝트(조회 옵션용)."""
    return _projects(incomplete, archived=None)


def complete_task_id(incomplete: str) -> Candidates:
    """todo·doing 태스크: (ID 문자열, 제목). ID 순. '#'으로 시작하면 '#'을 붙인 값."""
    prefix = "#" if incomplete.startswith("#") else ""

    def query(s: "Session") -> Candidates:
        from logbook.core import services
        from logbook.core.taskstatus import OPEN_STATUSES

        tasks = sorted(services.list_tasks(s, statuses=OPEN_STATUSES), key=lambda t: t.id)
        return [
            (f"{prefix}{t.id}", _one_line(t.title))
            for t in tasks
            if f"{prefix}{t.id}".startswith(incomplete)
        ]

    return _collect(query)
