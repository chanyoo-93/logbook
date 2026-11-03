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
from logbook.web.pages.settings import CATEGORY_NOTE, FONT_NOTE, INFO_NOTE, SLUG_HINT
from tests.web.conftest import LOCAL_BASE_URL
from tests.web.helpers import (
    Element,
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


def _row(html: str, row_id: str) -> str:
    start = html.index(f'id="{row_id}"')
    return html[start : html.index("</tr>", start)]


def _menu_items(row_html: str) -> list[Element]:
    return [e for e in parse_html(row_html) if e.attrs.get("role") == "menuitem"]


def test_project_rows_put_actions_in_a_context_menu(client: TestClient, web_engine: Engine) -> None:
    add_project(web_engine, "payment", "결제")

    row = _row(client.get("/settings").text, "project-payment")

    buttons = [e for e in parse_html(row) if e.tag == "button"]
    menu_button = buttons[0]
    assert "menu__button" in str(menu_button.attrs.get("class")).split()
    assert menu_button.attrs.get("aria-haspopup") == "menu"
    assert menu_button.attrs.get("aria-label") == "프로젝트 payment 동작"
    assert [e.attrs.get("role") for e in parse_html(row) if e.tag == "div"].count("menu") == 1
    items = _menu_items(row)
    assert [e.text for e in items] == ["수정", "보관"]
    assert items[0].attrs.get("hx-get") == "/settings/projects/payment/edit"
    assert items[1].attrs.get("hx-post") == "/settings/projects/payment/archive"
    assert "menu__item--danger" in str(items[1].attrs.get("class")).split()
    assert not [e for e in buttons if "btn" in str(e.attrs.get("class")).split()]


def test_common_menu_has_a_disabled_archive_item(client: TestClient) -> None:
    row = _row(client.get("/settings").text, "project-common")

    items = _menu_items(row)
    assert [e.text for e in items] == ["수정", "보관"]
    archive = items[1]
    assert "disabled" in archive.attrs
    assert "hx-post" not in archive.attrs
    assert archive.attrs.get("title") == "common 프로젝트는 보관할 수 없습니다"


def test_archived_project_menu_offers_unarchive(client: TestClient, web_engine: Engine) -> None:
    add_project(web_engine, "old", "옛 프로젝트")
    with db.session_scope(web_engine) as s:
        services.archive_project(s, "old")

    items = _menu_items(_row(client.get("/settings").text, "project-old"))

    assert [e.text for e in items] == ["수정", "보관 해제"]
    assert items[1].attrs.get("hx-post") == "/settings/projects/old/unarchive"
    assert "disabled" not in items[1].attrs


def test_project_and_category_table_heads_are_hidden_on_screen(client: TestClient) -> None:
    html = client.get("/settings").text

    heads = [e for e in parse_html(html) if e.tag == "thead"]
    assert len(heads) == 2
    assert all("visually-hidden" in str(e.attrs.get("class")).split() for e in heads)
    assert "동작" in [e.text for e in parse_html(html) if e.tag == "th"]


def test_invalid_color_from_import_is_shown_as_auto(client: TestClient, web_engine: Engine) -> None:
    add_project(web_engine, "legacy", "가져온 것")
    with db.session_scope(web_engine) as s:
        services.get_project(s, "legacy").color = "red"
    add_project(web_engine, "ok", "정상", color="#00ff00")

    html = client.get("/settings").text

    assert "자동" in by_id(html, "project-legacy").text
    assert "red" not in by_id(html, "project-legacy").text
    rects = [e.attrs.get("fill") for e in parse_html(html) if e.tag == "rect"]
    assert "#00ff00" in rects
    assert "red" not in rects


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


def _info_value(html: str, label: str) -> str:
    """설정 정보 정의 목록에서 글이 label인 dt 바로 다음 dd의 글."""
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
        assert _info_value(html, label).startswith("Bookk Gothic")
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


def _info_key(html: str, label: str) -> str:
    """정의 목록에서 글이 label인 dt 다음 dd 안의 설정 키(code.info__key) 글."""
    elements = parse_html(html)
    for index, element in enumerate(elements):
        if element.tag == "dt" and element.text == label:
            for e in elements[index + 1 :]:
                if e.tag == "dt":
                    break
                if e.tag == "code" and "info__key" in str(e.attrs.get("class") or ""):
                    return e.text
            return ""
    raise AssertionError(f"'{label}' 줄이 없습니다")


def test_settings_info_shows_values_in_words(client: TestClient) -> None:
    # 결정 C2: 설정 파일 값(monday, common)을 사람 말로 보이고 설정 키를 덧붙인다.
    html = client.get("/settings").text

    assert _info_value(html, "주 시작 요일").startswith("월요일")
    assert _info_value(html, "기본 프로젝트").startswith("common (공통)")
    assert _info_value(html, "하루 목표").startswith("8h")
    assert _info_key(html, "주 시작 요일") == "week_start"
    assert _info_key(html, "기본 프로젝트") == "default_project"
    assert _info_key(html, "하루 목표") == "daily_target_minutes"
    assert _info_key(html, "DB 파일") == "db_path"
    assert _info_key(html, "설정 파일") == ""
    assert INFO_NOTE in html
    assert INFO_NOTE.startswith("이 값들은 설정 파일에서 바꿉니다.")


def test_settings_info_follows_sunday_and_unknown_default_project(
    watched_client: TestClient, config_file: Path
) -> None:
    config_file.write_text(
        'week_start = "sunday"\ndefault_project = "ghost"\n[web]\nport = 8765\n',
        encoding="utf-8",
    )

    html = watched_client.get("/settings").text

    assert _info_value(html, "주 시작 요일").startswith("일요일")
    assert _info_value(html, "기본 프로젝트").split() == ["ghost", "default_project"]


def test_default_project_named_like_its_slug_shows_slug_once(
    watched_client: TestClient, config_file: Path, web_engine: Engine
) -> None:
    add_project(web_engine, "billing", "billing")
    config_file.write_text('default_project = "billing"\n[web]\nport = 8765\n', encoding="utf-8")

    html = watched_client.get("/settings").text

    assert _info_value(html, "기본 프로젝트").split() == ["billing", "default_project"]


def test_slug_field_has_rule_hint_and_unused_example(client: TestClient) -> None:
    # 결정 C3: 규칙 한 줄 + 이미 있는 payment 대신 쓰이지 않는 예시.
    html = client.get("/settings").text

    slug = by_id(html, "project-slug")
    assert slug.attrs["placeholder"] == "billing"
    assert slug.attrs["aria-describedby"] == "project-slug-hint"
    assert by_id(html, "project-slug-hint").text == SLUG_HINT
    assert SLUG_HINT == (
        "영문 소문자나 숫자로 시작하고 영문 소문자·숫자·-·_만 써서 32자까지. "
        "CLI에서 이 이름으로 씁니다."
    )
    assert by_id(html, "project-name").attrs["placeholder"] == "정산 서버"
