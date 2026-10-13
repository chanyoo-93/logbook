"""태스크 카드 수정 GET /tasks/{id}/edit·card, PATCH /tasks/{id} 테스트 (오늘 = 2026-10-01, W40)."""

from dataclasses import dataclass
from html import unescape
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import Engine

from logbook.core import db, services
from logbook.core.config import Config
from logbook.core.weeks import week_of
from logbook.web.errors import TASK_CHANGED
from logbook.web.pages.panels import NO_CHANGE
from logbook.web.pages.task_views import task_version
from tests.conftest import FIXED_TODAY
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
THIS_WEEK = week_of(FIXED_TODAY)


@dataclass(frozen=True)
class Stored:
    title: str
    category: str | None
    estimate: int | None
    week: str | None


def _stored(engine: Engine, task_id: int) -> Stored:
    with db.session_scope(engine) as s:
        t = services.get_task(s, task_id)
        return Stored(t.title, t.category, t.estimate_minutes, t.planned_week)


def _version(engine: Engine, task_id: int) -> str:
    with db.session_scope(engine) as s:
        return task_version(services.get_task(s, task_id))


def _patch(client: TestClient, engine: Engine, task_id: int, **fields: str):  # type: ignore[no-untyped-def]
    form = {
        "title": "",
        "task_category": "",
        "estimate": "",
        "week": "",
        "version": _version(engine, task_id),
        "project": "",
    }
    return client.patch(f"/tasks/{task_id}", data={**form, **fields}, headers=HTMX)


def _flash_text(html: str) -> str:
    return unescape(by_id(html, "flash").text)


def test_edit_card_shows_current_values(client: TestClient, web_engine: Engine) -> None:
    task_id = add_task(
        web_engine, title="결제 재시도", category="dev", estimate=240, week=THIS_WEEK.next()
    )

    response = client.get(f"/tasks/{task_id}/edit", headers=HTMX)

    assert response.status_code == 200
    html = response.text
    assert "<html" not in html
    card = by_id(html, f"task-{task_id}")
    assert "is-editing" in str(card.attrs["class"]).split()
    title = named_input(html, "title")
    assert title.attrs["value"] == "결제 재시도"
    assert "data-focus" in title.attrs
    assert named_input(html, "estimate").attrs["value"] == "4h"
    assert named_input(html, "week").attrs["value"] == THIS_WEEK.next().label
    assert named_input(html, "version").attrs["value"] == _version(web_engine, task_id)
    options = select_options(html, "task_category")
    assert ("", "없음", False) in options
    assert [value for value, _, selected in options if selected] == ["dev"]
    assert inline_code_violations(html) == []


def test_edit_card_keeps_category_missing_from_config(
    client: TestClient, web_engine: Engine, config: Config
) -> None:
    task_id = add_task(web_engine, title="옛 분류")
    with db.session_scope(web_engine) as s:
        services.get_task(s, task_id).category = "legacy"

    response = client.get(f"/tasks/{task_id}/edit", headers=HTMX)

    options = select_options(response.text, "task_category")
    assert ("legacy", "legacy", True) in options


def test_edit_card_buttons_use_outer_html(client: TestClient, web_engine: Engine) -> None:
    task_id = add_task(web_engine, title="버튼")

    html = client.get(f"/tasks/{task_id}/edit", headers=HTMX).text

    buttons = {e.text: e.attrs for e in parse_html(html) if e.tag == "button"}
    save = buttons["저장"]
    assert save["hx-patch"] == f"/tasks/{task_id}"
    assert save["hx-target"] == "#task-board"
    assert save["hx-swap"] == "outerHTML"
    assert save["hx-sync"] == "this:drop"
    assert buttons["취소"]["hx-get"] == f"/tasks/{task_id}/card"


def test_cancel_returns_view_card(client: TestClient, web_engine: Engine) -> None:
    task_id = add_task(web_engine, title="결제 재시도")

    response = client.get(f"/tasks/{task_id}/card", headers=HTMX)

    assert response.status_code == 200
    card = by_id(response.text, f"task-{task_id}")
    assert "is-editing" not in str(card.attrs["class"]).split()
    assert "결제 재시도" in response.text


def test_board_cards_have_edit_button(client: TestClient, web_engine: Engine) -> None:
    task_id = add_task(web_engine, title="수정 버튼")

    html = client.get("/tasks").text

    edits = [e for e in parse_html(html) if e.attrs.get("hx-get") == f"/tasks/{task_id}/edit"]
    assert len(edits) == 1
    assert edits[0].attrs["hx-target"] == f"#task-{task_id}"
    assert edits[0].attrs["hx-swap"] == "outerHTML"


