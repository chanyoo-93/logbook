"""설정 화면 프로젝트 변경 테스트: 추가, 편집 행, 수정(PATCH), 보관·해제 (버전 확인 포함)."""

from dataclasses import replace
from html import unescape

from fastapi.testclient import TestClient
from sqlalchemy import Engine

from logbook.core import db, services
from logbook.web.errors import PROJECT_CHANGED
from logbook.web.pages.panels import NO_CHANGE
from logbook.web.pages.settings import (
    ARCHIVE_CONFIRM,
    DEFAULT_ARCHIVED,
    PROJECT_ADDED,
    PROJECT_ARCHIVED,
    PROJECT_UNARCHIVED,
    PROJECT_UPDATED,
    project_version,
)
from tests.web.helpers import (
    add_project,
    all_by_tag,
    by_id,
    inline_code_violations,
    named_input,
    parse_html,
)

HTMX = {"HX-Request": "true"}


def _version(engine: Engine, slug: str) -> str:
    with db.session_scope(engine) as s:
        return project_version(services.get_project(s, slug))


def _stored(engine: Engine, slug: str) -> tuple[str, str | None, str | None, bool]:
    with db.session_scope(engine) as s:
        p = services.get_project(s, slug)
        return p.name, p.color, p.description, p.archived


def _add(client: TestClient, **fields: str):  # type: ignore[no-untyped-def]
    form = {"slug": "", "name": "", "color": ""}
    return client.post("/settings/projects", data={**form, **fields}, headers=HTMX)


def _patch(client: TestClient, engine: Engine, slug: str, **fields: str):  # type: ignore[no-untyped-def]
    form = {
        "name": "",
        "color": "",
        "description": "",
        "version": _version(engine, slug),
    }
    return client.patch(f"/settings/projects/{slug}", data={**form, **fields}, headers=HTMX)


def _flash_text(html: str) -> str:
    """#flash OOB 조각이면 그 안의 문구, 알림 조각(<p class="flash">)이면 그 문구."""
    flash = [e for e in parse_html(html) if e.tag == "p" and "flash" in str(e.attrs.get("class"))]
    return unescape(flash[0].text)


def _result(html: str) -> str:
    return unescape(by_id(html, "project-result").text)


def test_add_project_shows_new_row_and_clears_form(client: TestClient, web_engine: Engine) -> None:
    response = _add(client, slug="payment", name="결제", color="#4f46e5")

    assert response.status_code == 200
    html = response.text
    assert "<html" not in html
    assert by_id(html, "project-section").tag == "section"
    assert _result(html) == PROJECT_ADDED.format(slug="payment", name="결제")
    assert by_id(html, "project-payment").tag == "tr"
    assert named_input(html, "slug").attrs.get("value", "") == ""
    assert named_input(html, "name").attrs.get("value", "") == ""
    assert _stored(web_engine, "payment") == ("결제", "#4f46e5", None, False)
    assert inline_code_violations(html) == []


def test_add_form_uses_htmx_attributes(client: TestClient) -> None:
    html = client.get("/settings").text

    form = by_id(html, "project-add-form")
    assert form.attrs["hx-post"] == "/settings/projects"
    assert form.attrs["hx-target"] == "#project-section"
    assert form.attrs["hx-swap"] == "outerHTML"
    assert form.attrs["hx-sync"] == "this:drop"
    assert form.attrs["hx-disabled-elt"]
    assert "data-focus" in by_id(html, "project-section-title").attrs


def test_add_without_color_stores_none(client: TestClient, web_engine: Engine) -> None:
    response = _add(client, slug="infra", name="인프라")

    assert response.status_code == 200
    assert _stored(web_engine, "infra") == ("인프라", None, None, False)


def test_add_errors_keep_input(client: TestClient, web_engine: Engine) -> None:
    add_project(web_engine, "payment", "결제")
    cases = [
        ({"slug": "payment", "name": "또 결제", "color": ""}, "이미 존재하는 프로젝트입니다"),
        ({"slug": "Bad Slug", "name": "이름", "color": ""}, "프로젝트 slug가 올바르지 않습니다"),
        ({"slug": "ok", "name": "이름", "color": "red"}, "색상이 올바르지 않습니다"),
        ({"slug": "ok", "name": "  ", "color": ""}, "프로젝트 이름이 비어 있습니다"),
    ]
    for fields, expected in cases:
        response = _add(client, **fields)

        assert response.status_code == 400, fields
        html = response.text
        assert expected in _result(html)
        assert by_id(html, "project-result").attrs["role"] == "alert"
        assert named_input(html, "slug").attrs.get("value") == fields["slug"]
        assert named_input(html, "color").attrs.get("value", "") == fields["color"]
    with db.session_scope(web_engine) as s:
        assert [p.slug for p in services.list_projects(s)] == ["common", "payment"]


