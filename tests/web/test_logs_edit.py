"""기록 인라인 수정·삭제 테스트 (W40 = 09-28 ~ 10-04, 오늘 = 2026-10-01 목요일 09:30 +09:00)."""

from datetime import date
from html import unescape

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from logbook.core import db, services
from logbook.core.duration import parse_duration
from logbook.core.errors import InvalidInputError, NotFoundError
from logbook.core.taskstatus import TaskStatus
from logbook.core.weeks import parse_week
from logbook.web.errors import RECORD_CHANGED
from logbook.web.pages.views import worklog_version
from tests.helpers import hold_lock
from tests.web.conftest import LockedApp
from tests.web.helpers import (
    add_log,
    add_project,
    add_task,
    by_id,
    named_input,
    parse_html,
    row_ids,
    select_options,
)

W40_THURSDAY = date(2026, 10, 1)
W41_MONDAY = date(2026, 10, 5)
W39_THURSDAY = date(2026, 9, 24)
HTMX = {"HX-Request": "true"}
FILTERS = {"week": "this", "project": "", "category": ""}


def _snapshot(engine: Engine, log_id: int) -> tuple[object, ...]:
    """기록의 저장된 값 전부(변경 여부 비교용)."""
    with db.session_scope(engine) as s:
        log = services.get_worklog(s, log_id)
        return (
            log.minutes,
            log.note,
            log.date,
            log.project.slug,
            log.category,
            log.task_id,
            worklog_version(log),
        )


def _version(engine: Engine, log_id: int) -> str:
    return str(_snapshot(engine, log_id)[-1])


def _exists(engine: Engine, log_id: int) -> bool:
    with db.session_scope(engine) as s:
        return any(log.id == log_id for log in services.list_worklogs(s))


def _form(engine: Engine, log_id: int, **overrides: str) -> dict[str, str]:
    """현재 DB 값 그대로의 편집 폼(+필터). overrides로 바꾼 칸만 다르다."""
    minutes, note, day, slug, category, task_id, version = _snapshot(engine, log_id)
    assert isinstance(minutes, int)
    assert isinstance(day, date)
    form = {
        "duration": f"{minutes}m",
        "note": str(note),
        "log_date": day.isoformat(),
        "log_project": str(slug),
        "log_category": str(category),
        "log_task": "" if task_id is None else str(task_id),
        "version": str(version),
        **FILTERS,
    }
    return {**form, **overrides}


def _patch(client: TestClient, engine: Engine, log_id: int, **overrides: str):  # type: ignore[no-untyped-def]
    return client.patch(f"/logs/{log_id}", data=_form(engine, log_id, **overrides), headers=HTMX)


def _result_text(html: str) -> str:
    return by_id(html, "log-result").text


def _seed_log(engine: Engine, **kwargs: object) -> int:
    defaults: dict[str, object] = {"minutes": 60, "note": "결제 재시도", "day": W40_THURSDAY}
    return add_log(engine, **{**defaults, **kwargs})  # type: ignore[arg-type]


# --- GET 편집 행·표시 행 -------------------------------------------------------------------


def test_edit_row_shows_current_values(client: TestClient, web_engine: Engine) -> None:
    add_project(web_engine, "payment", "결제 서버")
    log_id = _seed_log(web_engine, minutes=90, project="payment", category="meeting")

    response = client.get(f"/logs/{log_id}/edit")

    assert response.status_code == 200
    html = response.text
    assert "<html" not in html
    row = by_id(html, f"log-{log_id}")
    assert row.tag == "tr"
    assert "is-editing" in str(row.attrs["class"]).split()
    assert named_input(html, "duration").attrs["value"] == "1h 30m"
    assert named_input(html, "note").attrs["value"] == "결제 재시도"
    date_input = named_input(html, "log_date")
    assert date_input.attrs["type"] == "date"
    assert date_input.attrs["value"] == "2026-10-01"
    assert named_input(html, "version").attrs["type"] == "hidden"
    assert named_input(html, "version").attrs["value"] == _version(web_engine, log_id)
    projects = select_options(html, "log_project")
    assert [v for v, _, selected in projects if selected] == ["payment"]
    categories = select_options(html, "log_category")
    assert [v for v, _, selected in categories if selected] == ["meeting"]
    tasks = select_options(html, "log_task")
    assert tasks[0] == ("", "없음", True)


