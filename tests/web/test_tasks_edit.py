"""태스크 수정 화면과 저장 PATCH /tasks/{id} 테스트 (오늘 = 2026-10-01, W40)."""

from dataclasses import dataclass
from datetime import date
from html import unescape
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import Engine

from logbook.core import db, services
from logbook.core.config import Config
from logbook.core.taskstatus import TaskStatus
from logbook.core.weeks import week_of
from logbook.web.errors import TASK_CHANGED
from logbook.web.pages.panels import NO_CHANGE
from logbook.web.pages.task_views import task_version
from tests.conftest import FIXED_TODAY
from tests.web.helpers import (
    add_project,
    add_task,
    by_id,
    inline_code_violations,
    parse_html,
    select_options,
)

HTMX = {"HX-Request": "true"}
THIS_WEEK = week_of(FIXED_TODAY)


@dataclass(frozen=True)
class Stored:
    title: str
    category: str | None
    estimate: int | None
    week: str | None
    due: date | None
    ref: str | None
    description: str | None
    status: TaskStatus


def _stored(engine: Engine, task_id: int) -> Stored:
    with db.session_scope(engine) as s:
        t = services.get_task(s, task_id)
        return Stored(
            t.title,
            t.category,
            t.estimate_minutes,
            t.planned_week,
            t.due_date,
            t.external_ref,
            t.description,
            t.status,
        )


def _version(engine: Engine, task_id: int) -> str:
    with db.session_scope(engine) as s:
        return task_version(services.get_task(s, task_id))


def _patch(client: TestClient, engine: Engine, task_id: int, **fields: str):  # type: ignore[no-untyped-def]
    with db.session_scope(engine) as s:
        task = services.get_task(s, task_id)
        current = {
            "title": task.title,
            "task_category": task.category or "",
            "estimate": "",
            "week": "",
            "due": "",
            "external_ref": "",
            "description": "",
            "status": task.status.value,
        }
    form = {**current, "version": _version(engine, task_id), "project": ""}
    return client.patch(f"/tasks/{task_id}", data={**form, **fields}, headers=HTMX)


def _field(html: str, name: str):  # type: ignore[no-untyped-def]
    for element in parse_html(html):
        if element.tag in {"input", "select", "textarea"} and element.attrs.get("name") == name:
            return element
    raise AssertionError(f"name이 '{name}'인 입력이 없습니다")


def test_edit_page_shows_current_values(client: TestClient, web_engine: Engine) -> None:
    add_project(web_engine, "payment", "결제 서버")
    task_id = add_task(
        web_engine,
        title="결제 재시도",
        project="payment",
        category="dev",
        estimate=240,
        week=THIS_WEEK.next(),
    )
    with db.session_scope(web_engine) as s:
        services.update_task(
            s,
            task_id,
            due_date=date(2026, 10, 20),
            external_ref="JIRA-12",
            description="첫 줄\n둘째 줄",
        )

    response = client.get(f"/tasks/{task_id}/edit")

    assert response.status_code == 200
    html = response.text
    assert "<html" in html
    form = by_id(html, "task-form")
    assert form.attrs["hx-patch"] == f"/tasks/{task_id}"
    assert form.attrs["hx-target"] == "this"
    assert form.attrs["hx-swap"] == "outerHTML"
    assert _field(html, "title").attrs["value"] == "결제 재시도"
    assert "autofocus" in _field(html, "title").attrs
    assert _field(html, "estimate").attrs["value"] == "4h"
    assert _field(html, "week").attrs["value"] == THIS_WEEK.next().label
    assert _field(html, "due").attrs["value"] == "2026-10-20"
    assert _field(html, "external_ref").attrs["value"] == "JIRA-12"
    assert "첫 줄" in _field(html, "description").text
    assert _field(html, "version").attrs["value"] == _version(web_engine, task_id)
    assert [v for v, _, sel in select_options(html, "task_category") if sel] == ["dev"]
    statuses = select_options(html, "status")
    assert [(v, label) for v, label, _ in statuses] == [
        ("todo", "할 일"),
        ("doing", "진행 중"),
        ("done", "완료"),
        ("dropped", "중단"),
    ]
    assert [v for v, _, sel in statuses if sel] == ["todo"]
    assert "payment" in html
    assert [e for e in parse_html(html) if e.attrs.get("name") == "task_project"] == []
    assert inline_code_violations(html) == []


