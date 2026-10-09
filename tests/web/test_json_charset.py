"""모든 JSON 응답은 charset=utf-8을 밝힌다(Windows PowerShell 5.1이 한글을 깨 읽는 것을 막는다)."""

import pytest
from fastapi.testclient import TestClient

from tests.web.conftest import RAISED_ERRORS

JSON_UTF8 = "application/json; charset=utf-8"


def test_success_responses_declare_utf8(client: TestClient) -> None:
    created = client.post("/api/tasks", json={"title": "한글 태스크"})
    assert created.status_code == 201
    assert created.headers["content-type"] == JSON_UTF8
    assert "한글 태스크".encode() in created.content
    listed = client.get("/api/tasks")
    assert listed.status_code == 200
    assert listed.headers["content-type"] == JSON_UTF8


@pytest.mark.parametrize(
    ("path", "status"),
    [
        ("/api/raise/invalid", 400),
        ("/api/raise/missing", 404),
        ("/api/raise/busy", 503),
        ("/api/boom", 500),
    ],
)
def test_error_responses_declare_utf8(probe_client: TestClient, path: str, status: int) -> None:
    response = probe_client.get(path)
    assert response.status_code == status
    assert response.headers["content-type"] == JSON_UTF8


def test_error_body_has_korean_as_utf8_bytes(probe_client: TestClient) -> None:
    response = probe_client.get("/api/raise/missing")
    assert str(RAISED_ERRORS["missing"]).encode() in response.content


def test_middleware_rejection_declares_utf8(probe_client: TestClient) -> None:
    response = probe_client.get("/api/x", headers={"Host": "evil.example"})
    assert response.status_code == 403
    assert response.headers["content-type"] == JSON_UTF8
