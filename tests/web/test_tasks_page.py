"""태스크 화면 GET /tasks 테스트 (W40 = 09-28 ~ 10-04, 오늘 = 2026-10-01 목요일 09:30 +09:00)."""

import json
import re
from datetime import UTC, date, datetime
from html import unescape

from fastapi.testclient import TestClient
from sqlalchemy import Engine

from logbook.core import db, services
from logbook.core.errors import NotFoundError
from logbook.core.taskstatus import TaskStatus
from logbook.core.weeks import Week, parse_week
from logbook.web.pages.task_views import DROP_CONFIRM, STATUS_LABELS, task_version
from tests.web.helpers import (
    add_log,
    add_project,
    add_task,
    all_by_tag,
    board_columns,
    by_class,
    by_id,
    inline_code_violations,
    parse_html,
    select_options,
)

HTMX = {"HX-Request": "true"}
THIS_WEEK_DONE = datetime(2026, 9, 30, 3, 0, tzinfo=UTC)  # 로컬 09-30 12:00, W40
LAST_WEEK_DONE = datetime(2026, 9, 24, 3, 0, tzinfo=UTC)  # 로컬 09-24 12:00, W39


def _week(text: str) -> Week:
    return parse_week(text, today=date(2026, 10, 1))


def _seed_board(engine: Engine) -> dict[str, int]:
    add_project(engine, "payment", "결제 서버")
    add_project(engine, "old", "보관된 프로젝트")
    ids = {
        "todo_b": add_task(engine, title="주차 없는 할 일"),
        "todo_a": add_task(engine, title="다음 주 할 일", project="payment", week=_week("next")),
        "doing": add_task(engine, title="진행하는 일", status=TaskStatus.DOING),
        "done_now": add_task(
            engine, title="이번 주 끝", status=TaskStatus.DONE, done_at=THIS_WEEK_DONE
        ),
        "done_old": add_task(
            engine, title="지난주 끝", status=TaskStatus.DONE, done_at=LAST_WEEK_DONE
        ),
        "dropped": add_task(engine, title="중단한 일", status=TaskStatus.DROPPED),
        "archived": add_task(engine, title="보관 프로젝트의 일", project="old"),
    }
    with db.session_scope(engine) as s:
        services.archive_project(s, "old")
    return ids


def _card(html: str, task_id: int) -> str:
    """카드 한 장의 텍스트."""
    return by_id(html, f"task-{task_id}").text


def _figures(html: str, task_id: int) -> str:
    """카드의 실적·예상 줄. 카드 id 바로 뒤에 나오는 task-card__figures 요소."""
    elements = parse_html(html)
    start = next(i for i, e in enumerate(elements) if e.attrs.get("id") == f"task-{task_id}")
    for element in elements[start:]:
        if "task-card__figures" in str(element.attrs.get("class") or "").split():
            return element.text
    raise AssertionError("실적 줄이 없습니다")


def test_page_has_menu_columns_and_filter(client: TestClient) -> None:
    response = client.get("/tasks")

    assert response.status_code == 200
    html = response.text
    assert [e.text for e in parse_html(html) if e.tag == "title"] == ["태스크 · logbook"]
    nav = [e for e in parse_html(html) if e.tag == "a" and e.attrs.get("href") == "/tasks"]
    assert [e.attrs.get("aria-current") for e in nav] == ["page"]
    assert [e for e in parse_html(html) if e.attrs.get("id") == "task-form"] == []
    assert by_id(html, "task-filters").tag == "form"
    assert by_id(html, "task-board").tag == "section"
    assert list(board_columns(html)) == ["todo", "doing", "done"]
    headings = [e.text for e in all_by_tag(html, "h3")]
    assert headings == ["할 일", "진행 중", "완료"]
    assert inline_code_violations(html) == []


def test_columns_hold_open_tasks_and_this_weeks_done(
    client: TestClient, web_engine: Engine
) -> None:
    ids = _seed_board(web_engine)

    html = client.get("/tasks").text

    assert board_columns(html) == {
        "todo": [ids["todo_a"], ids["todo_b"]],  # 계획 주차가 있는 것이 먼저
        "doing": [ids["doing"]],
        "done": [ids["done_now"]],
    }
    for hidden in ("done_old", "dropped", "archived"):
        assert f'id="task-{ids[hidden]}"' not in html


