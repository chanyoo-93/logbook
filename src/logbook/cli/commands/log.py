"""lb log: 기록 목록(하위 명령 없이 실행). 수정·삭제 하위 명령은 이 그룹에 붙는다."""

import typer

from logbook.cli import console, render, runtime
from logbook.cli.group import LogbookGroup
from logbook.core.errors import InvalidInputError

# no_args_is_help를 두지 않는다(그러면 'lb log'가 목록 대신 help를 보여 준다).
log_app = typer.Typer(
    cls=LogbookGroup,
    help="기록을 조회·수정·삭제합니다. 하위 명령 없이 실행하면 이번 주 기록을 보여 줍니다.",
)

QUERY_OPTIONS_WITH_SUBCOMMAND_MESSAGE = (
    "조회 옵션(--week, --date, -p, -c)은 'lb log' 목록에만 쓸 수 있습니다. "
    "기록을 고칠 때는 'lb log edit 128 -p payment'처럼 하위 명령 뒤에 쓰세요."
)
WEEK_AND_DATE_MESSAGE = "--week와 --date는 함께 쓸 수 없습니다. 하나만 지정하세요."


@log_app.callback(invoke_without_command=True)
def list_logs(
    ctx: typer.Context,
    week: runtime.WeekOpt = None,
    on: runtime.DateOpt = None,
    project: runtime.ProjectOpt = None,
    category: runtime.CategoryOpt = None,
) -> None:
    """기록 목록을 날짜, ID 순으로 보여 줍니다. 기본은 이번 주입니다."""
    has_query = any(option is not None for option in (week, on, project, category))
    if ctx.invoked_subcommand is not None:
        # 하위 명령 앞에 쓴 조회 옵션이 조용히 무시되지 않게 막는다.
        if has_query:
            raise InvalidInputError(QUERY_OPTIONS_WITH_SUBCOMMAND_MESSAGE)
        return
    if week is not None and on is not None:
        # 서비스는 둘을 AND로 걸어 조용히 0건을 내므로 미리 막는다.
        raise InvalidInputError(WEEK_AND_DATE_MESSAGE)

    from logbook.core.duration import format_duration
    from logbook.core.weeks import parse_date, parse_week, week_heading

    cfg = runtime.settings()
    today = runtime.today()
    if on is not None:
        day = parse_date(on, today=today, week_start=cfg.week_start)
        span = None
        heading = render.full_day(day)
    else:
        day = None
        span = parse_week(
            week if week is not None else "this", today=today, week_start=cfg.week_start
        )
        heading = week_heading(span)

    if category is not None and category not in cfg.categories:
        # 설정에서 지운 옛 카테고리의 기록도 볼 수 있게 경고만 하고 조회는 계속한다.
        console.print_warning(
            f"설정에 없는 카테고리입니다: '{category}'. "
            f"사용할 수 있는 카테고리: {', '.join(sorted(cfg.categories))}"
        )

    # services는 SQLAlchemy를 로드하므로 검증이 끝난 뒤에 import한다.
    from logbook.core import services

    with runtime.session(cfg) as s:
        logs = services.list_worklogs(s, week=span, on=day, project_slug=project, category=category)

    console.print_line(heading)
    if not logs:
        console.print_line("기록이 없습니다.")
        return
    console.print_table(render.worklog_table(logs), lambda: render.worklog_lines(logs))
    total = sum(log.minutes for log in logs)
    console.print_line(f"합계 {format_duration(total)} / 기록 {len(logs)}건")


def register(app: typer.Typer) -> None:
    app.add_typer(log_app, name="log")
