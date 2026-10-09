"""API 요청 본문 모델(pydantic)과 공통 입력 도우미."""

from pydantic import BaseModel, ConfigDict

from logbook.core.errors import InvalidInputError

NOT_NULLABLE = "'{field}' 값은 비울 수 없습니다."


class Body(BaseModel):
    """JSON 객체만 받는다. 알 수 없는 키와 타입 변환(숫자 -> 문자열 등)은 거부한다."""

    model_config = ConfigDict(extra="forbid", strict=True)


class LogCreate(Body):
    duration: str
    note: str
    project: str | None = None
    category: str | None = None
    date: str | None = None  # parse_date 입력(today, yesterday, mon~sun, 2026-10-01, 10-01)
    task_id: int | None = None


class LogPatch(Body):
    """보낸 키만 바꾼다(model_fields_set). null은 task_id만 허용한다(연결 해제)."""

    duration: str | None = None
    note: str | None = None
    category: str | None = None
    project: str | None = None
    date: str | None = None
    task_id: int | None = None


def optional_text(value: str | None) -> str | None:
    """쿼리 값: 앞뒤 공백을 지우고 비면 생략한 것(None)으로 본다."""
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def changed_fields(body: Body, *, nullable: frozenset[str]) -> dict[str, object]:
    """보낸 키와 값. nullable에 없는 키가 null이면 NOT_NULLABLE을 낸다.

    하나도 보내지 않았으면 빈 dict를 돌려주고, 그때의 문구는 호출자가 정한다.
    """
    fields: dict[str, object] = {}
    for name in type(body).model_fields:
        if name not in body.model_fields_set:
            continue
        value = getattr(body, name)
        if value is None and name not in nullable:
            raise InvalidInputError(NOT_NULLABLE.format(field=name))
        fields[name] = value
    return fields
