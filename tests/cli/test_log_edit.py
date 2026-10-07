"""lb log edit."""

import os
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import NamedTuple

import pytest
from typer.testing import Result

from logbook.core import services
from tests.cli.helpers import QUERY_OPTIONS_MESSAGE, OpenDb, assert_rejected, run_ok

CATEGORY_LIST = "admin, design, dev, docs, meeting, ops, review, study, support"
NOTHING_TO_CHANGE_MESSAGE = (
    '바꿀 항목을 하나 이상 지정하세요. 예: lb log edit 128 --minutes 90 --note "회의록 정리"'
)
DATE_FORMAT_ERROR = (
    "날짜 형식이 올바르지 않습니다: '{}'. 예: today, yesterday, mon~sun, 2026-10-01, 10-01"
)
DURATION_FORMAT_ERROR = "시간 형식이 올바르지 않습니다: '{}'. 예: 2h, 1.5h, 90m, 1h30m, 1:30"
EMPTY_NOTE_ERROR = "메모를 입력하세요. 무엇을 했는지 한 줄로 적어 주세요."


class Snapshot(NamedTuple):
    minutes: int
    note: str
    category: str
    project: str
    date: date
    task_id: int | None


# 준비 데이터의 원래 상태 (FIXED_TODAY 2026-10-01 목요일)
LOG_1 = Snapshot(120, "결제 재시도", "dev", "payment", date(2026, 10, 1), 1)
LOG_2 = Snapshot(60, "스프린트 플래닝", "meeting", "common", date(2026, 10, 1), None)


def snapshot(open_db: OpenDb, log_id: int) -> Snapshot:
    with open_db() as s:
        log = services.get_worklog(s, log_id)
        return Snapshot(
            log.minutes, log.note, log.category, log.project.slug, log.date, log.task_id
        )


@pytest.fixture
def seeded(lb: Callable[..., Result], initialized: Path, open_db: OpenDb) -> Path:
    """태스크 #1(payment, design), 프로젝트 search.

    기록 #1(payment/dev, 태스크 #1 연결), #2(common/meeting).
    """
    run_ok(lb, "project", "add", "payment", "결제 서버")
    run_ok(lb, "project", "add", "search", "검색")
    with open_db() as s:
        services.create_task(s, title="환불 API 설계", project_slug="payment", category="design")
    run_ok(lb, "add", "2h", "결제 재시도", "-t", "1", "-c", "dev")
    run_ok(lb, "add", "1h", "스프린트 플래닝", "-c", "meeting")
    return initialized


@pytest.mark.parametrize("args", [["--minutes", "90"], ["-m", "1h30m"]], ids=["long", "short"])
def test_edit_minutes(
    lb: Callable[..., Result], seeded: Path, open_db: OpenDb, args: list[str]
) -> None:
    result = run_ok(lb, "log", "edit", "2", *args)

    assert (
        result.stdout
        == "✔ 수정했습니다: #2 2026-10-01 (목) common/meeting 1h 30m — 스프린트 플래닝\n"
    )
    assert result.stderr == ""
    assert snapshot(open_db, 2) == LOG_2._replace(minutes=90)
    os.replace(seeded, seeded.with_name("moved.db"))


@pytest.mark.parametrize("option", ["--note", "-n"])
def test_edit_note_with_hash_id(
    lb: Callable[..., Result], seeded: Path, open_db: OpenDb, option: str
) -> None:
    result = run_ok(lb, "log", "edit", "#2", option, "새 메모")

    assert result.stdout == "✔ 수정했습니다: #2 2026-10-01 (목) common/meeting 1h — 새 메모\n"
    assert snapshot(open_db, 2) == LOG_2._replace(note="새 메모")


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        (["-c", "docs"], LOG_2._replace(category="docs")),
        (["--category", "docs"], LOG_2._replace(category="docs")),
        (["-d", "yesterday"], LOG_2._replace(date=date(2026, 9, 30))),
        (["--date", "2026-09-30"], LOG_2._replace(date=date(2026, 9, 30))),
        (["-p", "payment"], LOG_2._replace(project="payment")),
        (["--project", "payment"], LOG_2._replace(project="payment")),
    ],
    ids=["category", "category-long", "date", "date-long", "project", "project-long"],
)
def test_edit_single_field(
    lb: Callable[..., Result],
    seeded: Path,
    open_db: OpenDb,
    args: list[str],
    expected: Snapshot,
) -> None:
    run_ok(lb, "log", "edit", "2", *args)

    assert snapshot(open_db, 2) == expected


