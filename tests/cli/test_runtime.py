"""cli.runtime: ID·반올림 파싱, 확인 프롬프트, 지금 시각, 설정·DB 세션."""

import io
import os
import sys
from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import datetime, timedelta
from pathlib import Path

import pytest
import typer
from sqlalchemy.orm import Session

from logbook.cli import runtime
from logbook.core import db
from logbook.core.errors import DatabaseNotInitializedError, InvalidInputError, LogbookError
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


@pytest.mark.parametrize("answer", ["\ufeffy\n", "\ufeffyes\n", "\ufeffㅛ\n"])
def test_confirm_ignores_leading_bom(monkeypatch: pytest.MonkeyPatch, answer: str) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO(answer))

    assert runtime.confirm("삭제할까요?") is True


def test_confirm_rejects_no_after_bom(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO("\ufeffn\n"))

    assert runtime.confirm("삭제할까요?") is False


def _byte_stdin(data: bytes) -> io.TextIOWrapper:
    """파이프 stdin처럼 .buffer를 가진 스트림. 텍스트 계층은 cp1252라 잘못 읽으면 깨진다."""
    return io.TextIOWrapper(io.BytesIO(data), encoding="cp1252")


UTF8_BOM = b"\xef\xbb\xbf"


@pytest.mark.parametrize(
    "data",
    [
        pytest.param(b"y\r\n", id="plain"),
        pytest.param(UTF8_BOM + b"y\r\n", id="single-bom"),
        pytest.param(UTF8_BOM * 2 + b"y\r\n", id="double-bom"),
        pytest.param(UTF8_BOM + "ㅛ\r\n".encode(), id="bom-utf8-hangul"),
        pytest.param("ㅛ\r\n".encode("cp949"), id="cp949-hangul"),
        pytest.param(UTF8_BOM * 2 + "ㅛ\r\n".encode("cp949"), id="double-bom-cp949-hangul"),
    ],
)
def test_confirm_reads_bytes_ignoring_bom_and_codec(
    monkeypatch: pytest.MonkeyPatch, data: bytes
) -> None:
    monkeypatch.setattr(sys, "stdin", _byte_stdin(data))
    # UTF-8로 읽히지 않는 입력은 로캘 인코딩으로 읽는다.
    # CI 러너 로캘(utf-8 등)과 상관없이 한국어 Windows(cp949)를 재현한다.
    monkeypatch.setattr(runtime.locale, "getpreferredencoding", lambda do_setlocale=True: "cp949")

    assert runtime.confirm("삭제할까요?") is True


def test_cp949_hangul_bytes_are_the_expected_pair() -> None:
    assert "ㅛ".encode("cp949") == b"\xa4\xcb"


def test_confirm_bytes_reject_no_after_bom(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "stdin", _byte_stdin(UTF8_BOM * 2 + b"n\r\n"))

    assert runtime.confirm("삭제할까요?") is False


def test_confirm_bytes_empty_is_eof(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "stdin", _byte_stdin(b""))

    assert runtime.confirm("질문") is None
    assert capsys.readouterr().err == "질문 [y/N]: \n"


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


def _require(monkeypatch: pytest.MonkeyPatch, stdin: str) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO(stdin))
    runtime.require_confirmation("옮길까요?", cancelled="취소했습니다.", no_input="입력 없음.")


