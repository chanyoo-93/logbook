"""lb log: 기록 목록(하위 명령 없이 실행), lb log edit(수정), lb log rm(삭제)."""

from typing import Annotated

import typer

from logbook.cli import console, render, runtime
from logbook.cli.group import EXIT_ERROR, LogbookCommand, LogbookGroup
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
NOTHING_TO_CHANGE_MESSAGE = (
    '바꿀 항목을 하나 이상 지정하세요. 예: lb log edit 128 --minutes 90 --note "회의록 정리"'
)
DELETE_CANCELLED_MESSAGE = "삭제를 취소했습니다."
NO_CONFIRM_INPUT_MESSAGE = (
    "확인 입력을 받지 못해 삭제하지 않았습니다. 확인 없이 지우려면 --yes를 붙이세요."
)
CHANGED_WHILE_CONFIRMING_MESSAGE = (
    "확인하는 동안 기록이 바뀌어 삭제하지 않았습니다. 다시 실행하세요."
)

LogIdArg = Annotated[str, typer.Argument(metavar="ID", help="기록 ID (예: 128 또는 '#128')")]


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


@log_app.command("edit", cls=LogbookCommand)
def edit(
    log_id: LogIdArg,
    minutes: Annotated[
        str | None, typer.Option("--minutes", "-m", help="소요 시간 (예: 90, 1h30m)")
    ] = None,
    note: Annotated[str | None, typer.Option("--note", "-n", help="새 메모")] = None,
    category: runtime.CategoryOpt = None,
    project: runtime.ProjectOpt = None,
    on: runtime.DateOpt = None,
    task: runtime.TaskOpt = None,
    no_task: Annotated[bool, typer.Option("--no-task", help="태스크 연결을 해제합니다.")] = False,
) -> None:
    """기록을 고칩니다. 지정한 항목만 바꿉니다."""
    # DB와 설정 없이 끝낼 수 있는 검증을 먼저 한다(실패하면 SQLAlchemy를 로드하지 않는다).
    target_id = runtime.parse_id(log_id)
    changes = (minutes, note, category, project, on, task)
    if all(value is None for value in changes) and not no_task:
        # 빈 문자열(-n "")은 '지정함'이라 여기서 막지 않고 core 검증으로 넘긴다.
        raise InvalidInputError(NOTHING_TO_CHANGE_MESSAGE)

    from logbook.core.duration import parse_duration
    from logbook.core.weeks import parse_date

    new_minutes = parse_duration(minutes) if minutes is not None else None
    task_id = runtime.parse_id(task, "태스크") if task is not None else None

    cfg = runtime.settings()
    work_date = (
        parse_date(on, today=runtime.today(), week_start=cfg.week_start) if on is not None else None
    )

    # services는 SQLAlchemy를 로드하므로 검증이 끝난 뒤에 import한다.
    from logbook.core import services

    with runtime.session(cfg) as s:
        # -t와 --no-task를 함께 주면 core가 한 곳에서 거부한다.
        log = services.update_worklog(
            s,
            target_id,
            minutes=new_minutes,
            note=note,
            category=category,
            project_slug=project,
            work_date=work_date,
            task_id=task_id,
            clear_task=no_task,
            allowed_categories=tuple(cfg.categories),
        )

    console.print_line(render.ok_mark(), " 수정했습니다: ", render.worklog_record(log))


@log_app.command("rm", cls=LogbookCommand)
def remove(
    log_id: LogIdArg,
    yes: runtime.YesOpt = False,
) -> None:
    """기록을 삭제합니다. --yes가 없으면 먼저 확인합니다."""
    target_id = runtime.parse_id(log_id)
    cfg = runtime.settings()

    from logbook.core import services

    # 사람이 답하는 동안 SQLite 잠금을 쥐지 않도록 조회와 삭제를 다른 세션으로 나눈다.
    with runtime.session(cfg) as s:
        log = services.get_worklog(s, target_id)
    record = render.worklog_record(log)

    if not yes:
        answer = runtime.confirm(f"삭제할 기록: {record}\n삭제할까요?")
        if answer is None:
            console.print_notice(NO_CONFIRM_INPUT_MESSAGE)
            raise typer.Exit(EXIT_ERROR)
        if not answer:
            console.print_notice(DELETE_CANCELLED_MESSAGE)
            raise typer.Exit(EXIT_ERROR)

    with runtime.session(cfg) as s:
        # 확인하는 동안 다른 터미널이 기록을 고치거나, 지운 뒤 새 기록이 같은 ID를 다시 받았을 수
        # 있다(SQLite는 가장 큰 rowid를 재사용한다). 확인한 내용과 다르면 지우지 않는다.
        if str(render.worklog_record(services.get_worklog(s, target_id))) != str(record):
            console.print_notice(CHANGED_WHILE_CONFIRMING_MESSAGE)
            raise typer.Exit(EXIT_ERROR)
        services.delete_worklog(s, target_id)

    console.print_line(render.ok_mark(), " 삭제했습니다: ", record)


def register(app: typer.Typer) -> None:
    app.add_typer(log_app, name="log")
