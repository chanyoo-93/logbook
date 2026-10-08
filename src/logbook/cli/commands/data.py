"""lb export, lb import: 전체 데이터를 JSONL로 백업하고 빈 DB에 복원한다."""

from typing import TYPE_CHECKING, Annotated

import typer

from logbook.cli import console, render, runtime
from logbook.cli.group import LogbookCommand
from logbook.core import platform
from logbook.core.errors import InvalidInputError, LogbookError

if TYPE_CHECKING:
    from logbook.core.services import BackupCounts


def _print_done(verb: str, path_text: str, counts: "BackupCounts") -> None:
    """'✔ 내보냈습니다: 경로 (프로젝트 2 · 태스크 5 · 기록 41 · 타이머 0)' 한 줄."""
    from rich.text import Text

    dot = f" {render.info_mark()} "
    summary = dot.join(
        (
            f"프로젝트 {counts.projects}",
            f"태스크 {counts.tasks}",
            f"기록 {counts.worklogs}",
            f"타이머 {counts.timers}",
        )
    )
    console.print_line(render.ok_mark(), f" {verb}: ", Text(path_text), f" ({summary})")


def export(
    out: runtime.OutOpt = None,
    yes: runtime.YesOpt = False,
) -> None:
    """전체 데이터를 JSONL 파일로 내보냅니다. 경로를 생략하면 현재 폴더에 만듭니다."""
    now = runtime.now()
    # DB·설정 없이 끝나는 검증을 먼저 한다.
    path = runtime.prepare_output_path(
        out if out is not None else f"logbook-export-{platform.timestamp_for_filename(now)}.jsonl"
    )
    cfg = runtime.settings()

    from logbook.core import services

    with runtime.session(cfg) as s:
        lines, counts = services.export_records(s, now=now)

    # 세션을 닫은 뒤에 쓴다(덮어쓰기 확인 동안 DB를 잡고 있지 않는다).
    runtime.write_text_file(path, "\n".join(lines) + "\n", yes=yes)
    _print_done("내보냈습니다", str(path), counts)


def import_(
    path_text: Annotated[
        str,
        typer.Argument(metavar="PATH", help="가져올 JSONL 파일 (lb export로 만든 파일)"),
    ],
) -> None:
    """lb export로 만든 JSONL 파일을 빈 데이터베이스(lb init 직후)에 복원합니다."""
    from logbook.core.config import expand_home

    # 파일을 DB·설정보다 먼저 읽는다. 그래야 파일 오류가 DB 접근 없이 끝난다.
    path = expand_home(path_text, "가져올 파일 경로")
    if path.is_dir():
        raise InvalidInputError(f"파일 경로가 아니라 폴더입니다: {path}. 파일 이름까지 지정하세요.")
    if not path.is_file():
        raise InvalidInputError(f"가져올 파일이 없습니다: {path}")
    try:
        text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as error:
        raise InvalidInputError(
            f"UTF-8 텍스트 파일이 아닙니다: {path}. 'lb export'로 만든 파일을 지정하세요."
        ) from error
    except OSError as error:
        raise LogbookError(
            f"가져올 파일을 읽지 못했습니다: {path} ({error.strerror or error})."
        ) from error
    # splitlines()는 U+2028·U+2029·U+0085에서도 나눠 정상 파일을 거부하므로 LF로만 나눈다.
    lines = text.split("\n")

    cfg = runtime.settings()

    from logbook.core import services

    with runtime.session(cfg) as s:
        counts = services.import_records(s, lines)
    _print_done("가져왔습니다", str(path), counts)


def register(app: typer.Typer) -> None:
    app.command("export", cls=LogbookCommand)(export)
    app.command("import", cls=LogbookCommand)(import_)
