"""lb task add|list."""

from typing import TYPE_CHECKING, Annotated

import typer

from logbook.cli import console, render, runtime
from logbook.cli.group import LogbookCommand, LogbookGroup

if TYPE_CHECKING:
    from collections.abc import Sequence

    from rich.text import Text

task_app = typer.Typer(
    cls=LogbookGroup,
    help="태스크(할 일)를 추가·조회·수정하고 상태를 바꿉니다.",
    no_args_is_help=True,
)

# 'lb task list'의 기본 상태 목록(사용자 결정 T2: 할 일·진행 중)
DEFAULT_LIST_STATUSES = "todo,doing"


@task_app.command("add", cls=LogbookCommand)
def add(
    title: Annotated[
        str,
        typer.Argument(
            metavar="제목",
            help="할 일 한 줄. 공백이 있으면 따옴표로 감쌉니다. '-'로 시작하면 '--' 뒤에 씁니다.",
        ),
    ],
    project: runtime.ProjectOpt = None,
    category: runtime.CategoryOpt = None,
    estimate: runtime.EstimateOpt = None,
    week: runtime.WeekOpt = None,
    ref: runtime.RefOpt = None,
    due: runtime.DueOpt = None,
) -> None:
    """태스크를 추가합니다. 프로젝트를 생략하면 설정의 기본 프로젝트에 추가합니다."""
    from logbook.core.duration import parse_duration
    from logbook.core.weeks import parse_date, parse_week

    # DB와 설정 없이 끝낼 수 있는 검증을 먼저 한다(실패하면 SQLAlchemy를 로드하지 않는다).
    # 예상 공수는 하루를 넘을 수 있으므로 상한을 두지 않는다.
    estimate_minutes = parse_duration(estimate, max_minutes=None) if estimate is not None else None

    cfg = runtime.settings()
    today = runtime.today()
    planned_week = (
        parse_week(week, today=today, week_start=cfg.week_start) if week is not None else None
    )
    due_date = parse_date(due, today=today, week_start=cfg.week_start) if due is not None else None

    # services는 SQLAlchemy를 로드하므로 검증이 끝난 뒤에 import한다.
    from logbook.core import services

    with runtime.session(cfg) as s:
        task = services.create_task(
            s,
            title=title,
            project_slug=project if project is not None else cfg.default_project,
            category=category,
            estimate_minutes=estimate_minutes,
            planned_week=planned_week,
            due_date=due_date,
            external_ref=ref,
            allowed_categories=tuple(cfg.categories),
        )

    console.print_line(
        render.ok_mark(), " 태스크 추가: ", render.task_line(task), render.task_details(task)
    )


@task_app.command("list", cls=LogbookCommand)
def list_(
    project: Annotated[
        str | None,
        typer.Option(
            "--project",
            "-p",
            help="프로젝트 slug (예: payment). 지정하면 보관된 프로젝트도 볼 수 있습니다.",
        ),
    ] = None,
    status: runtime.StatusOpt = None,
    week: runtime.WeekOpt = None,
) -> None:
    """태스크 목록을 계획 주차, ID 순으로 보여 줍니다. 기본은 할 일·진행 중(todo,doing)입니다."""
    from logbook.core.taskstatus import parse_statuses

    statuses = parse_statuses(status if status is not None else DEFAULT_LIST_STATUSES)

    from logbook.core.duration import format_duration
    from logbook.core.weeks import parse_week

    cfg = runtime.settings()
    span = (
        parse_week(week, today=runtime.today(), week_start=cfg.week_start)
        if week is not None
        else None
    )

    # services는 SQLAlchemy를 로드하므로 검증이 끝난 뒤에 import한다.
    from logbook.core import services

    with runtime.session(cfg) as s:
        tasks = services.list_tasks(s, project_slug=project, statuses=statuses, week=span)
        actual = services.actual_minutes_by_task(s, [task.id for task in tasks])

    console.print_line(_list_heading(statuses, span.label if span is not None else None, project))
    if not tasks:
        console.print_line("태스크가 없습니다.")
        return
    console.print_table(render.task_table(tasks, actual), lambda: render.task_lines(tasks, actual))
    estimate_total = sum(t.estimate_minutes for t in tasks if t.estimate_minutes is not None)
    actual_total = sum(actual.values())
    console.print_line(
        f"태스크 {len(tasks)}건 / 예상 {format_duration(estimate_total)} "
        f"/ 실적 {format_duration(actual_total)}"
    )


def _list_heading(statuses: "Sequence[str]", week_label: str | None, project: str | None) -> "Text":
    """'태스크 (todo, doing)' 뒤에 주차와 프로젝트를 ' · '로 붙인다."""
    from rich.text import Text

    parts: list[str | Text] = [f"태스크 ({', '.join(statuses)})"]
    for value in (week_label, project):
        if value is not None:
            parts.extend((f" {render.info_mark()} ", Text(value)))
    return Text.assemble(*parts)


def register(app: typer.Typer) -> None:
    app.add_typer(task_app, name="task")
