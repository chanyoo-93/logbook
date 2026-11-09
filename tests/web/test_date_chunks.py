"""제목의 날짜·주차는 하이픈 뒤에서 쪼개지 않는다(2026-11-09 결정 D5).

`date_parts`가 글을 (글, 날짜인가) 조각으로 나누고, 공용 매크로 `keep_dates`가 날짜 조각만
`span.date-chunk`(줄바꿈 없음)로 감싼다. 글자는 그대로다.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from logbook.web.pages.templating import TEMPLATES, date_parts
from tests.web.helpers import add_task, by_class, by_id, parse_html
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
        ("", []),
    ],
)
def test_date_parts_split_dates_and_weeks(text: str, parts: list[tuple[str, bool]]) -> None:
    assert date_parts(text) == parts
    assert "".join(part for part, _ in date_parts(text)) == text


def test_keep_dates_macro_escapes_text() -> None:
    macro = TEMPLATES.env.from_string(
        '{% from "partials/marks.html" import keep_dates %}{{ keep_dates(text) }}'
    )

    html = macro.render(text="<b>보고</b> (2026-11-09 ~ 2026-11-15)")

    assert "<b>" not in html
    assert "&lt;b&gt;보고&lt;/b&gt; " in html
    assert [e.text for e in by_class(html, "date-chunk")] == ["(2026-11-09", "2026-11-15)"]


def test_date_chunks_do_not_wrap_inside() -> None:
    assert "white-space: nowrap" in _declarations(_read("components.css"), ".date-chunk")


def _chunks_in(html: str, element_id: str) -> list[str]:
    """element_id 요소 바로 안의 date-chunk 글자(평면 목록이라 뒤따르는 span을 순서로 찾는다)."""
    elements = parse_html(html)
    owner = by_id(html, element_id)
    start = next(i for i, e in enumerate(elements) if e.attrs.get("id") == element_id)
    chunks = []
    for element in elements[start + 1 :]:
        if "date-chunk" not in str(element.attrs.get("class") or "").split():
            if element.tag != "span":
                break
            continue
        chunks.append(element.text)
    assert all(chunk in owner.text for chunk in chunks)
    return chunks


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
    assert _chunks_in(html, element_id) == [p for p, is_date in date_parts(text) if is_date]


def test_plan_heading_keeps_dates_together(client: TestClient, web_engine: Engine) -> None:
    add_task(web_engine, title="다음 주 일")

    html = client.get("/tasks").text

    heading = by_id(html, "task-plan-title").text
    assert heading.startswith("다음 주 계획 2026-W")
    assert len(_chunks_in(html, "task-plan-title")) == 3


def test_masthead_week_keeps_dates_together(client: TestClient) -> None:
    html = client.get("/").text

    week = by_class(html, "masthead__week")[0]
    assert week.text.startswith("이번 주 2026-W")
    assert len([e for e in by_class(html, "date-chunk") if e.text in week.text]) >= 3


def test_dashboard_summary_week_keeps_dates_together(client: TestClient) -> None:
    html = client.get("/").text

    meta = next(e for e in by_class(html, "panel__meta") if e.text.startswith("2026-W"))
    chunks = [e.text for e in by_class(html, "date-chunk")]
    assert [p for p, is_date in date_parts(meta.text) if is_date] == chunks[3:6]
