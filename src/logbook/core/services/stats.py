"""주간 공수 집계: 프로젝트·카테고리·요일별 합계와 프로젝트 x 카테고리 표.

보관된 프로젝트의 기록도 집계한다. 범위는 week.start~week.end(sunday 모드 반영)다.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Literal, get_args

from sqlalchemy import Select, func, select
from sqlalchemy.orm import QueryableAttribute, Session

from logbook.core.errors import InvalidInputError
from logbook.core.models import Project, WorkLog
from logbook.core.weeks import Week, day_label

StatsBy = Literal["project", "category", "day"]


@dataclass(frozen=True)
class StatsRow:
    key: str
    label: str
    minutes: int
    count: int


@dataclass(frozen=True)
class StatsResult:
    week: Week
    by: StatsBy
    total_minutes: int
    count: int
    rows: tuple[StatsRow, ...]


@dataclass(frozen=True)
class MatrixResult:
    """프로젝트(slug) x 카테고리 표. cells에는 기록이 있는 칸만 들어 있다."""

    week: Week
    projects: tuple[str, ...]
    categories: tuple[str, ...]
    cells: Mapping[tuple[str, str], int]
    row_totals: Mapping[str, int]
    col_totals: Mapping[str, int]
    total_minutes: int
    count: int


def stats_by(
    s: Session,
    week: Week,
    by: StatsBy,
    *,
    category_labels: Mapping[str, str] | None = None,
) -> StatsResult:
    """week의 기록을 by 기준으로 묶은 합계(분)와 건수.

    project·category는 기록이 있는 묶음만 시간 내림차순(같으면 key 순), day는 7일 모두 날짜 순.
    """
    if by == "project":
        rows = _project_rows(s, week)
    elif by == "category":
        rows = _category_rows(s, week, category_labels)
    elif by == "day":
        rows = _day_rows(s, week)
    else:
        choices = ", ".join(get_args(StatsBy))
        raise InvalidInputError(
            f"집계 기준이 올바르지 않습니다: '{by}'. {choices} 중 하나를 쓰세요."
        )
    return StatsResult(
        week=week,
        by=by,
        total_minutes=sum(row.minutes for row in rows),
        count=sum(row.count for row in rows),
        rows=rows,
    )


def stats_matrix(
    s: Session, week: Week, *, category_order: Sequence[str] | None = None
) -> MatrixResult:
    """week의 프로젝트 x 카테고리 합계(분) 표.

    프로젝트는 합계 내림차순(같으면 slug 순). 카테고리는 category_order에 있는 것을 그 순서로,
    나머지는 이름 순으로 뒤에 붙인다. 기록이 없는 카테고리는 열에서 뺀다.
    """
    query = _grouped(week, Project.slug, WorkLog.category).join(WorkLog.project)
    cells: dict[tuple[str, str], int] = {}
    row_totals: dict[str, int] = {}
    col_totals: dict[str, int] = {}
    count = 0
    for slug, category, minutes, logs in s.execute(query):
        cells[(slug, category)] = minutes
        row_totals[slug] = row_totals.get(slug, 0) + minutes
        col_totals[category] = col_totals.get(category, 0) + minutes
        count += logs
    projects = sorted(row_totals, key=lambda slug: (-row_totals[slug], slug))
    return MatrixResult(
        week=week,
        projects=tuple(projects),
        categories=_ordered_categories(col_totals, category_order),
        cells=MappingProxyType(cells),
        row_totals=MappingProxyType(row_totals),
        col_totals=MappingProxyType(col_totals),
        total_minutes=sum(row_totals.values()),
        count=count,
    )


def _grouped(week: Week, *keys: QueryableAttribute[Any]) -> Select[*tuple[Any, ...]]:
    """week 범위의 기록을 keys로 묶어 (keys..., 분 합계, 건수)를 고르는 쿼리."""
    # 행 타입은 Any다. minutes는 NOT NULL이라 묶음마다 sum()이 None이 아닌 int다.
    return (
        select(*keys, func.sum(WorkLog.minutes), func.count(WorkLog.id))
        .where(WorkLog.date.between(week.start, week.end))
        .group_by(*keys)
    )


def _by_minutes(rows: list[StatsRow]) -> tuple[StatsRow, ...]:
    return tuple(sorted(rows, key=lambda row: (-row.minutes, row.key)))


def _project_rows(s: Session, week: Week) -> tuple[StatsRow, ...]:
    query = _grouped(week, Project.slug, Project.name).join(WorkLog.project)
    rows = [StatsRow(slug, name, minutes, logs) for slug, name, minutes, logs in s.execute(query)]
    return _by_minutes(rows)


def _category_rows(
    s: Session, week: Week, labels: Mapping[str, str] | None
) -> tuple[StatsRow, ...]:
    query = _grouped(week, WorkLog.category)
    rows = [
        StatsRow(
            category,
            labels.get(category, category) if labels is not None else category,
            minutes,
            logs,
        )
        for category, minutes, logs in s.execute(query)
    ]
    return _by_minutes(rows)


def _day_rows(s: Session, week: Week) -> tuple[StatsRow, ...]:
    totals = {
        day: (minutes, logs) for day, minutes, logs in s.execute(_grouped(week, WorkLog.date))
    }
    rows = []
    for day in week.days():
        minutes, logs = totals.get(day, (0, 0))
        rows.append(StatsRow(day.isoformat(), day_label(day), minutes, logs))
    return tuple(rows)


def _ordered_categories(present: Mapping[str, int], order: Sequence[str] | None) -> tuple[str, ...]:
    """order에 있는 카테고리를 그 순서로, 나머지를 이름 순으로. 기록 없는 것은 뺀다."""
    leading = [] if order is None else [c for c in dict.fromkeys(order) if c in present]
    rest = sorted(set(present) - set(leading))
    return (*leading, *rest)
