"""lb log rm."""

import os
from collections.abc import Callable
from pathlib import Path

import pytest
from typer.testing import Result

from logbook.cli import runtime
from logbook.core import services
from tests.cli.helpers import QUERY_OPTIONS_MESSAGE, OpenDb, assert_rejected, run_ok

RECORD = "#1 2026-10-01 (목) payment/dev 2h — 결제 재시도 로직 구현"
PROMPT = f"삭제할 기록: {RECORD}\n삭제할까요? [y/N]: "
DELETED = f"✔ 삭제했습니다: {RECORD}\n"
CANCELLED = "삭제를 취소했습니다.\n"
NO_INPUT = "확인 입력을 받지 못해 삭제하지 않았습니다. 확인 없이 지우려면 --yes를 붙이세요.\n"
CHANGED = "확인하는 동안 기록이 바뀌어 삭제하지 않았습니다. 다시 실행하세요.\n"


def log_ids(open_db: OpenDb) -> list[int]:
    with open_db() as s:
        return [log.id for log in services.list_worklogs(s)]


def assert_clean_output(result: Result) -> None:
    """프롬프트는 stdout에 없고, Click의 영어 안내(Aborted, invalid input)는 어디에도 없다."""
    assert "삭제할까요?" not in result.stdout
    assert "삭제할 기록" not in result.stdout
    for text in (result.stdout, result.stderr):
        assert "Aborted" not in text
        assert "invalid input" not in text.lower()


@pytest.fixture
def seeded(lb: Callable[..., Result], initialized: Path) -> Path:
    """기록 #1(payment/dev, 오늘), #2(common/meeting)."""
    run_ok(lb, "project", "add", "payment", "결제 서버")
    run_ok(lb, "add", "2h", "결제 재시도 로직 구현", "-p", "payment", "-c", "dev")
    run_ok(lb, "add", "1h", "스프린트 플래닝", "-c", "meeting")
    return initialized


@pytest.mark.parametrize("answer", ["y\n", "yes\n", "Y\n", "YES\n", "ㅛ\n", "ㅛㄷㄴ\n"])
def test_confirmed_delete(
    lb: Callable[..., Result], seeded: Path, open_db: OpenDb, answer: str
) -> None:
    result = lb("log", "rm", "1", input=answer)

    assert result.exit_code == 0, result.stderr
    assert result.stdout == DELETED
    assert result.stderr == PROMPT
    assert_clean_output(result)
    assert log_ids(open_db) == [2]
    assert "결제 재시도 로직 구현" not in run_ok(lb, "log").stdout
    os.replace(seeded, seeded.with_name("moved.db"))


def test_confirmed_delete_with_leading_bom(
    lb: Callable[..., Result], seeded: Path, open_db: OpenDb
) -> None:
    # Windows PowerShell 5.1은 파이프 입력 앞에 UTF-8 BOM을 붙일 수 있다.
    result = lb("log", "rm", "1", input="\ufeffy\n")

    assert result.exit_code == 0, result.stderr
    assert result.stdout == DELETED
    assert log_ids(open_db) == [2]
    os.replace(seeded, seeded.with_name("moved.db"))


@pytest.mark.parametrize("answer", ["n\n", "\n", "maybe\n", "no\n"])
def test_declined_delete(
    lb: Callable[..., Result], seeded: Path, open_db: OpenDb, answer: str
) -> None:
    result = lb("log", "rm", "1", input=answer)

    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr == PROMPT + CANCELLED
    assert_clean_output(result)
    assert log_ids(open_db) == [1, 2]
    os.replace(seeded, seeded.with_name("moved.db"))


def test_no_input_does_not_delete(lb: Callable[..., Result], seeded: Path, open_db: OpenDb) -> None:
    result = lb("log", "rm", "1")

    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr == PROMPT + "\n" + NO_INPUT
    assert_clean_output(result)
    assert log_ids(open_db) == [1, 2]
    os.replace(seeded, seeded.with_name("moved.db"))


@pytest.mark.parametrize("option", ["--yes", "-y"])
def test_yes_skips_prompt(
    lb: Callable[..., Result], seeded: Path, open_db: OpenDb, option: str
) -> None:
    result = lb("log", "rm", "#1", option)

    assert result.exit_code == 0, result.stderr
    assert result.stdout == DELETED
    assert result.stderr == ""
    assert_clean_output(result)
    assert log_ids(open_db) == [2]
    os.replace(seeded, seeded.with_name("moved.db"))


def test_markup_like_note_in_prompt(
    lb: Callable[..., Result], seeded: Path, open_db: OpenDb
) -> None:
    run_ok(lb, "add", "30m", "[bold]x[/bold] :smile:", "-c", "dev")

    result = lb("log", "rm", "3", input="n\n")

    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr.startswith(
        "삭제할 기록: #3 2026-10-01 (목) common/dev 30m — [bold]x[/bold] :smile:\n"
    )
    assert log_ids(open_db) == [1, 2, 3]


