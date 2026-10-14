"""GET /report/download 테스트 (오늘 = 2026-10-01, W40)."""

from pathlib import Path

from fastapi.testclient import TestClient

from logbook.core.report import TEMPLATE_NAME

DISPOSITION = 'attachment; filename="weekly-report-2026-W40.md"'


def test_download_returns_markdown_attachment(client: TestClient) -> None:
    response = client.get("/report/download", params={"week": "2026-W40"})

    assert response.status_code == 200
    assert response.headers["content-type"] == "text/markdown; charset=utf-8"
    assert response.headers["content-disposition"] == DISPOSITION
    assert response.headers["cache-control"] == "no-store"
    expected = client.get("/api/report", params={"week": "2026-W40"}).json()["data"]["markdown"]
    assert response.content == expected.encode("utf-8")
    assert b"\r" not in response.content


def test_download_defaults_to_this_week(client: TestClient) -> None:
    response = client.get("/report/download")

    assert response.headers["content-disposition"] == DISPOSITION


def test_download_rejects_bad_week(client: TestClient) -> None:
    response = client.get("/report/download", params={"week": "abc"})

    assert response.status_code == 400


def test_download_with_broken_user_template_is_bad_request(
    client: TestClient, tmp_home: Path
) -> None:
    (tmp_home / TEMPLATE_NAME).write_text("a\n{% if %}\n", encoding="utf-8")

    response = client.get("/report/download")

    assert response.status_code == 400
    assert "attachment" not in response.headers.get("content-disposition", "")
