"""로컬 전용 서버의 보안 경계: Host 검사, 교차 출처 쓰기 차단, 보안 헤더.

인증이 없는 서버라서 다른 웹사이트가 사용자의 브라우저를 통해 기록을 읽거나 바꾸지 못하게 한다.
- Host 검사: 공격자 도메인이 127.0.0.1로 바뀌는 DNS 리바인딩을 막는다.
- 교차 출처 쓰기 차단: Go 1.25 net/http.CrossOriginProtection과 같은 규칙이다.
- 보안 헤더: CSP 등. 인라인 코드가 없어 모든 출처를 'self'로 좁힌다.
"""

from urllib.parse import urlsplit

from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import PlainTextResponse, Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from logbook.core.duration import echo_input
from logbook.web.api.envelope import fail

ALLOWED_HOSTNAMES = frozenset({"127.0.0.1", "localhost"})
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
API_PREFIX = "/api/"
STATIC_PREFIX = "/static/"

HOST_REJECTED = (
    "허용되지 않은 Host 헤더입니다: '{host}'. http://127.0.0.1 또는 http://localhost 주소로 여세요."
)
CROSS_SITE_REJECTED = (
    "다른 사이트에서 보낸 변경 요청은 받지 않습니다. logbook 화면에서 다시 시도하세요."
)

CONTENT_SECURITY_POLICY = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; "
    "connect-src 'self'; font-src 'self'; object-src 'none'; base-uri 'none'; "
    "form-action 'self'; frame-ancestors 'none'"
)
_BASE_HEADERS: tuple[tuple[str, str], ...] = (
    ("Content-Security-Policy", CONTENT_SECURITY_POLICY),
    ("X-Content-Type-Options", "nosniff"),
    ("X-Frame-Options", "DENY"),
    ("Referrer-Policy", "same-origin"),
)
# Sec-Fetch-Site가 이 값이면 사용자가 직접 연 것이거나 같은 출처의 요청이다.
_SAME_ORIGIN_FETCH_SITES = frozenset({"same-origin", "none"})


def is_api_path(path: str) -> bool:
    return path.startswith(API_PREFIX)


def security_headers(path: str) -> tuple[tuple[str, str], ...]:
    """모든 응답에 붙이는 보안 헤더. /static/이 아니면 Cache-Control: no-store를 더한다.

    미들웨어와 500 처리기가 함께 쓴다(500 응답은 이 미들웨어를 지나지 않는다).
    """
    if path.startswith(STATIC_PREFIX):
        return _BASE_HEADERS
    return (*_BASE_HEADERS, ("Cache-Control", "no-store"))


def host_allowed(host_header: str | None) -> bool:
    """Host 헤더의 호스트 이름(포트 제외)이 루프백 이름이면 True. 헤더가 없으면 False.

    포트가 있으면 ASCII 숫자여야 한다('127.0.0.1:', 'localhost:evil'은 거부).
    대괄호 IPv6('[::1]:8765')는 호스트 이름이 '[::1]'이라 거부된다. 서버는 IPv4에만 열린다.
    """
    if not host_header:
        return False
    hostname, separator, port = host_header.rpartition(":")
    if not separator:
        return host_header.lower() in ALLOWED_HOSTNAMES
    if not (port.isascii() and port.isdigit()):
        return False
    return hostname.lower() in ALLOWED_HOSTNAMES


def cross_site_write(method: str, *, host: str, origin: str | None, fetch_site: str | None) -> bool:
    """True면 거부할 교차 출처 쓰기 요청이다.

    1. 읽기 메서드(GET, HEAD, OPTIONS)는 허용한다.
    2. Sec-Fetch-Site가 있으면 same-origin이나 none일 때만 허용한다.
    3. 없고 Origin이 있으면 http이고 host:port가 Host 헤더와 같을 때만 허용한다('null'은 거부).
    4. 둘 다 없으면 브라우저가 아닌 클라이언트(curl, 스크립트)라서 허용한다.
    """
    if method in SAFE_METHODS:
        return False
    if fetch_site:
        return fetch_site not in _SAME_ORIGIN_FETCH_SITES
    if origin is None or origin == "":
        return False
    return not _same_origin(origin, host)


def _same_origin(origin: str, host: str) -> bool:
    try:
        parts = urlsplit(origin)
    except ValueError:
        return False
    return parts.scheme == "http" and parts.netloc.lower() == host.lower()


class LocalOnlyMiddleware:
    """순수 ASGI 미들웨어(BaseHTTPMiddleware를 쓰지 않는다).

    http 요청만 검사하고, 통과한 응답의 http.response.start에 보안 헤더를 더한다.
    거부 응답에도 같은 헤더를 붙인다.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            # 주의: websocket(과 lifespan)은 Host·Origin 검사 없이 통과한다.
            # 지금은 websocket 라우트가 없다. 더하면 같은 Host·Origin 검사가 필요하다.
            await self.app(scope, receive, send)
            return

        path: str = scope["path"]

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for name, value in security_headers(path):
                    headers[name] = value
            await send(message)

        rejection = _rejection(scope, path)
        if rejection is not None:
            await rejection(scope, receive, send_with_headers)
            return
        await self.app(scope, receive, send_with_headers)


def _rejection(scope: Scope, path: str) -> Response | None:
    """요청을 거부해야 하면 403 응답을, 통과시키면 None을 돌려준다."""
    headers = Headers(scope=scope)
    hosts = headers.getlist("host")
    host = hosts[0] if hosts else None
    # 같은 헤더가 여럿이면 서버와 프록시가 다른 값을 고를 수 있어 거부한다.
    if len(hosts) > 1 or not host_allowed(host):
        return _forbidden(path, HOST_REJECTED.format(host=echo_input(", ".join(hosts))))
    origins = headers.getlist("origin")
    method = scope["method"]
    if (method not in SAFE_METHODS and len(origins) > 1) or cross_site_write(
        method,
        host=host or "",
        origin=origins[0] if origins else None,
        fetch_site=headers.get("sec-fetch-site"),
    ):
        return _forbidden(path, CROSS_SITE_REJECTED)
    return None


def _forbidden(path: str, message: str) -> Response:
    if is_api_path(path):
        return fail(403, "forbidden", message)
    return PlainTextResponse(message, status_code=403)