def test_edit_row_actions(client: TestClient, web_engine: Engine) -> None:
    log_id = _seed_log(web_engine)

    html = client.get(f"/logs/{log_id}/edit").text

    saves = [e for e in parse_html(html) if e.attrs.get("hx-patch") == f"/logs/{log_id}"]
    assert len(saves) == 1
    save = saves[0]
    assert save.attrs["hx-include"] == "closest tr, #log-filters"
    assert save.attrs["hx-target"] == "#log-table"
    assert save.attrs["hx-swap"] == "outerHTML"
    assert save.attrs["hx-sync"] == "this:drop"
    assert save.attrs["hx-disabled-elt"] == "this"
    cancels = [e for e in parse_html(html) if e.attrs.get("hx-get") == f"/logs/{log_id}/row"]
    assert len(cancels) == 1
    assert cancels[0].attrs["hx-target"] == "closest tr"
    assert cancels[0].attrs["hx-swap"] == "outerHTML"
    assert [e for e in parse_html(html) if e.tag == "form"] == []


def test_edit_row_choices_add_current_values(client: TestClient, web_engine: Engine) -> None:
    add_project(web_engine, "legacy", "옛 프로젝트")
    add_project(web_engine, "payment", "결제 서버")
    task_id = add_task(web_engine, title="완료된 일", project="legacy", category="dev")
    log_id = _seed_log(web_engine, project="legacy", task_id=task_id)
    with db.session_scope(web_engine) as s:
        services.set_task_status(s, task_id, TaskStatus.DONE)
        services.archive_project(s, "legacy")

    html = client.get(f"/logs/{log_id}/edit").text

    projects = {v: label for v, label, _ in select_options(html, "log_project")}
    assert "(보관)" in projects["legacy"]
    assert "payment" in projects
    tasks = select_options(html, "log_task")
    assert [v for v, _, selected in tasks if selected] == [str(task_id)]


def test_edit_row_keeps_unlisted_category(client: TestClient, web_engine: Engine) -> None:
    log_id = _seed_log(web_engine, category="dev")
    with db.session_scope(web_engine) as s:
        services.get_worklog(s, log_id).category = "retired"

    html = client.get(f"/logs/{log_id}/edit").text

    categories = select_options(html, "log_category")
    assert [v for v, _, selected in categories if selected] == ["retired"]


def test_display_row(client: TestClient, web_engine: Engine) -> None:
    log_id = _seed_log(web_engine)

    response = client.get(f"/logs/{log_id}/row")

    assert response.status_code == 200
    html = response.text
    row = by_id(html, f"log-{log_id}")
    assert row.tag == "tr"
    assert "is-editing" not in str(row.attrs.get("class", ""))
    assert "결제 재시도" in html
    assert [e for e in parse_html(html) if e.attrs.get("hx-delete") == f"/logs/{log_id}"]


@pytest.mark.parametrize("suffix", ["row", "edit"])
def test_row_fragments_for_missing_log_are_404(client: TestClient, suffix: str) -> None:
    response = client.get(f"/logs/999/{suffix}")

    assert response.status_code == 404
    assert "#999" in response.text


# --- PATCH 성공 ----------------------------------------------------------------------------


def test_patch_duration_only(client: TestClient, web_engine: Engine) -> None:
    log_id = _seed_log(web_engine, minutes=60)
    before = _snapshot(web_engine, log_id)

    response = _patch(client, web_engine, log_id, duration="90m")

    assert response.status_code == 200
    html = response.text
    assert by_id(html, "log-table").tag == "section"
    assert _result_text(html) == (
        f"✔ 수정했습니다: #{log_id} 2026-10-01 (목) common/dev 1h 30m — 결제 재시도"
    )
    after = _snapshot(web_engine, log_id)
    assert after[0] == 90
    assert after[1:6] == before[1:6]
    assert row_ids(html) == [f"log-{log_id}"]
    assert by_id(html, "week-nav").attrs["hx-swap-oob"] == "true"


