"""lb start|status (타이머)."""

import os
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from typer.testing import Result

from logbook.core import services
from tests.cli.helpers import Clock, OpenDb, assert_rejected, run_ok

KST = timezone(timedelta(hours=9))


@pytest.fixture
def seeded(lb: Callable[..., Result], initialized: Path) -> Path:
    """payment 프로젝트와 태스크 #1(payment/design '환불 API 설계', todo)."""
    run_ok(lb, "project", "add", "payment", "결제 서버")
    run_ok(lb, "task", "add", "환불 API 설계", "-p", "payment", "-c", "design")
    return initialized


def task_status(open_db: OpenDb, task_id: int) -> str:
    with open_db() as s:
        return str(services.get_task(s, task_id).status)


# --- lb start ---


def test_start_with_note(lb: Callable[..., Result], seeded: Path, open_db: OpenDb) -> None:
    result = run_ok(lb, "start", "환불 API 설계", "-p", "payment", "-c", "design")

    assert result.stdout == "✔ 타이머 시작: payment/design — 환불 API 설계 (09:30)\n"
    assert result.stderr == ""
    with open_db() as s:
        timer = services.get_timer(s)
        assert timer is not None
        assert timer.note == "환불 API 설계"
    os.replace(seeded, seeded.with_name("moved.db"))


def test_start_with_todo_task_uses_title_and_starts_task(
    lb: Callable[..., Result], seeded: Path, open_db: OpenDb
) -> None:
    result = run_ok(lb, "start", "-t", "1")

    assert result.stdout == (
        "✔ 타이머 시작: payment/design — 환불 API 설계 [#1] (09:30)\n"
        "· 태스크 #1 상태를 doing으로 바꿨습니다.\n"
    )
    assert task_status(open_db, 1) == "doing"


def test_start_with_doing_task_has_no_status_line(lb: Callable[..., Result], seeded: Path) -> None:
    run_ok(lb, "task", "start", "1")

    result = run_ok(lb, "start", "-t", "#1")

    assert result.stdout == "✔ 타이머 시작: payment/design — 환불 API 설계 [#1] (09:30)\n"


def test_start_when_already_running(lb: Callable[..., Result], seeded: Path) -> None:
    run_ok(lb, "start", "환불 API 설계", "-p", "payment", "-c", "design")

    result = lb("start", "다른 일", "-c", "dev")

    assert_rejected(
        result,
        "이미 진행 중인 타이머가 있습니다: payment/design '환불 API 설계' (09:30 시작). "
        "'lb stop'으로 저장하거나 'lb cancel'로 버리세요.",
    )


def test_start_without_note_or_task(lb: Callable[..., Result], initialized: Path) -> None:
    result = lb("start", "-c", "dev")

    assert_rejected(result, "메모를 입력하세요. 무엇을 했는지 한 줄로 적어 주세요.")


def test_start_without_category(lb: Callable[..., Result], initialized: Path) -> None:
    result = lb("start", "x")

    assert_rejected(result, "카테고리를 지정하세요. 예: -c dev")


def test_start_bad_task_id(lb: Callable[..., Result], tmp_home: Path) -> None:
    # lb init 전이라 DB에 접근하면 다른 오류가 난다.
    result = lb("start", "x", "-t", "abc")

    assert_rejected(
        result, "태스크 ID가 올바르지 않습니다: 'abc'. 숫자로 입력하세요 (예: 128 또는 #128)."
    )


def test_start_note_starting_with_dash(lb: Callable[..., Result], initialized: Path) -> None:
    result = run_ok(lb, "start", "-c", "dev", "--", "-5% 개선")

    assert result.stdout == "✔ 타이머 시작: common/dev — -5% 개선 (09:30)\n"


# --- lb status ---


def test_status_without_timer(lb: Callable[..., Result], initialized: Path) -> None:
    result = run_ok(lb, "status")

    assert result.stdout == "진행 중인 타이머가 없습니다.\n"


def test_status_right_after_start(lb: Callable[..., Result], seeded: Path) -> None:
    run_ok(lb, "start", "-t", "1")

    result = run_ok(lb, "status")

    assert result.stdout == ("진행 중: payment/design — 환불 API 설계 [#1]\n시작 09:30 · 경과 0m\n")


def test_status_shows_elapsed(lb: Callable[..., Result], seeded: Path, clock: Clock) -> None:
    run_ok(lb, "start", "환불 API 설계", "-p", "payment", "-c", "design")
    clock.advance(minutes=85)

    result = run_ok(lb, "status")

    assert result.stdout == ("진행 중: payment/design — 환불 API 설계\n시작 09:30 · 경과 1h 25m\n")


def test_status_started_yesterday_shows_date(
    lb: Callable[..., Result], initialized: Path, clock: Clock
) -> None:
    clock.now = datetime(2026, 9, 30, 22, 10, tzinfo=KST)
    run_ok(lb, "start", "야간 배포", "-c", "ops")
    clock.now = datetime(2026, 10, 1, 9, 30, tzinfo=KST)

    result = run_ok(lb, "status")

    assert result.stdout == (
        "진행 중: common/ops — 야간 배포\n시작 09-30 (수) 22:10 · 경과 11h 20m\n"
    )
