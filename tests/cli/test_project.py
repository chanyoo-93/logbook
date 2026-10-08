"""lb project add|list|archive."""

import os
from collections.abc import Callable
from pathlib import Path

import pytest
from typer.testing import Result

from logbook.core import platform
from tests.cli.helpers import tokens

ARCHIVE_DEFAULT_WARNING = (
    "주의: 보관한 프로젝트가 설정의 default_project입니다: 'payment'. "
    "-p 없이 기록하려면 설정 파일의 default_project를 바꾸세요.\n"
)


def add_payment(lb: Callable[..., Result]) -> None:
    result = lb("project", "add", "payment", "결제 서버", "--color", "#4f46e5")
    assert result.exit_code == 0, result.stderr


def table_rows(stdout: str) -> list[list[str]]:
    return [tokens(line) for line in stdout.splitlines() if line.strip()]


def test_add_with_color(lb: Callable[..., Result], initialized: Path) -> None:
    result = lb("project", "add", "payment", "결제 서버", "--color", "#4f46e5")

    assert result.exit_code == 0, result.stderr
    assert result.stdout == "✔ 프로젝트 추가: payment (결제 서버) #4f46e5\n"
    assert result.stderr == ""
    os.replace(initialized, initialized.with_name("moved.db"))


def test_add_without_color(lb: Callable[..., Result], initialized: Path) -> None:
    result = lb("project", "add", "search", "검색")

    assert result.exit_code == 0, result.stderr
    assert result.stdout == "✔ 프로젝트 추가: search (검색)\n"


def test_add_uses_ascii_mark_when_console_lacks_unicode(
    lb: Callable[..., Result], initialized: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(platform, "supports_unicode", lambda text="": False)

    result = lb("project", "add", "search", "검색")

    assert result.stdout == "v 프로젝트 추가: search (검색)\n"


def test_add_invalid_slug(lb: Callable[..., Result], initialized: Path) -> None:
    result = lb("project", "add", "Pay", "결제")

    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr == (
        "오류: 프로젝트 slug가 올바르지 않습니다: 'Pay'. 영문 소문자나 숫자로 시작하고 "
        "영문 소문자·숫자·'-'·'_'만 쓸 수 있습니다 (최대 32자).\n"
    )


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (["search", " "], "프로젝트 이름이 비어 있습니다. 이름을 입력하세요."),
        (
            ["search", "검색", "--color", "red"],
            "색상이 올바르지 않습니다: 'red'. '#4f46e5'처럼 '#'과 16진수 6자리로 입력하세요.",
        ),
        (
            ["payment", "다른 이름"],
            "프로젝트 'payment'가 이미 존재합니다. 'lb project list'로 확인하세요.",
        ),
    ],
    ids=["blank-name", "bad-color", "duplicate"],
)
def test_add_rejects_with_core_message(
    lb: Callable[..., Result], initialized: Path, args: list[str], message: str
) -> None:
    add_payment(lb)

    result = lb("project", "add", *args)

    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr == f"오류: {message}\n"


def test_add_before_init(lb: Callable[..., Result], tmp_home: Path) -> None:
    db_path = tmp_home / "logbook.db"

    result = lb("project", "add", "payment", "결제 서버")

    assert result.exit_code == 1
    assert result.stdout == ""
    assert (
        result.stderr == f"오류: 데이터베이스가 없습니다: {db_path}. 먼저 'lb init'을 실행하세요.\n"
    )
    assert not db_path.exists()


def test_markup_like_name_is_printed_verbatim(lb: Callable[..., Result], initialized: Path) -> None:
    added = lb("project", "add", "markup", "[bold]x[/bold]")
    listed = lb("project", "list")

    assert added.stdout == "✔ 프로젝트 추가: markup ([bold]x[/bold])\n"
    assert ["markup", "[bold]x[/bold]", "-"] in table_rows(listed.stdout)


def test_list(lb: Callable[..., Result], initialized: Path) -> None:
    add_payment(lb)

    result = lb("project", "list")

    assert result.exit_code == 0, result.stderr
    assert table_rows(result.stdout) == [
        ["slug", "이름", "색상"],
        ["common", "공통", "-"],
        ["payment", "결제 서버", "#4f46e5"],
    ]
    assert result.stderr == ""
    os.replace(initialized, initialized.with_name("moved.db"))


def test_list_hides_archived(lb: Callable[..., Result], initialized: Path) -> None:
    add_payment(lb)
    assert lb("project", "archive", "payment").exit_code == 0

    result = lb("project", "list")

    assert table_rows(result.stdout) == [["slug", "이름", "색상"], ["common", "공통", "-"]]


@pytest.mark.parametrize("flag", ["--all", "-a"])
def test_list_all_shows_status(lb: Callable[..., Result], initialized: Path, flag: str) -> None:
    add_payment(lb)
    assert lb("project", "archive", "payment").exit_code == 0

    result = lb("project", "list", flag)

    assert result.exit_code == 0, result.stderr
    assert table_rows(result.stdout) == [
        ["slug", "이름", "색상", "상태"],
        ["common", "공통", "-", "사용 중"],
        ["payment", "결제 서버", "#4f46e5", "보관"],
    ]


def test_list_has_no_include_all_option(lb: Callable[..., Result], initialized: Path) -> None:
    result = lb("project", "list", "--include-all")

    assert result.exit_code == 2


def test_archive_and_rerun(lb: Callable[..., Result], initialized: Path) -> None:
    add_payment(lb)

    first = lb("project", "archive", "payment")
    second = lb("project", "archive", "payment")

    assert first.exit_code == 0, first.stderr
    assert first.stdout == "✔ 프로젝트 보관: payment (과거 기록은 집계에 계속 포함됩니다)\n"
    assert first.stderr == ""
    assert second.exit_code == 0, second.stderr
    assert second.stdout == "· 이미 보관된 프로젝트입니다: payment\n"
    assert second.stderr == ""
    os.replace(initialized, initialized.with_name("moved.db"))


def test_archive_common_is_rejected(lb: Callable[..., Result], initialized: Path) -> None:
    result = lb("project", "archive", "common")

    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr == (
        "오류: common 프로젝트는 보관할 수 없습니다. "
        "프로젝트와 무관한 업무를 기록하는 기본 프로젝트입니다.\n"
    )


def test_archive_unknown_project(lb: Callable[..., Result], initialized: Path) -> None:
    result = lb("project", "archive", "zzz")

    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr == (
        "오류: 프로젝트 'zzz'가 없습니다. 'lb project list'로 확인하거나, "
        "새 프로젝트라면 'lb project add zzz <이름>'으로 만드세요.\n"
    )


def test_archive_default_project_warns(
    lb: Callable[..., Result], initialized: Path, tmp_home: Path
) -> None:
    (tmp_home / "config.toml").write_text(
        'default_project = "payment"\n', encoding="utf-8", newline="\n"
    )
    add_payment(lb)

    result = lb("project", "archive", "payment")

    assert result.exit_code == 0, result.stderr
    assert result.stdout == "✔ 프로젝트 보관: payment (과거 기록은 집계에 계속 포함됩니다)\n"
    assert result.stderr == ARCHIVE_DEFAULT_WARNING


def test_project_without_args_shows_help(lb: Callable[..., Result], tmp_home: Path) -> None:
    result = lb("project")

    assert result.exit_code == 2
    assert "Usage: lb project" in result.stdout + result.stderr
