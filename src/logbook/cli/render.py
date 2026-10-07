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


def worklog_line(log: "WorkLog") -> "Text":
    """기록 한 줄 요약: '#128 payment/dev 2h — 결제 재시도 로직 구현'."""
    from rich.text import Text

    from logbook.core.duration import format_duration

    return Text.assemble(
        f"#{log.id} ",
        Text(log.project.slug),
        "/",
        Text(log.category),
        f" {format_duration(log.minutes)} {dash()} ",
        Text(log.note),
    )


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
