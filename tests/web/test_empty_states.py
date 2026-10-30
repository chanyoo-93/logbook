"""빈 상태 안내(2026-10-29 G2): 다음 할 일을 글로 말하고, 다른 화면이면 링크를 둔다."""

from fastapi.testclient import TestClient
from sqlalchemy import Engine

from tests.web.helpers import Element, add_log, by_class, parse_html

BOARD_EMPTY = {
    "todo": "할 일이 없습니다. 새 태스크로 추가하세요.",
    "doing": "진행할 태스크를 여기로 끌어 오면 진행 중이 됩니다.",
    "done": "완료한 태스크를 여기로 끌어 오세요.",
    "dropped": "중단할 태스크를 여기로 끌어 오세요.",
}


def _empty_after(html: str, element_id: str) -> Element:
    """id가 element_id인 요소 뒤에 처음 나오는 빈 상태(.empty)."""
    elements = parse_html(html)
    start = next(i for i, e in enumerate(elements) if e.attrs.get("id") == element_id)
    return next(e for e in elements[start:] if "empty" in str(e.attrs.get("class")).split())


def _links(html: str) -> list[tuple[str, str]]:
    """빈 상태 안의 링크(.empty__link)의 (글, href)."""
    return [(e.text, str(e.attrs.get("href"))) for e in by_class(html, "empty__link")]


def test_board_columns_say_what_to_do(client: TestClient) -> None:
    html = client.get("/tasks").text

    for key, text in BOARD_EMPTY.items():
        empty = _empty_after(html, f"task-col-{key}")
        assert empty.text == text, key
        assert empty.tag == "li", key  # 목록 안에 있어야 빈 칸에 놓아도 이 열로 들어간다
    assert ("새 태스크", "/tasks/new") in _links(html)


def test_board_todo_link_keeps_project_filter(client: TestClient) -> None:
    html = client.get("/tasks?project=common").text

    assert ("새 태스크", "/tasks/new?project=common") in _links(html)


def test_plan_points_to_new_task(client: TestClient) -> None:
    html = client.get("/tasks").text

    assert _empty_after(html, "task-plan").text == (
        "계획한 태스크가 없습니다. 새 태스크에서 계획 주를 정하세요."
    )
    assert _links(html).count(("새 태스크", "/tasks/new")) == 2  # 할 일 열과 계획


def test_dashboard_recent_and_summary(client: TestClient) -> None:
    html = client.get("/").text

    assert _empty_after(html, "recent").text == (
        "아직 기록이 없습니다. 위에서 시간과 메모를 넣고 기록하세요."
    )
    assert _empty_after(html, "summary").text == (
        "이번 주 기록이 없습니다. 기록하면 요일별·프로젝트별 공수가 여기에 보입니다."
    )
    assert _links(html) == []  # 같은 화면의 일은 글로만 말한다


def test_logs_without_filter_points_to_dashboard(client: TestClient) -> None:
    html = client.get("/logs").text

    assert (
        _empty_after(html, "log-table").text
        == "이 주에는 기록이 없습니다. 대시보드에서 기록하세요."
    )
    assert _links(html) == [("대시보드", "/")]


def test_logs_with_filter_suggests_changing_it(client: TestClient, web_engine: Engine) -> None:
    add_log(web_engine, minutes=30, note="개발")  # common/dev: 필터에 걸리지 않는 기록

    for query in ("?project=common&category=meeting", "?category=meeting"):
        html = client.get(f"/logs{query}").text

        assert _empty_after(html, "log-table").text == (
            "조건에 맞는 기록이 없습니다. 주차나 필터를 바꿔 보세요."
        ), query
        assert _links(html) == [], query
