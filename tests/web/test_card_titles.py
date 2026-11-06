"""화면 제목은 모두 카드 머리 안(2026-11-05 결정 F2).

태스크 보드·다음 주 계획·새 태스크·태스크 수정·보고서·오류 화면의 제목(h2)이
`section.panel > div.panel__head > h2.panel__title`로 같은 단계다.
태스크 보드의 `새 태스크` 버튼은 제목과 같은 머리 줄에 있다.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from tests.web.helpers import Element, add_task, parse_html
from tests.web.test_css_layout import _declarations, _read


def _classes(element: Element) -> list[str]:
    return str(element.attrs.get("class") or "").split()


def _heading_frame(elements: list[Element], heading: Element) -> tuple[Element, Element]:
    """제목 바로 앞 div와 그 앞에서 가장 가까운 section."""
    index = elements.index(heading)
    head = elements[index - 1]
    section = next(e for e in reversed(elements[:index]) if e.tag == "section")
    return head, section


def _assert_in_card_head(html: str, heading_id: str | None = None) -> Element:
    elements = parse_html(html)
    if heading_id is None:
        heading = next(e for e in elements if e.tag == "h2")
    else:
        heading = next(e for e in elements if e.attrs.get("id") == heading_id)
    head, section = _heading_frame(elements, heading)
    assert heading.tag == "h2"
    assert "panel__title" in _classes(heading)
    assert (head.tag, _classes(head)) == ("div", ["panel__head"])
    assert "panel" in _classes(section)
    return heading


@pytest.mark.parametrize(
    ("path", "heading_id"),
    [
        ("/tasks", "task-board-title"),
        ("/tasks", "task-plan-title"),
        ("/tasks/new", "task-page-title"),
        ("/report?week=2026-W40", "report-heading"),
    ],
)
def test_screen_titles_sit_in_card_heads(client: TestClient, path: str, heading_id: str) -> None:
    _assert_in_card_head(client.get(path).text, heading_id)


def test_task_edit_title_sits_in_card_head(client: TestClient, web_engine: Engine) -> None:
    task_id = add_task(web_engine, title="결제 승인 오류 정리")

    _assert_in_card_head(client.get(f"/tasks/{task_id}/edit").text, "task-page-title")


def test_error_page_title_sits_in_card_head(client: TestClient) -> None:
    html = client.get("/nope").text

    heading = _assert_in_card_head(html)
    assert "error-card__title" in _classes(heading)


def test_new_task_button_shares_the_board_head_row(client: TestClient) -> None:
    elements = parse_html(client.get("/tasks").text)
    heading = next(e for e in elements if e.attrs.get("id") == "task-board-title")
    columns = next(e for e in elements if "board__columns" in _classes(e))

    between = elements[elements.index(heading) + 1 : elements.index(columns)]
    button = next(e for e in between if e.tag == "a" and "btn" in _classes(e))
    assert button.text == "새 태스크"


def test_card_titles_balance_their_lines() -> None:
    assert "text-wrap: balance" in _declarations(_read("dashboard.css"), ".panel__title")


def test_task_form_is_not_a_card_inside_the_card() -> None:
    properties = {d.split(":")[0] for d in _declarations(_read("tasks.css"), ".task-form")}

    assert not {"border", "box-shadow", "background"} & properties


@pytest.mark.parametrize("selector", [".board__title", ".plan__title", ".task-page__title"])
def test_old_title_rules_are_gone(selector: str) -> None:
    css = _read("tasks.css")

    with pytest.raises(AssertionError):
        _declarations(css, selector)
