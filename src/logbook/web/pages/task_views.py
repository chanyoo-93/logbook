"""태스크 화면이 쓰는 뷰 데이터: 칸반 보드, 카드, 추가 폼, 태스크 버전.

서비스가 돌려준 ORM 객체는 세션 안에서 이 모듈의 불변 값으로 바꾼다. 템플릿은 세션을 닫은 뒤 그린다.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC
from types import MappingProxyType
from typing import TYPE_CHECKING

from logbook.core import services
from logbook.core.duration import format_duration
from logbook.core.report import PlanGroup
from logbook.core.taskstatus import TaskStatus
from logbook.core.weeks import week_heading, week_of
from logbook.web.pages.views import (
    Choice,
    category_choices,
    content_version,
    project_choices,
    project_color,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from logbook.core.models import Task
    from logbook.core.weeks import Week
    from logbook.web.context import WebContext

STATUS_LABELS: Mapping[TaskStatus, str] = MappingProxyType(
    {
        TaskStatus.TODO: "할 일",
        TaskStatus.DOING: "진행",
        TaskStatus.DONE: "완료",
        TaskStatus.DROPPED: "중단",
    }
)
DROP_CONFIRM = (
    "중단할 태스크: #{id} {project} · {title}\n"
    "중단할까요? 중단한 태스크는 이 화면에 보이지 않습니다."
)
CARRY_CONFIRM = "이번 주의 할 일·진행 태스크를 다음 주로 옮길까요?\n{this} → {next}, {count}건"
COLUMN_TITLES = (("todo", "할 일"), ("doing", "진행 중"), ("done", "이번 주 완료"))
THIS_WEEK_TAG = "이번 주"
NEXT_WEEK_TAG = "다음 주"
LAST_WEEK_TAG = "지난 주"
# 상태 -> (버튼 글, 바꿀 상태, 확인 창이 필요한가)
_ACTIONS: Mapping[TaskStatus, tuple[tuple[str, TaskStatus, bool], ...]] = MappingProxyType(
    {
        TaskStatus.TODO: (
            ("시작", TaskStatus.DOING, False),
            ("완료", TaskStatus.DONE, False),
            ("중단", TaskStatus.DROPPED, True),
        ),
        TaskStatus.DOING: (
            ("완료", TaskStatus.DONE, False),
            ("할 일로", TaskStatus.TODO, False),
            ("중단", TaskStatus.DROPPED, True),
        ),
        TaskStatus.DONE: (("다시 열기", TaskStatus.DOING, False),),
        TaskStatus.DROPPED: (),
    }
)


@dataclass(frozen=True)
class StatusAction:
    status: str  # 'doing'
    label: str  # '시작'
    confirm: str  # 확인 창 문구, 없으면 ''


@dataclass(frozen=True)
class TaskCardView:
    id: int
    title: str
    project: str  # slug
    project_color: str  # '#rrggbb' (색 점)
    category: str  # key 또는 ''
    week: str  # '2026-W42' 또는 ''
    week_tag: str  # '이번 주' | '다음 주' | '지난 주' | ''
    actual: str  # 연결 기록 합계 '3h'(없으면 '0m')
    estimate: str  # '4h' 또는 ''
    over: bool  # 실적이 예상보다 많음
    percent: int  # 진행 막대 채움 0~100(예상이 없으면 0, 막대도 그리지 않는다)
    version: str
    actions: tuple[StatusAction, ...]


@dataclass(frozen=True)
class TaskColumnView:
    key: str  # 'todo' | 'doing' | 'done'
    title: str  # '할 일' | '진행 중' | '이번 주 완료'
    cards: tuple[TaskCardView, ...]


@dataclass(frozen=True)
class TaskBoardView:
    columns: tuple[TaskColumnView, ...]
    project: str  # 필터('' = 전체)
    message: str = ""
    is_error: bool = False


@dataclass(frozen=True)
class TaskFormValues:
    """추가 폼에 채워 둘 값(입력 문자열 그대로)."""

    title: str = ""
    task_project: str = ""
    task_category: str = ""
    estimate: str = ""
    week: str = ""


@dataclass(frozen=True)
class TaskFormView:
    """추가 폼: 채워 둘 값, 선택지, 결과 줄."""

    values: TaskFormValues
    projects: tuple[Choice, ...]  # 보관하지 않은 프로젝트
    categories: tuple[Choice, ...]
    default_project: str
    message: str = ""
    is_error: bool = False


@dataclass(frozen=True)
class TaskEditValues:
    """편집 카드에 채워 둘 값(입력 문자열 그대로, 오류 뒤에도 유지)."""

    title: str
    task_category: str  # key 또는 ''
    estimate: str  # '4h' 또는 ''
    week: str  # '2026-W42' 또는 ''
    version: str


@dataclass(frozen=True)
class TaskEditView:
    id: int
    project: str
    values: TaskEditValues
    categories: tuple[Choice, ...]  # 설정 카테고리 + 현재 값
    error: str = ""


@dataclass(frozen=True)
class PlanPanelView:
    heading: str  # '다음 주 계획 2026-W43 (10-19 ~ 10-25)'
    groups: tuple[PlanGroup, ...]
    carry_ids: tuple[int, ...]  # 표시된 이월 후보의 id
    carry_confirm: str
    message: str = ""
    is_error: bool = False


@dataclass(frozen=True)
class TaskFilterView:
    project: str  # 선택된 프로젝트 slug ('' = 전체)
    projects: tuple[Choice, ...]  # 보관 프로젝트를 포함한다


def task_version(task: Task) -> str:
    """화면이 본 태스크가 그사이 바뀌었는지 가리는 값.

    updated_at은 넣지 않는다. update_task는 바뀐 값이 없어도 updated_at을 바꾸므로,
    넣으면 내용이 같아도 충돌로 보인다.
    """
    return content_version(
        task.id,
        task.project_id,
        task.title,
        task.description,
        task.status.value,
        task.category,
        task.estimate_minutes,
        task.planned_week,
        task.due_date,
        task.external_ref,
        task.created_at.isoformat(),
        None if task.done_at is None else task.done_at.isoformat(),
    )


def _actions(task: Task) -> tuple[StatusAction, ...]:
    return tuple(
        StatusAction(
            status=status.value,
            label=label,
            confirm=(
                DROP_CONFIRM.format(id=task.id, project=task.project.slug, title=task.title)
                if needs_confirm
                else ""
            ),
        )
        for label, status, needs_confirm in _ACTIONS[task.status]
    )


def _week_tag(label: str | None, this_week: Week) -> str:
    """계획 주차 꼬리표. 이번 주와 바로 앞뒤 주만 이름을 붙인다."""
    if label == this_week.label:
        return THIS_WEEK_TAG
    if label == this_week.next().label:
        return NEXT_WEEK_TAG
    if label == this_week.prev().label:
        return LAST_WEEK_TAG
    return ""


def progress_percent(actual_minutes: int, estimate_minutes: int) -> int:
    """실적/예상 비율을 0~100 정수로. 예상이 0이면 실적이 있을 때만 100."""
    if estimate_minutes <= 0:
        return 100 if actual_minutes > 0 else 0
    return min(100, round(actual_minutes / estimate_minutes * 100))


def task_card(task: Task, actual_minutes: int, this_week: Week) -> TaskCardView:
    estimate = task.estimate_minutes
    return TaskCardView(
        id=task.id,
        title=task.title,
        project=task.project.slug,
        project_color=project_color(task.project),
        category=task.category or "",
        week=task.planned_week or "",
        week_tag=_week_tag(task.planned_week, this_week),
        actual=format_duration(actual_minutes),
        estimate="" if estimate is None else format_duration(estimate),
        over=estimate is not None and actual_minutes > estimate,
        percent=0 if estimate is None else progress_percent(actual_minutes, estimate),
        version=task_version(task),
        actions=_actions(task),
    )


def _column(
    key: str, title: str, tasks: Sequence[Task], actual: Mapping[int, int], this_week: Week
) -> TaskColumnView:
    cards = tuple(task_card(task, actual.get(task.id, 0), this_week) for task in tasks)
    return TaskColumnView(key=key, title=title, cards=cards)


def task_board(
    s: Session, ctx: WebContext, project: str, *, message: str = "", is_error: bool = False
) -> TaskBoardView:
    """칸반 보드. project가 ''면 전체, 없는 프로젝트는 NotFoundError다.

    할 일·진행 중은 열린 태스크, 완료 열은 이번 주에 완료한 태스크다. 중단한 태스크는 없다.
    """
    now = ctx.now()
    this_week = week_of(now.date(), ctx.cfg.week_start)
    slug = project or None
    open_tasks = services.list_tasks(
        s, project_slug=slug, statuses=(TaskStatus.TODO, TaskStatus.DOING)
    )
    done_tasks = services.done_tasks_in_week(s, this_week, tz=now.tzinfo or UTC, project_slug=slug)
    shown = [*open_tasks, *done_tasks]
    actual = services.actual_minutes_by_task(s, [task.id for task in shown])
    by_key = {
        "todo": [t for t in open_tasks if t.status == TaskStatus.TODO],
        "doing": [t for t in open_tasks if t.status == TaskStatus.DOING],
        "done": done_tasks,
    }
    columns = tuple(
        _column(key, title, by_key[key], actual, this_week) for key, title in COLUMN_TITLES
    )
    return TaskBoardView(columns=columns, project=project, message=message, is_error=is_error)


def task_form_view(
    s: Session,
    ctx: WebContext,
    values: TaskFormValues,
    *,
    message: str = "",
    is_error: bool = False,
) -> TaskFormView:
    """추가 폼. 프로젝트 선택지는 보관 프로젝트를 뺀다."""
    return TaskFormView(
        values=values,
        projects=project_choices(s, archived=False),
        categories=category_choices(ctx.cfg, values.task_category),
        default_project=ctx.cfg.default_project,
        message=message,
        is_error=is_error,
    )


def task_filter_view(s: Session, project: str) -> TaskFilterView:
    return TaskFilterView(project=project, projects=project_choices(s))


def edit_values(task: Task) -> TaskEditValues:
    estimate = task.estimate_minutes
    return TaskEditValues(
        title=task.title,
        task_category=task.category or "",
        estimate="" if estimate is None else format_duration(estimate),
        week=task.planned_week or "",
        version=task_version(task),
    )


def task_edit_view(
    ctx: WebContext, task: Task, values: TaskEditValues, *, error: str = ""
) -> TaskEditView:
    return TaskEditView(
        id=task.id,
        project=task.project.slug,
        values=values,
        categories=category_choices(ctx.cfg, task.category or ""),
        error=error,
    )


def plan_panel(
    s: Session, ctx: WebContext, project: str, *, message: str = "", is_error: bool = False
) -> PlanPanelView:
    """다음 주 계획 패널. 보고서 4절과 같은 묶음이고, project가 있으면 그 프로젝트만 보인다."""
    this_week = week_of(ctx.today(), ctx.cfg.week_start)
    next_week = this_week.next()
    groups = tuple(
        group
        for group in services.next_week_plan(s, this_week)
        if not project or group.project == project
    )
    carry_ids = tuple(item.task_id for group in groups for item in group.items if item.carried)
    return PlanPanelView(
        heading=f"다음 주 계획 {week_heading(next_week)}",
        groups=groups,
        carry_ids=carry_ids,
        carry_confirm=CARRY_CONFIRM.format(
            this=this_week.label, next=next_week.label, count=len(carry_ids)
        ),
        message=message,
        is_error=is_error,
    )
