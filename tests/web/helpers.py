"""웹 테스트 도우미: 데이터 준비와 HTML 파서 (fixture가 아닌 함수)."""

import json
from dataclasses import dataclass, field
from datetime import date, datetime
from html.parser import HTMLParser

from sqlalchemy import Engine

from logbook.core import db, services
from logbook.core.taskstatus import TaskStatus
from logbook.core.weeks import Week
from tests.conftest import FIXED_TODAY

# 끝 태그 없이 닫히는 요소
_VOID_TAGS = frozenset({"input", "meta", "link", "br", "img", "hr"})


def add_project(
    engine: Engine,
    slug: str,
    name: str,
    *,
    color: str | None = None,
    archived: bool = False,
) -> None:
    """프로젝트를 만든다. archived면 보관 처리까지 한다."""
    with db.session_scope(engine) as s:
        services.create_project(s, slug, name, color=color)
        if archived:
            services.archive_project(s, slug)


def add_log(
    engine: Engine,
    *,
    minutes: int,
    note: str,
    project: str = "common",
    category: str = "dev",
    day: date = FIXED_TODAY,
    task_id: int | None = None,
) -> int:
    """업무 기록을 추가하고 ID를 돌려준다."""
    with db.session_scope(engine) as s:
        log = services.add_worklog(
            s,
            minutes=minutes,
            note=note,
            project_slug=project,
            category=category,
            work_date=day,
            task_id=task_id,
        )
        s.flush()
        return log.id


def add_task(
    engine: Engine,
    *,
    title: str,
    project: str = "common",
    category: str | None = None,
    week: Week | None = None,
    estimate: int | None = None,
    status: TaskStatus = TaskStatus.TODO,
    done_at: datetime | None = None,
) -> int:
    """태스크를 추가하고 ID를 돌려준다. done_at을 주면 완료 시각을 그 값으로 고정한다."""
    with db.session_scope(engine) as s:
        task = services.create_task(
            s,
            title=title,
            project_slug=project,
            category=category,
            estimate_minutes=estimate,
            planned_week=week,
        )
        if status != TaskStatus.TODO:
            services.set_task_status(s, task.id, status)
        if done_at is not None:
            task.done_at = done_at
        s.flush()
        return task.id


@dataclass
class Element:
    """파싱한 HTML 요소 하나. text는 자손 텍스트를 공백 하나로 이은 값이다."""

    tag: str
    attrs: dict[str, str | None]
    text: str = ""
    _parts: list[str] = field(default_factory=list, repr=False, compare=False)


class _Collector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.elements: list[Element] = []
        self._open: list[Element] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        element = Element(tag, dict(attrs))
        self.elements.append(element)
        if tag not in _VOID_TAGS:
            self._open.append(element)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.elements.append(Element(tag, dict(attrs)))

    def handle_data(self, data: str) -> None:
        for element in self._open:
            element._parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if not any(element.tag == tag for element in self._open):
            return
        while self._open:
            element = self._open.pop()
            _finish(element)
            if element.tag == tag:
                break

    def close(self) -> None:
        super().close()
        while self._open:
            _finish(self._open.pop())


def _finish(element: Element) -> None:
    element.text = " ".join("".join(element._parts).split())


def parse_html(markup: str) -> list[Element]:
    """문서 순서대로 모든 요소를 돌려준다."""
    collector = _Collector()
    collector.feed(markup)
    collector.close()
    return collector.elements


def by_id(markup: str, element_id: str) -> Element:
    """id가 element_id인 요소. 없으면 AssertionError."""
    for element in parse_html(markup):
        if element.attrs.get("id") == element_id:
            return element
    raise AssertionError(f"id가 '{element_id}'인 요소가 없습니다")


def all_by_tag(markup: str, tag: str) -> list[Element]:
    return [element for element in parse_html(markup) if element.tag == tag]


def json_attr(markup: str, element_id: str, name: str) -> object:
    """id가 element_id인 요소의 name 속성 값을 JSON으로 읽는다."""
    value = by_id(markup, element_id).attrs.get(name)
    assert value is not None, f"'{element_id}' 요소에 '{name}' 속성이 없습니다"
    return json.loads(value)


def select_options(markup: str, name: str) -> list[tuple[str, str, bool]]:
    """name 속성이 name인 select의 (value, 표시 글, 선택됨) 목록."""
    result: list[tuple[str, str, bool]] = []
    in_select = False
    for element in parse_html(markup):
        if element.tag == "select":
            in_select = element.attrs.get("name") == name
        elif in_select and element.tag == "option":
            result.append((str(element.attrs["value"]), element.text, "selected" in element.attrs))
    return result


def named_input(markup: str, name: str) -> Element:
    """name 속성이 name인 input·select 요소. 없으면 AssertionError."""
    for element in parse_html(markup):
        if element.tag in {"input", "select"} and element.attrs.get("name") == name:
            return element
    raise AssertionError(f"name이 '{name}'인 입력이 없습니다")


def row_ids(markup: str) -> list[str]:
    """id가 'log-숫자'인 tr 요소의 id 목록(문서 순서)."""
    ids = [str(e.attrs.get("id")) for e in parse_html(markup) if e.tag == "tr"]
    return [i for i in ids if i.startswith("log-")]


def week_links(markup: str) -> list[Element]:
    """주차 이동 링크(href가 /logs?week=로 시작하는 a 요소)."""
    return [
        e
        for e in parse_html(markup)
        if e.tag == "a" and str(e.attrs.get("href", "")).startswith("/logs?week=")
    ]
