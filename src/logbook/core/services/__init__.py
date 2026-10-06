"""도메인 유스케이스. CLI와 Web은 이 패키지의 함수만 호출한다.

사용 예: from logbook.core import services; services.create_project(s, ...)
"""

from logbook.core.services.projects import (
    COMMON_SLUG,
    SLUG_PATTERN,
    archive_project,
    create_project,
    ensure_common_project,
    get_active_project,
    get_project,
    list_projects,
)
from logbook.core.services.worklogs import (
    add_worklog,
    day_total_minutes,
    delete_worklog,
    get_worklog,
    list_worklogs,
    update_worklog,
)

__all__ = [
    "COMMON_SLUG",
    "SLUG_PATTERN",
    "archive_project",
    "create_project",
    "ensure_common_project",
    "get_active_project",
    "get_project",
    "list_projects",
    "add_worklog",
    "day_total_minutes",
    "delete_worklog",
    "get_worklog",
    "list_worklogs",
    "update_worklog",
]
