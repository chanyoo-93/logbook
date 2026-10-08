"""lb plan, lb plan carry."""

import os
from collections.abc import Callable
from pathlib import Path

import pytest
from typer.testing import Result

from logbook.cli import console, runtime
from logbook.core import services
from logbook.core.taskstatus import TaskStatus
from tests.cli.helpers import OpenDb, assert_rejected, run_ok, tokens

W40_HEADING = "2026-W40 (09-28 ~ 10-04)"
W41_HEADING = "2026-W41 (10-05 ~ 10-11)"
BEFORE_SUBCOMMAND_MESSAGE = (
    "--week는 'lb plan' 목록에만 쓸 수 있습니다. "
    "이월할 주는 'lb plan carry -w last'처럼 하위 명령 뒤에 쓰세요."
)
BAD_WEEK_MESSAGE = "주차 형식이 올바르지 않습니다: 'x'. 예: this, last, next, 2026-W41"

CANDIDATES = (
    "이월할 태스크 (2026-W40 → 2026-W41):\n"
    "#1 doing payment/design 환불 API 설계\n"
    "#2 todo payment/dev 결제 재시도\n"
)
PROMPT = "옮길까요? [y/N]: "
MOVED = (
    "✔ 2건을 옮겼습니다: 2026-W40 → 2026-W41\n"
    "#1 payment/design 환불 API 설계\n"
    "#2 payment/dev 결제 재시도\n"
)
CANCELLED = "이월을 취소했습니다.\n"
NO_INPUT = "확인 입력을 받지 못해 옮기지 않았습니다. 확인 없이 옮기려면 --yes를 붙이세요.\n"


def weeks_of(open_db: OpenDb) -> dict[int, str | None]:
    """태스크 id별 계획 주차(보관 프로젝트 포함)."""
    with open_db() as s:
        return {
            task.id: task.planned_week for task in services.list_tasks(s, include_archived=True)
        }


@pytest.fixture
def seeded(lb: Callable[..., Result], initialized: Path) -> Path:
    """W40: #1 doing, #2 todo(payment), #3 done, #4 dropped(admin). W41: #5. 보관 old: #6(W40 todo).

    실적: #1 2h 30m, #3 1h.
    """
    run_ok(lb, "project", "add", "payment", "결제 서버")
    run_ok(lb, "project", "add", "admin", "관리자")
    run_ok(lb, "project", "add", "old", "옛 프로젝트")
    run_ok(
        lb,
        "task",
        "add",
        "환불 API 설계",
        "-p",
        "payment",
        "-c",
        "design",
        "-e",
        "4h",
        "-w",
        "this",
    )
    run_ok(lb, "task", "add", "결제 재시도", "-p", "payment", "-c", "dev", "-e", "4h", "-w", "this")
    run_ok(lb, "task", "add", "권한 정리", "-p", "admin", "-e", "4h", "-w", "this")
    run_ok(lb, "task", "add", "옛 계획", "-p", "admin", "-e", "2h", "-w", "this")
    run_ok(lb, "task", "add", "다음 주 작업", "-p", "payment", "-e", "3h", "-w", "next")
    run_ok(lb, "task", "add", "옛 작업", "-p", "old", "-e", "5h", "-w", "this")
    run_ok(lb, "task", "start", "1")
    run_ok(lb, "task", "done", "3")
    run_ok(lb, "task", "drop", "4")
    run_ok(lb, "add", "2h30m", "설계", "-t", "1")
    run_ok(lb, "add", "1h", "정리", "-t", "3", "-c", "docs")
    run_ok(lb, "project", "archive", "old")
    return initialized


INITIAL_WEEKS = {
    1: "2026-W40",
    2: "2026-W40",
    3: "2026-W40",
    4: "2026-W40",
    5: "2026-W41",
    6: "2026-W40",
}


# ---- lb plan ----


def test_plan_this_week(lb: Callable[..., Result], seeded: Path) -> None:
    result = run_ok(lb, "plan")

    out = result.stdout.splitlines()
    assert out[0] == (f"{W40_HEADING} 계획   예상 12h / 실적 3h 30m / 태스크 3건 (완료 1건)")
    assert tokens(out[1]) == ["ID", "상태", "프로젝트", "제목", "예상", "실적"]
    # (프로젝트 slug, id) 순. dropped·다음 주·보관 프로젝트는 뺀다.
    assert [tokens(line) for line in out[2:5]] == [
        ["3", "done", "admin", "권한 정리", "4h", "1h"],
        ["1", "doing", "payment", "환불 API 설계", "4h", "2h 30m"],
        ["2", "todo", "payment", "결제 재시도", "4h", "-"],
    ]
    assert out[5:] == ["프로젝트별 예상: admin 4h · payment 8h"]
    assert result.stderr == ""
    os.replace(seeded, seeded.with_name("moved.db"))


