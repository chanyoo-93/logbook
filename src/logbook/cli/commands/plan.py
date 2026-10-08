"""lb plan: 주간 계획(하위 명령 없이 실행), lb plan carry(이월)."""

from typing import TYPE_CHECKING

import typer

from logbook.cli import console, render, runtime
from logbook.cli.group import LogbookCommand, LogbookGroup
from logbook.core.errors import InvalidInputError

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from logbook.core.config import Config
    from logbook.core.models import Task
    from logbook.core.weeks import Week

# no_args_is_help를 두지 않는다(그러면 'lb plan'이 목록 대신 help를 보여 준다).
plan_app = typer.Typer(
    cls=LogbookGroup,
    help=(
        "주간 계획을 보고 남은 태스크를 다음 주로 옮깁니다. "
        "하위 명령 없이 실행하면 이번 주 계획을 보여 줍니다."
    ),
)

WEEK_WITH_SUBCOMMAND_MESSAGE = (
    "--week는 'lb plan' 목록에만 쓸 수 있습니다. "
    "이월할 주는 'lb plan carry -w last'처럼 하위 명령 뒤에 쓰세요."
)
EMPTY_PLAN_MESSAGE = "이 주에 계획된 태스크가 없습니다."
CARRY_QUESTION = "옮길까요?"
CARRY_CANCELLED_MESSAGE = "이월을 취소했습니다."
NO_CONFIRM_INPUT_MESSAGE = (
    "확인 입력을 받지 못해 옮기지 않았습니다. 확인 없이 옮기려면 --yes를 붙이세요."
)


def _parse_week(week: str | None, cfg: "Config") -> "Week":
    """'-w' 값(기본 this)을 주차로 바꾼다. 설정의 주 시작 요일을 따른다."""
    from logbook.core.weeks import parse_week

    return parse_week(
        week if week is not None else "this", today=runtime.today(), week_start=cfg.week_start
    )


@plan_app.callback(invoke_without_command=True)
def show_plan(ctx: typer.Context, week: runtime.WeekOpt = None) -> None:
    """주에 계획된 태스크(todo·doing·done)를 프로젝트, ID 순으로 보여 줍니다.

    기본은 이번 주입니다.
    """
    if ctx.invoked_subcommand is not None:
        # 하위 명령 앞에 쓴 -w가 조용히 무시되지 않게 막는다.
        if week is not None:
            raise InvalidInputError(WEEK_WITH_SUBCOMMAND_MESSAGE)
        return

    from logbook.core.taskstatus import TaskStatus
    from logbook.core.weeks import week_heading

    cfg = runtime.settings()
    span = _parse_week(week, cfg)

    # services는 SQLAlchemy를 로드하므로 검증이 끝난 뒤에 import한다.
    from logbook.core import services

    # 중단(dropped)은 계획에서 뺀다(설계 결정 7).
    statuses = (TaskStatus.TODO, TaskStatus.DOING, TaskStatus.DONE)
    with runtime.session(cfg) as s:
        tasks = services.list_tasks(s, week=span, statuses=statuses)
        actual = services.actual_minutes_by_task(s, [task.id for task in tasks])
    # 표에서 같은 프로젝트끼리 붙도록 프로젝트, ID 순으로 정렬한다.
    tasks = sorted(tasks, key=lambda task: (task.project.slug, task.id))

    console.print_line(f"{week_heading(span)} 계획   {_summary(tasks, actual)}")
    if not tasks:
        console.print_line(EMPTY_PLAN_MESSAGE)
        return
    console.print_table(render.plan_table(tasks, actual), lambda: render.plan_lines(tasks, actual))
    _print_estimates_by_project(tasks)