def test_edit_page_keeps_category_missing_from_config(
    client: TestClient, web_engine: Engine, config: Config
) -> None:
    task_id = add_task(web_engine, title="옛 분류")
    with db.session_scope(web_engine) as s:
        services.get_task(s, task_id).category = "legacy"

    html = client.get(f"/tasks/{task_id}/edit").text

    assert ("legacy", "legacy", True) in select_options(html, "task_category")


def test_edit_page_cancel_link_and_hidden_project_follow_filter(
    client: TestClient, web_engine: Engine
) -> None:
    task_id = add_task(web_engine, title="필터")

    plain = client.get(f"/tasks/{task_id}/edit").text
    filtered = client.get(f"/tasks/{task_id}/edit?project=common").text

    assert [e.attrs["href"] for e in parse_html(plain) if "data-cancel" in e.attrs] == ["/tasks"]
    assert _field(plain, "project").attrs["value"] == ""
    assert [e.attrs["href"] for e in parse_html(filtered) if "data-cancel" in e.attrs] == [
        "/tasks?project=common"
    ]
    assert _field(filtered, "project").attrs["value"] == "common"


def test_edit_page_unknown_task_is_not_found(client: TestClient) -> None:
    response = client.get("/tasks/99/edit")

    assert response.status_code == 404
    assert "<html" in response.text


def test_card_fragment_route_is_gone(client: TestClient, web_engine: Engine) -> None:
    task_id = add_task(web_engine, title="카드")

    assert client.get(f"/tasks/{task_id}/card", headers=HTMX).status_code == 404


def test_save_changes_all_fields_and_redirects(client: TestClient, web_engine: Engine) -> None:
    task_id = add_task(web_engine, title="옛 제목", category="dev")

    response = _patch(
        client,
        web_engine,
        task_id,
        title="새 제목",
        task_category="meeting",
        estimate="1h30m",
        week="next",
        due="2026-10-20",
        external_ref="JIRA-1",
        description="줄 하나\r\n줄 둘",
    )

    assert response.status_code == 200
    assert response.headers["HX-Redirect"] == f"/tasks?updated={task_id}"
    assert _stored(web_engine, task_id) == Stored(
        "새 제목",
        "meeting",
        90,
        THIS_WEEK.next().label,
        date(2026, 10, 20),
        "JIRA-1",
        "줄 하나\n줄 둘",
        TaskStatus.TODO,
    )


def test_save_redirect_keeps_the_filter(client: TestClient, web_engine: Engine) -> None:
    task_id = add_task(web_engine, title="필터")

    response = _patch(client, web_engine, task_id, title="필터 수정", project="common")

    assert response.headers["HX-Redirect"] == f"/tasks?updated={task_id}&project=common"


def test_save_clears_optional_fields(client: TestClient, web_engine: Engine) -> None:
    task_id = add_task(web_engine, title="비우기", category="dev", estimate=60, week=THIS_WEEK)
    with db.session_scope(web_engine) as s:
        services.update_task(s, task_id, external_ref="X", description="설명")

    response = _patch(client, web_engine, task_id, task_category="")

    assert response.status_code == 200
    assert _stored(web_engine, task_id) == Stored(
        "비우기", None, None, None, None, None, None, TaskStatus.TODO
    )


def test_status_only_change_to_done_records_done_at(client: TestClient, web_engine: Engine) -> None:
    task_id = add_task(web_engine, title="끝내기")

    response = _patch(client, web_engine, task_id, status="done")

    assert response.headers["HX-Redirect"] == f"/tasks?updated={task_id}"
    with db.session_scope(web_engine) as s:
        task = services.get_task(s, task_id)
        assert task.status == TaskStatus.DONE
        assert task.done_at is not None
        assert task.dropped_at is None


def test_status_only_change_to_dropped_records_dropped_at(
    client: TestClient, web_engine: Engine
) -> None:
    task_id = add_task(web_engine, title="접기", status=TaskStatus.DOING)

    response = _patch(client, web_engine, task_id, status="dropped")

    assert response.headers["HX-Redirect"] == f"/tasks?updated={task_id}"
    with db.session_scope(web_engine) as s:
        task = services.get_task(s, task_id)
        assert task.status == TaskStatus.DROPPED
        assert task.dropped_at is not None
        assert task.done_at is None


