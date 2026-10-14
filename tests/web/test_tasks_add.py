"""태스크 추가 POST /tasks 테스트 (W40 = 09-28 ~ 10-04, 오늘 = 2026-10-01 목요일 09:30 +09:00)."""

from dataclasses import dataclass, replace
from html import unescape

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from logbook.core import db, services
from logbook.core.duration import parse_duration
from logbook.core.errors import InvalidInputError
from logbook.web.app import create_app
from logbook.web.context import WebContext
from tests.web.conftest import LOCAL_BASE_URL
from tests.web.helpers import (
    add_project,
    add_task,
    board_columns,
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
    "project": "",
}


@dataclass(frozen=True)
class Stored:
    id: int
    project: str
    title: str
    category: str | None
    estimate: int | None
    week: str | None


def _tasks(engine: Engine) -> list[Stored]:
    with db.session_scope(engine) as s:
        return [
            Stored(t.id, t.project.slug, t.title, t.category, t.estimate_minutes, t.planned_week)
            for t in services.list_tasks(s, include_archived=True)
        ]


def _form_result(html: str) -> str:
    return by_id(html, "task-form-result").text


def test_add_with_all_fields_keeps_project_category_week(
    client: TestClient, web_engine: Engine
) -> None:
    add_project(web_engine, "payment", "결제 서버")

    response = client.post("/tasks", data=FORM, headers=HTMX)

    assert response.status_code == 200
    html = response.text
    assert "<html" not in html
    [stored] = _tasks(web_engine)
    assert (stored.project, stored.title, stored.category) == ("payment", "결제 재시도", "dev")
    assert (stored.estimate, stored.week) == (240, "2026-W41")
    form = by_id(html, "task-form")
    assert form.tag == "form"
    assert "hx-swap-oob" not in form.attrs
    assert (
        _form_result(html)
        == f"✔ 태스크 추가: #{stored.id} payment · 결제 재시도 (예상 4h, 2026-W41)"
    )
    assert named_input(html, "title").attrs["value"] == ""
    assert named_input(html, "estimate").attrs["value"] == ""
    assert named_input(html, "week").attrs["value"] == "next"
    assert [v for v, _, selected in select_options(html, "task_project") if selected] == ["payment"]
    assert [v for v, _, selected in select_options(html, "task_category") if selected] == ["dev"]


def test_add_returns_board_as_oob_with_new_card(client: TestClient, web_engine: Engine) -> None:
    add_project(web_engine, "payment", "결제 서버")

    html = client.post("/tasks", data=FORM, headers=HTMX).text

    [stored] = _tasks(web_engine)
    board = by_id(html, "task-board")
    assert board.attrs["hx-swap-oob"] == "true"
    assert board_columns(html)["todo"] == [stored.id]
    assert inline_code_violations(html) == []


def test_add_board_follows_the_filter(client: TestClient, web_engine: Engine) -> None:
    add_project(web_engine, "payment", "결제 서버")
    other = add_task(web_engine, title="공통 일")

    html = client.post("/tasks", data={**FORM, "project": "common"}, headers=HTMX).text

    assert board_columns(html)["todo"] == [other]  # 새 태스크는 payment라 필터 밖이다


def test_add_title_only_uses_default_project(client: TestClient, web_engine: Engine) -> None:
    form = {"title": "제목만", "task_project": "", "task_category": "", "estimate": "", "week": ""}

    response = client.post("/tasks", data=form, headers=HTMX)

    assert response.status_code == 200
    [stored] = _tasks(web_engine)
    assert (stored.project, stored.category, stored.estimate, stored.week) == (
        "common",
        None,
        None,
        None,
    )
    assert _form_result(response.text) == f"✔ 태스크 추가: #{stored.id} common · 제목만"


