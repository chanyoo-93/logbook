"""logbook.core.taskstatus 단위 테스트."""

import subprocess
import sys

import pytest

from logbook.core import models, taskstatus
from logbook.core.errors import InvalidInputError
from logbook.core.taskstatus import OPEN_STATUSES, TaskStatus, parse_statuses

ALL_STATUSES = (TaskStatus.TODO, TaskStatus.DOING, TaskStatus.DONE, TaskStatus.DROPPED)


def _message(text: str) -> str:
    return (
        f"상태가 올바르지 않습니다: '{text}'. "
        "todo, doing, done, dropped, all 중에서 쉼표로 구분해 쓰세요 (예: todo,doing)."
    )


@pytest.mark.parametrize("text", ["todo", "TODO", " todo "])
def test_parse_statuses_single_value_is_case_and_space_insensitive(text: str) -> None:
    assert parse_statuses(text) == (TaskStatus.TODO,)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("todo,doing", (TaskStatus.TODO, TaskStatus.DOING)),
        ("doing, todo", (TaskStatus.DOING, TaskStatus.TODO)),
        ("todo,todo,doing", (TaskStatus.TODO, TaskStatus.DOING)),
        ("todo,,doing,", (TaskStatus.TODO, TaskStatus.DOING)),
    ],
)
def test_parse_statuses_keeps_input_order_and_dedupes(
    text: str, expected: tuple[TaskStatus, ...]
) -> None:
    assert parse_statuses(text) == expected


@pytest.mark.parametrize("text", ["all", "done,all", "ALL"])
def test_parse_statuses_all_expands_to_every_status_in_definition_order(text: str) -> None:
    assert parse_statuses(text) == ALL_STATUSES


@pytest.mark.parametrize("text", ["", " , ", "todo,x", "완료"])
def test_parse_statuses_rejects_empty_or_unknown(text: str) -> None:
    with pytest.raises(InvalidInputError) as exc_info:
        parse_statuses(text)
    assert str(exc_info.value) == _message(text)


def test_parse_statuses_error_truncates_long_input() -> None:
    text = "x" * 45
    with pytest.raises(InvalidInputError) as exc_info:
        parse_statuses(text)
    assert str(exc_info.value) == _message("x" * 40 + "...")


def test_open_statuses_are_todo_and_doing() -> None:
    assert OPEN_STATUSES == (TaskStatus.TODO, TaskStatus.DOING)


def test_models_reexports_the_same_task_status() -> None:
    assert models.TaskStatus is taskstatus.TaskStatus


@pytest.mark.subprocess
def test_taskstatus_does_not_import_sqlalchemy() -> None:
    code = "import sys, logbook.core.taskstatus; sys.exit(1 if 'sqlalchemy' in sys.modules else 0)"
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=False)
    assert proc.returncode == 0, proc.stderr
