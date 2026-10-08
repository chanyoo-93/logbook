"""lb start|status|stop|cancel (타이머)."""

import os
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from typer.testing import Result

from logbook.cli import runtime
from logbook.core import services
from tests.cli.helpers import FIXED_NOW, Clock, OpenDb, assert_rejected, run_ok

KST = timezone(timedelta(hours=9))

NO_TIMER = "진행 중인 타이머가 없습니다. 'lb start \"메모\"'로 시작하세요."
TIMER = "payment/design — 환불 API 설계"
CANCEL_PROMPT = f"버릴 타이머: {TIMER} (시작 09:30 · 경과 25m)\n버릴까요? [y/N]: "
CANCELLED = f"✔ 타이머를 버렸습니다: {TIMER} (경과 25m)\n"
CANCEL_DECLINED = "취소하지 않았습니다. 타이머는 계속 진행됩니다.\n"
CANCEL_NO_INPUT = "확인 입력을 받지 못해 버리지 않았습니다. 확인 없이 버리려면 --yes를 붙이세요.\n"
CANCEL_CHANGED = "확인하는 동안 타이머가 바뀌어 버리지 않았습니다. 다시 실행하세요.\n"


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


# --- lb stop ---


@pytest.fixture
def running(lb: Callable[..., Result], seeded: Path) -> Path:
    """payment/design '환불 API 설계' 타이머(09:30 시작, 태스크 없음)."""
    run_ok(lb, "start", "환불 API 설계", "-p", "payment", "-c", "design")
    return seeded


def has_timer(open_db: OpenDb) -> bool:
    with open_db() as s:
        return services.get_timer(s) is not None


def log_count(open_db: OpenDb) -> int:
    with open_db() as s:
        return len(services.list_worklogs(s))


def test_stop_saves_worklog(
    lb: Callable[..., Result], running: Path, open_db: OpenDb, clock: Clock
) -> None:
    clock.advance(minutes=85)

    result = run_ok(lb, "stop")

    assert result.stdout == "✔ #1 payment/design 1h 25m — 환불 API 설계 (오늘 누적 1h 25m)\n"
    assert result.stderr == ""
    with open_db() as s:
        assert services.get_timer(s) is None
        log = services.get_worklog(s, 1)
        assert log.minutes == 85
        assert log.started_at == FIXED_NOW
        assert log.ended_at == FIXED_NOW + timedelta(minutes=85)
    os.replace(running, running.with_name("moved.db"))


def test_stop_adds_to_day_total(lb: Callable[..., Result], running: Path, clock: Clock) -> None:
    run_ok(lb, "add", "2h", "회의", "-c", "meeting")
    clock.advance(minutes=60)

    result = run_ok(lb, "stop")

    assert result.stdout == "✔ #2 payment/design 1h — 환불 API 설계 (오늘 누적 3h)\n"


def test_stop_with_round_shows_elapsed(
    lb: Callable[..., Result], running: Path, open_db: OpenDb, clock: Clock
) -> None:
    clock.advance(minutes=85)

    result = run_ok(lb, "stop", "--round", "15")

    assert result.stdout == (
        "✔ #1 payment/design 1h 30m — 환불 API 설계 (오늘 누적 1h 30m)\n"
        "· 경과 1h 25m을 15분 단위로 반올림했습니다.\n"
    )
    with open_db() as s:
        assert services.get_worklog(s, 1).minutes == 90


def test_stop_with_round_that_matches_elapsed_has_no_note(
    lb: Callable[..., Result], running: Path, clock: Clock
) -> None:
    clock.advance(minutes=90)

    result = run_ok(lb, "stop", "--round", "15")

    assert result.stdout == "✔ #1 payment/design 1h 30m — 환불 API 설계 (오늘 누적 1h 30m)\n"


@pytest.mark.parametrize("option", ["--note", "-n"])
def test_stop_appends_note(
    lb: Callable[..., Result], running: Path, clock: Clock, option: str
) -> None:
    clock.advance(minutes=30)

    result = run_ok(lb, "stop", option, "예외 케이스 정리")

    assert result.stdout == (
        "✔ #1 payment/design 30m — 환불 API 설계 — 예외 케이스 정리 (오늘 누적 30m)\n"
    )


def test_stop_blank_note_keeps_timer(
    lb: Callable[..., Result], running: Path, open_db: OpenDb, clock: Clock
) -> None:
    clock.advance(minutes=30)

    result = lb("stop", "-n", "  ")

    assert_rejected(
        result, "덧붙일 메모가 비어 있습니다. 메모를 덧붙이지 않으려면 --note를 빼세요."
    )
    assert has_timer(open_db)
    assert log_count(open_db) == 0


@pytest.mark.parametrize("value", ["0", "abc", "61", "-5", "１５"])
def test_stop_bad_round_before_db(lb: Callable[..., Result], tmp_home: Path, value: str) -> None:
    # lb init 전이라 DB에 접근하면 다른 오류가 난다.
    result = lb("stop", f"--round={value}")

    assert_rejected(
        result,
        f"반올림 단위가 올바르지 않습니다: '{value}'. "
        "1~60 사이의 분 단위 숫자로 입력하세요 (예: --round 15).",
    )


def test_stop_under_one_minute_keeps_timer(
    lb: Callable[..., Result], running: Path, open_db: OpenDb, clock: Clock
) -> None:
    clock.advance(seconds=20)

    result = lb("stop")

    assert_rejected(
        result, "1분이 지나지 않아 기록하지 않았습니다. 버리려면 'lb cancel'을 실행하세요."
    )
    assert run_ok(lb, "status").stdout.startswith(f"진행 중: {TIMER}\n")
    assert log_count(open_db) == 0


