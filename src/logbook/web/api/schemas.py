"""API 요청 본문 모델(pydantic)과 공통 입력 도우미."""

from pydantic import BaseModel, ConfigDict

from logbook.core.errors import InvalidInputError

NOT_NULLABLE = "'{field}' 값은 비울 수 없습니다."


class Body(BaseModel):
    """JSON 객체만 받는다. 알 수 없는 키와 타입 변환(숫자 -> 문자열 등)은 거부한다."""

    model_config = ConfigDict(extra="forbid", strict=True)


# 본문의 project·category·date는 빈 문자열이어도 그대로 서비스에 넘긴다.
# 쿼리와 달리 본문은 명시한 값이라 core가 검증해 오류를 낸다.
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


class TaskCreate(Body):
    title: str
    project: str | None = None  # 없으면 cfg.default_project
    category: str | None = None
    estimate: str | None = None  # parse_duration(text, max_minutes=None), 예: "40h"
    week: str | None = None  # parse_week
    due: str | None = None  # parse_date
    ref: str | None = None
    description: str | None = None


class TaskPatch(Body):
    """보낸 키만 바꾼다. null은 category·estimate·week·due·ref·description만 허용한다(값 비우기)."""

    title: str | None = None
    category: str | None = None
    estimate: str | None = None
    week: str | None = None
    due: str | None = None
    ref: str | None = None
    description: str | None = None
    status: str | None = None  # todo|doing|done|dropped


class TimerStart(Body):
    note: str | None = None
    project: str | None = None
    category: str | None = None
    task_id: int | None = None


class TimerStop(Body):
    note: str | None = None  # lb stop --note와 같다(' — '로 덧붙임)
    round: int | None = None  # 1~60, core가 검증


def optional_text(value: str | None) -> str | None:
    """쿼리 값: 앞뒤 공백을 지우고 비면 생략한 것(None)으로 본다."""
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def changed_fields(body: Body, *, nullable: frozenset[str]) -> frozenset[str]:
    """보낸 키 집합. nullable에 없는 키가 null이면 NOT_NULLABLE을 낸다.

    값은 호출자가 모델 속성(body.xxx)에서 읽는다(이미 타입이 맞다).
    하나도 보내지 않았으면 빈 집합을 돌려주고, 그때의 문구는 호출자가 정한다.
    """
    sent = body.model_fields_set
    for name in type(body).model_fields:
        if name in sent and name not in nullable and getattr(body, name) is None:
            raise InvalidInputError(NOT_NULLABLE.format(field=name))
    return frozenset(sent)
