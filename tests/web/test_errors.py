"""오류 분류와 처리기: API는 JSON 봉투, HTMX는 알림 조각, 그 밖은 오류 페이지."""

import json

import pytest
from fastapi.testclient import TestClient

from logbook.core.errors import (
    DatabaseBusyError,
    DatabaseNotInitializedError,
    InvalidInputError,
    LogbookError,
    NotFoundError,
)
from logbook.web import errors
from logbook.web.api.envelope import fail, ok
from logbook.web.errors import ConflictError, ErrorKind, classify
from tests.web.conftest import RAISED_ERRORS
from tests.web.helpers import all_by_tag

CASES = [
    ("invalid", 400, "invalid_input"),
    ("missing", 404, "not_found"),
    ("busy", 503, "busy"),
    ("uninitialized", 503, "not_initialized"),
    ("plain", 400, "error"),
    ("conflict", 409, "conflict"),
]
JSON_HEADERS = {"Content-Type": "application/json"}


def page_message(markup: str) -> str:
    """오류 페이지의 <p role="alert"> 문구."""
    [alert] = [p for p in all_by_tag(markup, "p") if p.attrs.get("role") == "alert"]
    return alert.text


def api_error(response_json: dict[str, object]) -> dict[str, str]:
    assert response_json["ok"] is False
    assert response_json["data"] is None
    error = response_json["error"]
    assert isinstance(error, dict)
    return error


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (InvalidInputError("x"), ErrorKind(400, "invalid_input")),
        (NotFoundError("x"), ErrorKind(404, "not_found")),
        (DatabaseBusyError("x"), ErrorKind(503, "busy")),
        (DatabaseNotInitializedError("x"), ErrorKind(503, "not_initialized")),
        (ConflictError("x"), ErrorKind(409, "conflict")),
        (LogbookError("x"), ErrorKind(400, "error")),
    ],
)
def test_classify_follows_status_table(error: LogbookError, expected: ErrorKind) -> None:
    assert classify(error) == expected


def test_envelope_ok_and_fail_shapes() -> None:
    body = json.loads(ok({"a": 1}).body)
    assert body == {"ok": True, "data": {"a": 1}, "error": None}
    listed = ok([1], status_code=201, meta={"total": 1})
    assert listed.status_code == 201
    assert json.loads(listed.body) == {"ok": True, "data": [1], "error": None, "meta": {"total": 1}}
    failed = fail(404, "not_found", "없음")
    assert failed.status_code == 404
    assert json.loads(failed.body) == {
        "ok": False,
        "data": None,
        "error": {"code": "not_found", "message": "없음"},
    }


@pytest.mark.parametrize(("kind", "status", "code"), CASES)
def test_api_errors_use_envelope(
    probe_client: TestClient, kind: str, status: int, code: str
) -> None:
    response = probe_client.get(f"/api/raise/{kind}")
    assert response.status_code == status
    assert api_error(response.json()) == {"code": code, "message": str(RAISED_ERRORS[kind])}


@pytest.mark.parametrize(("kind", "status", "code"), CASES)
def test_htmx_errors_become_flash_fragment(
    probe_client: TestClient, kind: str, status: int, code: str
) -> None:
    response = probe_client.get(f"/raise/{kind}", headers={"HX-Request": "true"})
    assert response.status_code == status
    assert response.headers["content-type"] == "text/html; charset=utf-8"
    assert response.headers["HX-Retarget"] == "#flash"
    assert response.headers["HX-Reswap"] == "innerHTML"
    assert response.headers["HX-Push-Url"] == "false"
    [paragraph] = all_by_tag(response.text, "p")
    assert paragraph.attrs == {"class": "flash flash--error", "role": "alert"}
    assert paragraph.text == str(RAISED_ERRORS[kind])
    assert "<html" not in response.text


def test_flash_fragment_escapes_message(probe_client: TestClient) -> None:
    response = probe_client.get("/raise/markup", headers={"HX-Request": "true"})
    assert "<b>" not in response.text
    [paragraph] = all_by_tag(response.text, "p")
    assert paragraph.text == str(RAISED_ERRORS["markup"])


