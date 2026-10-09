"""/api/logs 테스트 (W40 = 09-28 ~ 10-04, 오늘 = 2026-10-01)."""

from collections.abc import Iterator
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from logbook.core import db, services
from logbook.core.services._shared import MISSING_CATEGORY_MESSAGE
from tests.helpers import hold_lock
from tests.web.conftest import LockedApp
from tests.web.helpers import add_log, add_project, add_task

W40_DAY = date(2026, 10, 1)
W39_DAY = date(2026, 9, 24)


def _count_logs(engine: Engine) -> int:
    with db.session_scope(engine) as s:
        return len(services.list_worklogs(s))


def _error(response_json: dict[str, object]) -> dict[str, str]:
    assert response_json["ok"] is False
    assert response_json["data"] is None
    error = response_json["error"]
    assert isinstance(error, dict)
    return error


def test_list_defaults_to_this_week(client: TestClient, web_engine: Engine) -> None:
    add_log(web_engine, minutes=60, note="b", day=W40_DAY)
    add_log(web_engine, minutes=30, note="a", day=date(2026, 9, 29))
    add_log(web_engine, minutes=90, note="old", day=W39_DAY)

    response = client.get("/api/logs")

    body = response.json()
    assert response.status_code == 200
    assert [item["note"] for item in body["data"]] == ["a", "b"]
    assert body["meta"] == {
        "week": "2026-W40",
        "start": "2026-09-28",
        "end": "2026-10-04",
        "count": 2,
        "total_minutes": 90,
    }
    assert body["error"] is None


def test_list_filters(client: TestClient, web_engine: Engine) -> None:
    add_project(web_engine, "payment", "결제")
    add_log(web_engine, minutes=60, note="p", project="payment", category="dev", day=W40_DAY)
    add_log(web_engine, minutes=30, note="c", category="docs", day=W40_DAY)
    add_log(web_engine, minutes=90, note="old", day=W39_DAY)

    last = client.get("/api/logs", params={"week": "last"}).json()
    by_project = client.get("/api/logs", params={"project": "payment"}).json()
    by_category = client.get("/api/logs", params={"category": "dev"}).json()
    blank = client.get("/api/logs", params={"project": " ", "category": ""}).json()

    assert [i["note"] for i in last["data"]] == ["old"]
    assert [i["note"] for i in by_project["data"]] == ["p"]
    assert [i["note"] for i in by_category["data"]] == ["p"]
    assert len(blank["data"]) == 2


def test_list_invalid_week_and_unknown_project(client: TestClient) -> None:
    bad_week = client.get("/api/logs", params={"week": "x"})
    no_project = client.get("/api/logs", params={"project": "nope"})

    assert bad_week.status_code == 400
    assert _error(bad_week.json())["code"] == "invalid_input"
    assert "주차" in _error(bad_week.json())["message"]
    assert no_project.status_code == 404
    assert _error(no_project.json())["code"] == "not_found"
    assert "nope" in _error(no_project.json())["message"]


def test_create_log(client: TestClient, web_engine: Engine) -> None:
    add_project(web_engine, "payment", "결제")

    response = client.post(
        "/api/logs",
        json={"duration": "2h", "note": "결제 재시도", "project": "payment", "category": "dev"},
    )

    body = response.json()
    log = body["data"]["log"]
    assert response.status_code == 201
    assert log["minutes"] == 120
    assert log["duration"] == "2h"
    assert log["date"] == "2026-10-01"
    assert log["project"] == "payment"
    assert log["category"] == "dev"
    assert log["task_id"] is None
    assert log["started_at"] is None
    assert log["created_at"].endswith("+00:00")
    assert body["data"]["day_total_minutes"] == 120
    assert _count_logs(web_engine) == 1


def test_create_log_takes_project_and_category_from_task(
    client: TestClient, web_engine: Engine
) -> None:
    add_project(web_engine, "payment", "결제")
    task_id = add_task(web_engine, title="t", project="payment", category="docs")

    response = client.post("/api/logs", json={"duration": "1h", "note": "n", "task_id": task_id})

    log = response.json()["data"]["log"]
    assert response.status_code == 201
    assert (log["project"], log["category"], log["task_id"]) == ("payment", "docs", task_id)


def test_create_log_with_date_keyword(client: TestClient) -> None:
    response = client.post(
        "/api/logs",
        json={"duration": "1h", "note": "n", "category": "dev", "date": "yesterday"},
    )

    assert response.json()["data"]["log"]["date"] == "2026-09-30"


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ({"duration": "25h", "note": "n", "category": "dev"}, "소요 시간은 24시간 이하여야 합니다"),
        ({"duration": 90, "note": "n"}, "'duration' (문자열이어야 합니다)"),
        ({"duration": "1h"}, "'note' (필수 항목입니다)"),
        ({"duration": "1h", "note": "n", "task_id": "42"}, "'task_id' (정수여야 합니다)"),
        ({"duration": "1h", "note": "n", "task_id": 0}, "태스크 ID가 올바르지 않습니다: 0."),
        ({"duration": "1h", "note": "n", "extra": 1}, "'extra' (알 수 없는 항목입니다)"),
    ],
    ids=["too-long", "number-duration", "missing-note", "string-task-id", "zero-task-id", "extra"],
)
def test_create_log_rejects_bad_input(
    client: TestClient, web_engine: Engine, payload: dict[str, object], expected: str
) -> None:
    response = client.post("/api/logs", json=payload)

    assert response.status_code == 400
    error = _error(response.json())
    assert error["code"] == "invalid_input"
    assert expected in error["message"]
    assert _count_logs(web_engine) == 0