def test_edit_date_output_uses_new_date(lb: Callable[..., Result], seeded: Path) -> None:
    result = run_ok(lb, "log", "edit", "2", "-d", "yesterday")

    assert (
        result.stdout == "✔ 수정했습니다: #2 2026-09-30 (수) common/meeting 1h — 스프린트 플래닝\n"
    )


@pytest.mark.parametrize("option", ["-t", "--task"])
def test_link_task_moves_project(
    lb: Callable[..., Result], seeded: Path, open_db: OpenDb, option: str
) -> None:
    result = run_ok(lb, "log", "edit", "2", option, "1")

    assert (
        result.stdout == "✔ 수정했습니다: #2 2026-10-01 (목) payment/meeting 1h — 스프린트 플래닝\n"
    )
    assert snapshot(open_db, 2) == LOG_2._replace(project="payment", task_id=1)


def test_no_options_is_rejected(lb: Callable[..., Result], seeded: Path, open_db: OpenDb) -> None:
    result = lb("log", "edit", "2")

    assert_rejected(result, NOTHING_TO_CHANGE_MESSAGE)
    assert snapshot(open_db, 2) == LOG_2


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (["-n", ""], EMPTY_NOTE_ERROR),
        (["-n", "  "], EMPTY_NOTE_ERROR),
        (["-d", ""], DATE_FORMAT_ERROR.format("")),
        (["-d", "foo"], DATE_FORMAT_ERROR.format("foo")),
        (["-m", ""], DURATION_FORMAT_ERROR.format("")),
        (["-m", "abc"], DURATION_FORMAT_ERROR.format("abc")),
        (["-m", "0"], "소요 시간은 1분 이상이어야 합니다: '0'. 예: 30m, 1h"),
        (
            ["-c", "nope"],
            f"카테고리 'nope'는 쓸 수 없습니다. 사용할 수 있는 카테고리: {CATEGORY_LIST}",
        ),
    ],
    ids=[
        "empty-note",
        "blank-note",
        "empty-date",
        "bad-date",
        "empty-minutes",
        "bad-minutes",
        "zero-minutes",
        "unknown-category",
    ],
)
def test_invalid_values_keep_record(
    lb: Callable[..., Result],
    seeded: Path,
    open_db: OpenDb,
    args: list[str],
    message: str,
) -> None:
    result = lb("log", "edit", "2", *args)

    assert_rejected(result, message)
    assert snapshot(open_db, 2) == LOG_2
    os.replace(seeded, seeded.with_name("moved.db"))


def test_linked_record_cannot_move_project(
    lb: Callable[..., Result], seeded: Path, open_db: OpenDb
) -> None:
    result = lb("log", "edit", "1", "-p", "common")

    assert_rejected(
        result,
        "연결된 태스크 #1의 프로젝트('payment')와 다른 프로젝트로 옮길 수 없습니다. "
        "태스크 연결을 해제하거나 같은 프로젝트를 지정하세요.",
    )
    assert snapshot(open_db, 1) == LOG_1


def test_unlink_and_move_project(lb: Callable[..., Result], seeded: Path, open_db: OpenDb) -> None:
    result = run_ok(lb, "log", "edit", "1", "--no-task", "-p", "common")

    assert result.stdout == "✔ 수정했습니다: #1 2026-10-01 (목) common/dev 2h — 결제 재시도\n"
    assert snapshot(open_db, 1) == LOG_1._replace(project="common", task_id=None)


