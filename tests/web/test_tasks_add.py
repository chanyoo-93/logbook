"""태스크 등록 화면 GET /tasks/new와 저장 POST /tasks 테스트 (오늘 = 2026-10-01 목요일, W40)."""

from dataclasses import dataclass, replace
from datetime import date
from html import unescape

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from logbook.core import db, services
from logbook.core.duration import parse_duration
from logbook.core.errors import InvalidInputError
from logbook.core.weeks import parse_date, parse_week
from logbook.web.app import create_app
from logbook.web.context import WebContext
from tests.conftest import FIXED_TODAY
from tests.web.conftest import LOCAL_BASE_URL
from tests.web.helpers import (
    add_project,
    add_task,
    all_by_tag,
    by_id,
    inline_code_violations,
    named_input,
    parse_html,
    select_options,
)

HTMX = {"HX-Request": "true"}
FORM = {
    "title": "결제 재시도",
    "task_project": "payment",
    "task_category": "dev",
    "estimate": "4h",
    "week": "next",
    "due": "2026-10-20",
    "external_ref": "JIRA-12",
    "description": "첫 줄\r\n둘째 줄",
    "project": "",
}
FIELD_NAMES = [
    "title",
    "task_project",
    "task_category",
    "estimate",
    "week",
    "due",
    "external_ref",
    "description",
]


@dataclass(frozen=True)
class Stored:
    id: int
    project: str
    title: str
    category: str | None
    estimate: int | None
    week: str | None
    due: date | None
    ref: str | None
    description: str | None


def _tasks(engine: Engine) -> list[Stored]:
    with db.session_scope(engine) as s:
        return [
            Stored(
                t.id,
                t.project.slug,
                t.title,
                t.category,
                t.estimate_minutes,
                t.planned_week,
                t.due_date,
                t.external_ref,
                t.description,
            )
            for t in services.list_tasks(s, include_archived=True)
        ]


def _field(html: str, name: str):  # type: ignore[no-untyped-def]
    """name 속성이 name인 input·select·textarea."""
    for element in parse_html(html):
        if element.tag in {"input", "select", "textarea"} and element.attrs.get("name") == name:
            return element
    raise AssertionError(f"name이 '{name}'인 입력이 없습니다")


def test_new_page_has_eight_fields_and_autofocus_title(client: TestClient) -> None:
    response = client.get("/tasks/new")

    assert response.status_code == 200
    html = response.text
    assert "<html" in html
    assert [e.text for e in parse_html(html) if e.tag == "title"] == ["새 태스크 · logbook"]
    nav = [e for e in parse_html(html) if e.tag == "a" and e.attrs.get("href") == "/tasks"]
    assert [e.attrs.get("aria-current") for e in nav if "aria-current" in e.attrs] == ["page"]
    form = by_id(html, "task-form")
    assert form.tag == "form"
    assert form.attrs["hx-post"] == "/tasks"
    assert form.attrs["hx-target"] == "this"
    assert form.attrs["hx-swap"] == "outerHTML"
    assert form.attrs["hx-sync"] == "this:drop"
    visible = [
        e.attrs["name"]
        for e in parse_html(html)
        if e.tag in {"input", "select", "textarea"} and e.attrs.get("type") != "hidden"
    ]
    assert visible == FIELD_NAMES
    assert "autofocus" in _field(html, "title").attrs
    assert _field(html, "description").tag == "textarea"
    assert inline_code_violations(html) == []


def test_new_page_project_choices_exclude_archived(client: TestClient, web_engine: Engine) -> None:
    add_project(web_engine, "payment", "결제 서버")
    add_project(web_engine, "old", "보관")
    with db.session_scope(web_engine) as s:
        services.archive_project(s, "old")

    html = client.get("/tasks/new").text

    assert [v for v, _, _ in select_options(html, "task_project")] == ["", "common", "payment"]


