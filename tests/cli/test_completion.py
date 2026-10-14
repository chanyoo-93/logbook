"""셸 자동완성 후보 함수와 Typer 연결 테스트(실제 --install-completion은 실행하지 않는다)."""

from collections.abc import Callable
from pathlib import Path

import pytest
from typer.testing import CliRunner, Result

from logbook.cli import completion
from logbook.cli.main import app
from tests.cli.helpers import FORBIDDEN_MODULES, lb_env, run_import_guard, run_ok

Lb = Callable[..., Result]


@pytest.fixture
def seeded(lb: Lb, initialized: Path) -> Path:
    """활성 프로젝트 pay·pal·web, 보관 프로젝트 old. 태스크는 todo·doing·done."""
    run_ok(lb, "project", "add", "pay", "결제")
    run_ok(lb, "project", "add", "pal", "팔")
    run_ok(lb, "project", "add", "old", "옛날")
    run_ok(lb, "project", "archive", "old")
    run_ok(lb, "task", "add", "열린 일", "-p", "pay")
    run_ok(lb, "task", "add", "진행 중\n두 번째 줄 " + "가" * 80, "-p", "pay")
    run_ok(lb, "task", "add", "끝낸 일", "-p", "pay")
    run_ok(lb, "task", "start", "2")
    run_ok(lb, "task", "done", "3")
    return initialized


def test_complete_project_returns_active_with_prefix(seeded: Path) -> None:
    assert completion.complete_project("pa") == [("pal", "팔"), ("pay", "결제")]


def test_complete_project_without_prefix_excludes_archived(seeded: Path) -> None:
    slugs = [slug for slug, _ in completion.complete_project("")]

    assert slugs == ["common", "pal", "pay"]


def test_complete_archived_project(seeded: Path) -> None:
    assert completion.complete_archived_project("") == [("old", "옛날")]


def test_complete_any_project_includes_archived(seeded: Path) -> None:
    slugs = [slug for slug, _ in completion.complete_any_project("")]

    assert slugs == ["common", "old", "pal", "pay"]


def test_complete_task_id_lists_open_tasks_only(seeded: Path) -> None:
    result = completion.complete_task_id("")

    assert [task_id for task_id, _ in result] == ["1", "2"]
    assert result[0][1] == "열린 일"


def test_complete_task_id_keeps_hash_prefix_and_truncates_title(seeded: Path) -> None:
    result = completion.complete_task_id("#")

    assert [task_id for task_id, _ in result] == ["#1", "#2"]
    title = result[1][1]
    assert "\n" not in title
    assert len(title) == completion.MAX_TITLE_LENGTH
    assert title.startswith("진행 중 두 번째 줄 ")


def test_complete_task_id_filters_by_incomplete(seeded: Path) -> None:
    assert [task_id for task_id, _ in completion.complete_task_id("2")] == ["2"]


def test_returns_empty_without_database(tmp_home: Path) -> None:
    assert completion.complete_project("") == []
    assert completion.complete_task_id("") == []


def test_returns_empty_on_broken_config(tmp_home: Path) -> None:
    (tmp_home / "config.toml").write_text("not = [valid", encoding="utf-8", newline="\n")

    assert completion.complete_project("") == []


def test_returns_empty_when_database_is_old_version(tmp_home: Path) -> None:
    from tests.helpers import make_v1_database

    make_v1_database(tmp_home / "logbook.db")

    assert completion.complete_project("") == []


def bash_complete(words: str, cword: int) -> list[str]:
    """bash 완성 출력(줄마다 후보 하나)을 줄 단위로 돌려준다."""
    result = CliRunner().invoke(
        app,
        [],
        prog_name="lb",
        env={"_LB_COMPLETE": "complete_bash", "COMP_WORDS": words, "COMP_CWORD": str(cword)},
    )
    return result.output.splitlines()


def test_bash_completion_lists_project_slugs(seeded: Path) -> None:
    assert bash_complete("lb add 1h x -p ", 5) == ["common", "pal", "pay"]


def test_bash_completion_lists_task_ids(seeded: Path) -> None:
    assert bash_complete("lb task start ", 3) == ["1", "2"]


def test_bash_completion_for_timer_start_task_option(seeded: Path) -> None:
    assert bash_complete("lb start -t ", 3) == ["1", "2"]


def test_bash_completion_for_project_subcommands(seeded: Path) -> None:
    assert bash_complete("lb project unarchive ", 3) == ["old"]
    assert bash_complete("lb project archive ", 3) == ["common", "pal", "pay"]
    assert bash_complete("lb task list -p ", 4) == ["common", "old", "pal", "pay"]


def test_help_shows_completion_options(lb: Lb) -> None:
    output = run_ok(lb, "--help").stdout

    assert "--install-completion" in output
    assert "--show-completion" in output


@pytest.mark.parametrize("args", [["--help"], ["task", "start", "--help"]])
def test_completion_import_does_not_load_heavy_modules(tmp_path: Path, args: list[str]) -> None:
    guard = run_import_guard(args, env=lb_env(tmp_path, "utf-8"), cwd=tmp_path)

    assert guard.loaded == [], f"금지 모듈 로드됨: {guard.loaded} ({FORBIDDEN_MODULES})"
    assert guard.exit_code == 0, guard.stderr