def note_of(open_db: OpenDb, log_id: int) -> str:
    with open_db() as s:
        return services.get_worklog(s, log_id).note


def test_reused_id_while_confirming_is_not_deleted(
    lb: Callable[..., Result], seeded: Path, open_db: OpenDb, monkeypatch: pytest.MonkeyPatch
) -> None:
    # 확인하는 동안 다른 터미널이 가장 최근 기록 #2를 지우고 새로 기록해 ID 2가 재사용된 상황
    def confirm_after_reuse(question: str) -> bool:
        with open_db() as s:
            services.delete_worklog(s, 2)
            reused = services.add_worklog(s, minutes=15, note="새 기록", category="dev")
            assert reused.id == 2
        return True

    monkeypatch.setattr(runtime, "confirm", confirm_after_reuse)

    result = lb("log", "rm", "2")

    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr == CHANGED
    assert log_ids(open_db) == [1, 2]
    assert note_of(open_db, 2) == "새 기록"
    os.replace(seeded, seeded.with_name("moved.db"))


def test_edited_while_confirming_is_not_deleted(
    lb: Callable[..., Result], seeded: Path, open_db: OpenDb, monkeypatch: pytest.MonkeyPatch
) -> None:
    def confirm_after_edit(question: str) -> bool:
        with open_db() as s:
            services.update_worklog(s, 1, note="다른 터미널에서 고침")
        return True

    monkeypatch.setattr(runtime, "confirm", confirm_after_edit)

    result = lb("log", "rm", "1")

    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr == CHANGED
    assert log_ids(open_db) == [1, 2]
    os.replace(seeded, seeded.with_name("moved.db"))


def test_deleted_while_confirming_reports_not_found(
    lb: Callable[..., Result], seeded: Path, open_db: OpenDb, monkeypatch: pytest.MonkeyPatch
) -> None:
    def confirm_after_delete(question: str) -> bool:
        with open_db() as s:
            services.delete_worklog(s, 1)
        return True

    monkeypatch.setattr(runtime, "confirm", confirm_after_delete)

    result = lb("log", "rm", "1")

    assert_rejected(result, "기록을 찾을 수 없습니다: #1. 'lb log'로 확인하세요.")
    assert log_ids(open_db) == [2]
    os.replace(seeded, seeded.with_name("moved.db"))


def test_unknown_id_fails_without_prompt(lb: Callable[..., Result], seeded: Path) -> None:
    result = lb("log", "rm", "999", "--yes")

    assert_rejected(result, "기록을 찾을 수 없습니다: #999. 'lb log'로 확인하세요.")
    assert_clean_output(result)
    os.replace(seeded, seeded.with_name("moved.db"))


def test_unknown_id_without_yes_does_not_prompt(lb: Callable[..., Result], seeded: Path) -> None:
    result = lb("log", "rm", "999", input="y\n")

    assert_rejected(result, "기록을 찾을 수 없습니다: #999. 'lb log'로 확인하세요.")


@pytest.mark.parametrize("log_id", ["abc", "99999999999999999999"])
def test_invalid_id(lb: Callable[..., Result], seeded: Path, open_db: OpenDb, log_id: str) -> None:
    result = lb("log", "rm", log_id, "--yes")

    assert_rejected(
        result,
        f"기록 ID가 올바르지 않습니다: '{log_id}'. 숫자로 입력하세요 (예: 128 또는 #128).",
    )
    assert "Traceback" not in result.stderr
    assert log_ids(open_db) == [1, 2]


def test_invalid_id_without_yes(lb: Callable[..., Result], seeded: Path) -> None:
    result = lb("log", "rm", "abc")

    assert_rejected(
        result, "기록 ID가 올바르지 않습니다: 'abc'. 숫자로 입력하세요 (예: 128 또는 #128)."
    )


def test_query_option_before_subcommand_is_rejected(
    lb: Callable[..., Result], seeded: Path, open_db: OpenDb
) -> None:
    result = lb("log", "-w", "last", "rm", "1", "--yes")

    assert_rejected(result, QUERY_OPTIONS_MESSAGE)
    assert log_ids(open_db) == [1, 2]


def test_rm_before_init(lb: Callable[..., Result], tmp_home: Path) -> None:
    db_path = tmp_home / "logbook.db"

    result = lb("log", "rm", "1", "--yes")

    assert_rejected(result, f"데이터베이스가 없습니다: {db_path}. 먼저 'lb init'을 실행하세요.")
    assert not db_path.exists()
