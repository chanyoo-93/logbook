"""lb start, lb status, lb stop, lb cancel: 타이머."""

from datetime import datetime
from typing import TYPE_CHECKING, Annotated

import typer

from logbook.cli import console, render, runtime
from logbook.cli.group import EXIT_ERROR, LogbookCommand
from logbook.core.errors import NotFoundError

if TYPE_CHECKING:
    from logbook.core.models import ActiveTimer

# lb status 안내. 오류 문구는 core의 services.NO_TIMER_MESSAGE를 쓴다.
NO_TIMER_MESSAGE = "진행 중인 타이머가 없습니다."
CANCEL_DECLINED_MESSAGE = "취소하지 않았습니다. 타이머는 계속 진행됩니다."
CANCEL_NO_INPUT_MESSAGE = (
    "확인 입력을 받지 못해 버리지 않았습니다. 확인 없이 버리려면 --yes를 붙이세요."
)
CHANGED_WHILE_CONFIRMING_MESSAGE = (
    "확인하는 동안 타이머가 바뀌어 버리지 않았습니다. 다시 실행하세요."
)


def _started_label(timer: "ActiveTimer", now: datetime) -> str:
    """시작 시각을 로컬 시간대(now 기준)로 바꿔 '09:30' 또는 '09-30 (수) 22:10'으로 쓴다.

    '오늘'도 now에서 구해 표시 시각과 경과 시간이 같은 순간을 기준으로 한다.
    """
    return render.clock_label(timer.started_at.astimezone(now.tzinfo), now.date())


def _elapsed_text(timer: "ActiveTimer", now: datetime) -> str:
    """경과 시간 표기(예: '1h 25m')."""
    from logbook.core import services
    from logbook.core.duration import format_duration

    return format_duration(services.elapsed_minutes(timer.started_at, now))


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
    cfg = runtime.settings()
    now = runtime.now()

    from logbook.core import services

    with runtime.session(cfg) as s:
        timer = services.get_timer(s)

    if timer is None:
        console.print_line(NO_TIMER_MESSAGE)
        return
    started_label = _started_label(timer, now)
    elapsed = _elapsed_text(timer, now)
    console.print_line("진행 중: ", render.timer_line(timer))
    console.print_line(f"시작 {started_label} {render.info_mark()} 경과 {elapsed}")


def stop(
    note: Annotated[
        str | None,
        typer.Option("--note", "-n", help="시작 메모 뒤에 ' — '로 덧붙일 메모"),
    ] = None,
    round_to: Annotated[
        str | None,
        typer.Option(
            "--round", metavar="N", help="저장할 시간을 N분 단위로 반올림합니다 (1~60, 예: 15)."
        ),
    ] = None,
) -> None:
    """타이머를 멈추고 업무 기록으로 저장합니다. 기록 날짜는 시작한 날입니다."""
    from logbook.core.duration import format_duration

    # DB와 설정 없이 끝낼 수 있는 검증을 먼저 한다(실패하면 SQLAlchemy를 로드하지 않는다).
    step = runtime.parse_round(round_to) if round_to is not None else None

    cfg = runtime.settings()
    now = runtime.now()

    from logbook.core import services

    with runtime.session(cfg) as s:
        stopped = services.stop_timer(s, now=now, extra_note=note, round_to=step)
        log = stopped.log
        # 방금 flush한 기록도 합계에 들어간다.
        total = services.day_total_minutes(s, log.date)

    console.print_line(
        render.ok_mark(),
        " ",
        render.worklog_line(log),
        f" ({render.total_label(log.date, now.date())} 누적 {format_duration(total)})",
    )
    if log.minutes != stopped.elapsed_minutes:
        console.print_line(
            f"{render.info_mark()} 경과 {format_duration(stopped.elapsed_minutes)}을 "
            f"{step}분 단위로 반올림했습니다."
        )


def cancel(yes: runtime.YesOpt = False) -> None:
    """타이머를 기록하지 않고 버립니다. --yes가 없으면 먼저 확인합니다."""
    cfg = runtime.settings()
    now = runtime.now()

    from logbook.core import services

    # 사람이 답하는 동안 SQLite 잠금을 쥐지 않도록 조회와 삭제를 다른 세션으로 나눈다.
    with runtime.session(cfg) as s:
        timer = services.get_timer(s)
    if timer is None:
        # 확인 프롬프트를 띄우기 전에 core(cancel_timer)와 같은 오류로 끝낸다.
        raise NotFoundError(services.NO_TIMER_MESSAGE)
    line = render.timer_line(timer)
    started_at = timer.started_at
    elapsed = _elapsed_text(timer, now)

    if not yes:
        runtime.require_confirmation(
            f"버릴 타이머: {line} (시작 {_started_label(timer, now)} "
            f"{render.info_mark()} 경과 {elapsed})\n버릴까요?",
            cancelled=CANCEL_DECLINED_MESSAGE,
            no_input=CANCEL_NO_INPUT_MESSAGE,
        )

    with runtime.session(cfg) as s:
        # 확인하는 동안 다른 터미널이 타이머를 저장·취소하거나 새로 시작했을 수 있다.
        # 확인한 타이머와 다르면 버리지 않는다.
        current = services.get_timer(s)
        if (
            current is None
            or current.started_at != started_at
            or str(render.timer_line(current)) != str(line)
        ):
            console.print_notice(CHANGED_WHILE_CONFIRMING_MESSAGE)
            raise typer.Exit(EXIT_ERROR)
        services.cancel_timer(s)

    console.print_line(render.ok_mark(), " 타이머를 버렸습니다: ", line, f" (경과 {elapsed})")


def register(app: typer.Typer) -> None:
    app.command("start", cls=LogbookCommand)(start)
    app.command("status", cls=LogbookCommand)(status)
    app.command("stop", cls=LogbookCommand)(stop)
    app.command("cancel", cls=LogbookCommand)(cancel)
