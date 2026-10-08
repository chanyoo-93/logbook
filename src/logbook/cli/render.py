"""출력 줄과 표 조립. 사용자 데이터(slug, 이름, 메모 등)는 항상 rich.text.Text로 감싼다.

rich와 core 모델은 CLI 시작 시간을 줄이려고 함수 안이나 TYPE_CHECKING에서만 import한다.
"""

from datetime import date, datetime
from typing import TYPE_CHECKING

from logbook.core.platform import symbol

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from rich.table import Table
    from rich.text import Text

    from logbook.core.models import ActiveTimer, Project, Task, WorkLog
    from logbook.core.services import MatrixResult, StatsResult

# 접을 수 있는(fold) 이름 열의 최소 폭
NAME_MIN_WIDTH = 10
# 기록 표 메모 열의 최소 폭
NOTE_MIN_WIDTH = 10
# 태스크·계획 표 제목 열의 최소 폭
TITLE_MIN_WIDTH = 10
# 태스크 표 참조 열의 최소 폭
REF_MIN_WIDTH = 6
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


def percent(part: int, total: int) -> str:
    """비율의 정수 반올림(half-up) 표기: '54%'. total이나 part가 0이면 '-'."""
    if total == 0 or part == 0:
        return NO_VALUE
    return f"{(200 * part + total) // (2 * total)}%"


def _minutes_or_dash(minutes: int) -> str:
    """시간 표기. 0분이면 '-'."""
    from logbook.core.duration import format_duration

    return format_duration(minutes) if minutes else NO_VALUE


def matrix_table(result: "MatrixResult", labels: "Mapping[str, str]") -> "Table":
    """프로젝트 x 카테고리 표: 프로젝트 | 카테고리 라벨들 | 합계. 빈 칸은 '-'.

    설정에 없는 카테고리는 key를 그대로 머리글로 쓴다. 모든 열을 접지 않는다.
    """
    from rich.text import Text

    table = new_table()
    table.add_column("프로젝트", no_wrap=True)
    for category in result.categories:
        table.add_column(Text(labels.get(category, category)), justify="right", no_wrap=True)
    table.add_column("합계", justify="right", no_wrap=True)
    for slug in result.projects:
        table.add_row(
            Text(slug),
            *(
                _minutes_or_dash(result.cells.get((slug, category), 0))
                for category in result.categories
            ),
            _minutes_or_dash(result.row_totals[slug]),
        )
    return table


def matrix_lines(result: "MatrixResult", labels: "Mapping[str, str]") -> "list[Text]":
    """좁은 화면용 행렬 목록: 'payment  19h  개발 14h · 코드리뷰 3h · 회의 2h'.

    기록이 있는 칸만 카테고리 열 순서대로 적는다.
    """
    from rich.text import Text

    from logbook.core.duration import format_duration

    lines = []
    for slug in result.projects:
        parts: list[str | Text] = [Text(slug), f"  {format_duration(result.row_totals[slug])}  "]
        cells = [
            (category, result.cells[(slug, category)])
            for category in result.categories
            if (slug, category) in result.cells
        ]
        for index, (category, minutes) in enumerate(cells):
            if index:
                parts.append(f" {info_mark()} ")
            parts.extend((Text(labels.get(category, category)), f" {format_duration(minutes)}"))
        lines.append(Text.assemble(*parts))
    return lines


def by_table(result: "StatsResult") -> "Table":
    """묶음별 합계 표. 이름 열만 접는다.

    - project:  프로젝트 | 이름 | 시간 | 건수 | 비율
    - category: 카테고리 | 이름 | 시간 | 건수 | 비율
    - day:      날짜('09-28 (월)') | 시간(0이면 '-') | 건수 | 비율
    """
    from rich.text import Text

    table = new_table()
    if result.by == "day":
        table.add_column("날짜", no_wrap=True)
    else:
        table.add_column("프로젝트" if result.by == "project" else "카테고리", no_wrap=True)
        table.add_column("이름", overflow="fold", min_width=NAME_MIN_WIDTH)
    table.add_column("시간", justify="right", no_wrap=True)
    table.add_column("건수", justify="right", no_wrap=True)
    table.add_column("비율", justify="right", no_wrap=True)
    for row in result.rows:
        # day의 key는 ISO 날짜라 화면에는 label('09-28 (월)')만 쓴다.
        lead = [Text(row.label)] if result.by == "day" else [Text(row.key), Text(row.label)]
        table.add_row(
            *lead,
            _minutes_or_dash(row.minutes),
            str(row.count),
            percent(row.minutes, result.total_minutes),
        )
    return table