def test_new_page_cancel_link_and_hidden_project_follow_filter(client: TestClient) -> None:
    plain = client.get("/tasks/new").text
    filtered = client.get("/tasks/new?project=payment").text

    cancel = [e for e in parse_html(plain) if "data-cancel" in e.attrs]
    assert [(e.tag, e.attrs["href"]) for e in cancel] == [("a", "/tasks")]
    assert named_input(plain, "project").attrs["value"] == ""
    cancel = [e for e in parse_html(filtered) if "data-cancel" in e.attrs]
    assert [e.attrs["href"] for e in cancel] == ["/tasks?project=payment"]
    assert named_input(filtered, "project").attrs["value"] == "payment"


def test_add_saves_all_fields_and_redirects_to_board(
    client: TestClient, web_engine: Engine
) -> None:
    add_project(web_engine, "payment", "결제 서버")

    response = client.post("/tasks", data=FORM, headers=HTMX)

    [stored] = _tasks(web_engine)
    assert response.status_code == 200
    assert response.headers["HX-Redirect"] == f"/tasks?added={stored.id}"
    assert stored == Stored(
        stored.id,
        "payment",
        "결제 재시도",
        "dev",
        240,
        parse_week("next", today=FIXED_TODAY).label,
        date(2026, 10, 20),
        "JIRA-12",
        "첫 줄\n둘째 줄",
    )


def test_add_redirect_keeps_the_filter_project(client: TestClient, web_engine: Engine) -> None:
    add_project(web_engine, "payment", "결제 서버")

    response = client.post("/tasks", data={**FORM, "project": "payment"}, headers=HTMX)

    [stored] = _tasks(web_engine)
    assert response.headers["HX-Redirect"] == f"/tasks?added={stored.id}&project=payment"


def test_add_title_only_uses_default_project(client: TestClient, web_engine: Engine) -> None:
    response = client.post("/tasks", data={"title": "제목만"}, headers=HTMX)

    [stored] = _tasks(web_engine)
    assert response.headers["HX-Redirect"] == f"/tasks?added={stored.id}"
    assert (stored.project, stored.category, stored.estimate, stored.week) == (
        "common",
        None,
        None,
        None,
    )
    assert (stored.due, stored.ref, stored.description) == (None, None, None)


def test_add_blank_project_uses_configured_default(web_ctx: WebContext, web_engine: Engine) -> None:
    add_project(web_engine, "payment", "결제 서버")
    ctx = replace(web_ctx, cfg=replace(web_ctx.cfg, default_project="payment"))

    with TestClient(create_app(ctx), base_url=LOCAL_BASE_URL) as client:
        response = client.post("/tasks", data={"title": "기본 프로젝트"}, headers=HTMX)

    assert response.status_code == 200
    assert [t.project for t in _tasks(web_engine)] == ["payment"]


def _core_message(engine: Engine, action: str) -> str:
    """같은 잘못된 입력에 core가 내는 문구."""
    with db.session_scope(engine) as s:
        try:
            if action == "empty-title":
                services.create_task(s, title="  ", project_slug="common")
            elif action == "archived":
                services.get_active_project(s, "old")
            elif action == "bad-week":
                parse_week("2026-W99", today=FIXED_TODAY)
            elif action == "bad-due":
                parse_date("abc", today=FIXED_TODAY)
            else:
                parse_duration("abc", max_minutes=None)
        except InvalidInputError as error:
            return str(error)
    raise AssertionError("오류가 나야 합니다")


