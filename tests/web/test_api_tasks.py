"""/api/tasks 테스트 (W40 = 09-28 ~ 10-04, 오늘 = 2026-10-01)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from logbook.core import db, services
from logbook.core.taskstatus import TaskStatus
from logbook.core.weeks import week_of
from tests.conftest import FIXED_TODAY
from tests.web.helpers import add_log, add_project, add_task

THIS_WEEK = week_of(FIXED_TODAY)
NEXT_WEEK = THIS_WEEK.next()
STATUS_MESSAGE = (
    "태스크 상태가 올바르지 않습니다: '{value}'. todo, doing, done, dropped 중 하나를 쓰세요."
)
NOTHING_TO_CHANGE = (
    "바꿀 항목을 하나 이상 지정하세요: title, category, estimate, week, due, ref, "
    "description, status"
)


def _error(response_json: dict[str, object]) -> dict[str, str]:
    assert response_json["ok"] is False
    assert response_json["data"] is None
    error = response_json["error"]
    assert isinstance(error, dict)
    return error


def _count_tasks(engine: Engine) -> int:
    with db.session_scope(engine) as s:
        return len(services.list_tasks(s, statuses=tuple(TaskStatus)))


def test_list_defaults_to_open_tasks_in_plan_order(client: TestClient, web_engine: Engine) -> None:
    late = add_task(web_engine, title="late", week=NEXT_WEEK)
    early = add_task(web_engine, title="early", week=THIS_WEEK)
    unplanned = add_task(web_engine, title="unplanned")
    add_task(web_engine, title="finished", status=TaskStatus.DONE)
    add_task(web_engine, title="dropped", status=TaskStatus.DROPPED)
    add_log(web_engine, minutes=60, note="a", task_id=early)
    add_log(web_engine, minutes=30, note="b", task_id=early)

    response = client.get("/api/tasks")

    body = response.json()
    assert response.status_code == 200
    assert [item["id"] for item in body["data"]] == [early, late, unplanned]
    assert [item["actual_minutes"] for item in body["data"]] == [90, 0, 0]
    assert body["meta"] == {"count": 3}
    assert set(body["data"][0]) == {
        "id",
        "project",
        "title",
        "description",
        "status",
        "category",
        "estimate_minutes",
        "planned_week",
        "due_date",
        "external_ref",
        "created_at",
        "updated_at",
        "done_at",
        "actual_minutes",
    }


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("all", ["todo", "doing", "done", "dropped"]),
        ("done,dropped", ["done", "dropped"]),
    ],
    ids=["all", "two-statuses"],
)
def test_list_status_filter(
    client: TestClient, web_engine: Engine, query: str, expected: list[str]
) -> None:
    for status in TaskStatus:
        add_task(web_engine, title=status.value, status=status)

    response = client.get("/api/tasks", params={"status": query})

    assert sorted(item["status"] for item in response.json()["data"]) == sorted(expected)


def test_list_rejects_bad_status(client: TestClient) -> None:
    response = client.get("/api/tasks", params={"status": "x"})

    assert response.status_code == 400
    error = _error(response.json())
    assert error["code"] == "invalid_input"
    assert "상태가 올바르지 않습니다: 'x'" in error["message"]


def test_list_filters_by_week_and_project(client: TestClient, web_engine: Engine) -> None:
    add_project(web_engine, "old", "옛")
    next_id = add_task(web_engine, title="next", week=NEXT_WEEK)
    add_task(web_engine, title="this", week=THIS_WEEK)
    old_id = add_task(web_engine, title="old task", project="old")
    with db.session_scope(web_engine) as s:
        services.archive_project(s, "old")

    by_week = client.get("/api/tasks", params={"week": "next"}).json()
    by_project = client.get("/api/tasks", params={"project": "old"}).json()
    hidden = client.get("/api/tasks").json()

    assert [i["id"] for i in by_week["data"]] == [next_id]
    assert [i["id"] for i in by_project["data"]] == [old_id]
    assert old_id not in [i["id"] for i in hidden["data"]]


def test_create_task(client: TestClient, web_engine: Engine) -> None:
    add_project(web_engine, "payment", "결제")

    response = client.post(
        "/api/tasks",
        json={
            "title": "환불 API 설계",
            "project": "payment",
            "category": "design",
            "estimate": "40h",
            "week": "next",
            "due": "10-15",
            "ref": "#43",
            "description": "설명",
        },
    )

    task = response.json()["data"]
    assert response.status_code == 201
    assert task["title"] == "환불 API 설계"
    assert task["project"] == "payment"
    assert task["category"] == "design"
    assert task["estimate_minutes"] == 2400
    assert task["planned_week"] == "2026-W41"
    assert task["due_date"] == "2026-10-15"
    assert task["external_ref"] == "#43"
    assert task["description"] == "설명"
    assert task["status"] == "todo"
    assert task["actual_minutes"] == 0
    assert task["created_at"].endswith("+00:00")
    assert task["done_at"] is None


def test_create_task_uses_default_project(client: TestClient) -> None:
    response = client.post("/api/tasks", json={"title": "t"})

    assert response.status_code == 201
    assert response.json()["data"]["project"] == "common"


@pytest.mark.parametrize(
    "payload",
    [
        {"title": "  "},
        {"title": "t", "project": "old"},
        {"title": "t", "category": "nope"},
        {"title": "t", "estimate": "abc"},
        {"title": "t", "week": "x"},
        {"title": "t", "due": "x"},
        {"title": 1},
    ],
    ids=[
        "blank-title",
        "archived",
        "bad-category",
        "bad-estimate",
        "bad-week",
        "bad-due",
        "number",
    ],
)
def test_create_task_rejects_bad_input(
    client: TestClient, web_engine: Engine, payload: dict[str, object]
) -> None:
    add_project(web_engine, "old", "옛", archived=True)

    response = client.post("/api/tasks", json=payload)

    assert response.status_code == 400
    assert _error(response.json())["code"] == "invalid_input"
    assert _count_tasks(web_engine) == 0


def test_patch_clears_estimate_and_changes_week(client: TestClient, web_engine: Engine) -> None:
    task_id = add_task(web_engine, title="t", week=THIS_WEEK, estimate=120)
    before = client.get("/api/tasks").json()["data"][0]

    response = client.patch(f"/api/tasks/{task_id}", json={"estimate": None, "week": "2026-W42"})

    task = response.json()["data"]
    assert response.status_code == 200
    assert task["estimate_minutes"] is None
    assert task["planned_week"] == "2026-W42"
    assert task["updated_at"] >= before["updated_at"]
    assert task["updated_at"] != before["updated_at"]


def test_patch_status_done_then_doing(client: TestClient, web_engine: Engine) -> None:
    task_id = add_task(web_engine, title="t")

    done = client.patch(f"/api/tasks/{task_id}", json={"status": "done"}).json()["data"]
    doing = client.patch(f"/api/tasks/{task_id}", json={"status": "doing"}).json()["data"]

    assert done["status"] == "done"
    assert done["done_at"] is not None
    assert doing["status"] == "doing"
    assert doing["done_at"] is None


def test_patch_fields_and_status_together(client: TestClient, web_engine: Engine) -> None:
    linked_id = add_task(web_engine, title="old")
    add_log(web_engine, minutes=45, note="n", task_id=linked_id)

    response = client.patch(f"/api/tasks/{linked_id}", json={"title": "새 제목", "status": "doing"})

    task = response.json()["data"]
    assert (task["title"], task["status"]) == ("새 제목", "doing")
    assert task["actual_minutes"] == 45


@pytest.mark.parametrize(
    ("path", "payload", "message"),
    [
        ("{id}", {}, NOTHING_TO_CHANGE),
        ("{id}", {"title": None}, "'title' 값은 비울 수 없습니다."),
        ("{id}", {"status": None}, "'status' 값은 비울 수 없습니다."),
        ("{id}", {"status": "all"}, STATUS_MESSAGE.format(value="all")),
        ("{id}", {"status": "x"}, STATUS_MESSAGE.format(value="x")),
        ("x", {"title": "t"}, "태스크 ID가 올바르지 않습니다: 'x'."),
        ("{id}", {"title": "  "}, "태스크 제목을 입력하세요."),
    ],
    ids=["empty", "null-title", "null-status", "all", "unknown", "bad-id", "blank-title"],
)
def test_patch_rejects_bad_input(
    client: TestClient, web_engine: Engine, path: str, payload: dict[str, object], message: str
) -> None:
    task_id = add_task(web_engine, title="t")

    response = client.patch(f"/api/tasks/{path.format(id=task_id)}", json=payload)

    assert response.status_code == 400
    error = _error(response.json())
    assert error["code"] == "invalid_input"
    assert message in error["message"]


def test_patch_bad_status_changes_nothing(client: TestClient, web_engine: Engine) -> None:
    task_id = add_task(web_engine, title="t")

    client.patch(f"/api/tasks/{task_id}", json={"title": "new", "status": "all"})

    assert client.get("/api/tasks").json()["data"][0]["title"] == "t"


def test_patch_unknown_task(client: TestClient) -> None:
    response = client.patch("/api/tasks/999", json={"title": "t"})

    assert response.status_code == 404
    assert _error(response.json())["code"] == "not_found"


def test_patch_text_fields_and_clearing(client: TestClient, web_engine: Engine) -> None:
    task_id = add_task(web_engine, title="t")

    set_all = client.patch(
        f"/api/tasks/{task_id}",
        json={"category": "docs", "due": "10-15", "ref": "#9", "description": "설명"},
    ).json()["data"]
    cleared = client.patch(
        f"/api/tasks/{task_id}",
        json={"category": None, "due": None, "ref": None, "description": None},
    ).json()["data"]

    assert (set_all["category"], set_all["due_date"]) == ("docs", "2026-10-15")
    assert (set_all["external_ref"], set_all["description"]) == ("#9", "설명")
    assert [cleared[k] for k in ("category", "due_date", "external_ref", "description")] == [
        None,
        None,
        None,
        None,
    ]
