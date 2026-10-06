"""logbook.core.platform 단위 테스트."""

import io
import re
import sys
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pyperclip
import pytest

from logbook.core import platform

RESERVED_CHARS = '"*:<>?|/\\' + "".join(chr(i) for i in range(0x20))


class SpyStream:
    """reconfigure 호출을 기록하는 가짜 스트림."""

    def __init__(self, encoding: str | None, errors: str = "strict") -> None:
        self.encoding = encoding
        self.errors = errors
        self.calls: list[dict[str, str]] = []

    def reconfigure(self, **kwargs: str) -> None:
        self.calls.append(kwargs)


class FailingStream(SpyStream):
    """reconfigure가 io.UnsupportedOperation을 던지는 스트림."""

    def reconfigure(self, **kwargs: str) -> None:
        raise io.UnsupportedOperation("not supported")


def _cp949_stream(errors: str = "strict") -> io.TextIOWrapper:
    return io.TextIOWrapper(io.BytesIO(), encoding="cp949", errors=errors)


def _utf8_stream() -> io.TextIOWrapper:
    return io.TextIOWrapper(io.BytesIO(), encoding="utf-8")


# --- data_dir ---------------------------------------------------------------


def test_data_dir_is_logbook_under_home() -> None:
    assert platform.data_dir() == Path.home() / ".logbook"


def test_data_dir_follows_current_home(isolated_home: Path) -> None:
    assert platform.data_dir() == isolated_home / ".logbook"


def test_data_dir_does_not_create_directory() -> None:
    result = platform.data_dir()

    assert not result.exists()


# --- ensure_utf8_console ----------------------------------------------------


def test_ensure_utf8_console_reconfigures_cp949_streams(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stdout = _cp949_stream()
    stderr = _cp949_stream()
    monkeypatch.setattr(sys, "stdout", stdout)
    monkeypatch.setattr(sys, "stderr", stderr)

    platform.ensure_utf8_console()

    assert stdout.encoding == "utf-8"
    assert stderr.encoding == "utf-8"
    stdout.write("✔ 한글")
    stdout.flush()
    buffer = stdout.buffer
    assert isinstance(buffer, io.BytesIO)
    assert buffer.getvalue() == "✔ 한글".encode()


def test_ensure_utf8_console_keeps_errors_handler(monkeypatch: pytest.MonkeyPatch) -> None:
    stderr = _cp949_stream(errors="backslashreplace")
    monkeypatch.setattr(sys, "stdout", _cp949_stream())
    monkeypatch.setattr(sys, "stderr", stderr)

    platform.ensure_utf8_console()

    assert stderr.encoding == "utf-8"
    assert stderr.errors == "backslashreplace"


@pytest.mark.parametrize("encoding", ["utf-8", "UTF8", "cp65001"])
def test_ensure_utf8_console_leaves_utf8_streams_alone(
    monkeypatch: pytest.MonkeyPatch, encoding: str
) -> None:
    stdout = SpyStream(encoding)
    stderr = SpyStream(encoding)
    monkeypatch.setattr(sys, "stdout", stdout)
    monkeypatch.setattr(sys, "stderr", stderr)

    platform.ensure_utf8_console()

    assert stdout.calls == []
    assert stderr.calls == []


@pytest.mark.parametrize("encoding", [None, "no-such-codec"])
def test_ensure_utf8_console_treats_missing_or_unknown_encoding_as_not_utf8(
    monkeypatch: pytest.MonkeyPatch, encoding: str | None
) -> None:
    stdout = SpyStream(encoding, errors="replace")
    monkeypatch.setattr(sys, "stdout", stdout)
    monkeypatch.setattr(sys, "stderr", None)

    platform.ensure_utf8_console()

    assert stdout.calls == [{"encoding": "utf-8", "errors": "replace"}]


def test_ensure_utf8_console_ignores_string_io(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "stdout", io.StringIO())
    monkeypatch.setattr(sys, "stderr", io.StringIO())

    platform.ensure_utf8_console()


def test_ensure_utf8_console_ignores_missing_streams(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)

    platform.ensure_utf8_console()


def test_ensure_utf8_console_swallows_reconfigure_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "stdout", FailingStream("cp949"))
    monkeypatch.setattr(sys, "stderr", FailingStream("cp949"))

    platform.ensure_utf8_console()


# --- supports_unicode -------------------------------------------------------


def test_supports_unicode_true_for_utf8_stream(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "stdout", _utf8_stream())

    assert platform.supports_unicode() is True


def test_supports_unicode_false_for_cp949_default_probe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "stdout", _cp949_stream())

    assert platform.supports_unicode() is False


@pytest.mark.parametrize("text", ["→", "·", "한글"])
def test_supports_unicode_true_for_cp949_encodable_text(
    monkeypatch: pytest.MonkeyPatch, text: str
) -> None:
    monkeypatch.setattr(sys, "stdout", _cp949_stream())

    assert platform.supports_unicode(text) is True


