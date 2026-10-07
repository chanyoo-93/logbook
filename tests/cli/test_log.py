"""lb log 목록."""

import os
from collections.abc import Callable
from datetime import date
from pathlib import Path

import pytest
from typer.testing import Result

from logbook.cli import console, render
from logbook.core import services
from logbook.core.weeks import parse_week
from tests.cli.helpers import OpenDb, assert_fits, assert_rejected, run_ok, tokens

HEADER = ["ID", "날짜", "프로젝트", "카테고리", "시간", "메모", "Task"]
ROW_1 = ["1", "09-30 (수)", "payment", "ops", "30m", "장애 대응", "-"]
ROW_2 = ["2", "10-01 (목)", "payment", "dev", "2h", "결제 재시도 로직 구현", "#1"]
ROW_3 = ["3", "10-01 (목)", "common", "meeting", "1h", "스프린트 플래닝", "-"]
ROW_4 = ["4", "09-22 (화)", "common", "docs", "1h", "회의록 정리", "-"]
W40_HEADING = "2026-W40 (09-28 ~ 10-04)"
W39_HEADING = "2026-W39 (09-21 ~ 09-27)"
CATEGORY_LIST = "admin, design, dev, docs, meeting, ops, review, study, support"
# 기본 3건 기록 표의 필요 폭: 2+10+8+8+4+10+4 + 2×6
W40_TABLE_WIDTH = 58


@pytest.fixture
def seeded(lb: Callable[..., Result], initialized: Path, open_db: OpenDb) -> Path:
    """준비 데이터 4건을 기록한 DB 경로 (FIXED_TODAY 2026-10-01 목요일)."""
    run_ok(lb, "project", "add", "payment", "결제 서버")
    run_ok(lb, "add", "30m", "장애 대응", "-p", "payment", "-c", "ops", "-d", "yesterday")
    with open_db() as s:
        services.create_task(s, title="결제 재시도", project_slug="payment", category="dev")
    run_ok(lb, "add", "2h", "결제 재시도 로직 구현", "-p", "payment", "-c", "dev", "-t", "1")
    run_ok(lb, "add", "1h", "스프린트 플래닝", "-c", "meeting")
    run_ok(lb, "add", "1h", "회의록 정리", "-c", "docs", "-d", "2026-09-22")
    return initialized


def lines(result: Result) -> list[str]:
    return result.stdout.splitlines()


def rows(result: Result) -> list[list[str]]:
    """표의 데이터 행(첫 토큰이 ID인 줄)의 토큰 목록."""
    return [tokens(line) for line in lines(result) if tokens(line)[0].isdigit()]


def row_ids(result: Result) -> list[str]:
    return [row[0] for row in rows(result)]


def test_default_is_this_week(lb: Callable[..., Result], seeded: Path) -> None:
    result = run_ok(lb, "log")

    out = lines(result)
    assert out[0] == W40_HEADING
    assert tokens(out[1]) == HEADER
    assert rows(result) == [ROW_1, ROW_2, ROW_3]
    assert out[-1] == "합계 3h 30m / 기록 3건"
    assert len(out) == 6
    assert result.stderr == ""
    os.replace(seeded, seeded.with_name("moved.db"))


@pytest.mark.parametrize("week", ["last", "2026-W39"])
def test_week_option(lb: Callable[..., Result], seeded: Path, week: str) -> None:
    result = run_ok(lb, "log", "--week", week)

    assert lines(result)[0] == W39_HEADING
    assert rows(result) == [ROW_4]
    assert lines(result)[-1] == "합계 1h / 기록 1건"


def test_short_week_option(lb: Callable[..., Result], seeded: Path) -> None:
    result = run_ok(lb, "log", "-w", "2026-W39")

    assert row_ids(result) == ["4"]


def test_date_option(lb: Callable[..., Result], seeded: Path) -> None:
    result = run_ok(lb, "log", "-d", "today")

    assert lines(result)[0] == "2026-10-01 (목)"
    assert rows(result) == [ROW_2, ROW_3]
    assert lines(result)[-1] == "합계 3h / 기록 2건"


@pytest.mark.parametrize(
    ("args", "expected"),
    [(["-p", "payment"], ["1", "2"]), (["-c", "meeting"], ["3"])],
    ids=["project", "category"],
)
def test_filters(
    lb: Callable[..., Result], seeded: Path, args: list[str], expected: list[str]
) -> None:
    result = run_ok(lb, "log", *args)

    assert row_ids(result) == expected
    assert result.stderr == ""


def test_unknown_category_warns_and_still_lists(lb: Callable[..., Result], seeded: Path) -> None:
    result = run_ok(lb, "log", "-c", "nope")

    assert result.stdout == f"{W40_HEADING}\n기록이 없습니다.\n"
    assert result.stderr == (
        f"주의: 설정에 없는 카테고리입니다: 'nope'. 사용할 수 있는 카테고리: {CATEGORY_LIST}\n"
    )


def test_archived_project_logs_are_listed(lb: Callable[..., Result], seeded: Path) -> None:
    run_ok(lb, "project", "archive", "payment")

    result = run_ok(lb, "log")

    assert rows(result) == [ROW_1, ROW_2, ROW_3]


