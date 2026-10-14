"""logbook.core.polish 공통 흐름과 prompt 도우미 테스트. 실제 API는 부르지 않는다."""

import json
from dataclasses import replace
from types import SimpleNamespace
from typing import Any

import pytest

from logbook.core import polish
from logbook.core.config import LlmConfig
from logbook.core.errors import ExternalServiceError, InvalidInputError
from logbook.core.polish import prompt
from logbook.core.report import CommitGroup, CommitLine
from tests.core.test_report_render import three_project_data

NO_PROVIDER_AVAILABLE = (
    "문장 다듬기를 쓸 수 있는 제공자가 없습니다. "
    "ANTHROPIC_API_KEY나 OPENAI_API_KEY를 설정하고 "
    "'uv sync --extra anthropic'이나 'uv sync --extra openai'로 패키지를 설치하세요."
)


def set_environment(
    monkeypatch: pytest.MonkeyPatch,
    *,
    anthropic_key: bool = False,
    openai_key: bool = False,
    anthropic_package: bool = False,
    openai_package: bool = False,
) -> None:
    """키(환경변수)와 패키지(find_spec) 조합을 만든다."""
    for env, present in (("ANTHROPIC_API_KEY", anthropic_key), ("OPENAI_API_KEY", openai_key)):
        if present:
            monkeypatch.setenv(env, "test-key")
        else:
            monkeypatch.delenv(env, raising=False)
    installed = {"anthropic": anthropic_package, "openai": openai_package}
    monkeypatch.setattr(polish, "find_spec", lambda name: object() if installed.get(name) else None)


def full_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    set_environment(
        monkeypatch,
        anthropic_key=True,
        openai_key=True,
        anthropic_package=True,
        openai_package=True,
    )


@pytest.mark.parametrize(
    ("flags", "expected"),
    [
        ({}, ()),
        ({"anthropic_key": True, "anthropic_package": True}, ("anthropic",)),
        ({"openai_key": True, "openai_package": True}, ("openai",)),
        (
            {
                "anthropic_key": True,
                "openai_key": True,
                "anthropic_package": True,
                "openai_package": True,
            },
            ("anthropic", "openai"),
        ),
        # 키만 있고 패키지가 없거나, 패키지만 있고 키가 없으면 켜지지 않는다
        ({"anthropic_key": True, "openai_package": True}, ()),
        ({"anthropic_key": True, "openai_key": True, "openai_package": True}, ("openai",)),
    ],
)
def test_available_providers_needs_key_and_package(
    monkeypatch: pytest.MonkeyPatch, flags: dict[str, bool], expected: tuple[str, ...]
) -> None:
    set_environment(monkeypatch, **flags)

    assert polish.available_providers() == expected


def test_available_providers_ignores_blank_key(monkeypatch: pytest.MonkeyPatch) -> None:
    set_environment(monkeypatch, anthropic_package=True)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "  ")

    assert polish.available_providers() == ()


def test_choose_provider_prefers_requested_over_config(monkeypatch: pytest.MonkeyPatch) -> None:
    full_environment(monkeypatch)

    assert polish.choose_provider(LlmConfig(provider="anthropic"), "openai") == "openai"


def test_choose_provider_uses_config_when_not_requested(monkeypatch: pytest.MonkeyPatch) -> None:
    full_environment(monkeypatch)

    assert polish.choose_provider(LlmConfig(provider="openai"), None) == "openai"


def test_choose_provider_picks_only_available_one(monkeypatch: pytest.MonkeyPatch) -> None:
    set_environment(monkeypatch, openai_key=True, openai_package=True)

    assert polish.choose_provider(LlmConfig(), None) == "openai"


def test_choose_provider_picks_anthropic_when_both_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    full_environment(monkeypatch)

    assert polish.choose_provider(LlmConfig(), None) == "anthropic"


def test_choose_provider_rejects_unknown_requested_name(monkeypatch: pytest.MonkeyPatch) -> None:
    full_environment(monkeypatch)

    with pytest.raises(InvalidInputError) as error:
        polish.choose_provider(LlmConfig(), "gemini")

    assert str(error.value) == (
        "제공자 이름이 올바르지 않습니다: 'gemini'. anthropic 또는 openai를 쓰세요."
    )


def test_choose_provider_reports_missing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    set_environment(monkeypatch, anthropic_package=True)

    with pytest.raises(InvalidInputError) as error:
        polish.choose_provider(LlmConfig(provider="anthropic"), None)

    assert str(error.value) == (
        "환경변수가 없습니다: ANTHROPIC_API_KEY. Claude 문장 다듬기를 쓰려면 API 키를 설정하세요."
    )


