"""/api/stats 테스트 (W40 = 09-28 ~ 10-04, 오늘 = 2026-10-01)."""

from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import Engine

from tests.web.helpers import add_log, add_project

MONDAY = date(2026, 9, 28)
THURSDAY = date(2026, 10, 1)


def _seed(engine: Engine) -> None:
    add_project(engine, "payment", "결제")
    add_log(engine, minutes=60, note="a", project="payment", category="dev", day=MONDAY)
    add_log(engine, minutes=120, note="b", project="payment", category="docs", day=THURSDAY)
    add_log(engine, minutes=30, note="c", project="common", category="dev", day=THURSDAY)
    add_log(engine, minutes=500, note="old", day=date(2026, 9, 24))


def test_stats_by_project_is_default(client: TestClient, web_engine: Engine) -> None:
    _seed(web_engine)

    response = client.get("/api/stats")

    data = response.json()["data"]
    assert response.status_code == 200
    assert data["by"] == "project"
    assert (data["week"], data["start"], data["end"]) == ("2026-W40", "2026-09-28", "2026-10-04")
    assert data["total_minutes"] == 210
    assert data["count"] == 3
    assert [row["key"] for row in data["rows"]] == ["payment", "common"]
    assert data["rows"][0] == {"key": "payment", "label": "결제", "minutes": 180, "count": 2}


def test_stats_by_category_uses_configured_labels(client: TestClient, web_engine: Engine) -> None:
    _seed(web_engine)

    data = client.get("/api/stats", params={"by": "category"}).json()["data"]

    assert {row["key"]: row["label"] for row in data["rows"]} == {"dev": "개발", "docs": "문서"}
    assert data["rows"][0]["key"] == "docs"


def test_stats_by_day_has_seven_rows(client: TestClient, web_engine: Engine) -> None:
    _seed(web_engine)

    rows = client.get("/api/stats", params={"by": "day"}).json()["data"]["rows"]

    assert len(rows) == 7
    assert rows[0]["label"] == "09-28 (월)"
    assert rows[0]["minutes"] == 60
    assert rows[1]["minutes"] == 0


def test_stats_blank_params_use_defaults(client: TestClient) -> None:
    data = client.get("/api/stats", params={"week": " ", "by": ""}).json()["data"]

    assert data["by"] == "project"
    assert data["week"] == "2026-W40"


def test_stats_invalid_values(client: TestClient) -> None:
    bad_by = client.get("/api/stats", params={"by": "x"})
    bad_week = client.get("/api/stats", params={"week": "2026-W99"})

    assert bad_by.status_code == 400
    assert bad_by.json()["error"]["message"].startswith("집계 기준이 올바르지 않습니다: 'x'.")
    assert bad_week.status_code == 400
    assert "주차" in bad_week.json()["error"]["message"]
