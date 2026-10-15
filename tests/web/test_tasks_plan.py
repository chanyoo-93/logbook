"""다음 주 계획 패널(#task-plan)과 이월 POST /tasks/carry 테스트 (오늘 = 2026-10-01, W40)."""

from html import unescape

from fastapi.testclient import TestClient
from sqlalchemy import Engine

from logbook.core import db, services
from logbook.core.taskstatus import TaskStatus
from logbook.core.weeks import week_of
from logbook.web.pages.task_views import task_version
from logbook.web.pages.tasks import CARRIED, CARRY_CONFIRM, CARRY_NONE, CARRY_SKIPPED
from tests.conftest import FIXED_TODAY
from tests.helpers import Clock
from tests.web.helpers import (
    add_project,
    add_task,
    by_id,
    inline_code_violations,
    parse_html,
)

HTMX = {"HX-Request": "true"}
THIS_WEEK = week_of(FIXED_TODAY)
NEXT_WEEK = THIS_WEEK.next()


def _panel(html: str) -> str:
    return by_id(html, "task-plan").text


def _carry_button(html: str):  # type: ignore[no-untyped-def]
    found = [e for e in parse_html(html) if e.attrs.get("hx-post") == "/tasks/carry"]
    return found[0] if found else None


def _planned(engine: Engine, task_id: int) -> str | None:
    with db.session_scope(engine) as s:
        return services.get_task(s, task_id).planned_week


def _setup(engine: Engine) -> tuple[int, int]:
    """(다음 주 todo 8h, 이번 주 doing 4h)."""
    upcoming = add_task(engine, title="다음 주 일", week=NEXT_WEEK, estimate=480)
    current = add_task(
        engine, title="이번 주 일", week=THIS_WEEK, estimate=240, status=TaskStatus.DOING
    )
    return upcoming, current


def test_plan_panel_matches_report_section(client: TestClient, web_engine: Engine) -> None:
    upcoming, current = _setup(web_engine)

    html = client.get("/tasks").text

    text = _panel(html)
    assert "다음 주 계획 2026-W41 (10-05 ~ 10-11)" in text
    assert "common (예상 12h)" in text
    assert f"#{upcoming} 다음 주 일 — 예상 8h" in text
    assert f"#{current} 이번 주 일 — 예상 4h 이월 후보" in text
    assert text.count("이월 후보") == 1
    assert html.count('<span class="pill">이월 후보</span>') == 1
    assert inline_code_violations(html) == []


def test_plan_carry_button_lists_only_this_week_tasks(
    client: TestClient, web_engine: Engine
) -> None:
    _, current = _setup(web_engine)

    button = _carry_button(client.get("/tasks").text)

    assert button is not None
    assert unescape(str(button.attrs["hx-vals"])) == f'{{"ids": "{current}"}}'
    assert button.attrs["hx-target"] == "#task-plan"
    assert button.attrs["hx-swap"] == "outerHTML"
    assert button.attrs["hx-sync"] == "this:drop"
    assert button.attrs["hx-include"] == "#task-filters"
    assert button.attrs["hx-confirm"] == CARRY_CONFIRM.format(
        this=THIS_WEEK.label, next=NEXT_WEEK.label, count=1
    )


def test_plan_filter_shows_only_that_project(client: TestClient, web_engine: Engine) -> None:
    add_project(web_engine, "payment", "결제")
    _setup(web_engine)
    pay = add_task(web_engine, title="결제 이월", project="payment", week=THIS_WEEK)

    html = client.get("/tasks?project=payment").text

    text = _panel(html)
    assert "payment (예상" in text
    assert "common (" not in text
    button = _carry_button(html)
    assert button is not None
    assert unescape(str(button.attrs["hx-vals"])) == f'{{"ids": "{pay}"}}'


def test_empty_plan_has_no_carry_button(client: TestClient) -> None:
    html = client.get("/tasks").text

    assert "계획된 태스크가 없습니다." in _panel(html)
    assert _carry_button(html) is None


def test_filter_get_returns_panel_oob_with_same_filter(
    client: TestClient, web_engine: Engine
) -> None:
    add_project(web_engine, "payment", "결제")
    _setup(web_engine)
    add_task(web_engine, title="결제 다음", project="payment", week=NEXT_WEEK)

    html = client.get("/tasks?project=payment", headers=HTMX).text

    assert by_id(html, "task-plan").attrs["hx-swap-oob"] == "true"
    assert "common (" not in _panel(html)
    assert "payment (" in _panel(html)


