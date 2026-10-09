"""LocalOnlyMiddleware: Host 검사, 교차 출처 쓰기 차단, 보안 헤더."""

import httpx2
import pytest
from fastapi.testclient import TestClient

from logbook.web import security
from logbook.web.security import cross_site_write, host_allowed, security_headers

EXPECTED_CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; "
    "connect-src 'self'; font-src 'self'; object-src 'none'; base-uri 'none'; "
    "form-action 'self'; frame-ancestors 'none'"
)
EXPECTED_HEADERS = {
    "content-security-policy": EXPECTED_CSP,
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "referrer-policy": "same-origin",
}
LOCAL_ORIGIN = "http://127.0.0.1:8765"


def assert_security_headers(response: httpx2.Response, *, no_store: bool) -> None:
    for name, value in EXPECTED_HEADERS.items():
        assert response.headers.get(name) == value, name
    if no_store:
        assert response.headers.get("cache-control") == "no-store"


@pytest.mark.parametrize(
    "host",
    ["127.0.0.1:8765", "localhost:8765", "LOCALHOST:8765", "127.0.0.1"],
)
def test_host_allowed_accepts_loopback_names(host: str) -> None:
    assert host_allowed(host) is True


@pytest.mark.parametrize(
    "host",
    [
        "evil.example:8765",
        "127.0.0.1.evil.example",
        "",
        None,
        "[::1]:8765",
        "127.0.0.1:",
        "localhost:evil",
        "127.0.0.1:80a",
    ],
    ids=[
        "other-host",
        "suffix-trick",
        "empty",
        "missing",
        "ipv6",
        "empty-port",
        "alpha-port",
        "mixed-port",
    ],
)
def test_host_allowed_rejects_other_names(host: str | None) -> None:
    assert host_allowed(host) is False


def test_cross_site_write_ignores_safe_methods() -> None:
    assert (
        cross_site_write("GET", host="127.0.0.1:8765", origin=None, fetch_site="cross-site")
        is False
    )


@pytest.mark.parametrize(
    ("fetch_site", "rejected"),
    [("same-origin", False), ("none", False), ("same-site", True), ("cross-site", True)],
)
def test_cross_site_write_uses_fetch_site_first(fetch_site: str, rejected: bool) -> None:
    # Sec-Fetch-Site가 있으면 Origin은 보지 않는다.
    result = cross_site_write(
        "POST", host="127.0.0.1:8765", origin="http://evil.example", fetch_site=fetch_site
    )
    assert result is rejected


@pytest.mark.parametrize(
    ("origin", "rejected"),
    [
        (LOCAL_ORIGIN, False),
        ("http://LOCALHOST:8765", True),
        ("http://evil.example", True),
        ("null", True),
        ("https://127.0.0.1:8765", True),
        ("http://[bad", True),
    ],
    ids=["same", "other-name", "other-host", "null", "https", "malformed"],
)
def test_cross_site_write_compares_origin_with_host(origin: str, rejected: bool) -> None:
    result = cross_site_write("POST", host="127.0.0.1:8765", origin=origin, fetch_site=None)
    assert result is rejected


def test_cross_site_write_compares_origin_case_insensitively() -> None:
    result = cross_site_write(
        "POST", host="LOCALHOST:8765", origin="http://localhost:8765", fetch_site=None
    )
    assert result is False


def test_cross_site_write_allows_clients_without_headers() -> None:
    result = cross_site_write("POST", host="127.0.0.1:8765", origin=None, fetch_site=None)
    assert result is False


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
def test_cross_site_write_treats_every_unsafe_method_alike(method: str) -> None:
    result = cross_site_write(method, host="127.0.0.1:8765", origin="null", fetch_site=None)
    assert result is True


def test_security_headers_add_no_store_except_static() -> None:
    page = dict(security_headers("/logs"))
    static = dict(security_headers("/static/css/app.css"))
    assert page["Cache-Control"] == "no-store"
    assert "Cache-Control" not in static
    for name in ("Content-Security-Policy", "X-Content-Type-Options", "X-Frame-Options"):
        assert page[name] == static[name]
    assert page["Content-Security-Policy"] == EXPECTED_CSP
    assert page["Referrer-Policy"] == "same-origin"


def test_api_host_rejection_is_forbidden_envelope(probe_client: TestClient) -> None:
    response = probe_client.get("/api/x", headers={"Host": "evil.example"})
    assert response.status_code == 403
    assert response.json() == {
        "ok": False,
        "data": None,
        "error": {
            "code": "forbidden",
            "message": security.HOST_REJECTED.format(host="evil.example"),
        },
    }
    assert_security_headers(response, no_store=True)


def test_page_host_rejection_is_plain_text(probe_client: TestClient) -> None:
    response = probe_client.get("/x", headers={"Host": "evil.example"})
    assert response.status_code == 403
    assert response.headers["content-type"] == "text/plain; charset=utf-8"
    assert response.text == security.HOST_REJECTED.format(host="evil.example")
    assert_security_headers(response, no_store=True)