def test_archived_project_filter(lb: Callable[..., Result], seeded: Path) -> None:
    run_ok(lb, "project", "archive", "payment")

    result = run_ok(lb, "log", "-p", "payment")

    assert row_ids(result) == ["1", "2"]


def test_empty_week(lb: Callable[..., Result], seeded: Path) -> None:
    result = run_ok(lb, "log", "-w", "2026-W41")

    assert result.stdout == "2026-W41 (10-05 ~ 10-11)\n기록이 없습니다.\n"
    assert result.stderr == ""


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (
            ["-w", "2026-W99"],
            "주차 형식이 올바르지 않습니다: '2026-W99'. 예: this, last, next, 2026-W41",
        ),
        (
            ["-d", "foo"],
            "날짜 형식이 올바르지 않습니다: 'foo'. "
            "예: today, yesterday, mon~sun, 2026-10-01, 10-01",
        ),
        (
            ["-p", "nope"],
            "프로젝트 'nope'가 없습니다. 'lb project list'로 확인하거나, "
            "새 프로젝트라면 'lb project add nope <이름>'으로 만드세요.",
        ),
        (["-w", ""], "주차 형식이 올바르지 않습니다: ''. 예: this, last, next, 2026-W41"),
        (
            ["-d", ""],
            "날짜 형식이 올바르지 않습니다: ''. 예: today, yesterday, mon~sun, 2026-10-01, 10-01",
        ),
        (
            ["-w", "last", "-d", "today"],
            "--week와 --date는 함께 쓸 수 없습니다. 하나만 지정하세요.",
        ),
    ],
    ids=["bad-week", "bad-date", "unknown-project", "empty-week", "empty-date", "week-and-date"],
)
def test_rejects_with_message(
    lb: Callable[..., Result], seeded: Path, args: list[str], message: str
) -> None:
    result = lb("log", *args)

    assert_rejected(result, message)
    os.replace(seeded, seeded.with_name("moved.db"))


def test_markup_like_note_is_printed_verbatim(lb: Callable[..., Result], initialized: Path) -> None:
    run_ok(lb, "add", "1h", "[/api] fix", "-c", "dev")

    result = run_ok(lb, "log")

    assert rows(result) == [["1", "10-01 (목)", "common", "dev", "1h", "[/api] fix", "-"]]


def test_required_width_of_default_table(seeded: Path, open_db: OpenDb, today: date) -> None:
    with open_db() as s:
        logs = services.list_worklogs(s, week=parse_week("this", today=today))
        width = console.required_width(render.worklog_table(logs))

    assert width == W40_TABLE_WIDTH


def test_narrow_width_falls_back_to_lines(
    lb: Callable[..., Result], seeded: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(console, "PIPE_WIDTH", W40_TABLE_WIDTH - 1)

    result = run_ok(lb, "log")

    assert lines(result) == [
        W40_HEADING,
        "#1 09-30 (수) payment/ops 30m — 장애 대응",
        "#2 10-01 (목) payment/dev 2h — 결제 재시도 로직 구현 [#1]",
        "#3 10-01 (목) common/meeting 1h — 스프린트 플래닝",
        "합계 3h 30m / 기록 3건",
    ]
    assert result.stderr == (
        "터미널 폭이 좁아 표 대신 목록으로 보여 줍니다 (표에는 58칸이 필요합니다).\n"
    )


def test_exact_width_keeps_table(
    lb: Callable[..., Result], seeded: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(console, "PIPE_WIDTH", W40_TABLE_WIDTH)

    result = run_ok(lb, "log")

    assert_fits(result.stdout, W40_TABLE_WIDTH)
    assert tokens(lines(result)[1])[-1] == "Task"
    assert [row[-1] for row in rows(result)] == ["-", "#1", "-"]
    assert result.stderr == ""


def test_long_note_folds_inside_table(
    lb: Callable[..., Result], seeded: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    note = "가" * 60
    run_ok(lb, "add", "15m", note, "-c", "dev")
    monkeypatch.setattr(console, "PIPE_WIDTH", 80)

    result = run_ok(lb, "log")

    assert result.stderr == ""
    assert tokens(lines(result)[1]) == HEADER
    assert_fits(result.stdout, 80)
    assert result.stdout.count("가") == len(note)
    assert row_ids(result) == ["1", "2", "3", "5"]
    assert [row[-1] for row in rows(result)] == ["-", "#1", "-", "-"]


def test_long_note_stays_on_one_line_in_pipe(lb: Callable[..., Result], seeded: Path) -> None:
    note = ("가나다라 " * 40)[:199] + "끝"
    run_ok(lb, "add", "15m", note, "-c", "dev")

    result = run_ok(lb, "log")

    matching = [line for line in lines(result) if note in line]
    assert len(matching) == 1
    assert tokens(matching[0])[:2] == ["5", "10-01 (목)"]


def test_log_before_init(lb: Callable[..., Result], tmp_home: Path) -> None:
    db_path = tmp_home / "logbook.db"

    result = lb("log")

    assert_rejected(result, f"데이터베이스가 없습니다: {db_path}. 먼저 'lb init'을 실행하세요.")
    assert not db_path.exists()