def test_stop_without_timer(lb: Callable[..., Result], initialized: Path) -> None:
    assert_rejected(lb("stop"), NO_TIMER)


def test_stop_over_midnight_records_start_day(
    lb: Callable[..., Result], initialized: Path, open_db: OpenDb, clock: Clock
) -> None:
    clock.now = datetime(2026, 9, 30, 23, 50, tzinfo=KST)
    run_ok(lb, "start", "야간 배포", "-c", "ops")
    clock.now = datetime(2026, 10, 1, 0, 40, tzinfo=KST)

    result = run_ok(lb, "stop")

    assert result.stdout == "✔ #1 common/ops 50m — 야간 배포 (09-30 누적 50m)\n"
    with open_db() as s:
        assert str(services.get_worklog(s, 1).date) == "2026-09-30"


def test_stop_markup_like_note_is_verbatim(
    lb: Callable[..., Result], initialized: Path, clock: Clock
) -> None:
    run_ok(lb, "start", "[bold]x[/bold]", "-c", "dev")
    clock.advance(minutes=5)

    result = run_ok(lb, "stop", "-n", ":smile: [red]")

    assert result.stdout == ("✔ #1 common/dev 5m — [bold]x[/bold] — :smile: [red] (오늘 누적 5m)\n")


# --- lb cancel ---


@pytest.mark.parametrize("answer", ["y\n", "ㅛ\n"])
def test_cancel_confirmed(
    lb: Callable[..., Result], running: Path, open_db: OpenDb, clock: Clock, answer: str
) -> None:
    clock.advance(minutes=25)

    result = lb("cancel", input=answer)

    assert result.exit_code == 0, result.stderr
    assert result.stdout == CANCELLED
    assert result.stderr == CANCEL_PROMPT
    assert not has_timer(open_db)
    assert log_count(open_db) == 0
    os.replace(running, running.with_name("moved.db"))


@pytest.mark.parametrize("answer", ["n\n", "\n"])
def test_cancel_declined(
    lb: Callable[..., Result], running: Path, open_db: OpenDb, clock: Clock, answer: str
) -> None:
    clock.advance(minutes=25)

    result = lb("cancel", input=answer)

    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr == CANCEL_PROMPT + CANCEL_DECLINED
    assert has_timer(open_db)
    os.replace(running, running.with_name("moved.db"))


def test_cancel_without_input(
    lb: Callable[..., Result], running: Path, open_db: OpenDb, clock: Clock
) -> None:
    clock.advance(minutes=25)

    result = lb("cancel")

    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr == CANCEL_PROMPT + "\n" + CANCEL_NO_INPUT
    assert has_timer(open_db)


@pytest.mark.parametrize("option", ["--yes", "-y"])
def test_cancel_yes_skips_prompt(
    lb: Callable[..., Result], running: Path, open_db: OpenDb, clock: Clock, option: str
) -> None:
    clock.advance(minutes=25)

    result = lb("cancel", option)

    assert result.exit_code == 0, result.stderr
    assert result.stdout == CANCELLED
    assert result.stderr == ""
    assert not has_timer(open_db)


def test_cancel_prompt_shows_start_date_when_not_today(
    lb: Callable[..., Result], initialized: Path, clock: Clock
) -> None:
    clock.now = datetime(2026, 9, 30, 22, 10, tzinfo=KST)
    run_ok(lb, "start", "야간 배포", "-c", "ops")
    clock.now = datetime(2026, 10, 1, 9, 30, tzinfo=KST)

    result = lb("cancel", input="n\n")

    assert result.stderr.startswith(
        "버릴 타이머: common/ops — 야간 배포 (시작 09-30 (수) 22:10 · 경과 11h 20m)\n"
    )


def test_cancel_timer_replaced_while_confirming(
    lb: Callable[..., Result],
    running: Path,
    open_db: OpenDb,
    clock: Clock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock.advance(minutes=25)

    # 확인하는 동안 다른 터미널이 타이머를 버리고 같은 시각에 다른 타이머를 시작한 상황
    def confirm_after_replace(question: str) -> bool:
        with open_db() as s:
            services.cancel_timer(s)
            services.start_timer(s, now=FIXED_NOW, note="다른 일", category="dev")
        return True

    monkeypatch.setattr(runtime, "confirm", confirm_after_replace)

    result = lb("cancel")

    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr == CANCEL_CHANGED
    with open_db() as s:
        timer = services.get_timer(s)
        assert timer is not None
        assert timer.note == "다른 일"
    os.replace(running, running.with_name("moved.db"))


def test_cancel_timer_stopped_while_confirming(
    lb: Callable[..., Result],
    running: Path,
    open_db: OpenDb,
    clock: Clock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock.advance(minutes=25)

    def confirm_after_stop(question: str) -> bool:
        with open_db() as s:
            services.stop_timer(s, now=clock.now)
        return True

    monkeypatch.setattr(runtime, "confirm", confirm_after_stop)

    result = lb("cancel")

    assert result.exit_code == 1
    assert result.stderr == CANCEL_CHANGED
    assert log_count(open_db) == 1


def test_cancel_without_timer(lb: Callable[..., Result], initialized: Path) -> None:
    result = lb("cancel", input="y\n")

    assert_rejected(result, NO_TIMER)
