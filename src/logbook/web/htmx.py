"""HTMX 요청 판별. 패키지 초기화(pages)를 타지 않는 모듈이라 errors와 pages가 함께 쓴다."""

from starlette.requests import Request

HTMX_REQUEST_HEADER = "HX-Request"
HTMX_HISTORY_RESTORE_HEADER = "HX-History-Restore-Request"


def is_htmx(request: Request) -> bool:
    """조각만 돌려줘야 하는 HTMX 요청인지.

    뒤로 가기 복원 요청(HX-History-Restore-Request)에는 전체 페이지를 줘야 하므로 제외한다.
    """
    headers = request.headers
    return bool(headers.get(HTMX_REQUEST_HEADER)) and HTMX_HISTORY_RESTORE_HEADER not in headers
