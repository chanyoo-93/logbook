"""lb stats 주간 집계."""

import os
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import get_args

import pytest
from sqlalchemy.orm import Session
from typer.testing import Result

from logbook.cli import console, render
from logbook.cli.commands.stats import STATS_BY_CHOICES
from logbook.core import services
from logbook.core.config import DEFAULT_CATEGORIES
from logbook.core.errors import InvalidInputError
from logbook.core.weeks import parse_week
from tests.cli.helpers import OpenDb, assert_fits, assert_rejected, run_ok, tokens

W40_HEADING = "2026-W40 (09-28 ~ 10-04)   총 35h / 기록 41건"
MATRIX_HEADER = ["프로젝트", "개발", "코드리뷰", "회의", "행정/기타", "합계"]
BY_X_MESSAGE = "집계 기준이 올바르지 않습니다: 'x'. project, category, day 중 하나를 쓰세요."
BY_EMPTY_MESSAGE = "집계 기준이 올바르지 않습니다: ''. project, category, day 중 하나를 쓰세요."
# 카테고리 9개 각 1건 행렬의 필요 폭: 8 + (4+8+4+4+4+14+8+4+9) + 4 + 2×10
NINE_CATEGORY_WIDTH = 91

# SPEC 5 예시 재현: (프로젝트, 카테고리, 분, 건수). 모두 2026-10-01에 기록한다(41건, 35h).
SPEC_LOGS = (
    ("payment", "dev", 60, 14),
    ("payment", "review", 60, 3),
    ("payment", "meeting", 30, 4),
    ("admin", "dev", 60, 6),
    ("admin", "review", 30, 2),
    ("admin", "meeting", 30, 2),
    ("common", "meeting", 60, 5),
    ("common", "admin", 36, 5),
)


def add_logs(s: Session, today: date, logs: tuple[tuple[str, str, int, int], ...]) -> None:
    for slug, category, minutes, count in logs:
        for number in range(count):
            services.add_worklog(
                s,
                minutes=minutes,
                note=f"{category} {number}",
                project_slug=slug,
                category=category,
                work_date=today,
                today=today,
            )


@pytest.fixture
def seeded(initialized: Path, open_db: OpenDb, today: date) -> Path:
    """SPEC 5 예시 41건을 기록한 DB 경로 (FIXED_TODAY 2026-10-01 목요일)."""
    with open_db() as s:
        services.create_project(s, "payment", "결제 서버")
        services.create_project(s, "admin", "관리자 웹")
        add_logs(s, today, SPEC_LOGS)
    return initialized


@pytest.fixture
def nine_categories(initialized: Path, open_db: OpenDb, today: date) -> Path:
    """payment에 기본 카테고리 9개를 1h씩 기록한 DB 경로."""
    with open_db() as s:
        services.create_project(s, "payment", "결제 서버")
        add_logs(s, today, tuple(("payment", key, 60, 1) for key in DEFAULT_CATEGORIES))
    return initialized


def lines(result: Result) -> list[str]:
    return result.stdout.splitlines()


def table_rows(result: Result) -> list[list[str]]:
    """머리줄 다음 줄부터의 토큰 목록(머리글 포함)."""
    return [tokens(line) for line in lines(result)[1:]]


def test_heading_and_matrix(lb: Callable[..., Result], seeded: Path) -> None:
    result = run_ok(lb, "stats")

    assert lines(result)[0] == W40_HEADING
    assert table_rows(result) == [
        MATRIX_HEADER,
        ["payment", "14h", "3h", "2h", "-", "19h"],
        ["admin", "6h", "1h", "1h", "-", "8h"],
        ["common", "-", "-", "5h", "3h", "8h"],
    ]
    assert result.stderr == ""
    os.replace(seeded, seeded.with_name("moved.db"))


def test_by_project(lb: Callable[..., Result], seeded: Path) -> None:
    result = run_ok(lb, "stats", "--by", "project")

    assert lines(result)[0] == W40_HEADING
    assert table_rows(result) == [
        ["프로젝트", "이름", "시간", "건수", "비율"],
        ["payment", "결제 서버", "19h", "21", "54%"],
        ["admin", "관리자 웹", "8h", "10", "23%"],
        ["common", "공통", "8h", "10", "23%"],
    ]
    assert result.stderr == ""
    os.replace(seeded, seeded.with_name("moved.db"))


def test_by_category(lb: Callable[..., Result], seeded: Path) -> None:
    result = run_ok(lb, "stats", "--by", "category")

    assert lines(result)[0] == W40_HEADING
    assert table_rows(result) == [
        ["카테고리", "이름", "시간", "건수", "비율"],
        ["dev", "개발", "20h", "20", "57%"],
        ["meeting", "회의", "8h", "11", "23%"],
        ["review", "코드리뷰", "4h", "5", "11%"],
        ["admin", "행정/기타", "3h", "5", "9%"],
    ]
    assert result.stderr == ""


def test_by_day(lb: Callable[..., Result], seeded: Path) -> None:
    result = run_ok(lb, "stats", "--by", "day")

    assert lines(result)[0] == W40_HEADING
    assert table_rows(result) == [
        ["날짜", "시간", "건수", "비율"],
        ["09-28 (월)", "-", "0", "-"],
        ["09-29 (화)", "-", "0", "-"],
        ["09-30 (수)", "-", "0", "-"],
        ["10-01 (목)", "35h", "41", "100%"],
        ["10-02 (금)", "-", "0", "-"],
        ["10-03 (토)", "-", "0", "-"],
        ["10-04 (일)", "-", "0", "-"],
    ]
    assert result.stderr == ""


