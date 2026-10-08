"""cli.runtime: ID·반올림 파싱, 확인 프롬프트, 지금 시각, 설정·DB 세션."""

import io
import os
import sys
from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from logbook.cli import runtime
from logbook.core import db
from logbook.core.errors import DatabaseNotInitializedError, InvalidInputError
from tests.cli.helpers import FIXED_NOW, Clock

# deterministic_cli가 고정하기 전의 runtime.now (모듈 import 시점에 잡아 둔다)
_REAL_NOW = runtime.now


def id_error(text: str, what: str = "기록") -> str:
    return f"{what} ID가 올바르지 않습니다: '{text}'. 숫자로 입력하세요 (예: 128 또는 #128)."


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("128", 128),
        ("#128", 128),
        (" 7 ", 7),
        ("9223372036854775807", 2**63 - 1),
    ],
)
def test_parse_id_accepts_valid_ids(text: str, expected: int) -> None:
    assert runtime.parse_id(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "abc",
        "0",
        "-1",
        "１２",  # 전각 숫자
        "",
        "#",
        "9223372036854775808",  # 2**63
        "9" * 20,
        "9" * 5000,  # int() 자릿수 한도를 넘는 입력
    ],
    ids=["letters", "zero", "negative", "fullwidth", "empty", "hash", "max+1", "20-digits", "5000"],
)
def test_parse_id_rejects_invalid_ids(text: str) -> None:
    with pytest.raises(InvalidInputError) as exc_info:
        runtime.parse_id(text)

    assert str(exc_info.value) == id_error(text)


def test_parse_id_names_the_target() -> None:
    with pytest.raises(InvalidInputError) as exc_info:
        runtime.parse_id("x", "태스크")

    assert str(exc_info.value) == id_error("x", "태스크")


@pytest.mark.parametrize("answer", ["y\n", "YES\n", "ㅛ\n", "ㅛㄷㄴ\n"])
def test_confirm_accepts_yes(monkeypatch: pytest.MonkeyPatch, answer: str) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO(answer))

    assert runtime.confirm("삭제할까요?") is True


@pytest.mark.parametrize("answer", ["n\n", "\n", "maybe\n"])
def test_confirm_rejects_other_answers(monkeypatch: pytest.MonkeyPatch, answer: str) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO(answer))

    assert runtime.confirm("삭제할까요?") is False


def test_confirm_returns_none_on_eof(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))

    assert runtime.confirm("질문") is None

    captured = capsys.readouterr()
    assert captured.err == "질문 [y/N]: \n"
    assert captured.out == ""


def test_confirm_prompts_on_stderr(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO("y\n"))

    runtime.confirm("질문")

    captured = capsys.readouterr()
    assert captured.err == "질문 [y/N]: "
    assert captured.out == ""


def test_today_is_injected_by_fixture(today: object) -> None:
    assert runtime.today() == today


def test_settings_follow_environment(tmp_home: Path) -> None:
    assert runtime.settings().db_path == tmp_home / "logbook.db"


def test_session_without_database_asks_for_init(tmp_home: Path) -> None:
    with pytest.raises(DatabaseNotInitializedError), runtime.session(runtime.settings()):
        pass

    assert not (tmp_home / "logbook.db").exists()


def test_session_disposes_engine(tmp_home: Path) -> None:
    db_path = tmp_home / "logbook.db"
    db.initialize_database(db_path)

    with runtime.session(runtime.settings()) as session:
        assert session.is_active

    os.replace(db_path, db_path.with_name("moved.db"))


def test_open_db_fixture_disposes_engine(
    tmp_home: Path, open_db: Callable[[], AbstractContextManager[Session]]
) -> None:
    db_path = tmp_home / "logbook.db"
    db.initialize_database(db_path)

    with open_db() as session:
        assert session.is_active

    os.replace(db_path, db_path.with_name("moved.db"))


def round_error(text: str) -> str:
    return (
        f"반올림 단위가 올바르지 않습니다: '{text}'. "
        "1~60 사이의 분 단위 숫자로 입력하세요 (예: --round 15)."
    )


@pytest.mark.parametrize(("text", "expected"), [("1", 1), ("15", 15), ("60", 60), ("05", 5)])
def test_parse_round_accepts_one_to_sixty(text: str, expected: int) -> None:
    assert runtime.parse_round(text) == expected


@pytest.mark.parametrize(
    "text",
    ["0", "61", "015", "1.5", "", " ", "-5", "+5", "abc", "١٥", "１５"],
    ids=[
        "zero",
        "61",
        "three-digits",
        "decimal",
        "empty",
        "space",
        "negative",
        "plus",
        "letters",
        "arabic-indic",
        "fullwidth",
    ],
)
def test_parse_round_rejects_invalid(text: str) -> None:
    with pytest.raises(InvalidInputError) as exc_info:
        runtime.parse_round(text)

    assert str(exc_info.value) == round_error(text)


def test_parse_round_limit_matches_core() -> None:
    from logbook.core.services.timer import MAX_ROUND_MINUTES

    assert runtime.MAX_ROUND_MINUTES == MAX_ROUND_MINUTES


def test_now_is_injected_by_fixture() -> None:
    assert runtime.now() == FIXED_NOW


def test_clock_fixture_moves_runtime_now(clock: Clock) -> None:
    assert clock.advance(minutes=85) == FIXED_NOW + timedelta(minutes=85)

    assert runtime.now() == FIXED_NOW + timedelta(minutes=85)


def test_now_is_local_aware_datetime() -> None:
    moment = _REAL_NOW()

    assert moment.tzinfo is not None
    assert moment.utcoffset() == datetime.now().astimezone().utcoffset()