def test_edit_row_shows_current_values(client: TestClient, web_engine: Engine) -> None:
    add_project(web_engine, "payment", "결제", color="#4f46e5")
    with db.session_scope(web_engine) as s:
        services.update_project(s, "payment", description="결제 서버")

    response = client.get("/settings/projects/payment/edit", headers=HTMX)

    assert response.status_code == 200
    html = response.text
    row = by_id(html, "project-payment")
    assert row.tag == "tr"
    assert "is-editing" in str(row.attrs["class"]).split()
    name = named_input(html, "name")
    assert name.attrs["value"] == "결제"
    assert "data-focus" in name.attrs
    assert named_input(html, "color").attrs["value"] == "#4f46e5"
    description = by_id(html, "project-payment-description")
    assert description.attrs.get("value") == "결제 서버"
    assert named_input(html, "version").attrs["value"] == _version(web_engine, "payment")
    buttons = {e.text: e.attrs for e in parse_html(html) if e.tag == "button"}
    assert buttons["저장"]["hx-patch"] == "/settings/projects/payment"
    assert buttons["저장"]["hx-target"] == "#project-section"
    assert buttons["저장"]["hx-swap"] == "outerHTML"
    assert buttons["저장"]["hx-sync"] == "this:drop"
    assert buttons["취소"]["hx-get"] == "/settings/projects/payment/row"
    assert buttons["취소"]["hx-target"] == "closest tr"
    assert inline_code_violations(html) == []


def test_cancel_returns_view_row(client: TestClient, web_engine: Engine) -> None:
    add_project(web_engine, "payment", "결제")

    response = client.get("/settings/projects/payment/row", headers=HTMX)

    assert response.status_code == 200
    row = by_id(response.text, "project-payment")
    assert "is-editing" not in str(row.attrs.get("class") or "").split()
    assert "결제" in response.text


def test_edit_of_unknown_project_is_404_flash(client: TestClient) -> None:
    response = client.get("/settings/projects/nope/edit", headers=HTMX)

    assert response.status_code == 404
    assert response.headers["HX-Retarget"] == "#flash"


def test_patch_changes_name_color_and_description(client: TestClient, web_engine: Engine) -> None:
    add_project(web_engine, "payment", "결제")

    response = _patch(
        client, web_engine, "payment", name=" 새 결제 ", color="#112233", description=" 설명 "
    )

    assert response.status_code == 200
    html = response.text
    assert _result(html) == PROJECT_UPDATED.format(slug="payment", name="새 결제")
    assert by_id(html, "project-section").tag == "section"
    assert _stored(web_engine, "payment") == ("새 결제", "#112233", "설명", False)


def test_patch_blank_color_and_description_become_none(
    client: TestClient, web_engine: Engine
) -> None:
    add_project(web_engine, "payment", "결제", color="#112233")
    with db.session_scope(web_engine) as s:
        services.update_project(s, "payment", description="설명")

    response = _patch(client, web_engine, "payment", name="결제", color=" ", description="  ")

    assert response.status_code == 200
    assert _stored(web_engine, "payment") == ("결제", None, None, False)


def test_patch_without_changes_says_so(client: TestClient, web_engine: Engine) -> None:
    add_project(web_engine, "payment", "결제", color="#112233")

    response = _patch(client, web_engine, "payment", name="결제", color="#112233")

    assert response.status_code == 200
    assert _result(response.text) == NO_CHANGE


def test_patch_with_other_version_is_409(client: TestClient, web_engine: Engine) -> None:
    add_project(web_engine, "payment", "결제")

    response = _patch(client, web_engine, "payment", name="입력한 이름", version="stale")

    assert response.status_code == 409
    assert response.headers["HX-Retarget"] == "#project-payment"
    assert response.headers["HX-Reswap"] == "outerHTML"
    assert response.headers["HX-Push-Url"] == "false"
    html = response.text
    assert _flash_text(html) == PROJECT_CHANGED.format(slug="payment")
    assert by_id(html, "flash").attrs["hx-swap-oob"] == "innerHTML"
    assert named_input(html, "name").attrs["value"] == "입력한 이름"
    assert _stored(web_engine, "payment")[0] == "결제"