def test_unlink_keeps_project(lb: Callable[..., Result], seeded: Path, open_db: OpenDb) -> None:
    run_ok(lb, "log", "edit", "1", "--no-task")

    assert snapshot(open_db, 1) == LOG_1._replace(task_id=None)


def test_task_and_no_task_together_is_rejected(
    lb: Callable[..., Result], seeded: Path, open_db: OpenDb
) -> None:
    result = lb("log", "edit", "1", "-t", "1", "--no-task")

    assert_rejected(
        result, "태스크를 지정하면서 연결을 해제할 수는 없습니다. 둘 중 하나만 지정하세요."
    )
    assert snapshot(open_db, 1) == LOG_1


def test_no_negated_no_task_option(
    lb: Callable[..., Result], seeded: Path, open_db: OpenDb
) -> None:
    result = lb("log", "edit", "1", "--no-no-task")

    assert result.exit_code == 2
    assert result.stdout == ""
    assert snapshot(open_db, 1) == LOG_1


def test_cannot_move_to_archived_project(
    lb: Callable[..., Result], seeded: Path, open_db: OpenDb
) -> None:
    run_ok(lb, "project", "archive", "search")

    result = lb("log", "edit", "2", "-p", "search")

    assert_rejected(
        result, "보관된 프로젝트로는 기록을 옮길 수 없습니다: 'search'. 다른 프로젝트를 지정하세요."
    )
    assert snapshot(open_db, 2) == LOG_2


def test_unknown_id(lb: Callable[..., Result], seeded: Path) -> None:
    result = lb("log", "edit", "999", "-n", "x")

    assert_rejected(result, "기록 #999가 없습니다. 'lb log'로 확인하세요.")
    os.replace(seeded, seeded.with_name("moved.db"))


@pytest.mark.parametrize("log_id", ["abc", "0", "99999999999999999999"])
def test_invalid_id(lb: Callable[..., Result], seeded: Path, log_id: str) -> None:
    result = lb("log", "edit", log_id, "-n", "x")

    assert_rejected(
        result,
        f"기록 ID가 올바르지 않습니다: '{log_id}'. 숫자로 입력하세요 (예: 128 또는 #128).",
    )


def test_invalid_id_is_checked_before_missing_options(
    lb: Callable[..., Result], seeded: Path
) -> None:
    result = lb("log", "edit", "abc")

    assert_rejected(
        result, "기록 ID가 올바르지 않습니다: 'abc'. 숫자로 입력하세요 (예: 128 또는 #128)."
    )


def test_invalid_task_id(lb: Callable[..., Result], seeded: Path, open_db: OpenDb) -> None:
    result = lb("log", "edit", "2", "-t", "x")

    assert_rejected(
        result, "태스크 ID가 올바르지 않습니다: 'x'. 숫자로 입력하세요 (예: 128 또는 #128)."
    )
    assert snapshot(open_db, 2) == LOG_2


def test_markup_like_note_is_printed_verbatim(
    lb: Callable[..., Result], seeded: Path, open_db: OpenDb
) -> None:
    result = run_ok(lb, "log", "edit", "2", "-n", "[bold]x[/bold]")

    assert (
        result.stdout == "✔ 수정했습니다: #2 2026-10-01 (목) common/meeting 1h — [bold]x[/bold]\n"
    )
    assert snapshot(open_db, 2).note == "[bold]x[/bold]"


def test_query_option_before_subcommand_is_rejected(
    lb: Callable[..., Result], seeded: Path, open_db: OpenDb
) -> None:
    result = lb("log", "-p", "payment", "edit", "1", "-n", "x")

    assert_rejected(result, QUERY_OPTIONS_MESSAGE)
    assert snapshot(open_db, 1) == LOG_1


def test_edit_before_init(lb: Callable[..., Result], tmp_home: Path) -> None:
    db_path = tmp_home / "logbook.db"

    result = lb("log", "edit", "1", "-n", "x")

    assert_rejected(result, f"데이터베이스가 없습니다: {db_path}. 먼저 'lb init'을 실행하세요.")
    assert not db_path.exists()
