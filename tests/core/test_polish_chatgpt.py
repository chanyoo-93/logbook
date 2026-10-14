"""logbook.core.polish.chatgpt 테스트. 가짜 클라이언트만 쓴다(실제 API 호출 없음)."""

from types import SimpleNamespace
from typing import Any

import httpx2
import openai
import pytest

from logbook.core.config import LlmConfig
from logbook.core.errors import ExternalServiceError
from logbook.core.polish import chatgpt, polish_report
from tests.core.test_report_render import three_project_data

SYSTEM = "시스템 프롬프트"
USER = '{"a": 1}'
DEFAULT_MODEL = "gpt-6.1-sol"
REQUEST = httpx2.Request("POST", "https://api.openai.com/v1/responses")


def response(
    output_text: str = "요약",
    *,
    status: str = "completed",
    output: tuple[SimpleNamespace, ...] = (),
) -> SimpleNamespace:
    return SimpleNamespace(status=status, output_text=output_text, output=list(output))


def refusal_message() -> SimpleNamespace:
    content = SimpleNamespace(type="refusal", refusal="거절합니다")
    return SimpleNamespace(type="message", content=[content])


class FakeClient:
    """넘긴 인자를 기록한다. outcome이 예외면 던지고 아니면 돌려준다."""

    def __init__(self, outcome: object) -> None:
        self.outcome = outcome
        self.calls: list[dict[str, Any]] = []
        self.responses = SimpleNamespace(create=self._create)

    def _create(self, **kwargs: Any) -> object:
        self.calls.append(kwargs)
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        return self.outcome


def status_error(cls: type[Any], status: int) -> Any:
    return cls("x", response=httpx2.Response(status, request=REQUEST), body=None)


def test_summarize_sends_responses_request_and_returns_output_text() -> None:
    client = FakeClient(response("요약 문단"))

    result = chatgpt.summarize(SYSTEM, USER, model=DEFAULT_MODEL, client=client)

    assert result == "요약 문단"
    assert client.calls == [
        {
            "model": DEFAULT_MODEL,
            "instructions": SYSTEM,
            "input": USER,
            "reasoning": {"effort": "low"},
            "max_output_tokens": 4000,
        }
    ]


def test_summarize_builds_default_client_with_timeout_and_retries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created: list[dict[str, Any]] = []
    fake = FakeClient(response("요약"))

    def factory(**kwargs: Any) -> FakeClient:
        created.append(kwargs)
        return fake

    monkeypatch.setattr(openai, "OpenAI", factory)

    assert chatgpt.summarize(SYSTEM, USER, model=DEFAULT_MODEL) == "요약"
    assert created == [{"timeout": 60.0, "max_retries": 2}]


def test_incomplete_status_is_reported_as_truncated() -> None:
    client = FakeClient(response("잘린", status="incomplete"))

    with pytest.raises(ExternalServiceError) as error:
        chatgpt.summarize(SYSTEM, USER, model=DEFAULT_MODEL, client=client)

    assert str(error.value) == (
        "ChatGPT 응답이 길이 제한에 걸려 끝까지 오지 않았습니다. 다시 시도하세요."
    )


def test_refusal_item_without_text_is_reported_as_refused() -> None:
    client = FakeClient(response("", output=(refusal_message(),)))

    with pytest.raises(ExternalServiceError) as error:
        chatgpt.summarize(SYSTEM, USER, model=DEFAULT_MODEL, client=client)

    assert str(error.value) == "ChatGPT 모델이 요약을 거절했습니다. 다른 제공자로 다시 시도하세요."


def test_refusal_item_with_text_keeps_the_text() -> None:
    client = FakeClient(response("요약", output=(refusal_message(),)))

    assert chatgpt.summarize(SYSTEM, USER, model=DEFAULT_MODEL, client=client) == "요약"


def test_empty_text_without_refusal_is_returned_for_the_caller_to_reject() -> None:
    reasoning_item = SimpleNamespace(type="reasoning")
    client = FakeClient(response("", output=(reasoning_item,)))

    assert chatgpt.summarize(SYSTEM, USER, model=DEFAULT_MODEL, client=client) == ""


KEY_HINT = "ChatGPT API 키가 올바르지 않거나 권한이 없습니다. 확인할 환경변수: OPENAI_API_KEY."


@pytest.mark.parametrize(
    ("error", "message"),
    [
        (status_error(openai.AuthenticationError, 401), KEY_HINT),
        (status_error(openai.PermissionDeniedError, 403), KEY_HINT),
        (
            status_error(openai.NotFoundError, 404),
            "ChatGPT 모델을 쓸 수 없습니다: gpt-6.1-sol. 설정 [llm].openai_model을 확인하세요.",
        ),
        (
            status_error(openai.RateLimitError, 429),
            "ChatGPT 요청 한도를 넘었습니다. 잠시 후 다시 시도하세요.",
        ),
        (
            openai.APITimeoutError(REQUEST),
            "ChatGPT 응답이 60초 안에 오지 않았습니다. 잠시 후 다시 시도하세요.",
        ),
        (
            openai.APIConnectionError(request=REQUEST),
            "ChatGPT 서버에 연결하지 못했습니다. 인터넷 연결을 확인하세요.",
        ),
        (
            status_error(openai.InternalServerError, 500),
            "ChatGPT 요청이 실패했습니다 (HTTP 500). 잠시 후 다시 시도하세요.",
        ),
    ],
)
def test_sdk_errors_become_external_service_errors(error: Exception, message: str) -> None:
    client = FakeClient(error)

    with pytest.raises(ExternalServiceError) as raised:
        chatgpt.summarize(SYSTEM, USER, model=DEFAULT_MODEL, client=client)

    assert str(raised.value) == message
    assert raised.value.__cause__ is error


def test_other_exceptions_propagate_unchanged() -> None:
    error = RuntimeError("boom")
    client = FakeClient(error)

    with pytest.raises(RuntimeError) as raised:
        chatgpt.summarize(SYSTEM, USER, model=DEFAULT_MODEL, client=client)

    assert raised.value is error


def test_polish_report_with_openai_provider_returns_result() -> None:
    client = FakeClient(response("  요약\n"))

    result = polish_report(three_project_data(), LlmConfig(), "openai", client=client)

    assert (result.provider, result.model, result.summary) == ("openai", DEFAULT_MODEL, "요약")
    (call,) = client.calls
    assert call["model"] == DEFAULT_MODEL
    assert call["instructions"] != ""
