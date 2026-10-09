"""lb task add, lb task list."""

import os
from collections.abc import Callable
from pathlib import Path

import pytest
from typer.testing import Result

from logbook.cli import console
from logbook.core import services
from logbook.core.taskstatus import TaskStatus
from tests.cli.helpers import OpenDb, assert_fits, assert_rejected, lines, rows, run_ok, tokens

CATEGORY_LIST = "admin, design, dev, docs, meeting, ops, review, study, support"
HEADER = ["ID", "상태", "프로젝트", "카테고리", "제목", "예상", "실적", "주차", "참조"]
ROW_1 = ["1", "todo", "payment", "design", "환불 API 설계", "4h", "2h 30m", "2026-W40", "#43"]
ROW_2 = ["2", "todo", "common", "-", "권한 정리", "-", "-", "-", "-"]
ROW_3 = ["3", "doing", "payment", "dev", "결제 재시도", "3h", "1h", "2026-W41", "-"]
ROW_4 = ["4", "done", "common", "docs", "문서 정리", "1h", "45m", "2026-W40", "-"]
ROW_5 = ["5", "dropped", "common", "-", "옛 계획", "2h", "-", "2026-W40", "-"]
ROW_6 = ["6", "todo", "old", "-", "옛 작업", "5h", "-", "2026-W40", "-"]
ADD_OUTPUT = "✔ 태스크 추가: #1 payment/design 환불 API 설계 (예상 4h · 2026-W40 · 참조 #43)\n"
STATUS_MESSAGE = (
    "상태가 올바르지 않습니다: 'x'. "
    "todo, doing, done, dropped, all 중에서 쉼표로 구분해 쓰세요 (예: todo,doing)."
)


@pytest.fixture
def projects(lb: Callable[..., Result], initialized: Path) -> Path:
    """payment(사용 중)와 old(보관) 프로젝트가 있는 DB 경로."""
    run_ok(lb, "project", "add", "payment", "결제 서버")
    run_ok(lb, "project", "add", "old", "옛 프로젝트")
    run_ok(lb, "project", "archive", "old")
    return initialized


@pytest.fixture
def seeded(lb: Callable[..., Result], initialized: Path, open_db: OpenDb) -> Path:
    """태스크 6건(todo 2, doing 1, done 1, dropped 1, 보관 프로젝트 todo 1)과 연결 기록."""
    run_ok(lb, "project", "add", "payment", "결제 서버")
    run_ok(lb, "project", "add", "old", "옛 프로젝트")
    add_args = ["-p", "payment", "-c", "design", "--est", "4h", "-w", "this", "--ref", "#43"]
    run_ok(lb, "task", "add", "환불 API 설계", *add_args)
    run_ok(lb, "task", "add", "권한 정리")
    run_ok(lb, "task", "add", "결제 재시도", "-p", "payment", "-c", "dev", "-e", "3h", "-w", "next")
    run_ok(lb, "task", "add", "문서 정리", "-c", "docs", "-e", "1h", "-w", "this")
    run_ok(lb, "task", "add", "옛 계획", "-e", "2h", "-w", "this")
    run_ok(lb, "task", "add", "옛 작업", "-p", "old", "-e", "5h", "-w", "this")
    run_ok(lb, "project", "archive", "old")
    with open_db() as s:
        services.set_task_status(s, 3, TaskStatus.DOING)
        services.set_task_status(s, 4, TaskStatus.DONE)
        services.set_task_status(s, 5, TaskStatus.DROPPED)
    run_ok(lb, "add", "2h", "x", "-t", "1")
    run_ok(lb, "add", "30m", "y", "-t", "1")
    run_ok(lb, "add", "1h", "z", "-t", "3")
    run_ok(lb, "add", "45m", "w", "-t", "4")
    return initialized


# ---------- lb task add ----------


def test_add_with_all_options(lb: Callable[..., Result], projects: Path, open_db: OpenDb) -> None:
    result = lb(
        "task",
        "add",
        "환불 API 설계",
        "-p",
        "payment",
        "-c",
        "design",
        "--est",
        "4h",
        "--week",
        "this",
        "--ref",
        "#43",
    )

    assert result.exit_code == 0, result.stderr
    assert result.stdout == ADD_OUTPUT
    assert result.stderr == ""
    with open_db() as s:
        task = services.get_task(s, 1)
        assert task.project.slug == "payment"
        assert task.category == "design"
        assert task.estimate_minutes == 240
        assert task.planned_week == "2026-W40"
        assert task.external_ref == "#43"
        assert task.due_date is None
        assert task.status == TaskStatus.TODO
    os.replace(projects, projects.with_name("moved.db"))


