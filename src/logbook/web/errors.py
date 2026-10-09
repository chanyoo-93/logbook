"""오류 분류와 응답: API는 JSON 봉투, HTMX는 알림 조각, 그 밖은 오류 페이지.

사용자는 항상 우리가 만든 한국어 문구를 본다. htmx가 4xx·5xx도 swap하도록 설정되어 있어서
HTMX 오류 응답은 놓일 자리를 응답 헤더(HX-Retarget, HX-Reswap)로 정한다.
"""

from dataclasses import dataclass
from typing import cast

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from markupsafe import escape
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.requests import Request
from starlette.responses import HTMLResponse, Response

from logbook.core.errors import (
    DatabaseBusyError,
    DatabaseNotInitializedError,
    InvalidInputError,
    LogbookError,
    NotFoundError,
)
from logbook.web.api.envelope import fail
from logbook.web.pages.templating import is_htmx
from logbook.web.security import is_api_path, security_headers

API_NOT_FOUND = "요청한 API가 없습니다: {method} {path}"
PAGE_NOT_FOUND = "페이지를 찾을 수 없습니다: {path}"
METHOD_NOT_ALLOWED = "이 주소는 {method} 요청을 받지 않습니다: {path}"
BODY_FIELD_INVALID = "요청 본문이 올바르지 않습니다: '{field}' ({reason})."
BODY_NOT_JSON = "요청 본문을 JSON으로 읽을 수 없습니다. UTF-8로 인코딩한 JSON 객체를 보내세요."
BODY_NOT_OBJECT = "요청 본문은 JSON 객체여야 합니다. Content-Type: application/json으로 보내세요."
RECORD_CHANGED = "다른 곳에서 기록이 바뀌었습니다: #{id}. 목록을 새로 고친 뒤 다시 시도하세요."
VALUE_INVALID = "요청 값이 올바르지 않습니다: '{field}' ({reason})."
INTERNAL_ERROR = (
    "서버 내부 오류가 발생했습니다. lb serve를 실행한 터미널에서 오류 내용을 확인하세요."
)
HTTP_ERROR = "요청을 처리할 수 없습니다 (HTTP {status})."

# pydantic 오류 type -> 사유
_REASONS = {
    "missing": "필수 항목입니다",
    "extra_forbidden": "알 수 없는 항목입니다",
    "string_type": "문자열이어야 합니다",
    "int_type": "정수여야 합니다",
}
_DEFAULT_REASON = "값이 올바르지 않습니다"
# 본문 전체가 없거나 객체가 아닐 때의 loc
_WHOLE_BODY = ("body",)


class ConflictError(LogbookError):
    """화면이 본 기록이 그사이 바뀌었을 때(409 conflict). Task 5-8의 수정·삭제가 쓴다."""


@dataclass(frozen=True)
class ErrorKind:
    status: int
    code: str


def classify(error: LogbookError) -> ErrorKind:
    """core·웹 오류를 HTTP 상태 코드와 code로 나눈다."""
    if isinstance(error, ConflictError):
        return ErrorKind(409, "conflict")
    if isinstance(error, NotFoundError):
        return ErrorKind(404, "not_found")
    if isinstance(error, InvalidInputError):
        return ErrorKind(400, "invalid_input")
    if isinstance(error, DatabaseBusyError):
        return ErrorKind(503, "busy")
    if isinstance(error, DatabaseNotInitializedError):
        return ErrorKind(503, "not_initialized")
    return ErrorKind(400, "error")


def _flash_fragment(message: str) -> str:
    return f'<p class="flash flash--error" role="alert">{escape(message)}</p>'


def _error_page(message: str) -> str:
    return (
        "<!doctype html>\n"
        '<html lang="ko">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        "<title>오류 · logbook</title>\n"
        '<link rel="stylesheet" href="/static/css/app.css">\n'
        "</head>\n"
        "<body>\n"
        "<main>\n"
        f'<p role="alert">{escape(message)}</p>\n'
        '<a href="/">대시보드로 돌아가기</a>\n'
        "</main>\n"
        "</body>\n"
        "</html>\n"
    )