def test_save_changes_all_fields(client: TestClient, web_engine: Engine) -> None:
    task_id = add_task(web_engine, title="옛 제목", category="dev")

    response = _patch(
        client,
        web_engine,
        task_id,
        title="새 제목",
        task_category="meeting",
        estimate="1h30m",
        week="next",
    )

    assert response.status_code == 200
    html = response.text
    assert by_id(html, "task-result").text == f"✔ 수정했습니다: #{task_id} common · 새 제목"
    assert board_columns(html)["todo"] == [task_id]
    assert by_id(html, "task-plan").attrs["hx-swap-oob"] == "true"
    assert _stored(web_engine, task_id) == Stored("새 제목", "meeting", 90, THIS_WEEK.next().label)


def test_save_clears_optional_fields(client: TestClient, web_engine: Engine) -> None:
    task_id = add_task(web_engine, title="비우기", category="dev", estimate=60, week=THIS_WEEK)

    response = _patch(client, web_engine, task_id, title="비우기")

    assert response.status_code == 200
    assert _stored(web_engine, task_id) == Stored("비우기", None, None, None)


def test_save_without_changes_says_so(client: TestClient, web_engine: Engine) -> None:
    task_id = add_task(web_engine, title="그대로", category="dev", estimate=240, week=THIS_WEEK)

    response = _patch(
        client,
        web_engine,
        task_id,
        title="그대로",
        task_category="dev",
        estimate="4h",
        week=THIS_WEEK.label,
    )

    assert response.status_code == 200
    assert by_id(response.text, "task-result").text == NO_CHANGE


def test_invalid_input_redraws_edit_card_with_values(
    client: TestClient, web_engine: Engine
) -> None:
    task_id = add_task(web_engine, title="원래")

    response = _patch(
        client, web_engine, task_id, title="입력한 제목", estimate="abc", week="2026-W99"
    )

    assert response.status_code == 400
    assert response.headers["HX-Retarget"] == f"#task-{task_id}"
    assert response.headers["HX-Reswap"] == "outerHTML"
    assert response.headers["HX-Push-Url"] == "false"
    html = response.text
    card = by_id(html, f"task-{task_id}")
    assert "is-editing" in str(card.attrs["class"]).split()
    assert named_input(html, "title").attrs["value"] == "입력한 제목"
    assert named_input(html, "estimate").attrs["value"] == "abc"
    assert named_input(html, "week").attrs["value"] == "2026-W99"
    assert _flash_text(html)
    assert by_id(html, "flash").attrs["hx-swap-oob"] == "innerHTML"
    assert _stored(web_engine, task_id).title == "원래"


def test_stale_version_conflicts_and_keeps_input(client: TestClient, web_engine: Engine) -> None:
    task_id = add_task(web_engine, title="원래")
    stale = _version(web_engine, task_id)
    with db.session_scope(web_engine) as s:
        services.update_task(s, task_id, title="다른 곳에서 바꿈")

    response = _patch(client, web_engine, task_id, title="내 제목", version=stale)

    assert response.status_code == 409
    assert _flash_text(response.text) == TASK_CHANGED.format(id=task_id)
    assert named_input(response.text, "title").attrs["value"] == "내 제목"
    assert _stored(web_engine, task_id).title == "다른 곳에서 바꿈"


def test_unknown_task_is_not_found(client: TestClient) -> None:
    response = client.get("/tasks/99/edit", headers=HTMX)

    assert response.status_code == 404


def test_patch_keeps_project_filter(client: TestClient, web_engine: Engine) -> None:
    add_project(web_engine, "payment", "결제")
    keep = add_task(web_engine, title="결제 건", project="payment")
    other = add_task(web_engine, title="공통 건")

    response = _patch(client, web_engine, keep, title="결제 건 수정", project="payment")

    columns = board_columns(response.text)
    assert columns["todo"] == [keep]
    assert other not in columns["todo"]


def test_patch_from_other_origin_is_forbidden(client: TestClient, web_engine: Engine) -> None:
    task_id = add_task(web_engine, title="원래")

    response = client.patch(
        f"/tasks/{task_id}",
        data={"title": "해킹", "version": _version(web_engine, task_id)},
        headers={"Origin": "http://evil.example"},
    )

    assert response.status_code == 403
    assert _stored(web_engine, task_id).title == "원래"


def test_app_js_covers_editing_cards() -> None:
    root = Path(__file__).resolve().parents[2] / "src" / "logbook" / "web" / "static" / "js"
    script = (root / "app.js").read_text(encoding="utf-8")

    assert 'closest(".is-editing")' in script
    assert "[hx-patch]" in script
