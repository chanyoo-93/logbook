"""태스크 상태와 상태 목록 파서. SQLAlchemy를 import하지 않는다(CLI 형식 오류 경로용)."""

import enum

from logbook.core.duration import echo_input
from logbook.core.errors import InvalidInputError


class TaskStatus(enum.StrEnum):
    TODO = "todo"
    DOING = "doing"
    DONE = "done"
    DROPPED = "dropped"


OPEN_STATUSES: tuple[TaskStatus, ...] = (TaskStatus.TODO, TaskStatus.DOING)
ALL_KEYWORD = "all"


def parse_statuses(text: str) -> tuple[TaskStatus, ...]:
    """'todo,doing'처럼 쉼표로 구분한 상태 목록. 'all'은 네 상태 전부. 입력 순서대로, 중복 제거."""
    items = [item for item in (part.strip().lower() for part in text.split(",")) if item]
    if not items:
        raise _invalid(text)
    if ALL_KEYWORD in items and all(item == ALL_KEYWORD or _is_status(item) for item in items):
        return tuple(TaskStatus)
    result: list[TaskStatus] = []
    for item in items:
        if not _is_status(item):
            raise _invalid(text)
        status = TaskStatus(item)
        if status not in result:
            result.append(status)
    return tuple(result)


def _is_status(value: str) -> bool:
    return value in {status.value for status in TaskStatus}


def _invalid(text: str) -> InvalidInputError:
    return InvalidInputError(
        f"상태가 올바르지 않습니다: '{echo_input(text)}'. "
        "todo, doing, done, dropped, all 중에서 쉼표로 구분해 쓰세요 (예: todo,doing)."
    )
