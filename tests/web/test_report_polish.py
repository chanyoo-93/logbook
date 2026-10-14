"""보고서 문장 다듬기 화면과 POST /report/polish (실제 SDK는 부르지 않는다)."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import logbook.web
from logbook.core import polish
from logbook.core.config import LlmConfig
from logbook.core.errors import ExternalServiceError
from logbook.core.polish import PolishResult
from logbook.core.report import ReportData
from logbook.web.pages.report import POLISH_CONFIRM
from tests.web.helpers import all_by_tag, by_class, by_id, inline_code_violations, parse_html

HTMX = {"HX-Request": "true"}
SUMMARY = "이번 주에는 결제 재시도 로직을 구현했습니다."
STATIC_ROOT = Path(logbook.web.__file__).parent / "static"
COLOR_LITERAL = ("#", "rgb(", "rgba(", "hsl(", "oklch(")


class FakePolish:
    def __init__(self) -> None:
        self.calls: list[tuple[ReportData, str]] = []
        self.error: Exception | None = None

    def __call__(self, data: ReportData, llm: LlmConfig, provider: str) -> PolishResult:
        self.calls.append((data, provider))
        if self.error is not None:
            raise self.error
        return PolishResult(provider, polish.model_for(llm, provider), SUMMARY)


@pytest.fixture
def fake_polish(monkeypatch: pytest.MonkeyPatch) -> FakePolish:
    fake = FakePolish()
    monkeypatch.setattr("logbook.web.pages.report_polish.polish_report", fake)
    return fake


def _providers(monkeypatch: pytest.MonkeyPatch, *names: str) -> None:
    monkeypatch.setattr("logbook.core.polish.available_providers", lambda: names)
    monkeypatch.setattr(polish, "_has_key", lambda provider: True)
    monkeypatch.setattr(polish, "_has_package", lambda provider: True)


def _buttons(html: str) -> list[str]:
    form = by_class(html, "report__polish-form")
    assert len(form) == 1
    return [e.text for e in all_by_tag(html, "button") if e.attrs.get("name") == "provider"]


def test_no_providers_hides_polish_area(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("logbook.core.polish.available_providers", lambda: ())

    html = client.get("/report").text

    assert "report__polish-form" not in html
    assert "report-polish" not in html
    assert "polish-progress" not in html


def test_one_provider_shows_one_button(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _providers(monkeypatch, "anthropic")

    html = client.get("/report").text

    assert _buttons(html) == ["문장 다듬기 (Claude)"]
    assert "hidden" in by_id(html, "report-polish").attrs
    assert by_id(html, "polish-progress").attrs["role"] == "status"
    assert inline_code_violations(html) == []


def test_both_providers_show_claude_then_chatgpt(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _providers(monkeypatch, "anthropic", "openai")

    html = client.get("/report").text

    assert _buttons(html) == ["문장 다듬기 (Claude)", "문장 다듬기 (ChatGPT)"]


def test_confirm_text_names_week_and_scope(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _providers(monkeypatch, "anthropic")

    html = client.get("/report", params={"week": "2026-W40"}).text

    form = by_class(html, "report__polish-form")[0]
    assert form.attrs["hx-confirm"] == POLISH_CONFIRM.format(week="2026-W40")
    assert "커밋 내역과 작성자는 보내지 않습니다" in form.attrs["hx-confirm"]
    assert form.attrs["hx-post"] == "/report/polish"


def test_post_returns_panel_with_provider_model_and_summary(
    client: TestClient, fake_polish: FakePolish, monkeypatch: pytest.MonkeyPatch
) -> None:
    _providers(monkeypatch, "anthropic", "openai")

    response = client.post(
        "/report/polish", data={"week": "2026-W40", "provider": "openai"}, headers=HTMX
    )

    html = response.text
    assert response.status_code == 200
    assert "ChatGPT gpt-6.1-sol" in by_id(html, "report-polish-heading").text
    assert by_id(html, "report-polish-text").text == SUMMARY
    assert any(
        e.attrs.get("data-copy-done") == "요약을 클립보드에 복사했습니다."
        for e in all_by_tag(html, "button")
    )
    assert fake_polish.calls[0][1] == "openai"
    assert fake_polish.calls[0][0].commits == ()
    assert inline_code_violations(html) == []


def test_post_without_provider_uses_default_choice(
    client: TestClient, fake_polish: FakePolish, monkeypatch: pytest.MonkeyPatch
) -> None:
    _providers(monkeypatch, "anthropic")

    response = client.post("/report/polish", data={"week": "2026-W40"}, headers=HTMX)

    assert response.status_code == 200
    assert fake_polish.calls[0][1] == "anthropic"


def test_post_blank_week_means_this_week(
    client: TestClient, fake_polish: FakePolish, monkeypatch: pytest.MonkeyPatch
) -> None:
    _providers(monkeypatch, "anthropic")

    response = client.post("/report/polish", data={"provider": "anthropic"}, headers=HTMX)

    assert response.status_code == 200
    assert fake_polish.calls[0][0].week_label.startswith("2026-W40")


@pytest.mark.parametrize(
    "form",
    [{"week": "2026-W99", "provider": "anthropic"}, {"week": "2026-W40", "provider": "gemini"}],
)
def test_post_invalid_week_or_provider_is_400(
    client: TestClient,
    fake_polish: FakePolish,
    monkeypatch: pytest.MonkeyPatch,
    form: dict[str, str],
) -> None:
    _providers(monkeypatch, "anthropic")

    response = client.post("/report/polish", data=form, headers=HTMX)

    assert response.status_code == 400
    assert response.headers["hx-retarget"] == "#flash"
    assert fake_polish.calls == []


def test_post_external_failure_is_502_alert(
    client: TestClient, fake_polish: FakePolish, monkeypatch: pytest.MonkeyPatch
) -> None:
    _providers(monkeypatch, "anthropic")
    fake_polish.error = ExternalServiceError("요청이 실패했습니다: Claude.")

    response = client.post(
        "/report/polish", data={"week": "2026-W40", "provider": "anthropic"}, headers=HTMX
    )

    assert response.status_code == 502
    assert "요청이 실패했습니다: Claude." in response.text
    assert response.headers["hx-retarget"] == "#flash"


def test_post_cross_origin_is_rejected(client: TestClient, fake_polish: FakePolish) -> None:
    response = client.post(
        "/report/polish",
        data={"week": "2026-W40", "provider": "anthropic"},
        headers={**HTMX, "Sec-Fetch-Site": "cross-site"},
    )

    assert response.status_code == 403
    assert fake_polish.calls == []


def test_js_supports_data_copy_done() -> None:
    js = (STATIC_ROOT / "js" / "report.js").read_text(encoding="utf-8")

    assert 'getAttribute("data-copy-done")' in js


def test_css_has_polish_rules_without_color_literals() -> None:
    css = (STATIC_ROOT / "css" / "report.css").read_text(encoding="utf-8")

    assert ".report-polish {" in css
    assert ".report-polish__text {" in css
    assert not any(literal in css for literal in COLOR_LITERAL)


def test_parse_html_helper_sees_panel_section(
    client: TestClient, fake_polish: FakePolish, monkeypatch: pytest.MonkeyPatch
) -> None:
    _providers(monkeypatch, "anthropic")

    html = client.post(
        "/report/polish", data={"week": "2026-W40", "provider": "anthropic"}, headers=HTMX
    ).text

    assert [e.tag for e in parse_html(html) if e.attrs.get("id") == "report-polish"] == ["section"]