def test_save_without_changes_stays_and_says_so(client: TestClient, web_engine: Engine) -> None:
    task_id = add_task(web_engine, title="그대로", category="dev", estimate=240, week=THIS_WEEK)
    with db.session_scope(web_engine) as s:
        services.update_task(s, task_id, description="첫 줄\n둘째 줄")

    response = _patch(
        client,
        web_engine,
        task_id,
        task_category="dev",
        estimate="4h",
        week=THIS_WEEK.label,
        description="첫 줄\r\n둘째 줄",
    )

    assert response.status_code == 200
    assert "HX-Redirect" not in response.headers
    result = by_id(response.text, "task-form-result")
    assert result.text == NO_CHANGE
    assert result.attrs["role"] == "status"
    assert _stored(web_engine, task_id).description == "첫 줄\n둘째 줄"


def test_invalid_input_redraws_form_with_values(client: TestClient, web_engine: Engine) -> None:
    task_id = add_task(web_engine, title="원래")

    response = _patch(
        client,
        web_engine,
        task_id,
        title="입력한 제목",
        estimate="abc",
        week="2026-W99",
        description="적던 설명",
    )

    assert response.status_code == 400
    assert "HX-Redirect" not in response.headers
    html = response.text
    assert "<html" not in html
    assert by_id(html, "task-form").tag == "form"
    assert _field(html, "title").attrs["value"] == "입력한 제목"
    assert _field(html, "estimate").attrs["value"] == "abc"
    assert _field(html, "week").attrs["value"] == "2026-W99"
    assert "적던 설명" in _field(html, "description").text
    assert by_id(html, "task-form-result").attrs["role"] == "alert"
    assert by_id(html, "flash").attrs["hx-swap-oob"] == "innerHTML"
    assert _stored(web_engine, task_id).title == "원래"


def test_invalid_status_is_rejected(client: TestClient, web_engine: Engine) -> None:
    task_id = add_task(web_engine, title="원래")

    response = _patch(client, web_engine, task_id, status="nope")

    assert response.status_code == 400
    assert _stored(web_engine, task_id).status == TaskStatus.TODO


def test_stale_version_conflicts_with_message_and_reopen_link(
    client: TestClient, web_engine: Engine
) -> None:
    task_id = add_task(web_engine, title="원래")
    stale = _version(web_engine, task_id)
    with db.session_scope(web_engine) as s:
        services.update_task(s, task_id, title="다른 곳에서 바꿈")

    response = _patch(client, web_engine, task_id, title="내 제목", version=stale, project="common")

    assert response.status_code == 409
    html = response.text
    assert unescape(by_id(html, "task-form-result").text).startswith(
        TASK_CHANGED.format(id=task_id)
    )
    assert _field(html, "title").attrs["value"] == "내 제목"
    reopen = [e for e in parse_html(html) if e.tag == "a" and "reopen" in str(e.attrs.get("class"))]
    assert [(e.text, e.attrs["href"]) for e in reopen] == [
        ("최신 내용으로 다시 열기", f"/tasks/{task_id}/edit?project=common")
    ]
    assert _stored(web_engine, task_id).title == "다른 곳에서 바꿈"


def test_patch_unknown_task_is_not_found(client: TestClient) -> None:
    response = client.patch("/tasks/99", data={"title": "x", "version": "v"}, headers=HTMX)

    assert response.status_code == 404


def test_patch_from_other_origin_is_forbidden(client: TestClient, web_engine: Engine) -> None:
    task_id = add_task(web_engine, title="원래")

    response = client.patch(
        f"/tasks/{task_id}",
        data={"title": "해킹", "version": _version(web_engine, task_id)},
        headers={"Origin": "http://evil.example"},
    )

    assert response.status_code == 403
    assert _stored(web_engine, task_id).title == "원래"


def test_app_js_handles_cancel_escape_and_composition() -> None:
    root = Path(__file__).resolve().parents[2] / "src" / "logbook" / "web" / "static" / "js"
    script = (root / "app.js").read_text(encoding="utf-8")

    assert "[data-cancel]" in script
    assert "isComposing" in script
    assert 'event.key === "Escape"' in script or 'event.key !== "Escape"' in script