def test_carry_moves_tasks_to_next_week(client: TestClient, web_engine: Engine) -> None:
    _, current = _setup(web_engine)

    response = client.post("/tasks/carry", data={"ids": str(current), "project": ""}, headers=HTMX)

    assert response.status_code == 200
    html = response.text
    panel = by_id(html, "task-plan")
    assert "hx-swap-oob" not in panel.attrs
    result = by_id(html, "plan-result").text
    assert result == CARRIED.format(count=1, this=THIS_WEEK.label, next=NEXT_WEEK.label)
    assert _planned(web_engine, current) == NEXT_WEEK.label
    assert by_id(html, "task-board").attrs["hx-swap-oob"] == "true"
    assert "다음 주" in by_id(html, f"task-{current}").text
    assert "이월 후보" not in _panel(html)


def test_carry_skips_task_changed_in_between(client: TestClient, web_engine: Engine) -> None:
    _, current = _setup(web_engine)
    second = add_task(web_engine, title="또 하나", week=THIS_WEEK)
    with db.session_scope(web_engine) as s:
        services.set_task_status(s, second, TaskStatus.DONE)

    response = client.post(
        "/tasks/carry", data={"ids": f"{current},{second}", "project": ""}, headers=HTMX
    )

    assert response.status_code == 200
    result = by_id(response.text, "plan-result").text
    assert result.endswith(CARRY_SKIPPED.format(count=1).strip())
    assert _planned(web_engine, current) == NEXT_WEEK.label
    assert _planned(web_engine, second) == THIS_WEEK.label


def test_carry_requires_ids(client: TestClient) -> None:
    response = client.post("/tasks/carry", data={"ids": "", "project": ""}, headers=HTMX)

    assert response.status_code == 400
    assert "옮길 태스크가 없습니다." in unescape(response.text)


def test_carry_rejects_bad_id(client: TestClient) -> None:
    response = client.post("/tasks/carry", data={"ids": "x", "project": ""}, headers=HTMX)

    assert response.status_code == 400
    assert "태스크" in unescape(response.text)


def test_carry_after_week_changed_conflicts(
    client: TestClient, web_engine: Engine, clock: Clock
) -> None:
    _, current = _setup(web_engine)
    clock.advance(days=7)

    response = client.post("/tasks/carry", data={"ids": str(current), "project": ""}, headers=HTMX)

    assert response.status_code == 409
    html = response.text
    assert by_id(html, "plan-result").text == CARRY_NONE
    assert by_id(html, "task-board").attrs["hx-swap-oob"] == "true"
    assert _planned(web_engine, current) == THIS_WEEK.label
    # 409 뒤 다시 그린 계획 패널은 바뀐 주(W41)를 기준으로 한다.
    panel = _panel(html)
    assert f"다음 주 계획 {NEXT_WEEK.next().label}" in panel
    assert f"다음 주 계획 {NEXT_WEEK.label} " not in panel


def test_status_change_and_add_return_panel_oob(client: TestClient, web_engine: Engine) -> None:
    task_id = add_task(web_engine, title="상태", week=THIS_WEEK)
    with db.session_scope(web_engine) as s:
        current = task_version(services.get_task(s, task_id))

    status = client.post(
        f"/tasks/{task_id}/status",
        data={"status": "doing", "version": current, "project": ""},
        headers=HTMX,
    )
    added = client.post(
        "/tasks", data={"title": "새 태스크", "week": "next", "project": ""}, headers=HTMX
    )

    assert by_id(status.text, "task-plan").attrs["hx-swap-oob"] == "true"
    assert by_id(added.text, "task-plan").attrs["hx-swap-oob"] == "true"
    assert "새 태스크" in _panel(added.text)


def test_carry_from_other_origin_is_forbidden(client: TestClient, web_engine: Engine) -> None:
    _, current = _setup(web_engine)

    response = client.post(
        "/tasks/carry",
        data={"ids": str(current)},
        headers={"Origin": "http://evil.example"},
    )

    assert response.status_code == 403
    assert _planned(web_engine, current) == THIS_WEEK.label