def test_patch_invalid_color_redraws_edit_row_with_values(
    client: TestClient, web_engine: Engine
) -> None:
    add_project(web_engine, "payment", "결제")

    response = _patch(client, web_engine, "payment", name="입력한 이름", color="#12")

    assert response.status_code == 400
    assert response.headers["HX-Retarget"] == "#project-payment"
    html = response.text
    assert "색상이 올바르지 않습니다" in _flash_text(html)
    assert named_input(html, "name").attrs["value"] == "입력한 이름"
    assert named_input(html, "color").attrs["value"] == "#12"
    assert _stored(web_engine, "payment") == ("결제", None, None, False)


def test_archive_button_and_result(client: TestClient, web_engine: Engine) -> None:
    add_project(web_engine, "payment", "결제")
    html = client.get("/settings").text
    button = next(
        e
        for e in parse_html(html)
        if e.tag == "button" and e.attrs.get("hx-post") == "/settings/projects/payment/archive"
    )
    assert button.attrs["hx-confirm"] == ARCHIVE_CONFIRM.format(slug="payment", name="결제")
    assert button.attrs["hx-target"] == "#project-section"
    assert button.attrs["hx-sync"] == "this:drop"

    response = client.post(
        "/settings/projects/payment/archive",
        data={"version": _version(web_engine, "payment")},
        headers=HTMX,
    )

    assert response.status_code == 200
    assert _result(response.text) == PROJECT_ARCHIVED.format(slug="payment")
    assert _stored(web_engine, "payment")[3] is True


def test_archive_default_project_adds_warning(client: TestClient, web_engine: Engine) -> None:
    add_project(web_engine, "common2", "다른 것")
    # 기본 프로젝트는 common이라 보관할 수 없으므로, 설정이 가리키는 프로젝트를 바꿔 시험한다.
    ctx = client.app.state.ctx  # type: ignore[attr-defined]
    client.app.state.ctx = replace(  # type: ignore[attr-defined]
        ctx, cfg=replace(ctx.cfg, default_project="common2")
    )

    response = client.post(
        "/settings/projects/common2/archive",
        data={"version": _version(web_engine, "common2")},
        headers=HTMX,
    )

    assert response.status_code == 200
    assert _result(response.text) == PROJECT_ARCHIVED.format(slug="common2") + DEFAULT_ARCHIVED


def test_archive_common_is_rejected(client: TestClient, web_engine: Engine) -> None:
    response = client.post(
        "/settings/projects/common/archive",
        data={"version": _version(web_engine, "common")},
        headers=HTMX,
    )

    assert response.status_code == 400
    assert "common 프로젝트는 보관할 수 없습니다" in _flash_text(response.text)
    assert _stored(web_engine, "common")[3] is False


def test_unarchive_restores_project(client: TestClient, web_engine: Engine) -> None:
    add_project(web_engine, "old", "옛것", archived=True)

    response = client.post(
        "/settings/projects/old/unarchive",
        data={"version": _version(web_engine, "old")},
        headers=HTMX,
    )

    assert response.status_code == 200
    assert _result(response.text) == PROJECT_UNARCHIVED.format(slug="old")
    assert _stored(web_engine, "old")[3] is False
    assert [e for e in all_by_tag(response.text, "tr") if e.attrs.get("id") == "project-old"]


def test_archive_and_unarchive_with_other_version_are_409(
    client: TestClient, web_engine: Engine
) -> None:
    add_project(web_engine, "payment", "결제")
    add_project(web_engine, "old", "옛것", archived=True)

    archive = client.post(
        "/settings/projects/payment/archive", data={"version": "stale"}, headers=HTMX
    )
    unarchive = client.post(
        "/settings/projects/old/unarchive", data={"version": "stale"}, headers=HTMX
    )

    for response, slug in ((archive, "payment"), (unarchive, "old")):
        assert response.status_code == 409
        assert response.headers["HX-Retarget"] == "#flash"
        assert PROJECT_CHANGED.format(slug=slug) in _flash_text(response.text)
    assert _stored(web_engine, "payment")[3] is False
    assert _stored(web_engine, "old")[3] is True


def test_cross_origin_writes_are_forbidden(client: TestClient, web_engine: Engine) -> None:
    add_project(web_engine, "payment", "결제")
    evil = {"Origin": "http://evil.example"}
    version = {"version": _version(web_engine, "payment")}

    responses = [
        client.post("/settings/projects", data={"slug": "x", "name": "x"}, headers=evil),
        client.patch("/settings/projects/payment", data={**version, "name": "x"}, headers=evil),
        client.post("/settings/projects/payment/archive", data=version, headers=evil),
        client.post("/settings/projects/payment/unarchive", data=version, headers=evil),
    ]

    assert [r.status_code for r in responses] == [403, 403, 403, 403]
    assert _stored(web_engine, "payment") == ("결제", None, None, False)
