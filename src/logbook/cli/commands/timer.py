"""lb start, lb status: 타이머."""

from datetime import datetime
from typing import TYPE_CHECKING, Annotated

import typer

from logbook.cli import console, render, runtime
from logbook.cli.group import LogbookCommand

if TYPE_CHECKING:
    from logbook.core.models import ActiveTimer

NO_TIMER_MESSAGE = "진행 중인 타이머가 없습니다."


def _started_label(timer: "ActiveTimer", now: datetime) -> str:
    """시작 시각을 로컬 시간대(now 기준)로 바꿔 '09:30' 또는 '09-30 (수) 22:10'으로 쓴다."""
    return render.clock_label(timer.started_at.astimezone(now.tzinfo), runtime.today())


def start(
    note: Annotated[
        str | None,
        typer.Argument(
            metavar="메모",
            help=(
                "하는 일 한 줄. -t를 주고 생략하면 태스크 제목을 씁니다. "
                "'-'로 시작하면 '--' 뒤에 씁니다."
            ),
        ),
    ] = None,
    project: runtime.ProjectOpt = None,
    category: runtime.CategoryOpt = None,
    task: runtime.TaskOpt = None,
) -> None:
    """타이머를 시작합니다. 'lb stop'으로 멈추면 업무 기록으로 저장합니다.

    -t로 todo 태스크를 지정하면 태스크를 doing으로 바꿉니다.
    """
    # DB와 설정 없이 끝낼 수 있는 검증을 먼저 한다(실패하면 SQLAlchemy를 로드하지 않는다).
    task_id = runtime.parse_id(task, "태스크") if task is not None else None

    cfg = runtime.settings()
    now = runtime.now()

    # services는 SQLAlchemy를 로드하므로 검증이 끝난 뒤에 import한다.
    from logbook.core import services

    with runtime.session(cfg) as s:
        started = services.start_timer(
            s,
            now=now,
            note=note,
            project_slug=project,
            category=category,
            task_id=task_id,
            allowed_categories=tuple(cfg.categories),
            default_project=cfg.default_project,
        )

    timer = started.timer
    started_label = _started_label(timer, now)
    console.print_line(
        render.ok_mark(), " 타이머 시작: ", render.timer_line(timer), f" ({started_label})"
    )
    if started.task_started:
        console.print_line(
            f"{render.info_mark()} 태스크 #{timer.task_id} 상태를 doing으로 바꿨습니다."
        )


def status() -> None:
    """진행 중인 타이머와 경과 시간을 보여 줍니다."""
    from logbook.core.duration import format_duration

    cfg = runtime.settings()
    now = runtime.now()

    from logbook.core import services

    with runtime.session(cfg) as s:
        timer = services.get_timer(s)

    if timer is None:
        console.print_line(NO_TIMER_MESSAGE)
        return
    started_label = _started_label(timer, now)
    elapsed = format_duration(services.elapsed_minutes(timer.started_at, now))
    console.print_line("진행 중: ", render.timer_line(timer))
    console.print_line(f"시작 {started_label} {render.info_mark()} 경과 {elapsed}")


def register(app: typer.Typer) -> None:
    app.command("start", cls=LogbookCommand)(start)
    app.command("status", cls=LogbookCommand)(status)