def test_choose_provider_reports_missing_package(monkeypatch: pytest.MonkeyPatch) -> None:
    set_environment(monkeypatch, openai_key=True)

    with pytest.raises(InvalidInputError) as error:
        polish.choose_provider(LlmConfig(), "openai")

    assert str(error.value) == (
        "패키지가 설치되어 있지 않습니다: openai. 'uv sync --extra openai'로 설치하세요."
    )


def test_choose_provider_reports_nothing_available(monkeypatch: pytest.MonkeyPatch) -> None:
    set_environment(monkeypatch)

    with pytest.raises(InvalidInputError) as error:
        polish.choose_provider(LlmConfig(), None)

    assert str(error.value) == NO_PROVIDER_AVAILABLE


def test_model_for_reads_the_provider_model() -> None:
    llm = LlmConfig(anthropic_model="claude-a", openai_model="gpt-b")

    assert polish.model_for(llm, "anthropic") == "claude-a"
    assert polish.model_for(llm, "openai") == "gpt-b"


def test_report_payload_drops_summary_commits_and_author() -> None:
    data = replace(
        three_project_data(),
        summary="요약",
        commits=(
            CommitGroup("payment", "pay-api", (CommitLine("2026-10-12", "a1b2c3d", "제목"),)),
        ),
        notes="배포 일정 조정",
    )

    payload = prompt.report_payload(data)
    parsed = json.loads(payload)

    for key in ("summary", "commits", "author"):
        assert key not in parsed
    assert parsed["week_label"] == "2026-W40"
    assert parsed["notes"] == "배포 일정 조정"
    assert "홍길동" not in payload
    assert "제목" not in payload
    assert "결제 재시도 로직 구현" in payload  # 한글은 이스케이프하지 않는다
    assert list(parsed) == sorted(parsed)  # 키가 정렬되어 있다
    assert "\n" not in payload  # indent 없음


def test_send_scope_with_notes_and_risks() -> None:
    data = replace(three_project_data(), notes="메모")

    assert prompt.send_scope(data) == (
        "2026-W40 보고서 데이터(프로젝트 3개, 태스크 3건, 특이사항·리스크 포함)"
    )


def test_send_scope_with_risks_only() -> None:
    data = replace(three_project_data(), risks="일정 지연 위험")

    assert prompt.send_scope(data).endswith("특이사항·리스크 포함)")


def test_send_scope_without_notes_and_risks() -> None:
    assert prompt.send_scope(three_project_data()) == (
        "2026-W40 보고서 데이터(프로젝트 3개, 태스크 3건, 특이사항·리스크 없음)"
    )


def test_clean_summary_joins_lines_into_one_paragraph() -> None:
    assert prompt.clean_summary("  첫 줄\n\n둘째 줄 \n") == "첫 줄 둘째 줄"


def test_clean_summary_of_blank_text_is_empty() -> None:
    assert prompt.clean_summary(" \n\n ") == ""


class FakeClient:
    """messages.create와 beta.messages.create를 흉내 내는 Anthropic 클라이언트 대역."""

    def __init__(self, text: str) -> None:
        self.calls: list[dict[str, Any]] = []
        response = SimpleNamespace(
            content=[SimpleNamespace(type="text", text=text)], stop_reason="end_turn"
        )

        def create(**kwargs: Any) -> SimpleNamespace:
            self.calls.append(kwargs)
            return response

        self.messages = SimpleNamespace(create=create)
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=create))


def test_polish_report_returns_cleaned_summary_with_model() -> None:
    client = FakeClient("  요약\n")
    data = three_project_data()

    result = polish.polish_report(data, LlmConfig(), "anthropic", client=client)

    assert result == polish.PolishResult("anthropic", "claude-opus-5-5", "요약")
    (call,) = client.calls
    assert call["model"] == "claude-opus-5-5"
    assert call["system"] == prompt.SYSTEM_PROMPT
    assert call["messages"] == [{"role": "user", "content": prompt.report_payload(data)}]


def test_polish_report_uses_configured_model() -> None:
    client = FakeClient("요약")

    result = polish.polish_report(
        three_project_data(),
        LlmConfig(anthropic_model="claude-haiku-5-5"),
        "anthropic",
        client=client,
    )

    assert result.model == "claude-haiku-5-5"
    assert client.calls[0]["model"] == "claude-haiku-5-5"


def test_polish_report_rejects_empty_response() -> None:
    with pytest.raises(ExternalServiceError) as error:
        polish.polish_report(three_project_data(), LlmConfig(), "anthropic", client=FakeClient(" "))

    assert str(error.value) == "Claude 응답에 요약 문장이 없습니다. 다시 시도하세요."