def test_plan_tasks_without_estimate(lb: Callable[..., Result], seeded: Path) -> None:
    run_ok(lb, "task", "add", "회의 준비", "-p", "admin", "-w", "this")

    result = run_ok(lb, "plan")

    out = result.stdout.splitlines()
    assert out[0] == f"{W40_HEADING} 계획   예상 12h / 실적 3h 30m / 태스크 4건 (완료 1건)"
    assert tokens(out[3]) == ["7", "todo", "admin", "회의 준비", "-", "-"]
    assert out[-2:] == ["프로젝트별 예상: admin 4h · payment 8h", "예상이 없는 태스크 1건"]


def test_plan_only_tasks_without_estimate(lb: Callable[..., Result], initialized: Path) -> None:
    run_ok(lb, "task", "add", "회의 준비", "-w", "this")
    run_ok(lb, "task", "add", "문서 정리", "-w", "this")

    out = run_ok(lb, "plan").stdout.splitlines()

    # 완료가 0건이면 '(완료 0건)'을 붙이지 않는다.
    # 예상이 있는 프로젝트가 없으면 프로젝트별 줄도 없다.
    assert out[0] == f"{W40_HEADING} 계획   예상 0m / 실적 0m / 태스크 2건"
    assert out[-1] == "예상이 없는 태스크 2건"
    assert not any(line.startswith("프로젝트별 예상") for line in out)


def test_plan_next_week(lb: Callable[..., Result], seeded: Path) -> None:
    out = run_ok(lb, "plan", "-w", "next").stdout.splitlines()

    assert out[0] == f"{W41_HEADING} 계획   예상 3h / 실적 0m / 태스크 1건"
    assert [tokens(line) for line in out[2:-1]] == [
        ["5", "todo", "payment", "다음 주 작업", "3h", "-"]
    ]
    assert out[-1] == "프로젝트별 예상: payment 3h"


def test_plan_empty_week(lb: Callable[..., Result], seeded: Path) -> None:
    result = run_ok(lb, "plan", "--week", "2026-W30")

    assert result.stdout == (
        "2026-W30 (07-20 ~ 07-26) 계획   예상 0m / 실적 0m / 태스크 0건\n"
        "이 주에 계획된 태스크가 없습니다.\n"
    )
    assert result.stderr == ""


def test_plan_empty_database(lb: Callable[..., Result], initialized: Path) -> None:
    result = run_ok(lb, "plan")

    assert result.stdout == (
        f"{W40_HEADING} 계획   예상 0m / 실적 0m / 태스크 0건\n이 주에 계획된 태스크가 없습니다.\n"
    )


def test_plan_bad_week(lb: Callable[..., Result], seeded: Path) -> None:
    assert_rejected(lb("plan", "-w", "x"), BAD_WEEK_MESSAGE)


