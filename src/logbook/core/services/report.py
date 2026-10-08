"""주간보고서 데이터 조립: 한 주의 기록과 태스크로 ReportData를 만든다.

실적은 WorkLog 집계로만 만든다. 태스크 줄의 시간은 보고 주 마지막 날까지의 누적이라
지난 주 보고서가 그 뒤의 기록 때문에 달라지지 않는다. 렌더링은 core.report가 맡는다.
"""

from collections.abc import Mapping
from datetime import date, datetime, time, timedelta, tzinfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from logbook.core.duration import format_duration
from logbook.core.errors import InvalidInputError
from logbook.core.models import Project, Task, TaskStatus, WorkLog
from logbook.core.report import (
    NO_VALUE,
    MatrixRow,
    PlanGroup,
    PlanItem,
    ProjectSection,
    ReportData,
    TaskLine,
    percent_text,
)
from logbook.core.services.stats import MatrixResult, stats_matrix
from logbook.core.services.tasks import list_tasks
from logbook.core.taskstatus import OPEN_STATUSES
from logbook.core.weeks import Week

# 보고서 안의 상태 순서(완료 → 진행 → 할 일 → 중단)와 표기
_STATUS_ORDER = (TaskStatus.DONE, TaskStatus.DOING, TaskStatus.TODO, TaskStatus.DROPPED)
_STATUS_TEXT = {
    TaskStatus.DONE: "완료",
    TaskStatus.DOING: "진행",
    TaskStatus.TODO: "할 일",
    TaskStatus.DROPPED: "중단",
}
_DONE_LABEL = "실제"
_OPEN_LABEL = "누적"


def weekly_report(
    s: Session,
    week: Week,
    *,
    tz: tzinfo,
    title_format: str,
    author: str,
    category_labels: Mapping[str, str],
) -> ReportData:
    """week의 보고서 데이터. tz는 완료 시각(UTC)을 로컬 날짜로 바꿀 때 쓴다."""
    title = _format_title(title_format, week)
    matrix = stats_matrix(s, week, category_order=tuple(category_labels))
    labels = {key: _one_line(category_labels.get(key, key)) for key in matrix.categories}
    return ReportData(
        title=title,
        author=author,
        week_label=week.label,
        start=week.start.isoformat(),
        end=week.end.isoformat(),
        total=format_duration(matrix.total_minutes),
        log_count=matrix.count,
        done_task_count=_done_task_count(s, week, tz),
        categories=tuple(labels[key] for key in matrix.categories),
        matrix=_matrix_rows(matrix),
        sections=_sections(s, week, tz, matrix, labels),
        plan=_plan(s, week),
    )


def _format_title(title_format: str, week: Week) -> str:
    # 날짜가 아니라 문자열로 넘긴다. strftime 지정자가 OS마다 달라지지 않게 하려는 것이다.
    try:
        return title_format.format(start=week.start.isoformat(), end=week.end.isoformat())
    except (KeyError, IndexError, AttributeError, TypeError, ValueError) as error:
        raise InvalidInputError(
            f"보고서 제목 형식이 올바르지 않습니다: '{title_format}'. "
            "사용할 수 있는 이름: {start}, {end}"
        ) from error


def _one_line(text: str) -> str:
    """줄바꿈·탭·연속 공백을 공백 하나로 줄인다."""
    return " ".join(text.split())


def _local_midnight(day: date, tz: tzinfo) -> datetime:
    return datetime.combine(day, time.min, tzinfo=tz)


def _done_task_count(s: Session, week: Week, tz: tzinfo) -> int:
    """완료 시각의 로컬 날짜가 주 범위 안인 완료 태스크 수(보관 프로젝트 포함)."""
    first = _local_midnight(week.start, tz)
    after = _local_midnight(week.end + timedelta(days=1), tz)
    count = s.scalar(
        select(func.count(Task.id)).where(
            Task.status == TaskStatus.DONE, Task.done_at >= first, Task.done_at < after
        )
    )
    return count or 0


def _matrix_rows(matrix: MatrixResult) -> tuple[MatrixRow, ...]:
    total = matrix.total_minutes
    return tuple(
        MatrixRow(
            project=slug,
            cells=tuple(
                _minutes_or_dash(matrix.cells.get((slug, category), 0))
                for category in matrix.categories
            ),
            total=format_duration(matrix.row_totals[slug]),
            percent=percent_text(matrix.row_totals[slug], total),
        )
        for slug in matrix.projects
    )


def _minutes_or_dash(minutes: int) -> str:
    return format_duration(minutes) if minutes else NO_VALUE


def _week_rows(s: Session, week: Week) -> list[tuple[str, int | None, str, int]]:
    """주 범위 기록을 (프로젝트 slug, 태스크 id, 카테고리, 분 합계)로 묶어 읽는다. 쿼리 한 번."""
    rows = s.execute(
        select(Project.slug, WorkLog.task_id, WorkLog.category, func.sum(WorkLog.minutes))
        .join(WorkLog.project)
        .where(WorkLog.date.between(week.start, week.end))
        .group_by(Project.slug, WorkLog.task_id, WorkLog.category)
    )
    return [(slug, task_id, category, int(minutes)) for slug, task_id, category, minutes in rows]


