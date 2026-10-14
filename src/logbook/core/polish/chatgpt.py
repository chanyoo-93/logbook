"""OpenAI(ChatGPT) 호출. SDK는 호출할 때만 import한다(선택 설치)."""

from typing import Any

from logbook.core.errors import ExternalServiceError
from logbook.core.polish import PROVIDER_LABELS, prompt, sdk_errors

PROVIDER = "openai"
TIMEOUT_SECONDS = 60.0
MAX_RETRIES = 2
MAX_OUTPUT_TOKENS = 4000
EFFORT = "low"
CONTENT_FILTER_REASON = "content_filter"


def _has_refusal(response: Any) -> bool:
    return any(
        content.type == "refusal"
        for item in response.output
        if item.type == "message"
        for content in item.content
    )


def _text_of(response: Any) -> str:
    label = PROVIDER_LABELS[PROVIDER]
    if response.status == "incomplete":
        details = response.incomplete_details  # Response.incomplete_details: {reason} 또는 None
        if details is not None and details.reason == CONTENT_FILTER_REASON:
            raise ExternalServiceError(prompt.REFUSED.format(label=label))
        raise ExternalServiceError(prompt.TRUNCATED.format(label=label))
    text: str = response.output_text
    if not text and _has_refusal(response):
        raise ExternalServiceError(prompt.REFUSED.format(label=label))
    return text


def summarize(system: str, user: str, *, model: str, client: Any = None) -> str:
    """system·user 프롬프트를 Responses API로 보내 응답 텍스트를 돌려준다.

    client는 테스트용 SDK 클라이언트 대역이다. 없으면 openai.OpenAI를 만든다.
    """
    import openai

    api: Any = (
        client
        if client is not None
        else openai.OpenAI(timeout=TIMEOUT_SECONDS, max_retries=MAX_RETRIES)
    )
    try:
        response = api.responses.create(
            model=model,
            instructions=system,
            input=user,
            reasoning={"effort": EFFORT},
            max_output_tokens=MAX_OUTPUT_TOKENS,
        )
    except Exception as error:
        converted = sdk_errors.to_external_error(
            error, openai, provider=PROVIDER, model=model, timeout=TIMEOUT_SECONDS
        )
        if converted is None:
            raise
        raise converted from error
    return _text_of(response)
