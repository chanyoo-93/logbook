"""lb add: 한 일을 기록하고 그날의 누적 시간을 보여 준다."""

from typing import Annotated

import typer

from logbook.cli import console, render, runtime
from logbook.cli.group import LogbookCommand


def add(
    duration: Annotated[
        str,
        typer.Argument(
            metavar="시간", help="소요 시간: 2h, 1.5h, 90m, 1h30m, 1h 30m, 45(분), 1:30"
        ),
    ],
    note: Annotated[
        str,
        typer.Argument(
            metavar="메모",
            help="한 일 한 줄. 공백이 있으면 따옴표로 감쌉니다. '-'로 시작하면 '--' 뒤에 씁니다.",
        ),
    ],
    project: runtime.ProjectOpt = None,
    category: runtime.CategoryOpt = None,
    task: runtime.TaskOpt = None,
    on: runtime.DateOpt = None,
) -> None:
    """업무 기록을 추가합니다.

    프로젝트를 생략하면 태스크의 프로젝트, 태스크도 없으면 설정의 기본 프로젝트에 기록합니다.
    """
    from logbook.core.duration import format_duration, parse_duration
    from logbook.core.weeks import parse_date

    # DB와 설정 없이 끝낼 수 있는 검증을 먼저 한다(실패하면 SQLAlchemy를 로드하지 않는다).
    minutes = parse_duration(duration)
    task_id = runtime.parse_id(task, "태스크") if task is not None else None

    cfg = runtime.settings()
    today = runtime.today()
    work_date = parse_date(
        on if on is not None else "today", today=today, week_start=cfg.week_start
    )

    # services는 SQLAlchemy를 로드하므로 검증이 끝난 뒤에 import한다.
    from logbook.core import services

    with runtime.session(cfg) as s:
        log = services.add_worklog(
            s,
            minutes=minutes,
            note=note,
            project_slug=project,
            category=category,
            work_date=work_date,
            task_id=task_id,
            allowed_categories=tuple(cfg.categories),
            default_project=cfg.default_project,
            today=today,
        )
        # 방금 flush한 기록도 합계에 들어간다.
        total = services.day_total_minutes(s, log.date)

    console.print_line(
        render.ok_mark(),
        " ",
        render.worklog_line(log),
        f" ({render.total_label(log.date, today)} 누적 {format_duration(total)})",
    )


def register(app: typer.Typer) -> None:
    app.command("add", cls=LogbookCommand)(add)