def test_card_shows_actual_and_estimate_and_flags_overrun(
    client: TestClient, web_engine: Engine
) -> None:
    over = add_task(web_engine, title="예상 넘김", estimate=240)
    add_log(web_engine, minutes=180, note="가", task_id=over)
    add_log(web_engine, minutes=120, note="나", task_id=over)
    within = add_task(web_engine, title="예상 안", estimate=240)
    add_log(web_engine, minutes=60, note="다", task_id=within)

    html = client.get("/tasks").text

    assert _figures(html, over) == "실적 5h / 예상 4h"
    assert "task-card--over" in str(by_id(html, f"task-{over}").attrs["class"]).split()
    assert [e.text for e in by_class(html, "task-card__over")] == ["예상 초과"]
    assert str(by_class(html, "task-card__over")[0].attrs["class"]).split() == [
        "pill",
        "pill--danger",
        "task-card__over",
    ]
    assert _figures(html, within) == "실적 1h / 예상 4h"
    assert "task-card--over" not in str(by_id(html, f"task-{within}").attrs["class"]).split()


def test_card_without_estimate_shows_actual_only(client: TestClient, web_engine: Engine) -> None:
    plain = add_task(web_engine, title="예상 없음")
    worked = add_task(web_engine, title="실적만")
    add_log(web_engine, minutes=90, note="가", task_id=worked)

    html = client.get("/tasks").text

    assert _figures(html, plain) == "실적 0m"
    assert _figures(html, worked) == "실적 1h 30m"


def test_card_shows_week_and_tag(client: TestClient, web_engine: Engine) -> None:
    this = add_task(web_engine, title="가", week=_week("this"))
    nxt = add_task(web_engine, title="나", week=_week("next"))
    last = add_task(web_engine, title="다", week=_week("last"))
    none = add_task(web_engine, title="라")

    html = client.get("/tasks").text

    assert "2026-W40 이번 주" in _card(html, this)
    assert "2026-W41 다음 주" in _card(html, nxt)
    assert "2026-W39 지난 주" in _card(html, last)
    assert "2026-W" not in _card(html, none)
    assert [e.text for e in by_class(html, "task-card__tag")] == [
        "지난 주",
        "이번 주",
        "다음 주",
    ]  # 계획 주차 순
    for tag in by_class(html, "task-card__tag"):
        assert str(tag.attrs["class"]).split() == ["pill", "task-card__tag"]
    assert not any(week in _card(html, none) for week in ("이번 주", "다음 주", "지난 주"))


def test_card_shows_project_and_category(client: TestClient, web_engine: Engine) -> None:
    add_project(web_engine, "payment", "결제 서버")
    task = add_task(web_engine, title="분류 있음", project="payment", category="design")

    html = client.get("/tasks").text

    assert [e.text for e in by_class(html, "task-card__project")] == ["payment"]
    assert '<svg class="dot" width="8" height="8" viewBox="0 0 8 8" aria-hidden="true">' in html
    assert re.search(r'<circle cx="4" cy="4" r="4" fill="#[0-9a-f]{6}"/></svg>payment', html)
    assert "style=" not in html
    assert [e.text for e in by_class(html, "task-card__category")] == ["design"]
    category = by_class(html, "task-card__category")[0]
    assert str(category.attrs["class"]).split() == [
        "pill",
        "pill--cat-design",
        "task-card__category",
    ]
    assert f"#{task}" in _card(html, task)


def test_filter_shows_one_project_only(client: TestClient, web_engine: Engine) -> None:
    ids = _seed_board(web_engine)

    html = client.get("/tasks?project=payment").text

    assert board_columns(html) == {"todo": [ids["todo_a"]], "doing": [], "done": []}
    projects = select_options(html, "project")
    assert [value for value, _, selected in projects if selected] == ["payment"]


def test_filter_htmx_returns_board_fragment(client: TestClient, web_engine: Engine) -> None:
    ids = _seed_board(web_engine)

    response = client.get("/tasks?project=payment", headers=HTMX)

    assert response.status_code == 200
    html = response.text
    assert "<html" not in html
    assert by_id(html, "task-board").tag == "section"
    assert "hx-swap-oob" not in by_id(html, "task-board").attrs
    assert board_columns(html)["todo"] == [ids["todo_a"]]


def test_history_restore_returns_full_page(client: TestClient) -> None:
    response = client.get("/tasks", headers={**HTMX, "HX-History-Restore-Request": "true"})

    assert "<html" in response.text


def test_filter_form_attributes(client: TestClient) -> None:
    html = client.get("/tasks").text

    form = by_id(html, "task-filters")
    assert form.attrs["hx-get"] == "/tasks"
    assert form.attrs["hx-target"] == "#task-board"
    assert form.attrs["hx-swap"] == "outerHTML"
    assert form.attrs["hx-push-url"] == "true"


