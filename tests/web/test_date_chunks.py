"""제목의 날짜·주차는 하이픈 뒤에서 쪼개지 않는다(2026-11-09 결정 D5).

`date_parts`가 글을 (글, 날짜인가) 조각으로 나누고, 공용 매크로 `keep_dates`가 날짜 조각만
`span.date-chunk`(줄바꿈 없음)로 감싼다. 글자는 그대로다.
"""

import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from logbook.web.pages.templating import TEMPLATES, date_parts
from tests.web.helpers import add_task, by_class, by_id
from tests.web.test_css_layout import _declarations, _read


@pytest.mark.parametrize(
    ("text", "parts"),
    [
        (
            "2026-W40 (09-28 ~ 10-04)",
            [("2026-W40", True), (" ", False), ("(09-28", True), (" ~ ", False), ("10-04)", True)],
        ),
        (
            "다음 주 계획 2026-W47 (11-16 ~ 11-22)",
            [
                ("다음 주 계획 ", False),
                ("2026-W47", True),
                (" ", False),
                ("(11-16", True),
                (" ~ ", False),
                ("11-22)", True),
            ],
        ),
        (
            "주간업무보고 (2026-11-09 ~ 2026-11-15)",
            [
                ("주간업무보고 ", False),
                ("(2026-11-09", True),
                (" ~ ", False),
                ("2026-11-15)", True),
            ],
        ),
        ("설정 정보", [("설정 정보", False)]),
        # 더 긴 숫자열 한가운데는 날짜로 보지 않는다(숫자·하이픈 경계)
        ("ID 100-20-30", [("ID 100-20-30", False)]),
        ("v12026-11-09", [("v12026-11-09", False)]),
        ("1234-56-78-90", [("1234-56-78-90", False)]),
        ("", []),
    ],
)
def test_date_parts_split_dates_and_weeks(text: str, parts: list[tuple[str, bool]]) -> None:
    assert date_parts(text) == parts
    assert "".join(part for part, _ in date_parts(text)) == text


def test_keep_dates_macro_escapes_text() -> None:
    html = _render_keep_dates("<b>보고</b> (2026-11-09 ~ 2026-11-15)")

    assert "<b>" not in html
    assert "&lt;b&gt;보고&lt;/b&gt; " in html
    assert [e.text for e in by_class(html, "date-chunk")] == ["(2026-11-09", "2026-11-15)"]


def test_date_chunks_do_not_wrap_inside() -> None:
    assert "white-space: nowrap" in _declarations(_read("components.css"), ".date-chunk")


def _render_keep_dates(text: str) -> str:
    macro = TEMPLATES.env.from_string(
        '{% from "partials/marks.html" import keep_dates %}{{ keep_dates(text) }}'
    )
    return macro.render(text=text)


def _inner(html: str, opening: str) -> str:
    """opening(예: `id="log-table-title"`)이 든 요소의 안쪽 HTML(같은 이름 닫는 태그까지)."""
    match = re.search(rf"<(\w+) [^>]*{re.escape(opening)}[^>]*>(.*?)</\1>", html, re.DOTALL)
    assert match, f"{opening} 요소가 없습니다"
    return match.group(2)


@pytest.mark.parametrize(
    ("path", "element_id", "text"),
    [
        ("/logs?week=2026-W40", "log-table-title", "2026-W40 (09-28 ~ 10-04)"),
        ("/report?week=2026-W40", "report-heading", "2026-W40 (09-28 ~ 10-04)"),
        ("/report?week=2026-W40", "sheet-title", "주간업무보고 (2026-09-28 ~ 2026-10-04)"),
    ],
)
def test_screen_headings_keep_dates_together(
    client: TestClient, path: str, element_id: str, text: str
) -> None:
    html = client.get(path).text

    assert by_id(html, element_id).text == text
    assert _inner(html, f'id="{element_id}"') == _render_keep_dates(text)


def test_plan_heading_keeps_dates_together(client: TestClient, web_engine: Engine) -> None:
    add_task(web_engine, title="다음 주 일")

    html = client.get("/tasks").text

    heading = by_id(html, "task-plan-title").text
    assert heading.startswith("다음 주 계획 2026-W")
    assert _inner(html, 'id="task-plan-title"') == _render_keep_dates(heading)


def test_masthead_week_keeps_dates_together(client: TestClient) -> None:
    html = client.get("/").text

    week = by_class(html, "masthead__week")[0].text
    assert week.startswith("이번 주 2026-W")
    assert _inner(html, 'class="masthead__week"') == _render_keep_dates(week)


def test_dashboard_summary_week_keeps_dates_together(client: TestClient) -> None:
    html = client.get("/").text

    meta = next(e for e in by_class(html, "panel__meta") if e.text.startswith("2026-W")).text
    assert _inner(html, 'class="panel__meta"') == _render_keep_dates(meta)