def test_create_log_without_category_or_task(client: TestClient) -> None:
    response = client.post("/api/logs", json={"duration": "1h", "note": "n"})

    assert response.status_code == 400
    assert _error(response.json())["message"] == MISSING_CATEGORY_MESSAGE


def test_create_log_in_archived_project(client: TestClient, web_engine: Engine) -> None:
    add_project(web_engine, "old", "옛", archived=True)

    response = client.post(
        "/api/logs",
        json={"duration": "1h", "note": "n", "category": "dev", "project": "old"},
    )

    assert response.status_code == 400
    assert "old" in _error(response.json())["message"]
    assert _count_logs(web_engine) == 0


def test_create_log_when_database_is_locked(locked_client: LockedApp) -> None:
    client, engine, path = locked_client
    with hold_lock(path, "EXCLUSIVE"):
        response = client.post("/api/logs", json={"duration": "1h", "note": "n", "category": "dev"})
    assert response.status_code == 503
    assert _error(response.json())["code"] == "busy"
    assert "사용 중" in _error(response.json())["message"]
    assert _count_logs(engine) == 0


def test_create_log_rejects_cross_origin(client: TestClient, web_engine: Engine) -> None:
    response = client.post(
        "/api/logs",
        json={"duration": "1h", "note": "n", "category": "dev"},
        headers={"Origin": "http://evil.example"},
    )

    assert response.status_code == 403
    assert _count_logs(web_engine) == 0


@pytest.fixture
def two_tasks(web_engine: Engine) -> Iterator[tuple[int, int]]:
    yield (
        add_task(web_engine, title="a", category="dev"),
        add_task(web_engine, title="b", category="dev"),
    )


def test_patch_log(client: TestClient, web_engine: Engine) -> None:
    log_id = add_log(web_engine, minutes=60, note="before")

    response = client.patch(f"/api/logs/{log_id}", json={"duration": "90m", "note": "고침"})

    log = response.json()["data"]["log"]
    assert response.status_code == 200
    assert (log["minutes"], log["duration"], log["note"]) == (90, "1h 30m", "고침")


def test_patch_log_date_category_project(client: TestClient, web_engine: Engine) -> None:
    add_project(web_engine, "payment", "결제")
    log_id = add_log(web_engine, minutes=60, note="x")

    response = client.patch(
        f"/api/logs/{log_id}",
        json={"date": "2026-09-29", "category": "docs", "project": "payment"},
    )

    log = response.json()["data"]["log"]
    assert (log["date"], log["category"], log["project"]) == ("2026-09-29", "docs", "payment")


def test_patch_log_task_link(
    client: TestClient, web_engine: Engine, two_tasks: tuple[int, int]
) -> None:
    first, second = two_tasks
    log_id = add_log(web_engine, minutes=60, note="x", task_id=first)

    changed = client.patch(f"/api/logs/{log_id}", json={"task_id": second})
    cleared = client.patch(f"/api/logs/{log_id}", json={"task_id": None})

    assert changed.json()["data"]["log"]["task_id"] == second
    assert cleared.status_code == 200
    assert cleared.json()["data"]["log"]["task_id"] is None


def test_patch_log_requires_a_field(client: TestClient, web_engine: Engine) -> None:
    log_id = add_log(web_engine, minutes=60, note="x")

    response = client.patch(f"/api/logs/{log_id}", json={})

    assert response.status_code == 400
    assert _error(response.json())["message"] == (
        "바꿀 항목을 하나 이상 지정하세요: duration, note, category, project, date, task_id"
    )


def test_patch_log_null_note(client: TestClient, web_engine: Engine) -> None:
    log_id = add_log(web_engine, minutes=60, note="x")

    response = client.patch(f"/api/logs/{log_id}", json={"note": None})

    assert response.status_code == 400
    assert _error(response.json())["message"] == "'note' 값은 비울 수 없습니다."


def test_patch_log_bad_and_missing_id(client: TestClient) -> None:
    bad = client.patch("/api/logs/abc", json={"note": "x"})
    missing = client.patch("/api/logs/999", json={"note": "x"})

    assert bad.status_code == 400
    assert _error(bad.json())["message"].startswith("기록 ID가 올바르지 않습니다: 'abc'.")
    assert missing.status_code == 404
    assert "#999" in _error(missing.json())["message"]


def test_delete_log_twice(client: TestClient, web_engine: Engine) -> None:
    log_id = add_log(web_engine, minutes=60, note="x")

    first = client.delete(f"/api/logs/{log_id}")
    second = client.delete(f"/api/logs/{log_id}")

    assert first.status_code == 200
    assert first.json()["data"] == {"id": log_id}
    assert second.status_code == 404
    assert _count_logs(web_engine) == 0


def test_delete_log_bad_id(client: TestClient) -> None:
    response = client.delete("/api/logs/abc")

    assert response.status_code == 400