def test_patch_unchanged_does_not_update(
    client: TestClient, web_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    log_id = _seed_log(web_engine)
    before = _snapshot(web_engine, log_id)
    calls: list[int] = []
    real = services.update_worklog

    def spy(*args, **kwargs):  # type: ignore[no-untyped-def]
        calls.append(1)
        return real(*args, **kwargs)

    monkeypatch.setattr(services, "update_worklog", spy)

    response = _patch(client, web_engine, log_id, note="  결제 재시도  ")

    assert response.status_code == 200
    assert _result_text(response.text) == "바뀐 내용이 없습니다."
    assert calls == []
    assert _snapshot(web_engine, log_id) == before


def test_patch_note_date_category_project(client: TestClient, web_engine: Engine) -> None:
    add_project(web_engine, "payment", "결제 서버")
    log_id = _seed_log(web_engine)

    response = _patch(
        client,
        web_engine,
        log_id,
        note="새 메모",
        log_category="meeting",
        log_project="payment",
        log_date="2026-09-30",
    )

    assert response.status_code == 200
    _, note, day, slug, category, _, _ = _snapshot(web_engine, log_id)
    assert (note, day, slug, category) == ("새 메모", date(2026, 9, 30), "payment", "meeting")


def test_patch_clears_task(client: TestClient, web_engine: Engine) -> None:
    task_id = add_task(web_engine, title="환불", category="dev")
    log_id = _seed_log(web_engine, task_id=task_id)

    response = _patch(client, web_engine, log_id, log_task="")

    assert response.status_code == 200
    assert _snapshot(web_engine, log_id)[5] is None


def test_patch_changes_task(client: TestClient, web_engine: Engine) -> None:
    first = add_task(web_engine, title="첫째", category="dev")
    second = add_task(web_engine, title="둘째", category="dev")
    log_id = _seed_log(web_engine, task_id=first)

    response = _patch(client, web_engine, log_id, log_task=str(second))

    assert response.status_code == 200
    assert _snapshot(web_engine, log_id)[5] == second


def test_patch_sets_task_when_none(client: TestClient, web_engine: Engine) -> None:
    task_id = add_task(web_engine, title="환불", category="dev")
    log_id = _seed_log(web_engine)

    response = _patch(client, web_engine, log_id, log_task=f"#{task_id}")

    assert response.status_code == 200
    assert _snapshot(web_engine, log_id)[5] == task_id


def test_patch_project_mismatch_with_task_is_400(client: TestClient, web_engine: Engine) -> None:
    add_project(web_engine, "payment", "결제 서버")
    task_id = add_task(web_engine, title="환불", project="payment", category="dev")
    log_id = _seed_log(web_engine, project="payment", task_id=task_id)
    before = _snapshot(web_engine, log_id)

    response = _patch(client, web_engine, log_id, log_project="common")

    assert response.status_code == 400
    assert "다른 프로젝트로 옮길 수 없습니다" in response.text
    assert response.headers["HX-Retarget"] == f"#log-{log_id}"
    assert _snapshot(web_engine, log_id) == before


def test_patch_archived_project_log_note_only(client: TestClient, web_engine: Engine) -> None:
    add_project(web_engine, "legacy", "옛 프로젝트")
    log_id = _seed_log(web_engine, project="legacy")
    with db.session_scope(web_engine) as s:
        services.archive_project(s, "legacy")

    response = _patch(client, web_engine, log_id, note="보관 뒤 수정")

    assert response.status_code == 200
    assert _snapshot(web_engine, log_id)[1] == "보관 뒤 수정"


def test_patch_date_to_next_week_leaves_this_week_table(
    client: TestClient, web_engine: Engine
) -> None:
    log_id = _seed_log(web_engine)
    other = _seed_log(web_engine, note="그대로")

    response = _patch(client, web_engine, log_id, log_date=W41_MONDAY.isoformat())

    assert response.status_code == 200
    assert row_ids(response.text) == [f"log-{other}"]
    assert _snapshot(web_engine, log_id)[2] == W41_MONDAY


def test_patch_with_filter_keeps_filtered_table_and_week_nav(
    client: TestClient, web_engine: Engine
) -> None:
    log_id = _seed_log(web_engine, day=W39_THURSDAY)

    response = _patch(client, web_engine, log_id, duration="2h", week="2026-W39")

    assert response.status_code == 200
    html = response.text
    assert row_ids(html) == [f"log-{log_id}"]
    assert "2026-W39" in by_id(html, "log-table-title").text
    nav = by_id(html, "week-nav")
    assert nav.attrs["hx-swap-oob"] == "true"
    values = [e.attrs["value"] for e in parse_html(html) if e.attrs.get("name") == "week"]
    assert values == ["2026-W39"]


# --- PATCH 오류 ----------------------------------------------------------------------------


def test_patch_bad_duration_returns_edit_row_with_error(
    client: TestClient, web_engine: Engine
) -> None:
    log_id = _seed_log(web_engine)
    before = _snapshot(web_engine, log_id)
    with pytest.raises(InvalidInputError) as caught:
        parse_duration("abc")

    response = _patch(client, web_engine, log_id, duration="abc", note="입력하던 메모")

    assert response.status_code == 400
    assert response.headers["HX-Retarget"] == f"#log-{log_id}"
    assert response.headers["HX-Reswap"] == "outerHTML"
    assert response.headers["HX-Push-Url"] == "false"
    html = response.text
    row = by_id(html, f"log-{log_id}")
    assert "is-editing" in str(row.attrs["class"]).split()
    assert named_input(html, "duration").attrs["value"] == "abc"
    assert named_input(html, "note").attrs["value"] == "입력하던 메모"
    alerts = [e for e in parse_html(html) if e.attrs.get("role") == "alert"]
    assert [e.text for e in alerts] == [str(caught.value)]
    assert alerts[0].attrs["class"] == "row-error"
    assert [e for e in parse_html(html) if e.tag == "tr"] == [row]
    assert _snapshot(web_engine, log_id) == before


def test_patch_with_stale_version_conflicts(client: TestClient, web_engine: Engine) -> None:
    log_id = _seed_log(web_engine, minutes=60)
    stale = _form(web_engine, log_id, duration="120m")
    with db.session_scope(web_engine) as s:
        services.update_worklog(s, log_id, note="다른 곳에서 고침")
    before = _snapshot(web_engine, log_id)

    response = client.patch(f"/logs/{log_id}", data=stale, headers=HTMX)

    assert response.status_code == 409
    assert RECORD_CHANGED.format(id=log_id) in response.text
    assert response.headers["HX-Retarget"] == f"#log-{log_id}"
    assert _snapshot(web_engine, log_id) == before


def test_patch_missing_log_is_404(client: TestClient, web_engine: Engine) -> None:
    form = {**FILTERS, "duration": "1h", "note": "n", "log_date": "2026-10-01", "version": "x"}
    form |= {"log_project": "common", "log_category": "dev", "log_task": ""}

    response = client.patch("/logs/999", data=form, headers=HTMX)

    assert response.status_code == 404
    assert "#999" in response.text
    assert response.headers["HX-Retarget"] == "#flash"


def test_patch_rejects_cross_origin(client: TestClient, web_engine: Engine) -> None:
    log_id = _seed_log(web_engine)
    before = _snapshot(web_engine, log_id)

    response = client.patch(
        f"/logs/{log_id}",
        data=_form(web_engine, log_id, duration="3h"),
        headers={**HTMX, "Origin": "http://evil.example"},
    )

    assert response.status_code == 403
    assert _snapshot(web_engine, log_id) == before


def test_patch_bad_filter_week_is_400_and_leaves_db(client: TestClient, web_engine: Engine) -> None:
    log_id = _seed_log(web_engine)
    before = _snapshot(web_engine, log_id)
    with pytest.raises(InvalidInputError) as caught:
        parse_week("x")

    response = _patch(client, web_engine, log_id, duration="3h", week="x")

    assert response.status_code == 400
    assert str(caught.value) in unescape(response.text)
    assert _snapshot(web_engine, log_id) == before


def test_patch_unknown_filter_project_is_404_and_leaves_db(
    client: TestClient, web_engine: Engine
) -> None:
    log_id = _seed_log(web_engine)
    before = _snapshot(web_engine, log_id)
    with db.session_scope(web_engine) as s, pytest.raises(NotFoundError) as caught:
        services.get_project(s, "nope")

    response = _patch(client, web_engine, log_id, duration="3h", project="nope")

    assert response.status_code == 404
    assert str(caught.value) in unescape(response.text)
    assert _snapshot(web_engine, log_id) == before


def test_patch_bad_task_id_is_400(client: TestClient, web_engine: Engine) -> None:
    log_id = _seed_log(web_engine)
    before = _snapshot(web_engine, log_id)

    response = _patch(client, web_engine, log_id, log_task="abc")

    assert response.status_code == 400
    assert "태스크 ID가 올바르지 않습니다" in response.text
    assert _snapshot(web_engine, log_id) == before


# --- DELETE --------------------------------------------------------------------------------


def _delete(client: TestClient, log_id: int, version: str, **filters: str):  # type: ignore[no-untyped-def]
    params = {"version": version, **FILTERS, **filters}
    return client.delete(f"/logs/{log_id}", params=params, headers=HTMX)


def test_delete_removes_log_and_returns_table(client: TestClient, web_engine: Engine) -> None:
    log_id = _seed_log(web_engine, minutes=120, note="지울 기록")
    keep = _seed_log(web_engine, note="남길 기록")

    response = _delete(client, log_id, _version(web_engine, log_id))

    assert response.status_code == 200
    html = response.text
    assert row_ids(html) == [f"log-{keep}"]
    assert _result_text(html) == (
        f"✔ 삭제했습니다: #{log_id} 2026-10-01 (목) common/dev 2h — 지울 기록"
    )
    assert by_id(html, "week-nav").attrs["hx-swap-oob"] == "true"
    assert not _exists(web_engine, log_id)


def test_delete_with_reused_id_conflicts(client: TestClient, web_engine: Engine) -> None:
    old_id = _seed_log(web_engine, note="처음 기록")
    stale = _version(web_engine, old_id)
    with db.session_scope(web_engine) as s:
        services.delete_worklog(s, old_id)
    new_id = _seed_log(web_engine, note="새 기록")
    assert new_id == old_id  # SQLite는 지운 최대 id를 다시 쓴다.

    response = _delete(client, old_id, stale)

    assert response.status_code == 409
    assert RECORD_CHANGED.format(id=old_id) in response.text
    assert response.headers["HX-Retarget"] == "#flash"
    assert _exists(web_engine, new_id)


def test_delete_without_version_conflicts(client: TestClient, web_engine: Engine) -> None:
    log_id = _seed_log(web_engine)

    response = client.delete(f"/logs/{log_id}", params=FILTERS, headers=HTMX)

    assert response.status_code == 409
    assert _exists(web_engine, log_id)


def test_delete_missing_log_is_404(client: TestClient, web_engine: Engine) -> None:
    response = _delete(client, 999, "x")

    assert response.status_code == 404
    assert "#999" in response.text


def test_delete_rejects_cross_origin(client: TestClient, web_engine: Engine) -> None:
    log_id = _seed_log(web_engine)

    response = client.delete(
        f"/logs/{log_id}",
        params={"version": _version(web_engine, log_id), **FILTERS},
        headers={**HTMX, "Origin": "http://evil.example"},
    )

    assert response.status_code == 403
    assert _exists(web_engine, log_id)


@pytest.mark.parametrize(
    ("filters", "status"),
    [({"week": "x"}, 400), ({"project": "nope"}, 404)],
    ids=["bad-week", "unknown-project"],
)
def test_delete_bad_filter_leaves_db(
    client: TestClient, web_engine: Engine, filters: dict[str, str], status: int
) -> None:
    log_id = _seed_log(web_engine)

    response = _delete(client, log_id, _version(web_engine, log_id), **filters)

    assert response.status_code == status
    assert _exists(web_engine, log_id)


def test_delete_with_filter_keeps_week_nav(client: TestClient, web_engine: Engine) -> None:
    log_id = _seed_log(web_engine, day=W39_THURSDAY)

    response = _delete(client, log_id, _version(web_engine, log_id), week="2026-W39")

    assert response.status_code == 200
    values = [e.attrs["value"] for e in parse_html(response.text) if e.attrs.get("name") == "week"]
    assert values == ["2026-W39"]


# --- 잠금 ----------------------------------------------------------------------------------


@pytest.mark.parametrize("method", ["patch", "delete"])
def test_database_lock_is_503(locked_client: LockedApp, method: str) -> None:
    client, engine, path = locked_client
    log_id = _seed_log(engine)
    before = _snapshot(engine, log_id)
    form = _form(engine, log_id, duration="3h")
    with hold_lock(path, "EXCLUSIVE"):
        if method == "patch":
            response = client.patch(f"/logs/{log_id}", data=form, headers=HTMX)
        else:
            response = client.delete(
                f"/logs/{log_id}",
                params={"version": form["version"], **FILTERS},
                headers=HTMX,
            )
    assert response.status_code == 503
    assert response.headers["HX-Retarget"] == "#flash"
    assert "사용 중" in response.text
    assert _snapshot(engine, log_id) == before