@pytest.mark.parametrize(
    ("changes", "action"),
    [
        ({"title": "  "}, "empty-title"),
        ({"estimate": "abc"}, "bad-estimate"),
        ({"week": "2026-W99"}, "bad-week"),
        ({"due": "abc"}, "bad-due"),
        ({"task_project": "old"}, "archived"),
    ],
    ids=["empty-title", "bad-estimate", "bad-week", "bad-due", "archived-project"],
)
def test_add_failure_redraws_form_with_input_and_message(
    client: TestClient, web_engine: Engine, changes: dict[str, str], action: str
) -> None:
    add_project(web_engine, "payment", "결제 서버")
    add_project(web_engine, "old", "보관")
    with db.session_scope(web_engine) as s:
        services.archive_project(s, "old")
    message = _core_message(web_engine, action)
    sent = {**FORM, **changes}

    response = client.post("/tasks", data=sent, headers=HTMX)

    assert response.status_code == 400
    assert "HX-Redirect" not in response.headers
    html = response.text
    assert "<html" not in html
    assert by_id(html, "task-form").tag == "form"
    result = by_id(html, "task-form-result")
    assert unescape(result.text) == message
    # 화면 낭독기가 같은 문구를 두 번 읽지 않게 오류는 #flash(role=alert)만 알린다.
    assert "role" not in result.attrs
    assert by_id(html, "flash").attrs["hx-swap-oob"] == "innerHTML"
    assert unescape(all_by_tag(html, "p")[-1].text) == message
    assert all_by_tag(html, "p")[-1].attrs["role"] == "alert"
    for name in ("title", "estimate", "week", "due", "external_ref"):
        assert _field(html, name).attrs["value"] == sent[name]
    assert "첫 줄" in _field(html, "description").text
    assert _tasks(web_engine) == []


def test_add_unknown_category_is_rejected(client: TestClient, web_engine: Engine) -> None:
    add_project(web_engine, "payment", "결제 서버")

    response = client.post("/tasks", data={**FORM, "task_category": "nope"}, headers=HTMX)

    assert response.status_code == 400
    assert _tasks(web_engine) == []


def test_add_failure_keeps_filter_in_form(client: TestClient, web_engine: Engine) -> None:
    add_project(web_engine, "payment", "결제 서버")

    sent = {**FORM, "title": " ", "project": "payment"}

    html = client.post("/tasks", data=sent, headers=HTMX).text

    assert named_input(html, "project").attrs["value"] == "payment"
    cancel = [e for e in parse_html(html) if "data-cancel" in e.attrs]
    assert [e.attrs["href"] for e in cancel] == ["/tasks?project=payment"]


def test_add_escapes_title(client: TestClient, web_engine: Engine) -> None:
    sent = {"title": "<b>굵게</b>", "estimate": "abc"}

    html = client.post("/tasks", data=sent, headers=HTMX).text

    assert "<b>굵게</b>" not in html
    assert [e for e in parse_html(html) if e.tag == "b"] == []
    assert inline_code_violations(html) == []


def test_add_from_other_origin_is_forbidden(client: TestClient, web_engine: Engine) -> None:
    add_project(web_engine, "payment", "결제 서버")

    response = client.post("/tasks", data=FORM, headers={"Origin": "http://evil.example"})

    assert response.status_code == 403
    assert _tasks(web_engine) == []


def test_week_text_is_resolved_against_today(client: TestClient, web_engine: Engine) -> None:
    add_project(web_engine, "payment", "결제 서버")

    client.post("/tasks", data={**FORM, "week": "2026-W43"}, headers=HTMX)

    assert [t.week for t in _tasks(web_engine)] == ["2026-W43"]


def _result(html: str) -> str:
    return unescape(by_id(html, "task-result").text)


def test_board_shows_added_result_line(client: TestClient, web_engine: Engine) -> None:
    add_project(web_engine, "payment", "결제 서버")
    task_id = add_task(
        web_engine,
        title="결제 재시도",
        project="payment",
        estimate=240,
        week=parse_week("next", today=FIXED_TODAY),
    )

    html = client.get(f"/tasks?added={task_id}").text

    assert _result(html) == f"✔ 태스크 추가: #{task_id} payment · 결제 재시도 (예상 4h, 2026-W41)"


def test_board_shows_updated_result_line(client: TestClient, web_engine: Engine) -> None:
    task_id = add_task(web_engine, title="수정함")

    html = client.get(f"/tasks?updated={task_id}").text

    assert _result(html) == f"✔ 수정했습니다: #{task_id} common · 수정함"


@pytest.mark.parametrize("query", ["added=99", "updated=99", "added=abc", "updated=-1", "added="])
def test_board_ignores_unknown_or_malformed_ids(client: TestClient, query: str) -> None:
    response = client.get(f"/tasks?{query}")

    assert response.status_code == 200
    assert [e for e in parse_html(response.text) if e.attrs.get("id") == "task-result"] == []
    assert by_id(response.text, "task-board").tag == "section"
