"""/api/report 테스트 (W40 = 09-28 ~ 10-04, 오늘 = 2026-10-01)."""

import dataclasses
import json
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from logbook.core import db, services
from logbook.core.config import Config
from logbook.core.report import TEMPLATE_NAME, render_markdown
from logbook.core.weeks import parse_week
from tests.helpers import FIXED_NOW
from tests.web.helpers import add_log, add_project

W40_DAY = date(2026, 10, 1)


def _error(response_json: dict[str, object]) -> dict[str, str]:
    assert response_json["ok"] is False
    error = response_json["error"]
    assert isinstance(error, dict)
    return error


def _report_data(engine: Engine, config: Config, week_text: str = "this"):  # type: ignore[no-untyped-def]
    the_week = parse_week(week_text, today=W40_DAY, week_start=config.week_start)
    with db.session_scope(engine) as s:
        return services.weekly_report(
            s,
            the_week,
            tz=FIXED_NOW.tzinfo,  # type: ignore[arg-type]
            title_format=config.report.title_format,
            author=config.report.author,
            category_labels=config.categories,
        )


def test_report_markdown_matches_cli_rendering(
    client: TestClient, web_engine: Engine, config: Config
) -> None:
    add_project(web_engine, "payment", "결제")
    add_log(web_engine, minutes=90, note="결제 재시도", project="payment", day=W40_DAY)
    add_log(web_engine, minutes=30, note="회의", category="meeting", day=W40_DAY)

    response = client.get("/api/report")

    body = response.json()
    expected = render_markdown(_report_data(web_engine, config))
    assert response.status_code == 200
    assert body["data"] == {"week": "2026-W40", "markdown": expected}
    assert "### payment (1h 30m)" in expected


def test_report_json_format(client: TestClient, web_engine: Engine, config: Config) -> None:
    add_log(web_engine, minutes=60, note="n", day=W40_DAY)

    lower = client.get("/api/report", params={"format": "json"})
    upper = client.get("/api/report", params={"format": "JSON"})

    data = lower.json()["data"]
    assert lower.status_code == 200
    assert upper.json()["data"] == data
    expected = json.loads(json.dumps(dataclasses.asdict(_report_data(web_engine, config))))
    assert data == expected
    assert {"title", "matrix", "sections", "plan"} <= set(data)
    assert isinstance(data["matrix"], list)
    assert isinstance(data["categories"], list)


def test_report_rejects_unknown_format(client: TestClient) -> None:
    response = client.get("/api/report", params={"format": "pdf"})

    assert response.status_code == 400
    error = _error(response.json())
    assert error["code"] == "invalid_input"
    assert error["message"] == "보고서 형식이 올바르지 않습니다: 'pdf'. md 또는 json을 쓰세요."


def test_report_last_week(client: TestClient) -> None:
    response = client.get("/api/report", params={"week": "last"})

    data = response.json()["data"]
    assert data["week"] == "2026-W39"
    assert "2026-09-21 ~ 2026-09-27" in data["markdown"]


def test_report_rejects_bad_week(client: TestClient) -> None:
    response = client.get("/api/report", params={"week": "x"})

    assert response.status_code == 400
    assert "주차" in _error(response.json())["message"]


def test_report_uses_user_template(client: TestClient, tmp_home: Path) -> None:
    (tmp_home / TEMPLATE_NAME).write_text("CUSTOM {{ data.week_label }}", encoding="utf-8")

    response = client.get("/api/report")

    assert response.json()["data"]["markdown"] == "CUSTOM 2026-W40\n"


def test_report_broken_user_template(client: TestClient, tmp_home: Path) -> None:
    (tmp_home / TEMPLATE_NAME).write_text("a\n{% if %}\n", encoding="utf-8")

    response = client.get("/api/report")

    assert response.status_code == 400
    error = _error(response.json())
    assert error["code"] == "invalid_input"
    assert "보고서 템플릿을 읽지 못했습니다" in error["message"]
    assert TEMPLATE_NAME in error["message"]


@pytest.mark.parametrize("fmt", ["md", "json"])
def test_report_format_blank_means_default(client: TestClient, fmt: str) -> None:
    default = client.get("/api/report", params={"format": " "}).json()["data"]

    assert "markdown" in default
    assert client.get("/api/report", params={"format": fmt}).status_code == 200
