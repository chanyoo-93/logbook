"""/api/timer 테스트 (시작 시각 = FIXED_NOW = 2026-10-01 09:30 +09:00)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from logbook.core import db, services
from logbook.core.services.timer import NO_TIMER_MESSAGE
from tests.cli.helpers import Clock
from tests.web.helpers import add_project, add_task

STARTED_AT_UTC = "2026-10-01T00:30:00+00:00"
START_BODY = {"note": "환불 API 설계", "project": "payment", "category": "design"}


def _error(response_json: dict[str, object]) -> dict[str, str]:
    assert response_json["ok"] is False
    assert response_json["data"] is None
    error = response_json["error"]
    assert isinstance(error, dict)
    return error


def _has_timer(engine: Engine) -> bool:
    with db.session_scope(engine) as s:
        return services.get_timer(s) is not None


def test_start_timer(client: TestClient, web_engine: Engine) -> None:
    add_project(web_engine, "payment", "결제")

    response = client.post("/api/timer/start", json=START_BODY)

    data = response.json()["data"]
    assert response.status_code == 201
    assert data["task_started"] is False
    assert data["timer"] == {
        "project": "payment",
        "category": "design",
        "note": "환불 API 설계",
        "task_id": None,
        "started_at": STARTED_AT_UTC,
        "elapsed_minutes": 0,
    }
    assert _has_timer(web_engine)


def test_start_timer_from_task(client: TestClient, web_engine: Engine) -> None:
    task_id = add_task(web_engine, title="태스크 제목", category="docs")

    response = client.post("/api/timer/start", json={"task_id": task_id})

    data = response.json()["data"]
    assert response.status_code == 201
    assert data["task_started"] is True
    assert data["timer"]["note"] == "태스크 제목"
    assert data["timer"]["task_id"] == task_id
    tasks = client.get("/api/tasks", params={"status": "doing"}).json()["data"]
    assert [t["id"] for t in tasks] == [task_id]


def test_start_without_body_needs_note(client: TestClient) -> None:
    response = client.post("/api/timer/start")

    assert response.status_code == 400
    assert _error(response.json())["code"] == "invalid_input"


def test_start_twice(client: TestClient, web_engine: Engine) -> None:
    add_project(web_engine, "payment", "결제")
    client.post("/api/timer/start", json=START_BODY)

    response = client.post("/api/timer/start", json=START_BODY)

    assert response.status_code == 400
    assert "이미 진행 중인 타이머가 있습니다" in _error(response.json())["message"]


def test_start_rejects_bad_body(client: TestClient) -> None:
    response = client.post("/api/timer/start", json={"task_id": "1"})

    assert response.status_code == 400
    assert "'task_id' (정수여야 합니다)" in _error(response.json())["message"]


def test_stop_timer(client: TestClient, web_engine: Engine, clock: Clock) -> None:
    add_project(web_engine, "payment", "결제")
    client.post("/api/timer/start", json=START_BODY)
    clock.advance(minutes=85)

    response = client.post("/api/timer/stop")

    data = response.json()["data"]
    assert response.status_code == 200
    assert data["log"]["minutes"] == 85
    assert data["log"]["note"] == "환불 API 설계"
    assert data["log"]["started_at"] == STARTED_AT_UTC
    assert data["log"]["ended_at"] == "2026-10-01T01:55:00+00:00"
    assert data["elapsed_minutes"] == 85
    assert data["day_total_minutes"] == 85
    assert not _has_timer(web_engine)


def test_stop_with_note_and_round(client: TestClient, web_engine: Engine, clock: Clock) -> None:
    add_project(web_engine, "payment", "결제")
    client.post("/api/timer/start", json=START_BODY)
    clock.advance(minutes=85)

    response = client.post("/api/timer/stop", json={"note": "리뷰 반영", "round": 15})

    data = response.json()["data"]
    assert response.status_code == 200
    assert data["log"]["note"] == "환불 API 설계 — 리뷰 반영"
    assert data["log"]["minutes"] == 90
    assert data["elapsed_minutes"] == 85


def test_stop_rejects_bad_round_and_keeps_timer(
    client: TestClient, web_engine: Engine, clock: Clock
) -> None:
    add_project(web_engine, "payment", "결제")
    client.post("/api/timer/start", json=START_BODY)
    clock.advance(minutes=10)

    response = client.post("/api/timer/stop", json={"round": 0})

    assert response.status_code == 400
    assert "반올림 단위는 1~60분" in _error(response.json())["message"]
    assert _has_timer(web_engine)


def test_stop_without_timer(client: TestClient) -> None:
    response = client.post("/api/timer/stop")

    assert response.status_code == 404
    error = _error(response.json())
    assert error["code"] == "not_found"
    assert error["message"] == NO_TIMER_MESSAGE


def test_stop_under_a_minute_keeps_timer(
    client: TestClient, web_engine: Engine, clock: Clock
) -> None:
    add_project(web_engine, "payment", "결제")
    client.post("/api/timer/start", json=START_BODY)
    clock.advance(seconds=29)  # 30초부터 1분으로 올림된다

    response = client.post("/api/timer/stop")

    assert response.status_code == 400
    assert "1분이 지나지 않아" in _error(response.json())["message"]
    assert _has_timer(web_engine)


def test_stop_at_thirty_seconds_rounds_up_to_one_minute(
    client: TestClient, web_engine: Engine, clock: Clock
) -> None:
    add_project(web_engine, "payment", "결제")
    client.post("/api/timer/start", json=START_BODY)
    clock.advance(seconds=30)

    response = client.post("/api/timer/stop")

    assert response.status_code == 200
    assert response.json()["data"]["log"]["minutes"] == 1
    assert not _has_timer(web_engine)


def test_stop_rejects_round_above_sixty_with_core_message(
    client: TestClient, web_engine: Engine, clock: Clock
) -> None:
    add_project(web_engine, "payment", "결제")
    client.post("/api/timer/start", json=START_BODY)
    clock.advance(minutes=10)

    response = client.post("/api/timer/stop", json={"round": 61})

    assert response.status_code == 400
    assert "반올림 단위는 1~60분" in _error(response.json())["message"]
    assert _has_timer(web_engine)


@pytest.mark.parametrize("body", [{"extra": 1}, {"note": 1}, {"round": "15"}])
def test_stop_rejects_bad_body(client: TestClient, body: dict[str, object]) -> None:
    response = client.post("/api/timer/stop", json=body)

    assert response.status_code == 400
    assert _error(response.json())["code"] == "invalid_input"