def test_add_blank_project_uses_configured_default(web_ctx: WebContext, web_engine: Engine) -> None:
    add_project(web_engine, "payment", "결제 서버")
    ctx = replace(web_ctx, cfg=replace(web_ctx.cfg, default_project="payment"))
    form = {
        "title": "기본 프로젝트",
        "task_project": "",
        "task_category": "",
        "estimate": "",
        "week": "",
    }

    with TestClient(create_app(ctx), base_url=LOCAL_BASE_URL) as client:
        response = client.post("/tasks", data=form, headers=HTMX)

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
        ({"task_project": "old"}, "archived"),
    ],
    ids=["empty-title", "bad-estimate", "archived-project"],
)
def test_add_failure_keeps_input_and_sends_no_board(
    client: TestClient, web_engine: Engine, changes: dict[str, str], action: str
) -> None:
    add_project(web_engine, "payment", "결제 서버")
    add_project(web_engine, "old", "보관")
    with db.session_scope(web_engine) as s:
        services.archive_project(s, "old")
    message = _core_message(web_engine, action)

    response = client.post("/tasks", data={**FORM, **changes}, headers=HTMX)

    assert response.status_code == 400
    html = response.text
    assert unescape(by_id(html, "task-form-result").text) == message
    assert by_id(html, "task-form-result").attrs["role"] == "alert"
    assert named_input(html, "title").attrs["value"] == changes.get("title", FORM["title"])
    assert named_input(html, "estimate").attrs["value"] == changes.get("estimate", FORM["estimate"])
    assert named_input(html, "week").attrs["value"] == "next"
    assert [e for e in parse_html(html) if e.attrs.get("id") == "task-board"] == []
    assert _tasks(web_engine) == []


def test_add_unknown_category_is_rejected(client: TestClient, web_engine: Engine) -> None:
    add_project(web_engine, "payment", "결제 서버")

    response = client.post("/tasks", data={**FORM, "task_category": "nope"}, headers=HTMX)

    assert response.status_code == 400
    assert _tasks(web_engine) == []


def test_add_form_project_choices_exclude_archived(client: TestClient, web_engine: Engine) -> None:
    add_project(web_engine, "payment", "결제 서버")
    add_project(web_engine, "old", "보관")
    with db.session_scope(web_engine) as s:
        services.archive_project(s, "old")

    html = client.get("/tasks").text

    form_projects = [v for v, _, _ in select_options(html, "task_project")]
    assert form_projects == ["", "common", "payment"]
    filter_projects = [v for v, _, _ in select_options(html, "project")]
    assert "old" in filter_projects


def test_add_form_has_htmx_attributes_and_focus_target(client: TestClient) -> None:
    html = client.get("/tasks").text

    form = by_id(html, "task-form")
    assert form.attrs["hx-post"] == "/tasks"
    assert form.attrs["hx-target"] == "this"
    assert form.attrs["hx-swap"] == "outerHTML"
    assert form.attrs["hx-include"] == "#task-filters"
    assert form.attrs["hx-sync"] == "this:drop"
    assert form.attrs["hx-disabled-elt"] == "find button"
    title = named_input(html, "title")
    assert title.attrs["id"] == "task-title"
    assert "data-focus" in title.attrs


def test_add_escapes_title(client: TestClient, web_engine: Engine) -> None:
    add_project(web_engine, "payment", "결제 서버")

    html = client.post("/tasks", data={**FORM, "title": "<b>굵게</b>"}, headers=HTMX).text

    assert "<b>굵게</b>" not in html
    assert [e for e in parse_html(html) if e.tag == "b"] == []


def test_add_from_other_origin_is_forbidden(client: TestClient, web_engine: Engine) -> None:
    add_project(web_engine, "payment", "결제 서버")

    response = client.post("/tasks", data=FORM, headers={"Origin": "http://evil.example"})

    assert response.status_code == 403
    assert _tasks(web_engine) == []


def test_week_text_is_resolved_against_today(client: TestClient, web_engine: Engine) -> None:
    add_project(web_engine, "payment", "결제 서버")

    client.post("/tasks", data={**FORM, "week": "2026-W43"}, headers=HTMX)

    assert [t.week for t in _tasks(web_engine)] == ["2026-W43"]