def test_require_confirmation_returns_on_yes(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _require(monkeypatch, "y\n")

    captured = capsys.readouterr()
    assert captured.err == "옮길까요? [y/N]: "
    assert captured.out == ""


def test_require_confirmation_exits_on_no(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(typer.Exit) as exc_info:
        _require(monkeypatch, "n\n")

    assert exc_info.value.exit_code == 1
    captured = capsys.readouterr()
    assert captured.err == "옮길까요? [y/N]: 취소했습니다.\n"
    assert captured.out == ""


def test_require_confirmation_exits_on_eof(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(typer.Exit) as exc_info:
        _require(monkeypatch, "")

    assert exc_info.value.exit_code == 1
    captured = capsys.readouterr()
    assert captured.err == "옮길까요? [y/N]: \n입력 없음.\n"
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


def test_max_id_matches_core_sqlite_integer_limit() -> None:
    from logbook.core.services.backup_import import MAX_SQLITE_INTEGER

    assert runtime.MAX_ID == MAX_SQLITE_INTEGER


def test_now_is_injected_by_fixture() -> None:
    assert runtime.now() == FIXED_NOW


def test_clock_fixture_moves_runtime_now(clock: Clock) -> None:
    assert clock.advance(minutes=85) == FIXED_NOW + timedelta(minutes=85)

    assert runtime.now() == FIXED_NOW + timedelta(minutes=85)


def test_now_is_local_aware_datetime() -> None:
    moment = _REAL_NOW()

    assert moment.tzinfo is not None
    assert moment.utcoffset() == datetime.now().astimezone().utcoffset()


# --- prepare_output_path / write_text_file ---


def test_prepare_output_path_returns_new_file_path(tmp_path: Path) -> None:
    target = tmp_path / "out.md"

    assert runtime.prepare_output_path(str(target)) == target


def test_prepare_output_path_expands_home(isolated_home: Path) -> None:
    assert runtime.prepare_output_path("~/주간.md") == isolated_home / "주간.md"


def test_prepare_output_path_rejects_other_user_home() -> None:
    with pytest.raises(InvalidInputError) as exc_info:
        runtime.prepare_output_path("~nouser/x.md")

    assert str(exc_info.value) == (
        "경로가 올바르지 않습니다: --out 값 '~nouser/x.md'. "
        "홈 디렉터리 기준 경로는 '~/'로 시작하세요."
    )


@pytest.mark.parametrize("text", ["", "."], ids=["empty", "dot"])
def test_prepare_output_path_rejects_directory(text: str) -> None:
    with pytest.raises(InvalidInputError) as exc_info:
        runtime.prepare_output_path(text)

    assert str(exc_info.value) == (
        f"파일 경로가 아니라 폴더입니다: {Path(text)}. 파일 이름까지 지정하세요."
    )


def test_prepare_output_path_rejects_existing_directory(tmp_path: Path) -> None:
    with pytest.raises(InvalidInputError) as exc_info:
        runtime.prepare_output_path(str(tmp_path))

    assert str(exc_info.value).startswith("파일 경로가 아니라 폴더입니다:")


def test_prepare_output_path_rejects_missing_folder(tmp_path: Path) -> None:
    target = tmp_path / "없는폴더" / "out.md"

    with pytest.raises(InvalidInputError) as exc_info:
        runtime.prepare_output_path(str(target))

    assert str(exc_info.value) == (
        f"저장할 폴더가 없습니다: {target.parent}. 폴더를 먼저 만들거나 다른 경로를 지정하세요."
    )


def test_prepare_output_path_rejects_parent_that_is_file(tmp_path: Path) -> None:
    parent = tmp_path / "file.txt"
    parent.write_text("x", encoding="utf-8")

    with pytest.raises(InvalidInputError) as exc_info:
        runtime.prepare_output_path(str(parent / "out.md"))

    assert str(exc_info.value).startswith(f"저장할 폴더가 없습니다: {parent}.")


# --- prepare_input_path ---


def test_prepare_input_path_returns_existing_file(tmp_path: Path) -> None:
    target = tmp_path / "in.jsonl"
    target.write_text("x", encoding="utf-8")

    assert runtime.prepare_input_path(str(target), "가져올 파일 경로") == target


def test_prepare_input_path_expands_home(isolated_home: Path) -> None:
    (isolated_home / "백업.jsonl").write_text("x", encoding="utf-8")

    assert runtime.prepare_input_path("~/백업.jsonl", "가져올 파일 경로") == (
        isolated_home / "백업.jsonl"
    )


def test_prepare_input_path_names_the_target_for_bad_home() -> None:
    with pytest.raises(InvalidInputError) as exc_info:
        runtime.prepare_input_path("~nouser/x.jsonl", "가져올 파일 경로")

    assert str(exc_info.value).startswith("경로가 올바르지 않습니다: 가져올 파일 경로 값 ")


def test_prepare_input_path_rejects_directory_with_output_wording(tmp_path: Path) -> None:
    with pytest.raises(InvalidInputError) as exc_info:
        runtime.prepare_input_path(str(tmp_path), "가져올 파일 경로")

    assert str(exc_info.value) == (
        f"파일 경로가 아니라 폴더입니다: {tmp_path}. 파일 이름까지 지정하세요."
    )


def test_prepare_input_path_rejects_missing_file(tmp_path: Path) -> None:
    target = tmp_path / "없음.jsonl"

    with pytest.raises(InvalidInputError) as exc_info:
        runtime.prepare_input_path(str(target), "가져올 파일 경로")

    assert str(exc_info.value) == f"가져올 파일이 없습니다: {target}"


def test_write_text_file_writes_utf8_lf(tmp_path: Path) -> None:
    target = tmp_path / "out.md"

    runtime.write_text_file(target, "한글\n둘째\n", yes=False)

    assert target.read_bytes() == "한글\n둘째\n".encode()


def _existing(tmp_path: Path) -> Path:
    target = tmp_path / "out.md"
    target.write_text("old", encoding="utf-8")
    return target


def test_write_text_file_overwrites_after_yes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    target = _existing(tmp_path)
    monkeypatch.setattr(sys, "stdin", io.StringIO("y\n"))

    runtime.write_text_file(target, "new", yes=False)

    assert target.read_text(encoding="utf-8") == "new"
    assert capsys.readouterr().err == f"파일이 이미 있습니다: {target}\n덮어쓸까요? [y/N]: "


def test_write_text_file_keeps_file_on_no(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    target = _existing(tmp_path)
    monkeypatch.setattr(sys, "stdin", io.StringIO("n\n"))

    with pytest.raises(typer.Exit) as exc_info:
        runtime.write_text_file(target, "new", yes=False)

    assert exc_info.value.exit_code == 1
    assert target.read_text(encoding="utf-8") == "old"
    assert capsys.readouterr().err.endswith("덮어쓸까요? [y/N]: 덮어쓰지 않았습니다.\n")


def test_write_text_file_keeps_file_on_eof(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    target = _existing(tmp_path)
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))

    with pytest.raises(typer.Exit) as exc_info:
        runtime.write_text_file(target, "new", yes=False)

    assert exc_info.value.exit_code == 1
    assert target.read_text(encoding="utf-8") == "old"
    assert capsys.readouterr().err.endswith(
        "확인 입력을 받지 못해 덮어쓰지 않았습니다. 확인 없이 덮어쓰려면 --yes를 붙이세요.\n"
    )


def test_write_text_file_yes_skips_prompt(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    target = _existing(tmp_path)

    runtime.write_text_file(target, "new", yes=True)

    assert target.read_text(encoding="utf-8") == "new"
    assert capsys.readouterr().err == ""


def test_write_text_file_reports_os_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "out.md"

    def deny(self: Path, *args: object, **kwargs: object) -> int:
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(Path, "write_text", deny)

    with pytest.raises(LogbookError) as exc_info:
        runtime.write_text_file(target, "x", yes=False)

    assert str(exc_info.value) == f"파일을 저장하지 못했습니다: {target} (Permission denied)."


def test_write_text_file_os_error_without_strerror(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "out.md"

    def fail(self: Path, *args: object, **kwargs: object) -> int:
        raise OSError("x")

    monkeypatch.setattr(Path, "write_text", fail)

    with pytest.raises(LogbookError) as exc_info:
        runtime.write_text_file(target, "x", yes=False)

    assert str(exc_info.value) == f"파일을 저장하지 못했습니다: {target} (x)."