def test_unknown_project_full_page_shows_error(client: TestClient, web_engine: Engine) -> None:
    with db.session_scope(web_engine) as s:
        try:
            services.get_project(s, "nope")
        except NotFoundError as error:
            message = str(error)

    response = client.get("/tasks?project=nope")

    assert response.status_code == 404
    html = response.text
    assert "<html" in html
    assert by_id(html, "task-filters").tag == "form"
    alerts = [e.text for e in parse_html(html) if e.attrs.get("role") == "alert"]
    assert alerts == [message]
    assert board_columns(html) == {}


def test_unknown_project_htmx_writes_to_flash(client: TestClient) -> None:
    response = client.get("/tasks?project=nope", headers=HTMX)

    assert response.status_code == 404
    assert response.headers["HX-Retarget"] == "#flash"
    assert response.headers["HX-Push-Url"] == "false"
    assert "nope" in unescape(response.text)
    assert "<html" not in response.text


def test_archived_project_is_selectable_and_shows_its_tasks(
    client: TestClient, web_engine: Engine
) -> None:
    ids = _seed_board(web_engine)

    html = client.get("/tasks?project=old").text

    assert board_columns(html)["todo"] == [ids["archived"]]
    labels = {value: label for value, label, _ in select_options(html, "project")}
    assert labels["old"].endswith("(보관)")


def test_status_buttons_by_state(client: TestClient, web_engine: Engine) -> None:
    add_project(web_engine, "payment", "결제 서버")
    todo = add_task(web_engine, title="할 일", project="payment")
    doing = add_task(web_engine, title="진행", status=TaskStatus.DOING)
    done = add_task(web_engine, title="완료", status=TaskStatus.DONE, done_at=THIS_WEEK_DONE)

    html = client.get("/tasks").text

    def buttons(task_id: int) -> list[tuple[str, str, str | None]]:
        card = f"task-{task_id}"
        elements = parse_html(html)
        start = next(i for i, e in enumerate(elements) if e.attrs.get("id") == card)
        result = []
        for element in elements[start + 1 :]:
            if element.tag == "li":
                break
            if element.tag == "button" and "hx-post" in element.attrs:
                vals = json.loads(str(element.attrs["hx-vals"]))
                result.append((element.text, vals["status"], element.attrs.get("hx-confirm")))
        return result

    drop_confirm = DROP_CONFIRM.format(id=todo, project="payment", title="할 일")
    assert buttons(todo) == [
        ("시작", "doing", None),
        ("완료", "done", None),
        ("중단", "dropped", drop_confirm),
    ]
    assert [b[:2] for b in buttons(doing)] == [
        ("완료", "done"),
        ("할 일로", "todo"),
        ("중단", "dropped"),
    ]
    assert buttons(doing)[2][2] is not None
    assert buttons(done) == [("다시 열기", "doing", None)]


def test_status_button_attributes_and_version(client: TestClient, web_engine: Engine) -> None:
    task_id = add_task(web_engine, title="할 일")
    with db.session_scope(web_engine) as s:
        version = task_version(services.get_task(s, task_id))

    html = client.get("/tasks").text

    button = next(
        e for e in parse_html(html) if e.attrs.get("hx-post") == f"/tasks/{task_id}/status"
    )
    assert json.loads(str(button.attrs["hx-vals"])) == {"status": "doing", "version": version}
    assert button.attrs["hx-include"] == "#task-filters"
    assert button.attrs["hx-target"] == "#task-board"
    assert button.attrs["hx-swap"] == "outerHTML"
    assert button.attrs["hx-sync"] == "this:drop"
    assert button.attrs["hx-disabled-elt"] == "this"


def test_status_labels_are_korean() -> None:
    assert dict(STATUS_LABELS) == {
        TaskStatus.TODO: "할 일",
        TaskStatus.DOING: "진행",
        TaskStatus.DONE: "완료",
        TaskStatus.DROPPED: "중단",
    }


def test_user_text_is_escaped(client: TestClient, web_engine: Engine) -> None:
    add_task(web_engine, title="<b>굵게</b> & '따옴표'")

    html = client.get("/tasks").text

    assert "<b>굵게</b>" not in html
    assert "&lt;b&gt;굵게&lt;/b&gt;" in html
    assert inline_code_violations(html) == []


