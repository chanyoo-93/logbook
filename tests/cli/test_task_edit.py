"""lb task edit."""

import os
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import NamedTuple

import pytest
from typer.testing import Result

from logbook.core import services
from tests.cli.helpers import OpenDb, assert_rejected, run_ok

CATEGORY_LIST = "admin, design, dev, docs, meeting, ops, review, study, support"
NOTHING_TO_CHANGE_MESSAGE = (
    "바꿀 항목을 하나 이상 지정하세요. 예: lb task edit 43 --est 6h --week next"
)


class Snapshot(NamedTuple):
    title: str
    category: str | None
    estimate_minutes: int | None
    planned_week: str | None
    due_date: date | None
    external_ref: str | None


# 준비 데이터의 원래 상태 (FIXED_TODAY 2026-10-01 목요일, 이번 주 2026-W40)
TASK_1 = Snapshot("환불 API 설계", "design", 240, "2026-W40", date(2026, 10, 15), "#43")


def snapshot(open_db: OpenDb, task_id: int) -> Snapshot:
    with open_db() as s:
        task = services.get_task(s, task_id)
        return Snapshot(
            task.title,
            task.category,
            task.estimate_minutes,
            task.planned_week,
            task.due_date,
            task.external_ref,
        )


@pytest.fixture
def seeded(lb: Callable[..., Result], initialized: Path) -> Path:
    """payment 프로젝트의 태스크 #1(모든 선택 필드 지정)."""
    run_ok(lb, "project", "add", "payment", "결제 서버")
    run_ok(
        lb,
        "task",
        "add",
        "환불 API 설계",
        "-p",
        "payment",
        "-c",
        "design",
        "--est",
        "4h",
        "-w",
        "this",
        "--ref",
        "#43",
        "--due",
        "10-15",
    )
    return initialized


def test_edit_est_and_week(lb: Callable[..., Result], seeded: Path, open_db: OpenDb) -> None:
    result = run_ok(lb, "task", "edit", "1", "--est", "6h", "--week", "next")

    assert result.stdout == (
        "✔ 수정했습니다: #1 payment/design 환불 API 설계 "
        "(예상 6h · 2026-W41 · 참조 #43 · 마감 10-15)\n"
    )
    assert result.stderr == ""
    assert snapshot(open_db, 1) == TASK_1._replace(estimate_minutes=360, planned_week="2026-W41")
    os.replace(seeded, seeded.with_name("moved.db"))


def test_edit_title(lb: Callable[..., Result], seeded: Path, open_db: OpenDb) -> None:
    result = run_ok(lb, "task", "edit", "#1", "--title", "새 제목")

    assert result.stdout.startswith("✔ 수정했습니다: #1 payment/design 새 제목 (")
    assert snapshot(open_db, 1) == TASK_1._replace(title="새 제목")


def test_edit_short_options(lb: Callable[..., Result], seeded: Path, open_db: OpenDb) -> None:
    run_ok(lb, "task", "edit", "1", "-c", "dev", "-e", "90m", "-w", "last")

    assert snapshot(open_db, 1) == TASK_1._replace(
        category="dev", estimate_minutes=90, planned_week="2026-W39"
    )


def test_edit_ref_and_due(lb: Callable[..., Result], seeded: Path, open_db: OpenDb) -> None:
    run_ok(lb, "task", "edit", "1", "--ref", "JIRA-7", "--due", "2026-11-02")

    assert snapshot(open_db, 1) == TASK_1._replace(
        external_ref="JIRA-7", due_date=date(2026, 11, 2)
    )


def test_clear_week_and_ref(lb: Callable[..., Result], seeded: Path, open_db: OpenDb) -> None:
    result = run_ok(lb, "task", "edit", "1", "--no-week", "--no-ref")

    assert (
        result.stdout == "✔ 수정했습니다: #1 payment/design 환불 API 설계 (예상 4h · 마감 10-15)\n"
    )
    assert snapshot(open_db, 1) == TASK_1._replace(planned_week=None, external_ref=None)


def test_clear_all(lb: Callable[..., Result], seeded: Path, open_db: OpenDb) -> None:
    result = run_ok(
        lb, "task", "edit", "1", "--no-category", "--no-est", "--no-week", "--no-ref", "--no-due"
    )

    assert result.stdout == "✔ 수정했습니다: #1 payment 환불 API 설계\n"
    assert snapshot(open_db, 1) == Snapshot("환불 API 설계", None, None, None, None, None)


