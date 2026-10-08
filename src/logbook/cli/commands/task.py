"""lb task add|list|edit."""

from typing import TYPE_CHECKING, Annotated

import typer

from logbook.cli import console, render, runtime
from logbook.cli.group import LogbookCommand, LogbookGroup
from logbook.core.errors import InvalidInputError

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from rich.text import Text

    from logbook.core.config import Config
    from logbook.core.taskstatus import TaskStatus

task_app = typer.Typer(
    cls=LogbookGroup,
    help="태스크(할 일)를 추가·조회·수정하고 상태를 바꿉니다.",
    no_args_is_help=True,
)

# 'lb task list'의 기본 상태 목록(사용자 결정 T2: 할 일·진행 중)
DEFAULT_LIST_STATUSES = "todo,doing"

CONFLICT_MESSAGE = "{}와 {}는 함께 쓸 수 없습니다. 하나만 지정하세요."
NOTHING_TO_CHANGE_MESSAGE = (
    "바꿀 항목을 하나 이상 지정하세요. 예: lb task edit 43 --est 6h --week next"
)

# (값 옵션, 비우기 옵션, update_task 필드). 충돌 검사와 비우기 매핑이 이 표 하나를 쓴다.
_CLEARABLE = (
    ("--category", "--no-category", "category"),
    ("--est", "--no-est", "estimate_minutes"),
    ("--week", "--no-week", "planned_week"),
    ("--ref", "--no-ref", "external_ref"),
    ("--due", "--no-due", "due_date"),
)

TaskIdArg = Annotated[str, typer.Argument(metavar="ID", help="태스크 ID (예: 43 또는 '#43')")]


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


@task_app.command("edit", cls=LogbookCommand)
def edit(
    task_id: TaskIdArg,
    title: Annotated[str | None, typer.Option("--title", help="새 제목")] = None,
    category: runtime.CategoryOpt = None,
    estimate: runtime.EstimateOpt = None,
    week: runtime.WeekOpt = None,
    ref: runtime.RefOpt = None,
    due: runtime.DueOpt = None,
    no_category: Annotated[
        bool, typer.Option("--no-category", help="카테고리를 비웁니다.")
    ] = False,
    no_estimate: Annotated[bool, typer.Option("--no-est", help="예상 공수를 비웁니다.")] = False,
    no_week: Annotated[bool, typer.Option("--no-week", help="계획 주차를 비웁니다.")] = False,
    no_ref: Annotated[bool, typer.Option("--no-ref", help="외부 참조를 비웁니다.")] = False,
    no_due: Annotated[bool, typer.Option("--no-due", help="마감일을 비웁니다.")] = False,
) -> None:
    """태스크를 고칩니다. 지정한 항목만 바꾸며, 프로젝트는 바꿀 수 없습니다."""
    # DB와 설정 없이 끝낼 수 있는 검증을 먼저 한다(실패하면 SQLAlchemy를 로드하지 않는다).
    target_id = runtime.parse_id(task_id, "태스크")
    values = {
        "category": category,
        "estimate_minutes": estimate,
        "planned_week": week,
        "external_ref": ref,
        "due_date": due,
    }
    clears = {
        "category": no_category,
        "estimate_minutes": no_estimate,
        "planned_week": no_week,
        "external_ref": no_ref,
        "due_date": no_due,
    }
    _reject_bad_flags(title, values, clears)

    cfg = runtime.settings()
    fields = _build_fields(title, values, clears, cfg)

    # services는 SQLAlchemy를 로드하므로 검증이 끝난 뒤에 import한다.
    from logbook.core import services

    with runtime.session(cfg) as s:
        task = services.update_task(
            s, target_id, allowed_categories=tuple(cfg.categories), **fields
        )

    console.print_line(
        render.ok_mark(), " 수정했습니다: ", render.task_line(task), render.task_details(task)
    )


@task_app.command("start", cls=LogbookCommand)
def start(task_id: TaskIdArg) -> None:
    """태스크를 진행 중(doing)으로 바꿉니다. 완료·중단된 태스크를 다시 시작할 수도 있습니다."""
    from logbook.core.taskstatus import TaskStatus

    _change_status(task_id, TaskStatus.DOING)