@pytest.mark.parametrize("args", [["-w", "next"], ["-w", "next", "--by", "day"]])
def test_empty_week(lb: Callable[..., Result], seeded: Path, args: list[str]) -> None:
    result = run_ok(lb, "stats", *args)

    assert lines(result) == [
        "2026-W41 (10-05 ~ 10-11)   총 0m / 기록 0건",
        "이 주에는 기록이 없습니다.",
    ]
    assert result.stderr == ""


@pytest.mark.parametrize(
    ("by", "message"), [("x", BY_X_MESSAGE), ("", BY_EMPTY_MESSAGE)], ids=["unknown", "empty"]
)
def test_rejects_unknown_by(
    lb: Callable[..., Result], tmp_home: Path, by: str, message: str
) -> None:
    # init 전이라 DB가 없다. DB 없음 안내가 아니라 집계 기준 오류가 나오면
    # DB를 열기 전에 막은 것이다.
    result = lb("stats", "--by", by)

    assert_rejected(result, message)
    assert not (tmp_home / "logbook.db").exists()


def test_by_choices_match_core(session: Session, today: date) -> None:
    assert get_args(services.StatsBy) == STATS_BY_CHOICES
    with pytest.raises(InvalidInputError) as excinfo:
        services.stats_by(session, parse_week("this", today=today), "x")  # type: ignore[arg-type]
    assert str(excinfo.value) == BY_X_MESSAGE


@pytest.mark.parametrize(
    ("week", "message"),
    [
        ("2026-W99", "주차 형식이 올바르지 않습니다: '2026-W99'. 예: this, last, next, 2026-W41"),
        ("", "주차 형식이 올바르지 않습니다: ''. 예: this, last, next, 2026-W41"),
    ],
    ids=["bad-week", "empty-week"],
)
def test_rejects_bad_week(lb: Callable[..., Result], seeded: Path, week: str, message: str) -> None:
    result = lb("stats", "-w", week)

    assert_rejected(result, message)


def test_sunday_week_start(lb: Callable[..., Result], tmp_home: Path, open_db: OpenDb) -> None:
    (tmp_home / "config.toml").write_text('week_start = "sunday"\n', encoding="utf-8", newline="\n")
    run_ok(lb, "init")
    # 09-27(일)은 일요일 시작 주에 들고, 10-04(일)는 다음 주로 넘어간다.
    with open_db() as s:
        add_logs(s, date(2026, 9, 27), (("common", "meeting", 60, 1),))
        add_logs(s, date(2026, 10, 4), (("common", "meeting", 30, 1),))

    result = run_ok(lb, "stats")

    assert lines(result)[0] == "2026-W40 (09-27 ~ 10-03)   총 1h / 기록 1건"


def test_unknown_category_column_goes_last(
    lb: Callable[..., Result], seeded: Path, open_db: OpenDb, today: date
) -> None:
    with open_db() as s:
        add_logs(s, today, (("payment", "legacy", 60, 1),))

    result = run_ok(lb, "stats")

    rows = table_rows(result)
    assert rows[0] == [*MATRIX_HEADER[:-1], "legacy", "합계"]
    assert rows[1] == ["payment", "14h", "3h", "2h", "-", "1h", "20h"]


def test_required_width_of_nine_category_matrix(
    nine_categories: Path, open_db: OpenDb, today: date
) -> None:
    with open_db() as s:
        result = services.stats_matrix(
            s, parse_week("this", today=today), category_order=tuple(DEFAULT_CATEGORIES)
        )

    width = console.required_width(render.matrix_table(result, DEFAULT_CATEGORIES))

    assert width == NINE_CATEGORY_WIDTH


def test_narrow_width_falls_back_to_lines(
    lb: Callable[..., Result], nine_categories: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(console, "PIPE_WIDTH", NINE_CATEGORY_WIDTH - 1)

    result = run_ok(lb, "stats")

    assert lines(result) == [
        "2026-W40 (09-28 ~ 10-04)   총 9h / 기록 9건",
        "payment  9h  개발 1h · 코드리뷰 1h · 회의 1h · 문서 1h · 설계 1h · 운영/배포/장애 1h"
        " · 문의대응 1h · 학습 1h · 행정/기타 1h",
    ]
    assert result.stderr == (
        "터미널 폭이 좁아 표 대신 목록으로 보여 줍니다 (표에는 91칸이 필요합니다).\n"
    )


def test_exact_width_keeps_matrix(
    lb: Callable[..., Result], nine_categories: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(console, "PIPE_WIDTH", NINE_CATEGORY_WIDTH)

    result = run_ok(lb, "stats")

    assert_fits(result.stdout, NINE_CATEGORY_WIDTH)
    rows = table_rows(result)
    assert rows[0][-1] == "합계"
    assert rows[1][-1] == "9h"
    assert result.stderr == ""


def test_stats_before_init(lb: Callable[..., Result], tmp_home: Path) -> None:
    db_path = tmp_home / "logbook.db"

    result = lb("stats")

    assert_rejected(result, f"데이터베이스가 없습니다: {db_path}. 먼저 'lb init'을 실행하세요.")
    assert not db_path.exists()


@pytest.mark.parametrize(
    ("part", "total", "expected"),
    [(1, 2, "50%"), (1, 8, "13%"), (3, 35, "9%"), (35, 35, "100%"), (0, 35, "-"), (0, 0, "-")],
)
def test_percent_rounds_half_up(part: int, total: int, expected: str) -> None:
    assert render.percent(part, total) == expected