@pytest.mark.parametrize(
    ("args", "names"),
    [
        (["-c", "dev", "--no-category"], ("--category", "--no-category")),
        (["--est", "1h", "--no-est"], ("--est", "--no-est")),
        (["--week", "next", "--no-week"], ("--week", "--no-week")),
        (["--ref", "x", "--no-ref"], ("--ref", "--no-ref")),
        (["--due", "10-20", "--no-due"], ("--due", "--no-due")),
    ],
    ids=["category", "est", "week", "ref", "due"],
)
def test_value_and_clear_conflict(
    lb: Callable[..., Result],
    seeded: Path,
    open_db: OpenDb,
    args: list[str],
    names: tuple[str, str],
) -> None:
    result = lb("task", "edit", "1", *args)

    assert_rejected(result, f"{names[0]}와 {names[1]}는 함께 쓸 수 없습니다. 하나만 지정하세요.")
    assert snapshot(open_db, 1) == TASK_1
    os.replace(seeded, seeded.with_name("moved.db"))


def test_no_options_is_rejected(lb: Callable[..., Result], seeded: Path, open_db: OpenDb) -> None:
    result = lb("task", "edit", "1")

    assert_rejected(result, NOTHING_TO_CHANGE_MESSAGE)
    assert snapshot(open_db, 1) == TASK_1


def test_empty_title(lb: Callable[..., Result], seeded: Path, open_db: OpenDb) -> None:
    result = lb("task", "edit", "1", "--title", "")

    assert_rejected(result, "태스크 제목을 입력하세요. 무엇을 할지 한 줄로 적어 주세요.")
    assert snapshot(open_db, 1) == TASK_1


@pytest.mark.parametrize("task_id", ["abc", "0", "99999999999999999999"])
def test_invalid_id(lb: Callable[..., Result], seeded: Path, task_id: str) -> None:
    result = lb("task", "edit", task_id, "--est", "1h")

    assert_rejected(
        result,
        f"태스크 ID가 올바르지 않습니다: '{task_id}'. 숫자로 입력하세요 (예: 128 또는 #128).",
    )


def test_unknown_id(lb: Callable[..., Result], seeded: Path) -> None:
    result = lb("task", "edit", "9", "--est", "1h")

    assert_rejected(result, "태스크 #9가 없습니다. 'lb task list'로 확인하세요.")


def test_unknown_category(lb: Callable[..., Result], seeded: Path, open_db: OpenDb) -> None:
    result = lb("task", "edit", "1", "-c", "xyz")

    assert_rejected(
        result, f"카테고리 'xyz'는 쓸 수 없습니다. 사용할 수 있는 카테고리: {CATEGORY_LIST}"
    )
    assert snapshot(open_db, 1) == TASK_1


def test_project_option_is_not_supported(
    lb: Callable[..., Result], seeded: Path, open_db: OpenDb
) -> None:
    result = lb("task", "edit", "1", "-p", "payment")

    assert result.exit_code == 2
    assert result.stdout == ""
    assert snapshot(open_db, 1) == TASK_1


def test_no_negated_option_is_not_created(
    lb: Callable[..., Result], seeded: Path, open_db: OpenDb
) -> None:
    result = lb("task", "edit", "1", "--no-no-week")

    assert result.exit_code == 2
    assert snapshot(open_db, 1) == TASK_1


def test_estimate_has_no_upper_limit(
    lb: Callable[..., Result], seeded: Path, open_db: OpenDb
) -> None:
    run_ok(lb, "task", "edit", "1", "--est", "40h")

    assert snapshot(open_db, 1).estimate_minutes == 2400


def test_markup_like_title_is_printed_verbatim(lb: Callable[..., Result], seeded: Path) -> None:
    result = run_ok(lb, "task", "edit", "1", "--title", "[bold]x[/bold]")

    assert result.stdout.startswith("✔ 수정했습니다: #1 payment/design [bold]x[/bold] (")


def test_edit_before_init(lb: Callable[..., Result], tmp_home: Path) -> None:
    db_path = tmp_home / "logbook.db"

    result = lb("task", "edit", "1", "--est", "1h")

    assert_rejected(result, f"데이터베이스가 없습니다: {db_path}. 먼저 'lb init'을 실행하세요.")
    assert not db_path.exists()