def test_supports_unicode_false_for_em_dash_on_cp949(monkeypatch: pytest.MonkeyPatch) -> None:
    # U+2014(—)는 cp949에 없다 (U+2015 ―만 있음).
    monkeypatch.setattr(sys, "stdout", _cp949_stream())

    assert platform.supports_unicode("—") is False


def test_supports_unicode_true_for_string_io(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "stdout", io.StringIO())

    assert platform.supports_unicode() is True


def test_supports_unicode_false_without_stdout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "stdout", None)

    assert platform.supports_unicode() is False


def test_supports_unicode_false_for_unknown_codec(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "stdout", SpyStream("no-such-codec"))

    assert platform.supports_unicode() is False


# --- symbol -----------------------------------------------------------------


@pytest.mark.parametrize(("supported", "expected"), [(True, "✔"), (False, "v")])
def test_symbol_follows_supports_unicode(
    monkeypatch: pytest.MonkeyPatch, supported: bool, expected: str
) -> None:
    monkeypatch.setattr(platform, "supports_unicode", lambda text="": supported)

    assert platform.symbol("✔", "v") == expected


def test_symbol_falls_back_on_cp949_stdout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "stdout", _cp949_stream())

    assert platform.symbol("✔", "v") == "v"


def test_symbol_uses_unicode_on_utf8_stdout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "stdout", _utf8_stream())

    assert platform.symbol("✔", "v") == "✔"


# --- copy_to_clipboard ------------------------------------------------------


def test_copy_to_clipboard_returns_true_on_success(monkeypatch: pytest.MonkeyPatch) -> None:
    copied: list[str] = []
    monkeypatch.setattr(pyperclip, "copy", copied.append)

    assert platform.copy_to_clipboard("주간업무보고 ✔") is True
    assert copied == ["주간업무보고 ✔"]


@pytest.mark.parametrize("error", [pyperclip.PyperclipException("no clipboard"), OSError("denied")])
def test_copy_to_clipboard_returns_false_on_failure(
    monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    def failing_copy(text: str) -> None:
        raise error

    monkeypatch.setattr(pyperclip, "copy", failing_copy)

    assert platform.copy_to_clipboard("보고서") is False


# --- safe_filename ----------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("a:b*c?d", "a-b-c-d"),
        ("weekly-report-2026-W40.md", "weekly-report-2026-W40.md"),
        ("주간업무보고 2026-W40.md", "주간업무보고 2026-W40.md"),
        ("a/b\\c", "a-b-c"),
        ("a\tb\nc", "a-b-c"),
        ("report. ", "report"),
        ("report...", "report"),
        ("CON", "CON_"),
        ("aux.md", "aux_.md"),
        ("Com1.txt", "Com1_.txt"),
        ("lpt9", "lpt9_"),
        ("nul.tar.gz", "nul_.tar.gz"),
        ("CONIN$", "CONIN$_"),
        ("CONOUT$.log", "CONOUT$_.log"),
        ("com¹.txt", "com¹_.txt"),
        ("aux .md", "aux_ .md"),
        ("console.md", "console.md"),
        ("auxiliary.md", "auxiliary.md"),
        ("com10.txt", "com10.txt"),
        ("", "_"),
        ("...", "_"),
    ],
)
def test_safe_filename(name: str, expected: str) -> None:
    assert platform.safe_filename(name) == expected


@pytest.mark.parametrize("char", list(RESERVED_CHARS))
def test_safe_filename_replaces_each_reserved_char(char: str) -> None:
    assert platform.safe_filename(f"a{char}b") == "a-b"


def test_safe_filename_removes_every_reserved_ascii_char() -> None:
    result = platform.safe_filename("".join(chr(i) for i in range(128)))

    assert not any(char in RESERVED_CHARS for char in result)


# --- timestamp_for_filename -------------------------------------------------


def test_timestamp_for_filename_formats_given_time() -> None:
    assert platform.timestamp_for_filename(datetime(2026, 10, 2, 15, 30, 0)) == "20261002-153000"


def test_timestamp_for_filename_zero_pads() -> None:
    assert platform.timestamp_for_filename(datetime(2026, 1, 2, 3, 4, 5)) == "20260102-030405"


def test_timestamp_for_filename_uses_local_time_for_aware_datetimes() -> None:
    # 같은 순간이면 어느 시간대로 넘겨도 같은 (로컬 시각) 파일명이 나와야 한다.
    in_kst = datetime(2026, 10, 2, 15, 30, 0, tzinfo=timezone(timedelta(hours=9)))
    in_utc = datetime(2026, 10, 2, 6, 30, 0, tzinfo=UTC)

    assert platform.timestamp_for_filename(in_kst) == platform.timestamp_for_filename(in_utc)


def test_timestamp_for_filename_defaults_to_now() -> None:
    before = datetime.now().replace(microsecond=0)

    result = platform.timestamp_for_filename()

    after = datetime.now()
    assert re.fullmatch(r"\d{8}-\d{6}", result)
    assert before <= datetime.strptime(result, "%Y%m%d-%H%M%S") <= after