def clock_label(moment: datetime, today: date) -> str:
    """표시 시각: 오늘이면 '09:30', 아니면 '09-30 (수) 22:10'.

    moment는 호출자가 이미 로컬 시간대로 바꾼 값이다(x.astimezone(now.tzinfo)).
    """
    from logbook.core.weeks import day_label

    time_text = f"{moment.hour:02d}:{moment.minute:02d}"
    if moment.date() == today:
        return time_text
    return f"{day_label(moment.date())} {time_text}"


def _scope(slug: str, category: str | None) -> "Text":
    """'payment/design', 카테고리가 없으면 'payment'."""
    from rich.text import Text

    if category is None:
        return Text(slug)
    return Text.assemble(Text(slug), "/", Text(category))


def _join_info(parts: "Sequence[str | Text]") -> "Text":
    """항목을 ' · '로 잇는다."""
    from rich.text import Text

    joined: list[str | Text] = []
    for index, part in enumerate(parts):
        if index:
            joined.append(f" {info_mark()} ")
        joined.append(part)
    return Text.assemble(*joined)


def _estimate_part(minutes: int) -> str:
    from logbook.core.duration import format_duration

    return f"예상 {format_duration(minutes)}"


def _ref_part(ref: str) -> "Text":
    from rich.text import Text

    return Text.assemble("참조 ", Text(ref))


def task_line(task: "Task") -> "Text":
    """태스크 요약: '#43 payment/design 환불 API 설계', 카테고리가 없으면 '#44 admin 권한 정리'."""
    from rich.text import Text

    return Text.assemble(
        f"#{task.id} ", _scope(task.project.slug, task.category), " ", Text(task.title)
    )


def task_details(task: "Task") -> "Text":
    """태스크 상세 꼬리: ' (예상 4h · 2026-W42 · 참조 #43 · 마감 10-15)'.

    값이 있는 항목만 넣고, 하나도 없으면 빈 Text를 돌려준다.
    """
    from rich.text import Text

    parts: list[str | Text] = []
    if task.estimate_minutes is not None:
        parts.append(_estimate_part(task.estimate_minutes))
    if task.planned_week is not None:
        parts.append(Text(task.planned_week))
    if task.external_ref is not None:
        parts.append(_ref_part(task.external_ref))
    if task.due_date is not None:
        parts.append(f"마감 {task.due_date.month:02d}-{task.due_date.day:02d}")
    if not parts:
        return Text()
    return Text.assemble(" (", _join_info(parts), ")")


def _estimate_or_dash(minutes: int | None) -> str:
    """예상 공수 표기. 없으면 '-'."""
    return _minutes_or_dash(minutes) if minutes is not None else NO_VALUE


def _text_or_dash(value: str | None) -> "Text":
    from rich.text import Text

    return Text(value if value is not None else NO_VALUE)


def task_table(tasks: "Sequence[Task]", actual: "Mapping[int, int]") -> "Table":
    """태스크 표: ID | 상태 | 프로젝트 | 카테고리 | 제목 | 예상 | 실적 | 주차 | 참조.

    제목과 참조 열만 접는다. 빈 값과 실적 0분은 '-'.
    """
    from rich.text import Text

    table = new_table()
    table.add_column("ID", justify="right", no_wrap=True)
    table.add_column("상태", no_wrap=True)
    table.add_column("프로젝트", no_wrap=True)
    table.add_column("카테고리", no_wrap=True)
    table.add_column("제목", overflow="fold", min_width=TITLE_MIN_WIDTH)
    table.add_column("예상", justify="right", no_wrap=True)
    table.add_column("실적", justify="right", no_wrap=True)
    table.add_column("주차", no_wrap=True)
    table.add_column("참조", overflow="fold", min_width=REF_MIN_WIDTH)
    for task in tasks:
        table.add_row(
            str(task.id),
            str(task.status),
            Text(task.project.slug),
            _text_or_dash(task.category),
            Text(task.title),
            _estimate_or_dash(task.estimate_minutes),
            _minutes_or_dash(actual.get(task.id, 0)),
            _text_or_dash(task.planned_week),
            _text_or_dash(task.external_ref),
        )
    return table