def test_add_minimal_uses_default_project(lb: Callable[..., Result], initialized: Path) -> None:
    result = lb("task", "add", "권한 정리")

    assert result.exit_code == 0, result.stderr
    assert result.stdout == "✔ 태스크 추가: #1 common 권한 정리\n"
    assert result.stderr == ""


def test_add_default_project_from_config(
    lb: Callable[..., Result], projects: Path, tmp_home: Path
) -> None:
    (tmp_home / "config.toml").write_text(
        'default_project = "payment"\n', encoding="utf-8", newline="\n"
    )

    result = run_ok(lb, "task", "add", "권한 정리")

    assert result.stdout == "✔ 태스크 추가: #1 payment 권한 정리\n"


def test_add_due_date(lb: Callable[..., Result], initialized: Path, open_db: OpenDb) -> None:
    result = run_ok(lb, "task", "add", "배포", "--due", "10-15")

    assert result.stdout == "✔ 태스크 추가: #1 common 배포 (마감 10-15)\n"
    with open_db() as s:
        assert services.get_task(s, 1).due_date is not None
        assert str(services.get_task(s, 1).due_date) == "2026-10-15"


def test_estimate_has_no_upper_limit(
    lb: Callable[..., Result], initialized: Path, open_db: OpenDb
) -> None:
    result = run_ok(lb, "task", "add", "큰 작업", "--est", "40h")

    assert result.stdout == "✔ 태스크 추가: #1 common 큰 작업 (예상 40h)\n"
    with open_db() as s:
        assert services.get_task(s, 1).estimate_minutes == 2400


def test_huge_estimate_is_rejected_in_one_line(
    lb: Callable[..., Result], initialized: Path
) -> None:
    result = lb("task", "add", "T", "--est", "99999999999999999999h")

    assert_rejected(result, "예상 공수가 너무 큽니다. 더 작은 값으로 입력하세요.")


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (["--est", "0m"], "소요 시간은 1분 이상이어야 합니다: '0m'. 예: 30m, 1h"),
        (["--est", "abc"], "시간 형식이 올바르지 않습니다: 'abc'. 예: 2h, 1.5h, 90m, 1h30m, 1:30"),
        (["--week", ""], "주차 형식이 올바르지 않습니다: ''. 예: this, last, next, 2026-W41"),
        (
            ["--week", "2026-W99"],
            "주차 형식이 올바르지 않습니다: '2026-W99'. 예: this, last, next, 2026-W41",
        ),
        (
            ["--due", "13-45"],
            "날짜 형식이 올바르지 않습니다: '13-45'. "
            "예: today, yesterday, mon~sun, 2026-10-01, 10-01",
        ),
        (
            ["-c", "xyz"],
            f"쓸 수 없는 카테고리입니다: 'xyz'. 사용할 수 있는 카테고리: {CATEGORY_LIST}",
        ),
        (
            ["-p", "old"],
            "보관된 프로젝트에는 새 기록이나 태스크를 추가할 수 없습니다: 'old'. "
            "다른 프로젝트를 지정하세요.",
        ),
        (
            ["-p", "nope"],
            "프로젝트를 찾을 수 없습니다: 'nope'. 'lb project list'로 확인하거나, "
            "새 프로젝트라면 'lb project add nope <이름>'으로 만드세요.",
        ),
    ],
    ids=[
        "est-zero",
        "est-format",
        "week-empty",
        "week-range",
        "due-format",
        "bad-category",
        "archived-project",
        "unknown-project",
    ],
)
def test_add_rejects_with_core_message(
    lb: Callable[..., Result], projects: Path, open_db: OpenDb, args: list[str], message: str
) -> None:
    result = lb("task", "add", "x", *args)

    assert_rejected(result, message)
    with open_db() as s:
        assert services.list_tasks(s, include_archived=True) == []
    os.replace(projects, projects.with_name("moved.db"))


def test_add_blank_title(lb: Callable[..., Result], initialized: Path) -> None:
    result = lb("task", "add", "  ")

    assert_rejected(result, "태스크 제목을 입력하세요. 무엇을 할지 한 줄로 적어 주세요.")


def test_add_prints_markup_verbatim(lb: Callable[..., Result], initialized: Path) -> None:
    result = run_ok(lb, "task", "add", "[bold]x[/bold]", "--ref", "[link]")

    assert result.stdout == "✔ 태스크 추가: #1 common [bold]x[/bold] (참조 [link])\n"

    listed = run_ok(lb, "task", "list")
    assert rows(listed) == [["1", "todo", "common", "-", "[bold]x[/bold]", "-", "-", "-", "[link]"]]


def test_add_estimate_is_parsed_before_database(lb: Callable[..., Result], tmp_home: Path) -> None:
    result = lb("task", "add", "x", "--est", "abc")

    assert_rejected(result, "시간 형식이 올바르지 않습니다: 'abc'. 예: 2h, 1.5h, 90m, 1h30m, 1:30")
    assert not (tmp_home / "logbook.db").exists()


