"""lb report: 주간업무보고 Markdown을 stdout, 파일, 클립보드로 내보낸다."""

from datetime import UTC
from pathlib import Path
from typing import Annotated

import typer

from logbook.cli import console, render, runtime
from logbook.cli.group import LogbookCommand
from logbook.core import platform

COPY_FAILED_MESSAGE = "클립보드에 복사하지 못했습니다."


def _build_markdown(week: str | None) -> str:
    """주차를 해석하고 보고서 데이터를 모아 Markdown으로 렌더링한다."""
    from logbook.core.weeks import parse_week

    cfg = runtime.settings()
    the_week = parse_week(
        week if week is not None else "this", today=runtime.today(), week_start=cfg.week_start
    )

    # services는 SQLAlchemy를 로드하므로 주차 검증이 끝난 뒤에 import한다.
    from logbook.core import services

    now = runtime.now()
    tz = now.tzinfo or UTC
    with runtime.session(cfg) as s:
        data = services.weekly_report(
            s,
            the_week,
            tz=tz,
            title_format=cfg.report.title_format,
            author=cfg.report.author,
            category_labels=cfg.categories,
        )

    # 렌더링(jinja2 로드)은 세션을 닫은 뒤에 한다.
    from logbook.core.config import config_path
    from logbook.core.report import render_markdown, user_template_path

    return render_markdown(data, template_path=user_template_path(config_path()))


def _deliver(markdown: str, out_path: Path | None, *, copy: bool, yes: bool) -> None:
    """파일 저장, 클립보드 복사, stdout 출력을 처리한다."""
    if out_path is not None:
        from rich.text import Text

        runtime.write_text_file(out_path, markdown, yes=yes)
        console.print_line(render.ok_mark(), " 보고서를 저장했습니다: ", Text(str(out_path)))

    copied = platform.copy_to_clipboard(markdown) if copy else False
    if copied:
        console.print_line(render.ok_mark(), " 보고서를 클립보드에 복사했습니다.")
    elif copy and out_path is not None:
        console.print_warning(f"{COPY_FAILED_MESSAGE} 보고서는 파일로 저장했습니다: {out_path}")
    elif copy:
        console.print_warning(f"{COPY_FAILED_MESSAGE} --out으로 파일에 저장하세요.")

    # 저장도 복사도 하지 않았거나, 복사에 실패했는데 저장한 파일이 없으면 보고서를 stdout에 쓴다.
    if out_path is None and not copied:
        console.print_raw(markdown)


def report(
    week: runtime.WeekOpt = None,
    out: runtime.OutOpt = None,
    copy: Annotated[bool, typer.Option("--copy", help="클립보드에 복사합니다.")] = False,
    yes: runtime.YesOpt = False,
) -> None:
    """주간업무보고를 Markdown으로 만듭니다. 기본은 이번 주를 stdout에 출력합니다."""
    # DB·설정 없이 끝나는 검증을 먼저 한다.
    out_path = runtime.prepare_output_path(out) if out is not None else None
    markdown = _build_markdown(week)
    _deliver(markdown, out_path, copy=copy, yes=yes)


def register(app: typer.Typer) -> None:
    app.command("report", cls=LogbookCommand)(report)
