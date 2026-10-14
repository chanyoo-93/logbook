"""lb report --polish (실제 SDK는 부르지 않고 polish_report를 대역으로 바꾼다)."""

import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from typer.testing import Result

from logbook.cli import render
from logbook.core import polish
from logbook.core.config import LlmConfig
from logbook.core.errors import ExternalServiceError
from logbook.core.polish import PolishResult
from logbook.core.report import ReportData
from tests.cli.helpers import Clipboard, assert_rejected, run_ok
from tests.cli.test_report import expected_report

SUMMARY = "이번 주에는 결제 재시도를 구현했습니다."
SUMMARY_HEADING = "## 요약 (자동 생성)"
CONFIRM_QUESTION = (
    "보낼 내용: 2026-W40 보고서 데이터(프로젝트 2개, 태스크 0건, 특이사항·리스크 없음). "
    "커밋 내역과 작성자는 보내지 않습니다.\n"
    "Claude(claude-opus-5-5)로 보낼까요? [y/N]: "
)
REQUESTING = f"{render.info_mark()} Claude에 요약을 요청하는 중입니다…\n"
PROVIDER_OPTION_WITHOUT_POLISH = "--provider 옵션은 --polish와 함께 쓰세요."
CANCELLED = "문장 다듬기를 취소했습니다. 보고서를 만들지 않았습니다.\n"
NO_INPUT = "확인 입력이 없습니다. 보내려면 --yes를 붙이세요.\n"


class FakePolish:
    """polish_report 대역: 받은 인자를 기록하고 결과를 돌려주거나 오류를 낸다."""

    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[tuple[ReportData, LlmConfig, str]] = []

    def __call__(
        self, data: ReportData, llm: LlmConfig, provider: str, *, client: Any = None
    ) -> PolishResult:
        self.calls.append((data, llm, provider))
        if self.error is not None:
            raise self.error
        return PolishResult(provider, polish.model_for(llm, provider), SUMMARY)


@pytest.fixture
def fake_polish(monkeypatch: pytest.MonkeyPatch) -> FakePolish:
    fake = FakePolish()
    monkeypatch.setattr(polish, "polish_report", fake)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(polish, "_has_package", lambda provider: True)
    return fake


def test_polish_adds_summary_section(
    lb: Callable[..., Result], seeded: Path, fake_polish: FakePolish
) -> None:
    result = run_ok(lb, "report", "--polish", "--yes")

    assert result.stderr == REQUESTING
    assert f"{SUMMARY_HEADING}\n{SUMMARY}\n" in result.stdout
    assert len(fake_polish.calls) == 1
    assert fake_polish.calls[0][2] == "anthropic"


def test_polish_confirmation_yes(
    lb: Callable[..., Result], seeded: Path, fake_polish: FakePolish
) -> None:
    result = lb("report", "--polish", input="y\n")

    assert result.exit_code == 0
    assert result.stderr == CONFIRM_QUESTION + REQUESTING
    assert SUMMARY in result.stdout
    assert len(fake_polish.calls) == 1


def test_polish_confirmation_no(
    lb: Callable[..., Result], seeded: Path, fake_polish: FakePolish
) -> None:
    result = lb("report", "--polish", input="n\n")

    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr == CONFIRM_QUESTION + CANCELLED
    assert fake_polish.calls == []


def test_polish_confirmation_without_input(
    lb: Callable[..., Result], seeded: Path, fake_polish: FakePolish
) -> None:
    result = lb("report", "--polish")

    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr.endswith(NO_INPUT)
    assert fake_polish.calls == []


def test_polish_confirmation_shows_configured_model(
    lb: Callable[..., Result], seeded: Path, fake_polish: FakePolish
) -> None:
    config = Path(os.environ["LOGBOOK_CONFIG"])
    config.write_text(
        config.read_text(encoding="utf-8").replace(
            'anthropic_model = "claude-opus-5-5"', 'anthropic_model = "claude-test-1"'
        ),
        encoding="utf-8",
    )

    result = lb("report", "--polish", input="n\n")

    assert "Claude(claude-test-1)로 보낼까요?" in result.stderr


