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
    is_valid_slug,
    list_projects,
)
from logbook.core.services.report import weekly_report
from logbook.core.services.stats import (
    MatrixResult,
    StatsBy,
    StatsResult,
    StatsRow,
    stats_by,
    stats_matrix,
)
from logbook.core.services.tasks import (
    actual_minutes_by_task,
    carry_candidates,
    carry_tasks,
    create_task,
    get_task,
    list_tasks,
    set_task_status,
    task_actual_minutes,
    update_task,
)
from logbook.core.services.timer import (
    MAX_ROUND_MINUTES,
    NO_TIMER_MESSAGE,
    StartedTimer,
    TimerStopped,
    cancel_timer,
    elapsed_minutes,
    get_timer,
    start_timer,
    stop_timer,
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
    "is_valid_slug",
    "list_projects",
    "actual_minutes_by_task",
    "carry_candidates",
    "carry_tasks",
    "create_task",
    "get_task",
    "list_tasks",
    "set_task_status",
    "task_actual_minutes",
    "update_task",
    "MAX_ROUND_MINUTES",
    "NO_TIMER_MESSAGE",
    "StartedTimer",
    "TimerStopped",
    "cancel_timer",
    "elapsed_minutes",
    "get_timer",
    "start_timer",
    "stop_timer",
    "add_worklog",
    "day_total_minutes",
    "delete_worklog",
    "get_worklog",
    "list_worklogs",
    "update_worklog",
    "MatrixResult",
    "StatsBy",
    "StatsResult",
    "StatsRow",
    "stats_by",
    "stats_matrix",
    "weekly_report",
]