def test_history_restore_request_gets_full_page(probe_client: TestClient) -> None:
    response = probe_client.get(
        "/raise/invalid",
        headers={"HX-Request": "true", "HX-History-Restore-Request": "true"},
    )
    assert response.status_code == 400
    assert "<html" in response.text
    assert "HX-Retarget" not in response.headers


def test_page_errors_render_error_page(probe_client: TestClient) -> None:
    response = probe_client.get("/raise/missing")
    assert response.status_code == 404
    assert response.headers["content-type"] == "text/html; charset=utf-8"
    assert '<html lang="ko">' in response.text
    assert page_message(response.text) == str(RAISED_ERRORS["missing"])
    [title] = all_by_tag(response.text, "title")
    assert title.text == "오류 · logbook"
    [sheet] = [e for e in all_by_tag(response.text, "link") if e.attrs.get("rel") == "stylesheet"]
    assert sheet.attrs["href"] == "/static/css/app.css"
    [back] = all_by_tag(response.text, "a")
    assert back.attrs["href"] == "/"
    assert back.text == "대시보드로 돌아가기"
    assert "<script" not in response.text
    assert "style=" not in response.text
    assert "<style" not in response.text


def test_error_page_escapes_message(probe_client: TestClient) -> None:
    response = probe_client.get("/raise/markup")
    assert "<b>" not in response.text
    assert page_message(response.text) == str(RAISED_ERRORS["markup"])


def test_unknown_paths_say_what_was_requested(probe_client: TestClient) -> None:
    api = probe_client.get("/api/nope")
    assert api.status_code == 404
    assert api_error(api.json()) == {
        "code": "not_found",
        "message": "요청한 API가 없습니다: GET /api/nope",
    }
    page = probe_client.get("/nope")
    assert page.status_code == 404
    assert page_message(page.text) == "페이지를 찾을 수 없습니다: /nope"


def test_long_paths_are_limited_in_not_found_messages(probe_client: TestClient) -> None:
    path = "/" + "a" * 100
    api = probe_client.get("/api" + path)
    page = probe_client.get(path)

    assert api_error(api.json())["message"] == "요청한 API가 없습니다: GET /api/" + "a" * 35 + "..."
    assert page_message(page.text) == "페이지를 찾을 수 없습니다: /" + "a" * 39 + "..."


def test_long_field_names_are_limited_in_validation_messages(probe_client: TestClient) -> None:
    response = probe_client.post("/api/echo", json={"n": 1, "x" * 100: 2})

    assert api_error(response.json())["message"] == (
        f"요청 본문이 올바르지 않습니다: '{'x' * 40}...' (알 수 없는 항목입니다)."
    )


@pytest.mark.parametrize("prefix", ["/api", ""])
def test_method_not_allowed(probe_client: TestClient, prefix: str) -> None:
    response = probe_client.delete(f"{prefix}/get-only")
    assert response.status_code == 405
    assert "GET" in response.headers["allow"]
    message = errors.METHOD_NOT_ALLOWED.format(method="DELETE", path=f"{prefix}/get-only")
    assert message == f"이 주소는 DELETE 요청을 받지 않습니다: {prefix}/get-only"
    if prefix:
        assert api_error(response.json()) == {"code": "method_not_allowed", "message": message}
    else:
        assert page_message(response.text) == message


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({}, "요청 본문이 올바르지 않습니다: 'n' (필수 항목입니다)."),
        ({"n": "1"}, "요청 본문이 올바르지 않습니다: 'n' (정수여야 합니다)."),
        ({"n": 1, "x": 2}, "요청 본문이 올바르지 않습니다: 'x' (알 수 없는 항목입니다)."),
        ([], errors.BODY_NOT_OBJECT),
        ({"n": 1.5}, "요청 본문이 올바르지 않습니다: 'n' (정수여야 합니다)."),
    ],
    ids=["missing", "string-int", "extra", "array", "float"],
)
def test_body_validation_messages(probe_client: TestClient, payload: object, message: str) -> None:
    response = probe_client.post("/api/echo", json=payload)
    assert response.status_code == 400
    assert api_error(response.json()) == {"code": "invalid_input", "message": message}


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"content": b"{", "headers": JSON_HEADERS}, errors.BODY_NOT_JSON),
        ({"content": b'{"n": 1}'}, errors.BODY_NOT_OBJECT),
        ({}, errors.BODY_NOT_OBJECT),
        (
            {"content": '{"n": "가"}'.encode("cp949"), "headers": JSON_HEADERS},
            errors.BODY_NOT_JSON,
        ),
    ],
    ids=["broken-json", "no-content-type", "no-body", "cp949"],
)
def test_unreadable_bodies(
    probe_client: TestClient, kwargs: dict[str, object], message: str
) -> None:
    response = probe_client.post("/api/echo", **kwargs)  # type: ignore[arg-type]
    assert response.status_code == 400
    assert api_error(response.json()) == {"code": "invalid_input", "message": message}


