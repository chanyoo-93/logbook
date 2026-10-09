"""API 응답 봉투: {"ok", "data", "error"}. 한글은 이스케이프하지 않는다(JSONResponse 기본)."""

from collections.abc import Mapping

from starlette.responses import JSONResponse


class Utf8JSONResponse(JSONResponse):
    """Content-Type에 charset을 밝힌다(없으면 PowerShell 5.1이 본문을 ISO-8859-1로 읽는다)."""

    media_type = "application/json; charset=utf-8"


def ok(
    data: object,
    *,
    status_code: int = 200,
    meta: Mapping[str, object] | None = None,
) -> Utf8JSONResponse:
    """성공 응답. 목록 응답은 meta(개수 등)를 더한다."""
    body: dict[str, object] = {"ok": True, "data": data, "error": None}
    if meta is not None:
        body["meta"] = dict(meta)
    return Utf8JSONResponse(body, status_code=status_code)


def fail(status_code: int, code: str, message: str) -> Utf8JSONResponse:
    """실패 응답. code는 기계가 읽는 값, message는 사용자에게 보여 줄 한국어 문구다."""
    body = {"ok": False, "data": None, "error": {"code": code, "message": message}}
    return Utf8JSONResponse(body, status_code=status_code)
