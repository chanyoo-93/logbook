"""lb task start|done|drop."""

import os
from collections.abc import Callable
from pathlib import Path

import pytest
from typer.testing import Result

from logbook.core import services
from tests.cli.helpers import OpenDb, assert_rejected, run_ok


def status_of(open_db: OpenDb, task_id: int) -> tuple[str, bool]:
    """(상태, done_at이 있는지)."""
    with open_db() as s:
        task = services.get_task(s, task_id)
        return str(task.status), task.done_at is not None


@pytest.fixture
def seeded(lb: Callable[..., Result], initialized: Path) -> Path:
    """payment 프로젝트의 태스크 #1(예상 4h)."""
    run_ok(lb, "project", "add", "payment", "결제 서버")
    run_ok(lb, "task", "add", "환불 API 설계", "-p", "payment", "-c", "design", "--est", "4h")
    return initialized


def test_start(lb: Callable[..., Result], seeded: Path, open_db: OpenDb) -> None:
    result = run_ok(lb, "task", "start", "1")

    assert result.stdout == "✔ #1 todo → doing: payment/design 환불 API 설계\n"
    assert result.stderr == ""
    assert status_of(open_db, 1) == ("doing", False)
    os.replace(seeded, seeded.with_name("moved.db"))


def test_start_accepts_hash_id(lb: Callable[..., Result], seeded: Path) -> None:
    result = run_ok(lb, "task", "start", "#1")

    assert result.stdout.startswith("✔ #1 todo → doing: ")


def test_drop(lb: Callable[..., Result], seeded: Path, open_db: OpenDb) -> None:
    result = run_ok(lb, "task", "drop", "1")

    assert result.stdout == "✔ #1 todo → dropped: payment/design 환불 API 설계\n"
    assert status_of(open_db, 1) == ("dropped", False)


def test_done_without_logs(lb: Callable[..., Result], seeded: Path, open_db: OpenDb) -> None:
    result = run_ok(lb, "task", "done", "1")

    assert result.stdout == "✔ #1 todo → done: payment/design 환불 API 설계 (실적 0m / 예상 4h)\n"
    assert status_of(open_db, 1) == ("done", True)


def test_done_with_actual_and_estimate(lb: Callable[..., Result], seeded: Path) -> None:
    run_ok(lb, "add", "3h", "설계", "-t", "1")
    run_ok(lb, "add", "2h30m", "리뷰", "-t", "1")

    result = run_ok(lb, "task", "done", "1")

    assert result.stdout == (
        "✔ #1 todo → done: payment/design 환불 API 설계 (실적 5h 30m / 예상 4h)\n"
    )


def test_done_without_estimate(lb: Callable[..., Result], seeded: Path) -> None:
    run_ok(lb, "task", "add", "문서 정리", "-p", "payment")
    run_ok(lb, "add", "1h30m", "문서", "-t", "2", "-c", "docs")

    result = run_ok(lb, "task", "done", "2")

    assert result.stdout == "✔ #2 todo → done: payment 문서 정리 (실적 1h 30m)\n"


def test_same_state(lb: Callable[..., Result], seeded: Path, open_db: OpenDb) -> None:
    run_ok(lb, "task", "start", "1")

    result = run_ok(lb, "task", "start", "1")

    assert result.stdout == "· 태스크 #1 상태는 이미 doing입니다: payment/design 환불 API 설계\n"
    assert status_of(open_db, 1) == ("doing", False)


def test_same_state_line_has_no_particle_after_id(lb: Callable[..., Result], seeded: Path) -> None:
    # '#2는'/'#1은'처럼 받침에 따라 달라지는 조사를 숫자 뒤에 붙이지 않는다.
    run_ok(lb, "task", "add", "문서 정리", "-p", "payment")
    run_ok(lb, "task", "start", "2")

    result = run_ok(lb, "task", "start", "2")

    assert result.stdout == "· 태스크 #2 상태는 이미 doing입니다: payment 문서 정리\n"


def test_same_state_dropped(lb: Callable[..., Result], seeded: Path) -> None:
    run_ok(lb, "task", "drop", "1")

    result = run_ok(lb, "task", "drop", "1")

    assert result.stdout == "· 태스크 #1 상태는 이미 dropped입니다: payment/design 환불 API 설계\n"


def test_done_again_keeps_tail(lb: Callable[..., Result], seeded: Path, open_db: OpenDb) -> None:
    run_ok(lb, "add", "2h", "설계", "-t", "1")
    run_ok(lb, "task", "done", "1")

    result = run_ok(lb, "task", "done", "1")

    assert result.stdout == (
        "· 태스크 #1 상태는 이미 done입니다: payment/design 환불 API 설계 (실적 2h / 예상 4h)\n"
    )
    assert status_of(open_db, 1) == ("done", True)


def test_start_after_done_clears_done_at(
    lb: Callable[..., Result], seeded: Path, open_db: OpenDb
) -> None:
    run_ok(lb, "task", "done", "1")

    result = run_ok(lb, "task", "start", "1")

    assert result.stdout == "✔ #1 done → doing: payment/design 환불 API 설계\n"
    assert status_of(open_db, 1) == ("doing", False)


def test_start_after_drop(lb: Callable[..., Result], seeded: Path, open_db: OpenDb) -> None:
    run_ok(lb, "task", "drop", "1")

    result = run_ok(lb, "task", "start", "1")

    assert result.stdout.startswith("✔ #1 dropped → doing: ")
    assert status_of(open_db, 1) == ("doing", False)


def test_markup_like_title_is_printed_verbatim(lb: Callable[..., Result], seeded: Path) -> None:
    run_ok(lb, "task", "edit", "1", "--title", "[bold]x[/bold]")

    result = run_ok(lb, "task", "start", "1")

    assert result.stdout == "✔ #1 todo → doing: payment/design [bold]x[/bold]\n"


@pytest.mark.parametrize("command", ["start", "done", "drop"])
def test_unknown_id(lb: Callable[..., Result], seeded: Path, command: str) -> None:
    result = lb("task", command, "9")

    assert_rejected(result, "태스크 #9가 없습니다. 'lb task list'로 확인하세요.")


@pytest.mark.parametrize("command", ["start", "done", "drop"])
@pytest.mark.parametrize("task_id", ["abc", "0"])
def test_invalid_id(lb: Callable[..., Result], seeded: Path, command: str, task_id: str) -> None:
    result = lb("task", command, task_id)

    assert_rejected(
        result,
        f"태스크 ID가 올바르지 않습니다: '{task_id}'. 숫자로 입력하세요 (예: 128 또는 #128).",
    )
