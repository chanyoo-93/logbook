"""주간보고서 데이터 클래스와 표기 도우미. SQLAlchemy를 import하지 않는다.

DB에서 읽어 이 데이터를 만드는 일은 core.services.weekly_report가 맡는다.
시간·비율은 모두 표기가 끝난 문자열로 담아, 템플릿이 표기를 다시 구현하지 않게 한다.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class MatrixRow:
    project: str  # slug
    cells: tuple[str, ...]  # categories 순서의 시간 표기, 0이면 "-"
    total: str
    percent: str


@dataclass(frozen=True)
class TaskLine:
    status: str  # "완료" | "진행" | "할 일" | "중단"
    title: str
    task_id: int
    actual: str  # 보고 주 마지막 날까지의 누적(이번 주만이 아님)
    estimate: str | None
    actual_label: str  # "실제"(완료) | "누적"


@dataclass(frozen=True)
class ProjectSection:
    project: str
    total: str  # 이번 주 이 프로젝트 합계
    tasks: tuple[TaskLine, ...]
    others: tuple[tuple[str, str], ...]  # (카테고리 라벨, 시간), 비면 기타 줄 생략


@dataclass(frozen=True)
class PlanItem:
    title: str
    task_id: int
    estimate: str | None
    carried: bool  # 이번 주 미완료에서 넘어온 후보


@dataclass(frozen=True)
class PlanGroup:
    project: str
    estimate_total: str  # 예상 합계, 하나도 없으면 "0m"
    items: tuple[PlanItem, ...]


@dataclass(frozen=True)
class ReportData:
    title: str
    author: str
    week_label: str  # "2026-W40"
    start: str  # "2026-09-28"
    end: str
    total: str  # "35h"
    log_count: int
    done_task_count: int
    categories: tuple[str, ...]  # 표 머리글(라벨)
    matrix: tuple[MatrixRow, ...]
    sections: tuple[ProjectSection, ...]
    plan: tuple[PlanGroup, ...]


NO_VALUE = "-"


def percent_text(part: int, total: int) -> str:
    """비율의 정수 반올림(half-up) 표기: '54%'. total이나 part가 0이면 '-'."""
    if total == 0 or part == 0:
        return NO_VALUE
    return f"{(200 * part + total) // (2 * total)}%"