def _summary(tasks: "Sequence[Task]", actual: "Mapping[int, int]") -> str:
    """'예상 12h / 실적 7h 30m / 태스크 5건 (완료 2건)'. 완료가 없으면 괄호를 뺀다."""
    from logbook.core.duration import format_duration
    from logbook.core.taskstatus import TaskStatus

    estimate = sum(t.estimate_minutes for t in tasks if t.estimate_minutes is not None)
    done = sum(1 for t in tasks if t.status == TaskStatus.DONE)
    text = (
        f"예상 {format_duration(estimate)} / 실적 {format_duration(sum(actual.values()))} "
        f"/ 태스크 {len(tasks)}건"
    )
    return f"{text} (완료 {done}건)" if done else text


def _print_estimates_by_project(tasks: "Sequence[Task]") -> None:
    """'프로젝트별 예상: admin 4h · payment 8h'와 '예상이 없는 태스크 N건'."""
    from rich.text import Text

    from logbook.core.duration import format_duration

    by_project: dict[str, int] = {}
    for task in tasks:
        if task.estimate_minutes is not None:
            slug = task.project.slug
            by_project[slug] = by_project.get(slug, 0) + task.estimate_minutes
    if by_project:
        parts: list[str | Text] = []
        for index, slug in enumerate(sorted(by_project)):
            if index:
                parts.append(f" {render.info_mark()} ")
            parts.extend((Text(slug), f" {format_duration(by_project[slug])}"))
        console.print_line("프로젝트별 예상: ", *parts)
    missing = sum(1 for task in tasks if task.estimate_minutes is None)
    if missing:
        console.print_line(f"예상이 없는 태스크 {missing}건")


def _print_carry_preview(src: "Week", dst: "Week", candidates: "Sequence[Task]") -> None:
    """stderr에 이월 미리보기: '이월할 태스크 (W40 → W41):'와 '#1 doing payment/design 제목' 줄."""
    console.print_notice(f"이월할 태스크 ({src.label} {render.arrow()} {dst.label}):")
    for task in candidates:
        console.print_notice(f"#{task.id} {task.status} ", render.task_scope_title(task))


@plan_app.command("carry", cls=LogbookCommand)
def carry(week: runtime.WeekOpt = None, yes: runtime.YesOpt = False) -> None:
    """주(기본 이번 주)에 계획된 todo·doing 태스크를 다음 주로 옮깁니다.

    --yes가 없으면 먼저 확인합니다.
    """
    cfg = runtime.settings()
    src = _parse_week(week, cfg)
    dst = src.next()

    from logbook.core import services

    # 사람이 답하는 동안 SQLite 잠금을 쥐지 않도록 조회와 변경을 다른 세션으로 나눈다.
    with runtime.session(cfg) as s:
        candidates = services.carry_candidates(s, src)

    if not candidates:
        console.print_line(
            f"이월할 태스크가 없습니다 ({src.label} 주차의 todo{render.info_mark()}doing 태스크)."
        )
        return

    if not yes:
        _print_carry_preview(src, dst, candidates)
        runtime.require_confirmation(
            CARRY_QUESTION, cancelled=CARRY_CANCELLED_MESSAGE, no_input=NO_CONFIRM_INPUT_MESSAGE
        )

    with runtime.session(cfg) as s:
        # 확인하는 동안 상태·주차가 바뀐 후보는 서비스가 건너뛴다.
        moved = services.carry_tasks(s, src, [task.id for task in candidates])

    # 주차 뒤에 조사를 붙이지 않는다(W40은 '으로', W41은 '로'라 하나로 맞출 수 없다).
    console.print_line(
        render.ok_mark(), f" {len(moved)}건을 옮겼습니다: {src.label} {render.arrow()} {dst.label}"
    )
    for task in moved:
        console.print_line(render.task_line(task))
    skipped = len(candidates) - len(moved)
    if skipped:
        console.print_warning(f"{skipped}건은 확인하는 동안 바뀌어 옮기지 않았습니다.")


def register(app: typer.Typer) -> None:
    app.add_typer(plan_app, name="plan")