def _status_line(task: "Task", head: "Text", extras: "Sequence[str | Text]") -> "Text":
    """'#43 doing {head} · {extras…}' 형식의 한 줄. extras가 없으면 꼬리를 생략한다."""
    from rich.text import Text

    line = Text.assemble(f"#{task.id} {task.status} ", head)
    if not extras:
        return line
    return Text.assemble(line, f" {info_mark()} ", _join_info(extras))


def _plan_extras(task: "Task", actual: "Mapping[int, int]") -> "list[str | Text]":
    """예상·실적 항목. 값이 있는 것만 넣는다(실적 0분은 뺀다)."""
    from logbook.core.duration import format_duration

    extras: list[str | Text] = []
    if task.estimate_minutes is not None:
        extras.append(_estimate_part(task.estimate_minutes))
    minutes = actual.get(task.id, 0)
    if minutes:
        extras.append(f"실적 {format_duration(minutes)}")
    return extras


def task_lines(tasks: "Sequence[Task]", actual: "Mapping[int, int]") -> "list[Text]":
    """좁은 화면용 태스크 목록. 값이 있는 항목만 넣는다.

    예: '#43 doing payment/design 환불 API 설계 · 예상 4h · 실적 2h 30m · 2026-W42 · 참조 #43'
    """
    from rich.text import Text

    lines = []
    for task in tasks:
        extras = _plan_extras(task, actual)
        if task.planned_week is not None:
            extras.append(Text(task.planned_week))
        if task.external_ref is not None:
            extras.append(_ref_part(task.external_ref))
        head = Text.assemble(_scope(task.project.slug, task.category), " ", Text(task.title))
        lines.append(_status_line(task, head, extras))
    return lines


def plan_table(tasks: "Sequence[Task]", actual: "Mapping[int, int]") -> "Table":
    """계획 표: ID | 상태 | 프로젝트 | 제목 | 예상 | 실적. 제목 열만 접는다."""
    from rich.text import Text

    table = new_table()
    table.add_column("ID", justify="right", no_wrap=True)
    table.add_column("상태", no_wrap=True)
    table.add_column("프로젝트", no_wrap=True)
    table.add_column("제목", overflow="fold", min_width=TITLE_MIN_WIDTH)
    table.add_column("예상", justify="right", no_wrap=True)
    table.add_column("실적", justify="right", no_wrap=True)
    for task in tasks:
        table.add_row(
            str(task.id),
            str(task.status),
            Text(task.project.slug),
            Text(task.title),
            _estimate_or_dash(task.estimate_minutes),
            _minutes_or_dash(actual.get(task.id, 0)),
        )
    return table


def plan_lines(tasks: "Sequence[Task]", actual: "Mapping[int, int]") -> "list[Text]":
    """좁은 화면용 계획 목록: '#43 doing payment 환불 API 설계 · 예상 4h · 실적 2h 30m'."""
    from rich.text import Text

    return [
        _status_line(
            task,
            Text.assemble(Text(task.project.slug), " ", Text(task.title)),
            _plan_extras(task, actual),
        )
        for task in tasks
    ]


def timer_line(timer: "ActiveTimer") -> "Text":
    """타이머 요약: 'payment/design — 환불 API 설계 [#43]'. 태스크가 없으면 '[#43]'을 뺀다."""
    from rich.text import Text

    return Text.assemble(
        _scope(timer.project.slug, timer.category),
        f" {dash()} ",
        Text(timer.note),
        f" [#{timer.task_id}]" if timer.task_id is not None else "",
    )
