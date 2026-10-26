"""화면마다 보이지 않는 h1(화면 이름) 하나: 화면 읽기 프로그램의 제목 탐색용."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine

from tests.web.helpers import add_task, all_by_tag


@pytest.mark.parametrize(
    ("path", "name"),
    [
        ("/", "대시보드"),
        ("/logs", "기록"),
        ("/tasks", "태스크"),
        ("/tasks/new", "새 태스크"),
        ("/report", "보고서"),
        ("/settings", "설정"),
    ],
)
def test_each_page_has_one_hidden_h1_with_its_name(
    client: TestClient, path: str, name: str
) -> None:
    headings = all_by_tag(client.get(path).text, "h1")

    assert [(h.text, h.attrs.get("class")) for h in headings] == [(name, "visually-hidden")]


def test_task_edit_page_h1_names_the_task(client: TestClient, web_engine: Engine) -> None:
    task_id = add_task(web_engine, title="환불 API")

    headings = all_by_tag(client.get(f"/tasks/{task_id}/edit").text, "h1")

    assert [h.text for h in headings] == [f"태스크 #{task_id} 수정"]


def test_h1_is_the_first_element_of_main(client: TestClient) -> None:
    html = client.get("/").text

    main_start = html.index('<main id="main"')
    first_tag = html.index("<", html.index(">", main_start) + 1)

    assert html.startswith('<h1 class="visually-hidden">', first_tag)


@pytest.mark.parametrize("path", ["/logs", "/report", "/tasks"])
def test_htmx_partial_responses_have_no_h1(client: TestClient, path: str) -> None:
    html = client.get(path, headers={"HX-Request": "true"}).text

    assert all_by_tag(html, "h1") == []