def test_board_title_can_take_focus(client: TestClient) -> None:
    html = client.get("/tasks").text

    title = by_id(html, "task-board-title")
    assert title.attrs["tabindex"] == "-1"
    assert "data-focus" in title.attrs


def _progress(html: str, task_id: int) -> tuple[list[str], str | None]:
    """카드 안 진행 막대 svg의 class 목록과 채움 막대 width(막대가 없으면 [], None)."""
    elements = parse_html(html)
    start = next(i for i, e in enumerate(elements) if e.attrs.get("id") == f"task-{task_id}")
    svg: list[str] = []
    width: str | None = None
    for element in elements[start + 1 :]:
        if element.tag == "li":
            break
        classes = str(element.attrs.get("class") or "").split()
        if element.tag == "svg" and "progress" in classes:
            svg = classes
        if element.tag == "rect" and "progress__fill" in classes:
            width = str(element.attrs.get("width"))
    return svg, width


def test_card_has_no_progress_bar_without_estimate(client: TestClient, web_engine: Engine) -> None:
    task = add_task(web_engine, title="예상 없음")
    add_log(web_engine, minutes=60, note="가", task_id=task)

    html = client.get("/tasks").text

    assert _progress(html, task) == ([], None)


def test_card_progress_bar_shows_zero_half_and_capped_over(
    client: TestClient, web_engine: Engine
) -> None:
    zero = add_task(web_engine, title="0", estimate=120)
    half = add_task(web_engine, title="절반", estimate=120)
    add_log(web_engine, minutes=60, note="가", task_id=half)
    over = add_task(web_engine, title="초과", estimate=120)
    add_log(web_engine, minutes=300, note="나", task_id=over)

    html = client.get("/tasks").text

    assert _progress(html, zero) == (["progress"], "0")
    assert _progress(html, half) == (["progress"], "50")
    assert _progress(html, over) == (["progress", "progress--over"], "100")


def test_card_progress_bar_is_decorative_svg_without_inline_style(
    client: TestClient, web_engine: Engine
) -> None:
    task = add_task(web_engine, title="막대", estimate=120)

    html = client.get("/tasks").text

    svg = next(e for e in by_class(html, "progress") if e.tag == "svg")
    assert svg.attrs["aria-hidden"] == "true"
    assert svg.attrs["viewbox"] == "0 0 100 4"
    assert "style=" not in html
    assert _progress(html, task)[1] == "0"


def test_progress_percent_handles_zero_estimate_and_caps_at_100() -> None:
    from logbook.web.pages.task_views import progress_percent

    assert progress_percent(0, 0) == 0
    assert progress_percent(10, 0) == 100
    assert progress_percent(30, 120) == 25
    assert progress_percent(999, 120) == 100


def _links(html: str, css_class: str) -> list[tuple[str, str]]:
    return [(str(e.attrs["href"]), e.text) for e in by_class(html, css_class) if e.tag == "a"]


def test_board_has_new_task_link(client: TestClient) -> None:
    html = client.get("/tasks").text

    new = [e for e in parse_html(html) if e.tag == "a" and e.attrs.get("href") == "/tasks/new"]
    assert [e.text for e in new] == ["새 태스크"]
    assert "btn--primary" in str(new[0].attrs["class"]).split()


def test_new_task_link_follows_the_filter(client: TestClient, web_engine: Engine) -> None:
    _seed_board(web_engine)

    html = client.get("/tasks?project=payment", headers=HTMX).text

    hrefs = [str(e.attrs["href"]) for e in parse_html(html) if e.tag == "a"]
    assert "/tasks/new?project=payment" in hrefs


def test_card_is_one_link_to_the_edit_page_without_edit_button(
    client: TestClient, web_engine: Engine
) -> None:
    task_id = add_task(web_engine, title="수정 링크")

    html = client.get("/tasks").text

    [(href, text)] = _links(html, "task-card__link")
    assert href == f"/tasks/{task_id}/edit"
    assert text.startswith(f"#{task_id} 수정 링크")
    assert [e for e in parse_html(html) if e.attrs.get("hx-get") == f"/tasks/{task_id}/edit"] == []
    assert "수정" not in [e.text for e in parse_html(html) if e.tag == "button"]


def test_card_link_carries_the_filter_project(client: TestClient, web_engine: Engine) -> None:
    add_project(web_engine, "payment", "결제 서버")
    task_id = add_task(web_engine, title="결제 건", project="payment")

    html = client.get("/tasks?project=payment").text

    assert [href for href, _ in _links(html, "task-card__link")] == [
        f"/tasks/{task_id}/edit?project=payment"
    ]
