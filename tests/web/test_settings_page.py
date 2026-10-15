"""설정 화면 GET /settings 테스트: 프로젝트 표, 설정 정보, 설정 자동 반영."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from logbook.core import db, services
from logbook.core.config import load_config
from logbook.web.app import create_app
from logbook.web.config_watch import ConfigWatcher
from logbook.web.context import WebContext
from logbook.web.pages.settings import CATEGORY_NOTE, FONT_NOTE
from tests.web.conftest import LOCAL_BASE_URL
from tests.web.helpers import (
    add_project,
    all_by_tag,
    by_class,
    by_id,
    inline_code_violations,
    parse_html,
)


def _row_ids(html: str) -> list[str]:
    ids = [str(e.attrs.get("id")) for e in all_by_tag(html, "tr")]
    return [i for i in ids if i.startswith("project-")]


def test_settings_page_lists_projects_and_info(
    client: TestClient, web_engine: Engine, web_ctx: WebContext
) -> None:
    add_project(web_engine, "payment", "결제", color="#4f46e5")
    add_project(web_engine, "old", "옛 프로젝트", archived=True)

    response = client.get("/settings")

    html = response.text
    assert response.status_code == 200
    current = [
        e for e in parse_html(html) if e.tag == "a" and e.attrs.get("aria-current") == "page"
    ]
    assert [e.attrs.get("href") for e in current] == ["/settings"]
    assert _row_ids(html) == ["project-common", "project-old", "project-payment"]
    assert by_id(html, "project-section").tag == "section"
    assert by_id(html, "project-payment").text.startswith("payment 결제")
    assert "#4f46e5" in by_id(html, "project-payment").text
    assert "보관" in by_id(html, "project-old").text
    assert '<span class="pill">보관</span>' in html
    assert '<span class="pill pill--ok">사용 중</span>' in html
    assert by_id(html, "category-dev").text.startswith("dev 개발")
    assert str(web_ctx.config_file) in html
    assert str(web_ctx.engine.url.database) in html
    assert CATEGORY_NOTE in html
    assert by_class(html, "table-wrap")
    assert inline_code_violations(html) == []


def test_common_row_has_no_archive_button(client: TestClient, web_engine: Engine) -> None:
    add_project(web_engine, "payment", "결제")

    html = client.get("/settings").text

    archive_urls = [
        str(e.attrs["hx-post"])
        for e in parse_html(html)
        if e.tag == "button" and "hx-post" in e.attrs and "/archive" in str(e.attrs["hx-post"])
    ]
    assert "/settings/projects/payment/archive" in archive_urls
    assert "/settings/projects/common/archive" not in archive_urls


def test_invalid_color_from_import_has_no_swatch(client: TestClient, web_engine: Engine) -> None:
    add_project(web_engine, "legacy", "가져온 것")
    with db.session_scope(web_engine) as s:
        services.get_project(s, "legacy").color = "red"
    add_project(web_engine, "ok", "정상", color="#00ff00")

    html = client.get("/settings").text

    assert "red" in by_id(html, "project-legacy").text
    swatches = [e for e in by_class(html, "swatch") if e.tag == "svg"]
    rects = [e.attrs.get("fill") for e in parse_html(html) if e.tag == "rect"]
    assert len(swatches) == 1
    assert rects == ["#00ff00"]


@pytest.fixture
def config_file(web_ctx: WebContext) -> Path:
    path = web_ctx.config_file
    path.write_text("[web]\nport = 8765\n", encoding="utf-8")
    return path


@pytest.fixture
def watched_client(web_ctx: WebContext, config_file: Path) -> Iterator[TestClient]:
    watcher = ConfigWatcher(config_file, load_config(config_file))
    with TestClient(create_app(web_ctx, watcher=watcher), base_url=LOCAL_BASE_URL) as c:
        yield c


def test_added_category_shows_after_reload(watched_client: TestClient, config_file: Path) -> None:
    config_file.write_text(
        '[web]\nport = 8765\n[categories]\ndev = "개발"\nops = "운영"\n', encoding="utf-8"
    )

    html = watched_client.get("/settings").text

    assert "ops" in html
    assert "운영" in html


def test_changed_db_path_shows_running_db_and_restart_notice(
    watched_client: TestClient,
    config_file: Path,
    web_ctx: WebContext,
    tmp_home: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("LOGBOOK_DB")  # 환경변수가 설정 파일 값보다 우선하므로 지운다
    other = tmp_home / "other.db"
    config_file.write_text(
        f'db_path = "{other.as_posix()}"\n[web]\nport = 8765\n', encoding="utf-8"
    )

    html = watched_client.get("/settings").text

    assert str(web_ctx.engine.url.database) in html
    assert "other.db" not in html
    notices = [
        e for e in all_by_tag(html, "p") if "config-notice" in str(e.attrs.get("class") or "")
    ]
    assert len(notices) == 1
    assert "db_path" in notices[0].text


def _font_row_value(html: str, label: str) -> str:
    """정의 목록에서 글이 label인 dt 바로 다음 dd의 글."""
    elements = parse_html(html)
    for index, element in enumerate(elements):
        if element.tag == "dt" and element.text == label:
            following = next(e for e in elements[index + 1 :] if e.tag in {"dt", "dd"})
            assert following.tag == "dd"
            return following.text.strip()
    raise AssertionError(f"'{label}' 줄이 없습니다")


def test_settings_info_shows_font_rows_with_previews(client: TestClient) -> None:
    html = client.get("/settings").text

    assert "제목 글꼴" in html
    assert "문서 글꼴" in html
    assert "본문 글꼴" in html
    assert "Bookk Gothic" in html
    assert "Bookk Myungjo" not in html
    for label in ("제목 글꼴", "문서 글꼴", "본문 글꼴"):
        assert _font_row_value(html, label).startswith("Bookk Gothic")
    assert FONT_NOTE in html
    for cls in ("font-preview--heading", "font-preview--document", "font-preview--body"):
        assert len(by_class(html, cls)) == 1
    body_row = by_class(html, "font-preview--body")[0]
    assert body_row.text == "가나다 ABC 123 · 8h 55m"


def test_settings_info_shows_default_font_label_for_empty_body_font(client: TestClient) -> None:
    html = client.get("/settings").text

    assert "기본 글꼴" in html


def test_settings_font_rows_follow_config(watched_client: TestClient, config_file: Path) -> None:
    config_file.write_text(
        '[web]\nport = 8765\nheading_font = "나눔고딕"\nbody_font = "Batang"\n',
        encoding="utf-8",
    )

    html = watched_client.get("/settings").text

    assert "나눔고딕" in html
    assert "Batang" in html
