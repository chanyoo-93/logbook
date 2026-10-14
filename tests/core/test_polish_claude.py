"""logbook.core.polish.claude와 sdk_errors 테스트. 가짜 클라이언트만 쓴다(실제 API 호출 없음)."""

from types import SimpleNamespace
from typing import Any

import anthropic
import httpx2
import openai
import pytest

from logbook.core.errors import ExternalServiceError
from logbook.core.polish import claude, sdk_errors

SYSTEM = "시스템 프롬프트"
USER = '{"a": 1}'
DEFAULT_MODEL = "claude-opus-5-5"
REQUEST = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")


def response(*blocks: SimpleNamespace, stop_reason: str = "end_turn") -> SimpleNamespace:
    return SimpleNamespace(content=list(blocks), stop_reason=stop_reason)


def text(value: str) -> SimpleNamespace:
    return SimpleNamespace(type="text", text=value)


class FakeClient:
    """넘긴 인자를 기록한다. outcome이 예외면 던지고 아니면 돌려준다."""

    def __init__(self, outcome: object) -> None:
        self.outcome = outcome
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.messages = SimpleNamespace(create=self._call("messages"))
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._call("beta")))

    def _call(self, path: str) -> Any:
        def create(**kwargs: Any) -> object:
            self.calls.append((path, kwargs))
            if isinstance(self.outcome, BaseException):
                raise self.outcome
            return self.outcome

        return create


def status_error(cls: type[Any], status: int) -> Any:
    return cls("x", response=httpx2.Response(status, request=REQUEST), body=None)


def test_default_model_uses_beta_path_with_fallbacks() -> None:
    client = FakeClient(response(text("요약")))

    result = claude.summarize(SYSTEM, USER, model=DEFAULT_MODEL, client=client)

    assert result == "요약"
    ((path, kwargs),) = client.calls
    assert path == "beta"
    assert kwargs == {
        "model": DEFAULT_MODEL,
        "max_tokens": 4000,
        "system": SYSTEM,
        "messages": [{"role": "user", "content": USER}],
        "output_config": {"effort": "low"},
        "betas": ["server-side-fallback-2026-07-01"],
        "fallbacks": "default",
    }
    assert "thinking" not in kwargs


def test_other_model_uses_plain_path_without_fallbacks() -> None:
    client = FakeClient(response(text("요약")))

    claude.summarize(SYSTEM, USER, model="claude-haiku-5-5", client=client)

    ((path, kwargs),) = client.calls
    assert path == "messages"
    assert "fallbacks" not in kwargs
    assert "betas" not in kwargs
    assert kwargs["output_config"] == {"effort": "low"}
    assert "thinking" not in kwargs


def test_summarize_joins_only_text_blocks() -> None:
    client = FakeClient(
        response(
            SimpleNamespace(type="thinking", thinking="속마음"),
            text("첫째. "),
            text("둘째."),
        )
    )

    assert claude.summarize(SYSTEM, USER, model=DEFAULT_MODEL, client=client) == "첫째. 둘째."


def test_summarize_builds_default_client_with_timeout_and_retries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created: list[dict[str, Any]] = []
    fake = FakeClient(response(text("요약")))

    def factory(**kwargs: Any) -> FakeClient:
        created.append(kwargs)
        return fake

    monkeypatch.setattr(anthropic, "Anthropic", factory)

    assert claude.summarize(SYSTEM, USER, model=DEFAULT_MODEL) == "요약"
    assert created == [{"timeout": 60.0, "max_retries": 2}]


def test_refusal_is_reported() -> None:
    client = FakeClient(response(text("거절"), stop_reason="refusal"))

    with pytest.raises(ExternalServiceError) as error:
        claude.summarize(SYSTEM, USER, model=DEFAULT_MODEL, client=client)

    assert str(error.value) == "Claude 모델이 요약을 거절했습니다. 다른 제공자로 다시 시도하세요."


def test_max_tokens_is_reported() -> None:
    client = FakeClient(response(text("잘린"), stop_reason="max_tokens"))

    with pytest.raises(ExternalServiceError) as error:
        claude.summarize(SYSTEM, USER, model=DEFAULT_MODEL, client=client)

    assert str(error.value) == (
        "Claude 응답이 길이 제한에 걸려 끝까지 오지 않았습니다. 다시 시도하세요."
    )


KEY_HINT = "Claude API 키가 올바르지 않거나 권한이 없습니다. 확인할 환경변수: ANTHROPIC_API_KEY."


@pytest.mark.parametrize(
    ("error", "message"),
    [
        (status_error(anthropic.AuthenticationError, 401), KEY_HINT),
        (status_error(anthropic.PermissionDeniedError, 403), KEY_HINT),
        (
            status_error(anthropic.NotFoundError, 404),
            "Claude 모델을 쓸 수 없습니다: claude-opus-5-5. "
            "설정 [llm].anthropic_model을 확인하세요.",
        ),
        (
            status_error(anthropic.RateLimitError, 429),
            "Claude 요청 한도를 넘었습니다. 잠시 후 다시 시도하세요.",
        ),
        (
            anthropic.APITimeoutError(REQUEST),
            "Claude 응답이 60초 안에 오지 않았습니다. 잠시 후 다시 시도하세요.",
        ),
        (
            anthropic.APIConnectionError(request=REQUEST),
            "Claude 서버에 연결하지 못했습니다. 인터넷 연결을 확인하세요.",
        ),
        (
            status_error(anthropic.InternalServerError, 500),
            "Claude 요청이 실패했습니다 (HTTP 500). 잠시 후 다시 시도하세요.",
        ),
    ],
)
def test_sdk_errors_become_external_service_errors(error: Exception, message: str) -> None:
    client = FakeClient(error)

    with pytest.raises(ExternalServiceError) as raised:
        claude.summarize(SYSTEM, USER, model=DEFAULT_MODEL, client=client)

    assert str(raised.value) == message
    assert raised.value.__cause__ is error


def test_other_exceptions_propagate_unchanged() -> None:
    error = RuntimeError("boom")
    client = FakeClient(error)

    with pytest.raises(RuntimeError) as raised:
        claude.summarize(SYSTEM, USER, model=DEFAULT_MODEL, client=client)

    assert raised.value is error


def test_to_external_error_returns_none_for_unrelated_exception() -> None:
    assert (
        sdk_errors.to_external_error(
            ValueError("x"), anthropic, provider="anthropic", model="m", timeout=60.0
        )
        is None
    )


def test_to_external_error_works_with_openai_classes() -> None:
    request = httpx2.Request("POST", "https://api.openai.com/v1/responses")
    error = openai.RateLimitError("x", response=httpx2.Response(429, request=request), body=None)

    result = sdk_errors.to_external_error(
        error, openai, provider="openai", model="gpt-6.1-sol", timeout=60.0
    )

    assert isinstance(result, ExternalServiceError)
    assert str(result) == "ChatGPT 요청 한도를 넘었습니다. 잠시 후 다시 시도하세요."


def test_to_external_error_names_openai_key_variable() -> None:
    request = httpx2.Request("POST", "https://api.openai.com/v1/responses")
    error = openai.AuthenticationError(
        "x", response=httpx2.Response(401, request=request), body=None
    )

    result = sdk_errors.to_external_error(
        error, openai, provider="openai", model="gpt-6.1-sol", timeout=60.0
    )

    assert result is not None
    assert "OPENAI_API_KEY" in str(result)
    assert str(result).startswith("ChatGPT API 키")
