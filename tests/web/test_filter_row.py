"""공용 필터 줄(2026-11-05 결정 F1): 기록·태스크·보고서의 필터 줄을 한 모양으로 맞춘다.

세 화면 모두 카드 위 `form.filters` 하나에 주 이동 묶음(있으면) → select 순서로 둔다.
select는 최대 폭을 두어 긴 프로젝트 이름이 줄을 늘리지 않게 하고,
좁은 폭에서는 주 이동 아래 select들을 격자로 나란히 둔다(페이지 가로 넘침 0).
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from tests.web.helpers import Element, add_project
from tests.web.test_css_layout import NARROW_QUERY, _declarations, _media_block, _read
from tests.web.test_narrow_tables import _inside

LONG_SLUG = "a-very-long-project-slug-for-qa3"

FILTER_FORMS = [
    ("/logs?week=2026-W40", "log-filters"),
    ("/tasks", "task-filters"),
    ("/report?week=2026-W40", "report-nav"),
]


def _shape(elements: list[Element]) -> list[str]:
    """요소의 태그와 class만 남긴 모양(값·id는 뺀다)."""
    return [f"{e.tag}.{'.'.join(str(e.attrs.get('class') or '').split())}" for e in elements]


@pytest.mark.parametrize(("path", "form_id"), FILTER_FORMS)
def test_every_filter_row_is_one_filters_form(client: TestClient, path: str, form_id: str) -> None:
    elements = _inside(client.get(path).text, form_id)

    form = elements[0]
    assert form.tag == "form"
    assert form.attrs.get("class") == "filters"


@pytest.mark.parametrize(("path", "form_id"), FILTER_FORMS)
def test_every_select_sits_in_a_labelled_filters_field(
    client: TestClient, web_engine: Engine, path: str, form_id: str
) -> None:
    add_project(web_engine, LONG_SLUG, "아주 긴 이름의 프로젝트")

    elements = _inside(client.get(path).text, form_id)

    for index, element in enumerate(elements):
        if element.tag != "select":
            continue
        field, label = elements[index - 2], elements[index - 1]
        assert _shape([field, label]) == ["div.filters__field", "label."]
        assert label.attrs.get("for") == element.attrs.get("id")


def test_week_moves_share_one_shape_on_logs_and_report(client: TestClient) -> None:
    def week_nav(path: str, form_id: str) -> list[str]:
        elements = _inside(client.get(path).text, form_id)
        start = next(i for i, e in enumerate(elements) if e.attrs.get("class") == "week-nav")
        return _shape(elements[start : start + 6])

    logs = week_nav("/logs?week=2026-W40", "log-filters")

    assert logs == week_nav("/report?week=2026-W40", "report-nav")
    assert logs == [
        "div.week-nav",
        "a.week-nav__link",
        "div.filters__field",
        "label.",
        "input.",
        "a.week-nav__link",
    ]


def test_filter_selects_have_a_maximum_width() -> None:
    declarations = _declarations(_read("logs.css"), ".filters select")

    assert "max-width: 16rem" in declarations


def test_narrow_filter_row_puts_selects_side_by_side_under_week_moves() -> None:
    narrow = _media_block(_read("responsive.css"), NARROW_QUERY)

    row = _declarations(narrow, ".filters")
    assert "display: grid" in row
    assert "grid-template-columns: repeat(auto-fit, minmax(7.5rem, 1fr))" in row
    assert "grid-column: 1 / -1" in _declarations(narrow, ".filters > .week-nav")
    assert {"width: 100%", "max-width: none"} <= _declarations(narrow, ".filters select")