def test_polish_provider_openai(
    lb: Callable[..., Result], seeded: Path, fake_polish: FakePolish
) -> None:
    result = run_ok(lb, "report", "--polish", "--provider", "openai", "--yes")

    assert fake_polish.calls[0][2] == "openai"
    assert result.stderr == f"{render.info_mark()} ChatGPT에 요약을 요청하는 중입니다…\n"


def test_polish_without_provider_available(
    lb: Callable[..., Result],
    seeded: Path,
    fake_polish: FakePolish,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    monkeypatch.delenv("OPENAI_API_KEY")

    result = lb("report", "--polish", "--yes")

    assert_rejected(result, polish.NO_PROVIDER)
    assert fake_polish.calls == []


def test_polish_service_error_makes_no_report(
    lb: Callable[..., Result],
    seeded: Path,
    fake_polish: FakePolish,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    fake_polish.error = ExternalServiceError("Claude 요청이 실패했습니다.")

    result = lb("report", "--polish", "--yes", "-o", "out.md")

    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr == REQUESTING + "오류: Claude 요청이 실패했습니다.\n"
    assert not (tmp_path / "out.md").exists()


def test_polish_service_error_prints_no_report_to_stdout(
    lb: Callable[..., Result], seeded: Path, fake_polish: FakePolish
) -> None:
    fake_polish.error = ExternalServiceError("Claude 요청이 실패했습니다.")

    result = lb("report", "--polish", "--yes")

    assert result.exit_code == 1
    assert result.stdout == ""


def test_polish_overwrite_is_asked_before_request(
    lb: Callable[..., Result],
    seeded: Path,
    fake_polish: FakePolish,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "out.md").write_text("old", encoding="utf-8")

    result = lb("report", "--polish", "-o", "out.md", input="y\nn\n")

    assert result.exit_code == 1
    assert result.stderr.endswith("덮어쓸까요? [y/N]: 덮어쓰지 않았습니다.\n")
    assert REQUESTING not in result.stderr
    assert fake_polish.calls == []
    assert (tmp_path / "out.md").read_text(encoding="utf-8") == "old"


def test_polish_overwrite_confirmed_writes_once(
    lb: Callable[..., Result],
    seeded: Path,
    fake_polish: FakePolish,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "out.md").write_text("old", encoding="utf-8")

    result = lb("report", "--polish", "-o", "out.md", input="y\ny\n")

    assert result.exit_code == 0
    assert result.stderr.count("덮어쓸까요?") == 1
    assert SUMMARY in (tmp_path / "out.md").read_text(encoding="utf-8")


def test_polish_copy_includes_summary(
    lb: Callable[..., Result], seeded: Path, fake_polish: FakePolish, clipboard: Clipboard
) -> None:
    result = run_ok(lb, "report", "--polish", "--copy", "--yes")

    assert result.stdout == f"{render.ok_mark()[0]} 보고서를 클립보드에 복사했습니다.\n"
    assert len(clipboard.copied) == 1
    assert f"{SUMMARY_HEADING}\n{SUMMARY}" in clipboard.copied[0]


def test_provider_without_polish_is_rejected(
    lb: Callable[..., Result], seeded: Path, fake_polish: FakePolish
) -> None:
    result = lb("report", "--provider", "openai")

    assert_rejected(result, PROVIDER_OPTION_WITHOUT_POLISH)
    assert fake_polish.calls == []


def test_unknown_provider_is_rejected(
    lb: Callable[..., Result], seeded: Path, fake_polish: FakePolish
) -> None:
    result = lb("report", "--polish", "--provider", "x", "--yes")

    assert_rejected(result, polish.UNKNOWN_PROVIDER.format(echo="x"))
    assert fake_polish.calls == []


def test_report_without_polish_has_no_summary(
    lb: Callable[..., Result], seeded: Path, fake_polish: FakePolish
) -> None:
    result = run_ok(lb, "report")

    assert result.stdout == expected_report()
    assert SUMMARY_HEADING not in result.stdout
    assert fake_polish.calls == []