def _split_rows(
    rows: list[tuple[str, int | None, str, int]],
) -> tuple[dict[str, list[int]], dict[str, dict[str, int]]]:
    """프로젝트별로 (연결된 태스크 id 목록, 연결되지 않은 카테고리별 분)으로 나눈다."""
    # dict는 삽입 순서를 지키므로 순서를 유지한 채 중복을 없애는 데 쓴다.
    linked: dict[str, dict[int, None]] = {}
    unlinked: dict[str, dict[str, int]] = {}
    for slug, task_id, category, minutes in rows:
        if task_id is not None:
            linked.setdefault(slug, {})[task_id] = None
        else:
            by_category = unlinked.setdefault(slug, {})
            by_category[category] = by_category.get(category, 0) + minutes
    return {slug: list(ids) for slug, ids in linked.items()}, unlinked


def _sections(
    s: Session,
    week: Week,
    tz: tzinfo,
    matrix: MatrixResult,
    labels: Mapping[str, str],
) -> tuple[ProjectSection, ...]:
    if not matrix.projects:
        return ()
    rows = _week_rows(s, week)
    task_ids = sorted({task_id for _, task_id, _, _ in rows if task_id is not None})
    tasks = _tasks_by_id(s, task_ids)
    cumulative = _cumulative_minutes(s, task_ids, week.end)
    column = {category: index for index, category in enumerate(matrix.categories)}
    tasks_of, unlinked = _split_rows(rows)

    return tuple(
        ProjectSection(
            project=slug,
            total=format_duration(matrix.row_totals[slug]),
            tasks=_task_lines(
                [tasks[task_id] for task_id in tasks_of.get(slug, [])], cumulative, week, tz
            ),
            others=_others(unlinked.get(slug, {}), labels, column),
        )
        for slug in matrix.projects
    )


def _tasks_by_id(s: Session, task_ids: list[int]) -> dict[int, Task]:
    if not task_ids:
        return {}
    return {task.id: task for task in s.scalars(select(Task).where(Task.id.in_(task_ids)))}


def _cumulative_minutes(s: Session, task_ids: list[int], until: date) -> dict[int, int]:
    """태스크별 until(포함)까지의 연결 기록 합계(분). 쿼리 한 번."""
    if not task_ids:
        return {}
    rows = s.execute(
        select(WorkLog.task_id, func.sum(WorkLog.minutes))
        .where(WorkLog.task_id.in_(task_ids), WorkLog.date <= until)
        .group_by(WorkLog.task_id)
    )
    return {task_id: int(total) for task_id, total in rows if task_id is not None}


def _status_at_week_end(task: Task, week: Week, tz: tzinfo) -> TaskStatus:
    """현재 상태를 쓰되, 보고 주가 끝난 뒤에 완료한 태스크는 진행으로 본다."""
    finished_late = (
        task.status is TaskStatus.DONE
        and task.done_at is not None
        and task.done_at.astimezone(tz).date() > week.end
    )
    return TaskStatus.DOING if finished_late else task.status


def _task_lines(
    tasks: list[Task], cumulative: Mapping[int, int], week: Week, tz: tzinfo
) -> tuple[TaskLine, ...]:
    statuses = {task.id: _status_at_week_end(task, week, tz) for task in tasks}
    ordered = sorted(tasks, key=lambda task: (_STATUS_ORDER.index(statuses[task.id]), task.id))
    return tuple(
        TaskLine(
            status=_STATUS_TEXT[statuses[task.id]],
            title=_one_line(task.title),
            task_id=task.id,
            actual=format_duration(cumulative.get(task.id, 0)),
            estimate=_estimate_text(task),
            actual_label=_DONE_LABEL if statuses[task.id] is TaskStatus.DONE else _OPEN_LABEL,
        )
        for task in ordered
    )


def _estimate_text(task: Task) -> str | None:
    return None if task.estimate_minutes is None else format_duration(task.estimate_minutes)


def _others(
    unlinked: Mapping[str, int], labels: Mapping[str, str], column: Mapping[str, int]
) -> tuple[tuple[str, str], ...]:
    """연결되지 않은 기록을 라벨별로 합산한다. 시간 내림차순, 같으면 앞선 열 순서."""
    minutes: dict[str, int] = {}
    order: dict[str, int] = {}
    for category, value in unlinked.items():
        label = labels[category]
        minutes[label] = minutes.get(label, 0) + value
        order[label] = min(order.get(label, column[category]), column[category])
    ranked = sorted(minutes, key=lambda label: (-minutes[label], order[label]))
    return tuple((label, format_duration(minutes[label])) for label in ranked)


def _plan(s: Session, week: Week) -> tuple[PlanGroup, ...]:
    """다음 주 계획 태스크와 이번 주 미완료(이월 후보)를 프로젝트 slug 순으로 묶는다."""
    upcoming = list_tasks(s, statuses=OPEN_STATUSES, week=week.next())
    carried = list_tasks(s, statuses=OPEN_STATUSES, week=week)
    items: dict[str, list[tuple[Task, bool]]] = {}
    for task, is_carried in [(t, False) for t in upcoming] + [(t, True) for t in carried]:
        items.setdefault(task.project.slug, []).append((task, is_carried))
    return tuple(
        PlanGroup(
            project=slug,
            estimate_total=format_duration(sum(t.estimate_minutes or 0 for t, _ in entries)),
            items=tuple(
                PlanItem(_one_line(t.title), t.id, _estimate_text(t), is_carried)
                for t, is_carried in entries
            ),
        )
        for slug, entries in sorted(items.items())
    )