def test_list_item_location_joins_integer_positions(probe_client: TestClient) -> None:
    response = probe_client.post("/api/list", json={"items": [1, "x"]})
    assert response.status_code == 400
    assert api_error(response.json())["message"] == (
        "요청 본문이 올바르지 않습니다: 'items.1' (정수여야 합니다)."
    )


def test_other_error_types_use_default_reason(probe_client: TestClient) -> None:
    response = probe_client.post("/api/list", json={"items": "x"})
    assert api_error(response.json())["message"] == (
        "요청 본문이 올바르지 않습니다: 'items' (값이 올바르지 않습니다)."
    )


def test_query_validation_uses_value_message(probe_client: TestClient) -> None:
    response = probe_client.get("/api/query", params={"limit": "abc"})
    assert response.status_code == 400
    assert api_error(response.json()) == {
        "code": "invalid_input",
        "message": "요청 값이 올바르지 않습니다: 'limit' (값이 올바르지 않습니다).",
    }
    missing = probe_client.get("/api/query")
    assert api_error(missing.json())["message"] == (
        "요청 값이 올바르지 않습니다: 'limit' (필수 항목입니다)."
    )


@pytest.mark.parametrize("path", ["/api/boom", "/boom"])
def test_unexpected_exception_is_internal_error(probe_client: TestClient, path: str) -> None:
    response = probe_client.get(path)
    assert response.status_code == 500
    if path.startswith("/api/"):
        assert api_error(response.json()) == {
            "code": "internal",
            "message": errors.INTERNAL_ERROR,
        }
    else:
        assert page_message(response.text) == errors.INTERNAL_ERROR
    assert "boom" not in response.text


def test_unexpected_exception_in_htmx_is_flash_with_headers(probe_client: TestClient) -> None:
    response = probe_client.get("/boom", headers={"HX-Request": "true"})
    assert response.status_code == 500
    assert response.headers["HX-Retarget"] == "#flash"
    assert response.headers["HX-Push-Url"] == "false"


def test_api_path_ignores_htmx_header(probe_client: TestClient) -> None:
    response = probe_client.get("/api/raise/invalid", headers={"HX-Request": "true"})
    assert response.headers["content-type"] == "application/json"
    assert "HX-Retarget" not in response.headers


@pytest.mark.parametrize("prefix", ["/api", ""])
def test_other_http_status_uses_generic_message(probe_client: TestClient, prefix: str) -> None:
    response = probe_client.get(f"{prefix}/teapot")
    assert response.status_code == 418
    message = "요청을 처리할 수 없습니다 (HTTP 418)."
    if prefix:
        assert api_error(response.json()) == {"code": "error", "message": message}
    else:
        assert page_message(response.text) == message


def test_json_keeps_korean_unescaped(probe_client: TestClient) -> None:
    response = probe_client.get("/api/raise/invalid")
    assert str(RAISED_ERRORS["invalid"]).encode("utf-8") in response.content
    assert b"\\u" not in response.content