def test_host_rejection_message_limits_long_host(probe_client: TestClient) -> None:
    host = "a" * 100 + ".example"
    message = probe_client.get("/x", headers={"Host": host}).text
    assert host not in message
    assert "a" * 40 + "..." in message


def test_host_rejection_happens_before_routing(probe_client: TestClient) -> None:
    # 없는 경로여도 Host가 나쁘면 404가 아니라 403이다.
    response = probe_client.get("/nope", headers={"Host": "evil.example"})
    assert response.status_code == 403


def test_loopback_host_is_served(probe_client: TestClient) -> None:
    for host in ("127.0.0.1:8765", "localhost:8765", "127.0.0.1"):
        response = probe_client.get("/x", headers={"Host": host})
        assert response.status_code == 200, host


def test_cross_origin_post_is_rejected_before_handler(
    probe_client: TestClient, probe_calls: list[str]
) -> None:
    response = probe_client.post("/api/x", headers={"Origin": "http://evil.example"})
    assert response.status_code == 403
    assert response.json()["error"] == {
        "code": "forbidden",
        "message": security.CROSS_SITE_REJECTED,
    }
    assert probe_calls == []
    assert_security_headers(response, no_store=True)


def test_cross_site_fetch_metadata_post_is_rejected_on_pages(
    probe_client: TestClient, probe_calls: list[str]
) -> None:
    response = probe_client.post("/x", headers={"Sec-Fetch-Site": "cross-site"})
    assert response.status_code == 403
    assert response.headers["content-type"] == "text/plain; charset=utf-8"
    assert response.text == security.CROSS_SITE_REJECTED
    assert probe_calls == []


def test_same_origin_and_plain_clients_may_write(
    probe_client: TestClient, probe_calls: list[str]
) -> None:
    assert probe_client.post("/api/x", headers={"Origin": LOCAL_ORIGIN}).status_code == 200
    assert probe_client.post("/api/x", headers={"Sec-Fetch-Site": "same-origin"}).status_code == 200
    assert probe_client.post("/api/x").status_code == 200
    assert probe_calls == ["write", "write", "write"]


def test_cross_origin_reads_are_not_blocked(probe_client: TestClient) -> None:
    # 읽기는 막지 않는다. 응답을 다른 사이트가 읽는 것은 브라우저의 동일 출처 정책이 막는다.
    response = probe_client.get("/api/x", headers={"Origin": "http://evil.example"})
    assert response.status_code == 200


@pytest.mark.parametrize("path", ["/api/x", "/x"])
def test_headers_on_ok_responses(probe_client: TestClient, path: str) -> None:
    assert_security_headers(probe_client.get(path), no_store=True)


@pytest.mark.parametrize("path", ["/api/nope", "/nope"])
def test_headers_on_not_found(probe_client: TestClient, path: str) -> None:
    response = probe_client.get(path)
    assert response.status_code == 404
    assert_security_headers(response, no_store=True)


@pytest.mark.parametrize("path", ["/api/boom", "/boom"])
def test_headers_on_server_error(probe_client: TestClient, path: str) -> None:
    # 500 응답은 ServerErrorMiddleware가 보내 LocalOnlyMiddleware를 지나지 않는다.
    response = probe_client.get(path)
    assert response.status_code == 500
    assert_security_headers(response, no_store=True)
    assert response.headers["cache-control"].count("no-store") == 1


def test_docs_are_disabled_so_csp_is_never_needed_for_cdn(probe_client: TestClient) -> None:
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert probe_client.get(path).status_code == 404


def test_duplicate_host_headers_are_rejected(probe_client: TestClient) -> None:
    response = probe_client.get("/x", headers=[("Host", "127.0.0.1:8765"), ("Host", "localhost")])

    assert response.status_code == 403
    assert response.text.startswith("허용되지 않은 Host 헤더입니다:")


def test_duplicate_origin_headers_are_rejected_on_writes(
    probe_client: TestClient, probe_calls: list[str]
) -> None:
    response = probe_client.post(
        "/api/x", headers=[("Origin", LOCAL_ORIGIN), ("Origin", LOCAL_ORIGIN)]
    )

    assert response.status_code == 403
    assert response.json()["error"]["message"] == security.CROSS_SITE_REJECTED
    assert probe_calls == []


def test_empty_origin_header_is_treated_as_absent(
    probe_client: TestClient, probe_calls: list[str]
) -> None:
    response = probe_client.post("/api/x", headers={"Origin": ""})

    assert response.status_code == 200
    assert probe_calls == ["write"]


@pytest.mark.parametrize("path", ["/api/x", "/x"])
def test_headers_on_head_requests(probe_client: TestClient, path: str) -> None:
    response = probe_client.head(path)

    assert_security_headers(response, no_store=True)