# ---------- lb task list ----------


def test_list_defaults_to_open_tasks(lb: Callable[..., Result], seeded: Path) -> None:
    result = run_ok(lb, "task", "list")

    out = lines(result)
    assert out[0] == "태스크 (todo, doing)"
    assert tokens(out[1]) == HEADER
    assert rows(result) == [ROW_1, ROW_3, ROW_2]
    assert out[-1] == "태스크 3건 / 예상 7h / 실적 3h 30m"
    assert len(out) == 6
    assert result.stderr == ""
    os.replace(seeded, seeded.with_name("moved.db"))


def test_list_all_statuses_excludes_archived(lb: Callable[..., Result], seeded: Path) -> None:
    result = run_ok(lb, "task", "list", "-s", "all")

    assert lines(result)[0] == "태스크 (todo, doing, done, dropped)"
    assert rows(result) == [ROW_1, ROW_4, ROW_5, ROW_3, ROW_2]
    assert lines(result)[-1] == "태스크 5건 / 예상 10h / 실적 4h 15m"


def test_list_selected_statuses(lb: Callable[..., Result], seeded: Path) -> None:
    result = run_ok(lb, "task", "list", "--status", "done,dropped")

    assert lines(result)[0] == "태스크 (done, dropped)"
    assert rows(result) == [ROW_4, ROW_5]
    assert lines(result)[-1] == "태스크 2건 / 예상 3h / 실적 45m"


def test_list_bad_status(lb: Callable[..., Result], seeded: Path) -> None:
    result = lb("task", "list", "-s", "x")

    assert_rejected(result, STATUS_MESSAGE)


def test_list_archived_project_by_slug(lb: Callable[..., Result], seeded: Path) -> None:
    result = run_ok(lb, "task", "list", "-p", "old")

    assert lines(result)[0] == "태스크 (todo, doing) · old"
    assert rows(result) == [ROW_6]
    assert lines(result)[-1] == "태스크 1건 / 예상 5h / 실적 0m"


def test_list_week(lb: Callable[..., Result], seeded: Path) -> None:
    result = run_ok(lb, "task", "list", "-w", "this")

    assert lines(result)[0] == "태스크 (todo, doing) · 2026-W40"
    assert rows(result) == [ROW_1]
    assert lines(result)[-1] == "태스크 1건 / 예상 4h / 실적 2h 30m"


def test_list_week_and_project(lb: Callable[..., Result], seeded: Path) -> None:
    result = run_ok(lb, "task", "list", "--week", "next", "--project", "payment")

    assert lines(result)[0] == "태스크 (todo, doing) · 2026-W41 · payment"
    assert rows(result) == [ROW_3]


def test_list_bad_week(lb: Callable[..., Result], seeded: Path) -> None:
    result = lb("task", "list", "-w", "")

    assert_rejected(result, "주차 형식이 올바르지 않습니다: ''. 예: this, last, next, 2026-W41")


def test_list_empty(lb: Callable[..., Result], initialized: Path) -> None:
    result = run_ok(lb, "task", "list")

    assert result.stdout == "태스크 (todo, doing)\n태스크가 없습니다.\n"
    assert result.stderr == ""
    os.replace(initialized, initialized.with_name("moved.db"))


def test_list_narrow_width_falls_back_to_lines(
    lb: Callable[..., Result], initialized: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_ok(lb, "task", "add", "권한 정리", "--est", "1h")
    run_ok(lb, "task", "add", "문서", "-w", "this")
    monkeypatch.setattr(console, "PIPE_WIDTH", 60)

    result = run_ok(lb, "task", "list")

    assert lines(result) == [
        "태스크 (todo, doing)",
        "#2 todo common 문서 · 2026-W40",
        "#1 todo common 권한 정리 · 예상 1h",
        "태스크 2건 / 예상 1h / 실적 0m",
    ]
    assert result.stderr == (
        "터미널 폭이 좁아 표 대신 목록으로 보여 줍니다 (표에는 70칸이 필요합니다).\n"
    )
    assert_fits(result.stdout, 60)


def test_task_without_args_shows_help(lb: Callable[..., Result], tmp_home: Path) -> None:
    result = lb("task")

    assert result.exit_code == 2
    assert "Usage: lb task" in result.stdout + result.stderr


def test_list_before_init(lb: Callable[..., Result], tmp_home: Path) -> None:
    db_path = tmp_home / "logbook.db"

    result = lb("task", "list")

    assert_rejected(result, f"데이터베이스가 없습니다: {db_path}. 먼저 'lb init'을 실행하세요.")
    assert not db_path.exists()