@task_app.command("done", cls=LogbookCommand)
def done(task_id: TaskIdArg) -> None:
    """태스크를 완료(done)로 바꾸고 실적을 보여 줍니다."""
    from logbook.core.taskstatus import TaskStatus

    _change_status(task_id, TaskStatus.DONE)


@task_app.command("drop", cls=LogbookCommand)
def drop(task_id: TaskIdArg) -> None:
    """태스크를 중단(dropped)으로 바꿉니다."""
    from logbook.core.taskstatus import TaskStatus

    _change_status(task_id, TaskStatus.DROPPED)


def _change_status(task_id_text: str, status: "TaskStatus") -> None:
    """세 상태 명령의 공통 처리. 같은 상태면 안내만 하고 성공(exit 0)한다."""
    target_id = runtime.parse_id(task_id_text, "태스크")
    cfg = runtime.settings()

    # services는 SQLAlchemy를 로드하므로 검증이 끝난 뒤에 import한다.
    from logbook.core import services
    from logbook.core.taskstatus import TaskStatus

    with runtime.session(cfg) as s:
        old_status = services.get_task(s, target_id).status
        task = services.set_task_status(s, target_id, status)
        scope_title = render.task_scope_title(task)
        tail = (
            _actual_tail(services.task_actual_minutes(s, target_id), task.estimate_minutes)
            if status == TaskStatus.DONE
            else ""
        )

    if old_status == status:
        console.print_line(
            render.info_mark(),
            f" 태스크 #{target_id} 상태는 이미 {status}입니다: ",
            scope_title,
            tail,
        )
    else:
        console.print_line(
            render.ok_mark(),
            f" #{target_id} {old_status} {render.arrow()} {status}: ",
            scope_title,
            tail,
        )


def _actual_tail(actual: int, estimate: int | None) -> str:
    """done 꼬리: ' (실적 5h 30m / 예상 4h)', 예상이 없으면 ' (실적 5h 30m)'."""
    from logbook.core.duration import format_duration

    text = f"실적 {format_duration(actual)}"
    if estimate is not None:
        text += f" / 예상 {format_duration(estimate)}"
    return f" ({text})"


def _reject_bad_flags(
    title: str | None, values: dict[str, str | None], clears: dict[str, bool]
) -> None:
    """값과 --no-…를 함께 줬거나 바꿀 항목이 없으면 거부한다(DB·설정을 읽기 전에)."""
    # update_task(**fields)는 값과 비우기를 구분해 볼 수 없으므로(log edit은 core가 -t와
    # --no-task를 거부한다) CLI가 직접 충돌을 막는다.
    for value_flag, clear_flag, field in _CLEARABLE:
        if values[field] is not None and clears[field]:
            raise InvalidInputError(CONFLICT_MESSAGE.format(value_flag, clear_flag))
    # 빈 문자열(--title "")은 '지정함'이라 여기서 막지 않고 core 검증으로 넘긴다.
    if title is None and all(v is None for v in values.values()) and not any(clears.values()):
        raise InvalidInputError(NOTHING_TO_CHANGE_MESSAGE)


def _build_fields(
    title: str | None, values: dict[str, str | None], clears: dict[str, bool], cfg: "Config"
) -> dict[str, object]:
    """update_task에 넘길 필드. 값은 파싱하고, --no-…는 None으로 비운다."""
    from logbook.core.duration import parse_duration
    from logbook.core.weeks import parse_date, parse_week

    today = runtime.today()
    parsers: dict[str, Callable[[str], object]] = {
        "estimate_minutes": lambda text: parse_duration(text, max_minutes=None),
        "planned_week": lambda text: parse_week(text, today=today, week_start=cfg.week_start),
        "due_date": lambda text: parse_date(text, today=today, week_start=cfg.week_start),
    }
    fields: dict[str, object] = {} if title is None else {"title": title}
    for _, _, field in _CLEARABLE:
        value = values[field]
        if value is not None:
            fields[field] = parsers[field](value) if field in parsers else value
        elif clears[field]:
            fields[field] = None
    return fields


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