def test_plan_narrow_width_falls_back_to_lines(
    lb: Callable[..., Result], seeded: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(console, "PIPE_WIDTH", 40)

    result = run_ok(lb, "plan")

    assert result.stdout.splitlines()[1:] == [
        "#3 done admin 권한 정리 · 예상 4h · 실적 1h",
        "#1 doing payment 환불 API 설계 · 예상 4h · 실적 2h 30m",
        "#2 todo payment 결제 재시도 · 예상 4h",
        "프로젝트별 예상: admin 4h · payment 8h",
    ]
    assert result.stderr.startswith("터미널 폭이 좁아 표 대신 목록으로 보여 줍니다")


def test_week_before_subcommand_is_rejected(
    lb: Callable[..., Result], seeded: Path, open_db: OpenDb
) -> None:
    result = lb("plan", "-w", "next", "carry", "--yes")

    assert_rejected(result, BEFORE_SUBCOMMAND_MESSAGE)
    assert weeks_of(open_db) == INITIAL_WEEKS


def test_plan_before_init(lb: Callable[..., Result], tmp_home: Path) -> None:
    db_path = tmp_home / "logbook.db"

    result = lb("plan")

    assert_rejected(result, f"데이터베이스가 없습니다: {db_path}. 먼저 'lb init'을 실행하세요.")


# ---- lb plan carry ----


@pytest.mark.parametrize("answer", ["y\n", "ㅛ\n"])
def test_carry_confirmed(
    lb: Callable[..., Result], seeded: Path, open_db: OpenDb, answer: str
) -> None:
    result = lb("plan", "carry", input=answer)

    assert result.exit_code == 0, result.stderr
    assert result.stdout == MOVED
    assert result.stderr == CANDIDATES + PROMPT
    # todo·doing만 다음 주로. done·dropped·보관 프로젝트는 그대로.
    assert weeks_of(open_db) == {**INITIAL_WEEKS, 1: "2026-W41", 2: "2026-W41"}
    os.replace(seeded, seeded.with_name("moved.db"))


@pytest.mark.parametrize("answer", ["n\n", "\n"])
def test_carry_declined(
    lb: Callable[..., Result], seeded: Path, open_db: OpenDb, answer: str
) -> None:
    result = lb("plan", "carry", input=answer)

    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr == CANDIDATES + PROMPT + CANCELLED
    assert weeks_of(open_db) == INITIAL_WEEKS
    os.replace(seeded, seeded.with_name("moved.db"))


def test_carry_without_input(lb: Callable[..., Result], seeded: Path, open_db: OpenDb) -> None:
    result = lb("plan", "carry")

    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr == CANDIDATES + PROMPT + "\n" + NO_INPUT
    assert weeks_of(open_db) == INITIAL_WEEKS
    os.replace(seeded, seeded.with_name("moved.db"))


@pytest.mark.parametrize("option", ["--yes", "-y"])
def test_carry_yes_skips_prompt(
    lb: Callable[..., Result], seeded: Path, open_db: OpenDb, option: str
) -> None:
    result = lb("plan", "carry", option)

    assert result.exit_code == 0, result.stderr
    assert result.stdout == MOVED
    assert result.stderr == ""
    assert weeks_of(open_db) == {**INITIAL_WEEKS, 1: "2026-W41", 2: "2026-W41"}


def test_carry_last_week(lb: Callable[..., Result], seeded: Path, open_db: OpenDb) -> None:
    run_ok(lb, "task", "add", "지난주 작업", "-p", "admin", "-w", "last")

    result = run_ok(lb, "plan", "carry", "-w", "last", "--yes")

    assert result.stdout == "✔ 1건을 옮겼습니다: 2026-W39 → 2026-W40\n#7 admin 지난주 작업\n"
    assert weeks_of(open_db) == {**INITIAL_WEEKS, 7: "2026-W40"}


def test_carry_no_candidates(lb: Callable[..., Result], seeded: Path, open_db: OpenDb) -> None:
    result = lb("plan", "carry", "-w", "2026-W30", input="y\n")

    assert result.exit_code == 0, result.stderr
    assert result.stdout == "이월할 태스크가 없습니다 (2026-W30의 todo·doing 태스크).\n"
    assert result.stderr == ""
    assert weeks_of(open_db) == INITIAL_WEEKS


def test_carry_bad_week(lb: Callable[..., Result], seeded: Path) -> None:
    assert_rejected(lb("plan", "carry", "-w", "x"), BAD_WEEK_MESSAGE)


def test_carry_skips_task_changed_while_confirming(
    lb: Callable[..., Result], seeded: Path, open_db: OpenDb, monkeypatch: pytest.MonkeyPatch
) -> None:
    # 확인하는 동안 다른 터미널이 #2를 완료한 상황
    def confirm_after_done(question: str) -> bool:
        assert question == "옮길까요?"
        with open_db() as s:
            services.set_task_status(s, 2, TaskStatus.DONE)
        return True

    monkeypatch.setattr(runtime, "confirm", confirm_after_done)

    result = lb("plan", "carry")

    assert result.exit_code == 0, result.stderr
    assert (
        result.stdout
        == "✔ 1건을 옮겼습니다: 2026-W40 → 2026-W41\n#1 payment/design 환불 API 설계\n"
    )
    assert result.stderr == (CANDIDATES + "주의: 1건은 확인하는 동안 바뀌어 옮기지 않았습니다.\n")
    assert weeks_of(open_db) == {**INITIAL_WEEKS, 1: "2026-W41"}
    os.replace(seeded, seeded.with_name("moved.db"))


def test_carry_before_init(lb: Callable[..., Result], tmp_home: Path) -> None:
    db_path = tmp_home / "logbook.db"

    result = lb("plan", "carry", "--yes")

    assert_rejected(result, f"데이터베이스가 없습니다: {db_path}. 먼저 'lb init'을 실행하세요.")


def test_markup_like_title_is_printed_verbatim(
    lb: Callable[..., Result], initialized: Path
) -> None:
    run_ok(lb, "task", "add", "[red]x[/red] :smile:", "-w", "this", "-e", "1h")

    plan = run_ok(lb, "plan")
    carry = lb("plan", "carry", input="n\n")

    row = ["1", "todo", "common", "[red]x[/red] :smile:", "1h", "-"]
    assert tokens(plan.stdout.splitlines()[2]) == row
    assert carry.exit_code == 1
    assert carry.stderr.splitlines()[1] == "#1 todo common [red]x[/red] :smile:"
