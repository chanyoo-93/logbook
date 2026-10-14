"""LLM 문장 다듬기(주간업무보고 요약). DB에 접근하지 않는다.

제공자(Anthropic, OpenAI) SDK는 선택 설치라 제공자 모듈이 호출될 때만 import한다.
"""

import os
from dataclasses import dataclass
from importlib import import_module
from importlib.util import find_spec
from types import MappingProxyType
from typing import Any

from logbook.core.config import LlmConfig
from logbook.core.duration import echo_input
from logbook.core.errors import ExternalServiceError, InvalidInputError
from logbook.core.polish import prompt
from logbook.core.report import ReportData

PROVIDERS = ("anthropic", "openai")
PROVIDER_LABELS = MappingProxyType({"anthropic": "Claude", "openai": "ChatGPT"})
KEY_ENV = MappingProxyType({"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY"})
EXTRA = MappingProxyType({"anthropic": "anthropic", "openai": "openai"})  # 패키지·extra 이름

UNKNOWN_PROVIDER = "제공자 이름이 올바르지 않습니다: '{echo}'. anthropic 또는 openai를 쓰세요."
NO_PROVIDER = (
    "문장 다듬기를 쓸 수 있는 제공자가 없습니다. "
    "ANTHROPIC_API_KEY나 OPENAI_API_KEY를 설정하고 "
    "'uv sync --extra anthropic'이나 'uv sync --extra openai'로 패키지를 설치하세요."
)
KEY_MISSING = "환경변수가 없습니다: {env}. {label} 문장 다듬기를 쓰려면 API 키를 설정하세요."
PACKAGE_MISSING = (
    "패키지가 설치되어 있지 않습니다: {extra}. 'uv sync --extra {extra}'로 설치하세요."
)

# 제공자 이름 -> 제공자 모듈 이름(logbook.core.polish 아래)
_MODULES = MappingProxyType({"anthropic": "claude", "openai": "chatgpt"})


@dataclass(frozen=True)
class PolishResult:
    provider: str
    model: str
    summary: str


def _has_key(provider: str) -> bool:
    return bool(os.environ.get(KEY_ENV[provider], "").strip())


def _has_package(provider: str) -> bool:
    return find_spec(EXTRA[provider]) is not None


def available_providers() -> tuple[str, ...]:
    """키(비어 있지 않은 환경변수)와 패키지가 모두 있는 제공자. PROVIDERS 순."""
    return tuple(p for p in PROVIDERS if _has_key(p) and _has_package(p))


def choose_provider(llm: LlmConfig, requested: str | None) -> str:
    """requested > llm.provider > 사용 가능한 첫 제공자. 고른 제공자를 못 쓰면 InvalidInputError."""
    if requested is not None and requested not in PROVIDERS:
        raise InvalidInputError(UNKNOWN_PROVIDER.format(echo=echo_input(requested)))
    provider = requested or llm.provider
    if not provider:
        available = available_providers()
        if not available:
            raise InvalidInputError(NO_PROVIDER)
        return available[0]
    if not _has_key(provider):
        raise InvalidInputError(
            KEY_MISSING.format(env=KEY_ENV[provider], label=PROVIDER_LABELS[provider])
        )
    if not _has_package(provider):
        raise InvalidInputError(PACKAGE_MISSING.format(extra=EXTRA[provider]))
    return provider


def model_for(llm: LlmConfig, provider: str) -> str:
    return llm.anthropic_model if provider == "anthropic" else llm.openai_model


def polish_report(
    data: ReportData, llm: LlmConfig, provider: str, *, client: Any = None
) -> PolishResult:
    """보고서 데이터로 요약 문단을 받는다. client는 테스트용(SDK 클라이언트 대역)."""
    model = model_for(llm, provider)
    module = import_module(f"{__name__}.{_MODULES[provider]}")
    raw: str = module.summarize(
        prompt.SYSTEM_PROMPT, prompt.report_payload(data), model=model, client=client
    )
    summary = prompt.clean_summary(raw)
    if not summary:
        raise ExternalServiceError(prompt.EMPTY_RESPONSE.format(label=PROVIDER_LABELS[provider]))
    return PolishResult(provider, model, summary)
