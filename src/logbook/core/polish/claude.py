"""Anthropic(Claude) 호출. SDK는 호출할 때만 import한다(선택 설치)."""

from typing import Any

from logbook.core.errors import ExternalServiceError
from logbook.core.polish import PROVIDER_LABELS, prompt, sdk_errors

PROVIDER = "anthropic"
TIMEOUT_SECONDS = 60.0
MAX_RETRIES = 2
MAX_TOKENS = 4000
EFFORT = "low"
# 거절 시 서버가 다른 모델로 다시 시도하는 기능(beta)을 받는 모델
FALLBACK_MODELS = frozenset(
    {"claude-fable-5-1", "claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5"}
)
FALLBACK_BETA = "server-side-fallback-2026-07-01"


def _text_of(response: Any) -> str:
    label = PROVIDER_LABELS[PROVIDER]
    if response.stop_reason == "refusal":
        raise ExternalServiceError(prompt.REFUSED.format(label=label))
    if response.stop_reason == "max_tokens":
        raise ExternalServiceError(prompt.TRUNCATED.format(label=label))
    return "".join(block.text for block in response.content if block.type == "text")


def summarize(system: str, user: str, *, model: str, client: Any = None) -> str:
    """system·user 프롬프트를 보내 응답의 텍스트 블록을 이어 붙여 돌려준다.

    client는 테스트용 SDK 클라이언트 대역이다. 없으면 anthropic.Anthropic을 만든다.
    thinking은 보내지 않는다(Opus 5.5는 끌 수 없고 effort로만 조절한다).
    """
    import anthropic

    api = (
        client
        if client is not None
        else anthropic.Anthropic(timeout=TIMEOUT_SECONDS, max_retries=MAX_RETRIES)
    )
    request: dict[str, Any] = {
        "model": model,
        "max_tokens": MAX_TOKENS,
        "system": system,
        "messages": [{"role": "user", "content": user}],
        "output_config": {"effort": EFFORT},
    }
    try:
        if model in FALLBACK_MODELS:
            response = api.beta.messages.create(
                **request, betas=[FALLBACK_BETA], fallbacks="default"
            )
        else:
            response = api.messages.create(**request)
    except Exception as error:
        converted = sdk_errors.to_external_error(
            error, anthropic, provider=PROVIDER, model=model, timeout=TIMEOUT_SECONDS
        )
        if converted is None:
            raise
        raise converted from error
    return _text_of(response)
