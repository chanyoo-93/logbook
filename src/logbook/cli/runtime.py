"""명령이 함께 쓰는 런타임 헬퍼.

오늘 날짜, 지금 시각, 설정, DB 세션, 공용 옵션, ID·반올림 파싱, 확인 프롬프트.

core.config와 core.db는 CLI 시작 시간을 줄이려고 함수 안에서 지연 import한다.
"""

import locale
import re
import sys
from contextlib import contextmanager
from datetime import date, datetime
from typing import TYPE_CHECKING, Annotated

import typer

from logbook.cli import console
from logbook.cli.group import EXIT_ERROR
from logbook.core.errors import InvalidInputError

if TYPE_CHECKING:
    from collections.abc import Iterator

    from sqlalchemy.orm import Session

    from logbook.core.config import Config

ProjectOpt = Annotated[
    str | None, typer.Option("--project", "-p", help="프로젝트 slug (예: payment)")
]
CategoryOpt = Annotated[str | None, typer.Option("--category", "-c", help="카테고리 키 (예: dev)")]
DateOpt = Annotated[
    str | None,
    typer.Option("--date", "-d", help="날짜: today, yesterday, mon~sun, 2026-10-01, 10-01"),
]
WeekOpt = Annotated[
    str | None, typer.Option("--week", "-w", help="주차: this, last, next, 2026-W40")
]
TaskOpt = Annotated[str | None, typer.Option("--task", "-t", help="태스크 ID (예: 42 또는 '#42')")]
YesOpt = Annotated[bool, typer.Option("--yes", "-y", help="확인 없이 진행합니다.")]
StatusOpt = Annotated[
    str | None,
    typer.Option("--status", "-s", help="상태: todo,doing,done,dropped,all (쉼표 구분)"),
]
EstimateOpt = Annotated[
    str | None, typer.Option("--est", "-e", help="예상 공수 (예: 4h, 90m, 40h)")
]
RefOpt = Annotated[str | None, typer.Option("--ref", help="외부 참조 (예: '#43', URL, Jira 키)")]
DueOpt = Annotated[str | None, typer.Option("--due", help="마감일: today, 10-15, 2026-10-15 …")]

# SQLite INTEGER 최댓값. 넘는 값은 서비스에서 OverflowError(traceback)가 난다.
MAX_ID = 2**63 - 1
MAX_ID_DIGITS = 19
# 자릿수를 먼저 제한해 int()의 자릿수 한도(4300자리) ValueError도 피한다.
_ID_PATTERN = re.compile(rf"#?([0-9]{{1,{MAX_ID_DIGITS}}})")
# core.services.timer.MAX_ROUND_MINUTES와 같은 값이다. services를 import하면 형식 오류 경로에서
# SQLAlchemy가 로드되므로 여기 따로 두고, 두 값이 같은지는 테스트가 확인한다.
MAX_ROUND_MINUTES = 60
# ASCII 숫자 1~2자리만 받는다(\d는 아랍 숫자·전각 숫자도 받는다).
_ROUND_PATTERN = re.compile(r"[0-9]{1,2}")
_UTF8_BOM = b"\xef\xbb\xbf"
_YES_ANSWERS = frozenset({"y", "yes", "ㅛ", "ㅛㄷㄴ"})  # 한글 자판 상태의 y, yes


def today() -> date:
    """오늘 날짜. 테스트가 monkeypatch하는 단일 지점이다."""
    return date.today()


def now() -> datetime:
    """로컬 시간대가 붙은 지금 시각. 테스트가 monkeypatch하는 단일 지점이다."""
    return datetime.now().astimezone()


def settings() -> "Config":
    """설정을 읽는다(LOGBOOK_CONFIG, LOGBOOK_DB 반영)."""
    from logbook.core.config import load_config

    return load_config()


@contextmanager
def session(cfg: "Config") -> "Iterator[Session]":
    """'lb init'으로 만든 DB의 세션. 성공하면 커밋하고, 끝나면 항상 엔진을 dispose한다."""
    from logbook.core import db

    engine = db.open_database(cfg.db_path)
    try:
        with db.session_scope(engine) as s:
            yield s
    finally:
        engine.dispose()


def parse_id(text: str, what: str = "기록") -> int:
    """'128', '#128' 형식의 ID. 1 이상 MAX_ID 이하의 ASCII 숫자만 받는다."""
    match = _ID_PATTERN.fullmatch(text.strip())
    value = int(match.group(1)) if match else 0
    if not 1 <= value <= MAX_ID:
        raise InvalidInputError(
            f"{what} ID가 올바르지 않습니다: '{text}'. 숫자로 입력하세요 (예: 128 또는 #128)."
        )
    return value


def parse_round(text: str) -> int:
    """'--round' 값: 1~MAX_ROUND_MINUTES 분. ASCII 숫자 1~2자리만 받는다."""
    value = int(text) if _ROUND_PATTERN.fullmatch(text) else 0
    if not 1 <= value <= MAX_ROUND_MINUTES:
        raise InvalidInputError(
            f"반올림 단위가 올바르지 않습니다: '{text}'. "
            f"1~{MAX_ROUND_MINUTES} 사이의 분 단위 숫자로 입력하세요 (예: --round 15)."
        )
    return value


def confirm(question: str) -> bool | None:
    """stderr에 '질문 [y/N]: '를 쓰고 stdin 한 줄을 읽는다. EOF면 None.

    isatty로 분기하지 않는다(파이프 입력과 CliRunner에서도 같은 동작).
    typer.confirm은 영어 안내를 내고 stdout에 공백을 섞어 쓰지 않는다.
    """
    console.print_notice(f"{question} [y/N]: ", end="")
    answer = _read_answer_line()
    if answer is None:
        console.print_notice("")
        return None
    # 텍스트 경로(.buffer 없는 스트림)에서는 U+FEFF가 남을 수 있고, strip()은 이를 지우지 않는다.
    return answer.lstrip("\ufeff").strip().lower() in _YES_ANSWERS


def _read_answer_line() -> str | None:
    """stdin 한 줄을 읽는다. EOF면 None.

    Windows PowerShell 5.1은 프로필이 입출력 인코딩을 UTF-8로 두면 파이프 입력 앞에 UTF-8 BOM을
    붙이고($OutputEncoding까지 UTF-8이면 두 번), 파이프 stdin은 로케일 코덱(cp949 등)으로
    디코드되어 BOM이 깨진다. 그래서 바이트로 읽어 BOM을 먼저 지운 뒤 디코드한다.
    """
    buffer = getattr(sys.stdin, "buffer", None)
    if buffer is None:  # .buffer가 없는 스트림(일부 테스트 대역)은 텍스트로 읽는다.
        line = sys.stdin.readline()
        return None if line == "" else line
    raw: bytes = buffer.readline()
    if raw == b"":
        return None
    while raw.startswith(_UTF8_BOM):
        raw = raw[len(_UTF8_BOM) :]
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode(locale.getpreferredencoding(False), errors="replace")


def require_confirmation(question: str, *, cancelled: str, no_input: str) -> None:
    """confirm(question)이 '예'면 돌아온다. 아니면 안내를 stderr에 쓰고 exit 1로 끝낸다.

    거절하면 cancelled, 입력이 없으면(EOF) no_input을 쓴다.
    """
    answer = confirm(question)
    if answer:
        return
    console.print_notice(no_input if answer is None else cancelled)
    raise typer.Exit(EXIT_ERROR)