def error_response(request: Request, kind: ErrorKind, message: str) -> Response:
    """요청 종류에 맞는 오류 응답을 만든다.

    /api/는 JSON 봉투, HTMX 요청은 알림 조각(+HX 헤더), 그 밖은 최소 오류 페이지다.
    """
    if is_api_path(request.url.path):
        return fail(kind.status, kind.code, message)
    if is_htmx(request):
        return HTMLResponse(
            _flash_fragment(message),
            status_code=kind.status,
            headers={"HX-Retarget": "#flash", "HX-Reswap": "innerHTML", "HX-Push-Url": "false"},
        )
    return HTMLResponse(_error_page(message), status_code=kind.status)


def validation_message(error: RequestValidationError) -> str:
    """검증 오류가 여럿이어도 첫 번째 하나만 문구로 만든다(CLI의 한 줄 오류와 같다)."""
    first = error.errors()[0]
    location = tuple(first["loc"])
    if first["type"] == "json_invalid":
        return BODY_NOT_JSON
    if location == _WHOLE_BODY:
        return BODY_NOT_OBJECT
    template = BODY_FIELD_INVALID if location[:1] == _WHOLE_BODY else VALUE_INVALID
    field = ".".join(str(part) for part in location[1:])
    reason = _REASONS.get(first["type"], _DEFAULT_REASON)
    return template.format(field=field, reason=reason)


def _http_kind_and_message(
    request: Request, error: StarletteHTTPException
) -> tuple[ErrorKind, str]:
    path = request.url.path
    method = request.method
    status = error.status_code
    if status == 400:
        # FastAPI는 UTF-8이 아닌 본문 같은 해석 실패를 400 HTTPException으로 낸다.
        return ErrorKind(400, "invalid_input"), BODY_NOT_JSON
    if status == 404:
        template = API_NOT_FOUND if is_api_path(path) else PAGE_NOT_FOUND
        return ErrorKind(404, "not_found"), template.format(method=method, path=path)
    if status == 405:
        return (
            ErrorKind(405, "method_not_allowed"),
            METHOD_NOT_ALLOWED.format(method=method, path=path),
        )
    return ErrorKind(status, "error"), HTTP_ERROR.format(status=status)


async def _handle_logbook_error(request: Request, exc: Exception) -> Response:
    error = cast(LogbookError, exc)
    return error_response(request, classify(error), str(error))


async def _handle_validation_error(request: Request, exc: Exception) -> Response:
    message = validation_message(cast(RequestValidationError, exc))
    return error_response(request, ErrorKind(400, "invalid_input"), message)


async def _handle_http_exception(request: Request, exc: Exception) -> Response:
    error = cast(StarletteHTTPException, exc)
    kind, message = _http_kind_and_message(request, error)
    response = error_response(request, kind, message)
    for name, value in (error.headers or {}).items():  # 405의 Allow 같은 헤더를 유지한다.
        response.headers[name] = value
    return response


async def _handle_unexpected(request: Request, exc: Exception) -> Response:
    # Starlette의 ServerErrorMiddleware가 이 응답을 보낸 뒤 예외를 다시 던진다
    # (traceback은 uvicorn이 터미널에 남긴다).
    # 이 응답은 LocalOnlyMiddleware를 지나지 않으므로 보안 헤더를 직접 붙인다.
    response = error_response(request, ErrorKind(500, "internal"), INTERNAL_ERROR)
    for name, value in security_headers(request.url.path):
        response.headers[name] = value
    return response


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(LogbookError, _handle_logbook_error)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
    app.add_exception_handler(StarletteHTTPException, _handle_http_exception)
    app.add_exception_handler(Exception, _handle_unexpected)
