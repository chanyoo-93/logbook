"""OS 차이를 흡수하는 헬퍼: 데이터 디렉터리, 콘솔 인코딩, 클립보드, 파일명."""

import codecs
import contextlib
import re
import sys
from datetime import datetime
from pathlib import Path

DATA_DIR_NAME = ".logbook"
UNICODE_PROBE = "✔"

# Windows 금지 문자: ASCII 제어 문자와 " * : < > ? | / \
_RESERVED_CHARS = re.compile(r'[\x00-\x1f"*:<>?|/\\]')
# Windows 예약 장치 이름 (CPython 3.13 ntpath.isreserved 기준)
_RESERVED_NAMES = frozenset(
    {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        "CONIN$",
        "CONOUT$",
        *(f"COM{c}" for c in "123456789¹²³"),
        *(f"LPT{c}" for c in "123456789¹²³"),
    }
)


def data_dir() -> Path:
    """데이터 디렉터리 경로 (~/.logbook). 디렉터리를 만들지는 않는다."""
    return Path.home() / DATA_DIR_NAME


def _is_utf8(encoding: object) -> bool:
    if not isinstance(encoding, str):
        return False
    try:
        return codecs.lookup(encoding).name == "utf-8"
    except LookupError:
        return False


def ensure_utf8_console() -> None:
    """stdout/stderr가 UTF-8이 아니면 UTF-8로 재설정을 시도한다. 실패해도 예외 없음."""
    for stream in (sys.stdout, sys.stderr):
        if stream is None or _is_utf8(getattr(stream, "encoding", None)):
            continue
        reconfigure = getattr(stream, "reconfigure", None)
        if not callable(reconfigure):
            continue
        errors = getattr(stream, "errors", None) or "strict"
        # 의도적으로 best-effort: 재설정할 수 없는 스트림은 그대로 둔다.
        with contextlib.suppress(OSError, ValueError):
            reconfigure(encoding="utf-8", errors=errors)


def supports_unicode(text: str = UNICODE_PROBE) -> bool:
    """text를 현재 stdout 인코딩으로 출력할 수 있는지 여부 (errors="strict" 기준)."""
    stream = sys.stdout
    if stream is None:
        return False
    encoding = getattr(stream, "encoding", None)
    if encoding is None:
        return True
    try:
        text.encode(encoding)
    except (UnicodeEncodeError, LookupError):
        return False
    return True


def symbol(unicode_char: str, ascii_fallback: str) -> str:
    """출력 가능하면 unicode_char, 아니면 ascii_fallback."""
    return unicode_char if supports_unicode(unicode_char) else ascii_fallback


def copy_to_clipboard(text: str) -> bool:
    """클립보드에 복사한다. 실패하면 False (안내 문구는 호출자가 출력)."""
    import pyperclip  # CLI 시작 시간을 줄이려고 지연 import

    try:
        pyperclip.copy(text)
    except (pyperclip.PyperclipException, OSError):
        return False
    return True


def safe_filename(name: str) -> str:
    """Windows와 macOS 모두에서 쓸 수 있는 단일 파일명으로 바꾼다.

    금지 문자, 끝의 점·공백, 예약 장치 이름만 처리한다. 길이(255) 제한은 호출자가 지켜야 한다.
    """
    cleaned = _RESERVED_CHARS.sub("-", name).rstrip(". ")
    stem, dot, rest = cleaned.partition(".")
    base = stem.rstrip(" ")
    if base.upper() in _RESERVED_NAMES:
        cleaned = f"{base}_{stem[len(base) :]}{dot}{rest}"
    return cleaned or "_"


def timestamp_for_filename(now: datetime | None = None) -> str:
    """파일명용 로컬 시각 타임스탬프 ("20261002-153000").

    now가 없으면 현재 시각을 쓰고, 시간대가 있는 값(예: UTC로 저장한 시각)은 로컬 시각으로 바꾼다.
    """
    moment = datetime.now() if now is None else now
    if moment.tzinfo is not None:
        moment = moment.astimezone()
    return moment.strftime("%Y%m%d-%H%M%S")
