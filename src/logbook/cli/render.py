"""출력 줄과 표 조립. 사용자 데이터(slug, 이름, 메모 등)는 항상 rich.text.Text로 감싼다.

rich와 core 모델은 CLI 시작 시간을 줄이려고 함수 안이나 TYPE_CHECKING에서만 import한다.
"""

from datetime import date
from typing import TYPE_CHECKING

from logbook.core.platform import symbol

if TYPE_CHECKING:
    from collections.abc import Sequence

    from rich.table import Table
    from rich.text import Text

    from logbook.core.models import Project, WorkLog

# 접을 수 있는(fold) 이름 열의 최소 폭
NAME_MIN_WIDTH = 10
# 기록 표 메모 열의 최소 폭
NOTE_MIN_WIDTH = 10
NO_VALUE = "-"


def ok_mark() -> tuple[str, str]:
    """성공 기호와 스타일."""
    return (symbol("✔", "v"), "green")


def info_mark() -> str:
    """안내 기호."""
    return symbol("·", "-")


def arrow() -> str:
    """변화 표시 화살표 (예: v1 → v2)."""
    return symbol("→", "->")


def dash() -> str:
    """메모 앞 대시."""
    return symbol("—", "-")


def _summary(log: "WorkLog", *, day_text: str | None = None, suffix: str = "") -> "Text":
    """'#128 {day_text} payment/dev 2h — 메모{suffix}' 형식의 기록 요약.

    day_text가 없으면 날짜를 뺀다: '#128 payment/dev 2h — 메모'.
    """
    from rich.text import Text

    from logbook.core.duration import format_duration

    day_part = f"{day_text} " if day_text is not None else ""
    return Text.assemble(
        f"#{log.id} {day_part}",
        Text(log.project.slug),
        "/",
        Text(log.category),
        f" {format_duration(log.minutes)} {dash()} ",
        Text(log.note),
        suffix,
    )


def worklog_line(log: "WorkLog") -> "Text":
    """기록 한 줄 요약: '#128 payment/dev 2h — 결제 재시도 로직 구현'."""
    return _summary(log)


def full_day(d: date) -> str:
    """연도를 붙인 날짜·요일 표기: '2026-10-01 (목)'."""
    from logbook.core.weeks import day_label

    return f"{d.year:04d}-{day_label(d)}"


def worklog_record(log: "WorkLog") -> "Text":
    """연도를 붙인 기록 한 줄 요약.

    예: '#128 2026-10-01 (목) payment/dev 2h — 결제 재시도 로직 구현'
    """
    return _summary(log, day_text=full_day(log.date))


def task_ref(log: "WorkLog") -> str:
    """연결된 태스크 표기: '#42', 없으면 '-'."""
    return f"#{log.task_id}" if log.task_id is not None else NO_VALUE


def worklog_table(logs: "Sequence[WorkLog]") -> "Table":
    """기록 표(SPEC 5): ID | 날짜 | 프로젝트 | 카테고리 | 시간 | 메모 | Task. 메모 열만 접는다."""
    from rich.text import Text

    from logbook.core.duration import format_duration
    from logbook.core.weeks import day_label

    table = new_table()
    table.add_column("ID", justify="right", no_wrap=True)
    table.add_column("날짜", no_wrap=True)
    table.add_column("프로젝트", no_wrap=True)
    table.add_column("카테고리", no_wrap=True)
    table.add_column("시간", justify="right", no_wrap=True)
    table.add_column("메모", overflow="fold", min_width=NOTE_MIN_WIDTH)
    table.add_column("Task", no_wrap=True)
    for log in logs:
        table.add_row(
            str(log.id),
            day_label(log.date),
            Text(log.project.slug),
            Text(log.category),
            format_duration(log.minutes),
            Text(log.note),
            task_ref(log),
        )
    return table


def worklog_lines(logs: "Sequence[WorkLog]") -> "list[Text]":
    """좁은 화면용 기록 목록: '#128 10-01 (목) payment/dev 2h — 메모 [#42]'.

    태스크가 없으면 끝의 '[#42]'를 생략한다.
    """
    from logbook.core.weeks import day_label

    return [
        _summary(
            log,
            day_text=day_label(log.date),
            suffix=f" [#{log.task_id}]" if log.task_id is not None else "",
        )
        for log in logs
    ]


def total_label(day: date, today: date) -> str:
    """누적 합계의 날짜 표기: 오늘이면 '오늘', 아니면 'MM-DD'(예: '09-30')."""
    if day == today:
        return "오늘"
    return f"{day.month:02d}-{day.day:02d}"


def new_table() -> "Table":
    """공통 표 형식: 테두리 없음, 바깥 여백 없음, 굵은 머리글."""
    from rich.table import Table

    return Table(box=None, pad_edge=False, header_style="bold")


def project_table(projects: "Sequence[Project]", *, show_status: bool) -> "Table":
    """프로젝트 목록 표: slug | 이름 | 색상 (| 상태)."""
    from rich.text import Text

    table = new_table()
    table.add_column("slug", no_wrap=True)
    table.add_column("이름", overflow="fold", min_width=NAME_MIN_WIDTH)
    table.add_column("색상", no_wrap=True)
    if show_status:
        table.add_column("상태", no_wrap=True)
    for project in projects:
        cells = [
            Text(project.slug),
            Text(project.name),
            Text(project.color) if project.color else Text(NO_VALUE),
        ]
        if show_status:
            cells.append(Text("보관" if project.archived else "사용 중"))
        table.add_row(*cells)
    return table
