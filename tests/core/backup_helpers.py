"""가져오기·내보내기 테스트가 함께 쓰는 데이터와 줄 만들기 도우미."""

import json
from datetime import UTC, date, datetime
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from logbook.core import db, services
from logbook.core.errors import InvalidInputError
from logbook.core.models import ActiveTimer, Project, Task, WorkLog
from logbook.core.taskstatus import TaskStatus

NOW = datetime(2026, 10, 8, 3, 0, 0, tzinfo=UTC)
STAMP = "2026-09-01T00:00:00+00:00"
LS = chr(0x2028)
PS = chr(0x2029)
NEL = chr(0x85)
BOM = chr(0xFEFF)

INT_EXPECT = "1 이상 9223372036854775807 이하의 정수"
OPT_INT_EXPECT = "null 또는 " + INT_EXPECT
SLUG_EXPECT = "영문 소문자나 숫자로 시작하고 영문 소문자·숫자·'-'·'_'만 쓴 32자 이하 문자열"
STATUS_EXPECT = "todo, doing, done, dropped 중 하나"
DATE_EXPECT = "YYYY-MM-DD 형식의 날짜"
TIME_EXPECT = "시간대가 있는 ISO 8601 시각"
ENVELOPE_MESSAGE = (
    '레코드 형식이 올바르지 않습니다. {"row": {...}, "table": "..."} 형식이어야 합니다.'
)
NON_EMPTY_MESSAGE = (
    "데이터가 있는 데이터베이스에는 가져올 수 없습니다. 새 데이터베이스에서 실행하세요 "
    "(예: LOGBOOK_DB를 새 경로로 바꾸고 'lb init' 후 'lb import')."
)
NO_COMMON_MESSAGE = "가져올 파일에 common 프로젝트가 없습니다."

DEFAULT_ROWS: dict[str, dict[str, Any]] = {
    "projects": {
        "id": 1,
        "slug": "common",
        "name": "공통",
        "description": None,
        "color": None,
        "archived": False,
        "created_at": STAMP,
    },
    "tasks": {
        "id": 1,
        "project_id": 2,
        "title": "작업",
        "description": None,
        "status": "todo",
        "category": None,
        "estimate_minutes": None,
        "planned_week": None,
        "due_date": None,
        "external_ref": None,
        "created_at": STAMP,
        "updated_at": STAMP,
        "done_at": None,
    },
    "worklogs": {
        "id": 1,
        "project_id": 2,
        "task_id": 1,
        "category": "dev",
        "date": "2026-10-07",
        "minutes": 30,
        "note": "메모",
        "started_at": None,
        "ended_at": None,
        "created_at": STAMP,
    },
    "active_timer": {
        "id": 1,
        "project_id": 2,
        "task_id": 1,
        "category": "dev",
        "note": "타이머",
        "started_at": STAMP,
    },
}


def dumps(obj: object) -> str:
    return json.dumps(obj, ensure_ascii=False)


def header(**changes: Any) -> str:
    header: dict[str, Any] = {
        "type": "logbook-export",
        "format": 1,
        "schema_version": db.SCHEMA_VERSION,
        "exported_at": "2026-10-08T03:00:00+00:00",
    }
    header.update(changes)
    return dumps({key: value for key, value in header.items() if value != "<missing>"})


HEADER = header()


def line(table: str, **changes: Any) -> str:
    row = {**DEFAULT_ROWS[table], **changes}
    return dumps({"table": table, "row": row})


COMMON = line("projects")
PAY = line("projects", id=2, slug="pay", name="결제")
TASK = line("tasks")
WORKLOG = line("worklogs")
TIMER = line("active_timer")

# 테이블 줄 앞에 와야 하는 정상 줄(머리글 포함)
PREFIX = {
    "projects": [HEADER],
    "tasks": [HEADER, COMMON, PAY],
    "worklogs": [HEADER, COMMON, PAY, TASK],
    "active_timer": [HEADER, COMMON, PAY, TASK, WORKLOG],
}


def valid() -> list[str]:
    return [HEADER, COMMON, PAY, TASK, WORKLOG, TIMER]


def assert_unchanged(session: Session) -> None:
    slugs = [p.slug for p in session.scalars(select(Project))]
    assert slugs == ["common"]
    for model in (Task, WorkLog, ActiveTimer):
        assert session.scalar(select(func.count()).select_from(model)) == 0


def rejects(fresh: Session, lines: list[str], message: str) -> None:
    with pytest.raises(InvalidInputError) as excinfo:
        services.import_records(fresh, lines)
    assert str(excinfo.value) == message
    assert_unchanged(fresh)


def populate(s: Session) -> None:
    """모든 테이블에 행을 넣는다. null 필드가 있는 행도 포함한다."""
    common = services.ensure_common_project(s)
    pay = Project(
        id=5,
        slug="pay",
        name="결제",
        description="설명",
        color="#112233",
        archived=True,
        created_at=datetime(2026, 9, 1, 0, 0, 0, tzinfo=UTC),
    )
    s.add(pay)
    s.flush()
    full = Task(
        project_id=pay.id,
        title="전체 필드",
        description="설명",
        status=TaskStatus.DONE,
        category="dev",
        estimate_minutes=90,
        planned_week="2026-W41",
        due_date=date(2026, 10, 9),
        external_ref="JIRA-1",
        created_at=datetime(2026, 9, 2, 1, 0, 0, tzinfo=UTC),
        updated_at=datetime(2026, 9, 3, 1, 0, 0, tzinfo=UTC),
        done_at=datetime(2026, 9, 4, 1, 0, 0, tzinfo=UTC),
    )
    sparse = Task(
        project_id=common.id,
        title="빈 필드",
        status=TaskStatus.TODO,
        created_at=NOW,
        updated_at=NOW,
    )
    s.add_all([full, sparse])
    s.flush()
    s.add_all(
        [
            WorkLog(
                project_id=pay.id,
                task_id=full.id,
                category="dev",
                date=date(2026, 10, 7),
                minutes=90,
                note="메모",
                started_at=datetime(2026, 10, 7, 1, 0, 0, tzinfo=UTC),
                ended_at=datetime(2026, 10, 7, 2, 30, 0, tzinfo=UTC),
                created_at=NOW,
            ),
            WorkLog(
                project_id=common.id,
                task_id=None,
                category="meeting",
                date=date(2026, 10, 6),
                minutes=30,
                note="",
                created_at=NOW,
            ),
        ]
    )
    s.add(
        ActiveTimer(
            project_id=pay.id,
            task_id=None,
            category="dev",
            note="타이머",
            started_at=NOW,
        )
    )
    s.flush()


def add_exotic_rows(s: Session) -> None:
    """populate 뒤에 마이크로초와 줄 구분 문자가 든 행을 더한다(왕복 테스트용)."""
    pay = s.scalars(select(Project).where(Project.slug == "pay")).one()
    mixed = f"앞{LS}가운데{PS}가운데{NEL}뒤 한글"
    micro = datetime(2026, 10, 8, 3, 0, 0, 123456, tzinfo=UTC)
    task = Task(
        project_id=pay.id,
        title=mixed,
        description=mixed,
        status=TaskStatus.DONE,
        created_at=micro,
        updated_at=micro,
        done_at=micro,
    )
    s.add(task)
    s.flush()
    s.add(
        WorkLog(
            project_id=pay.id,
            task_id=task.id,
            category="dev",
            date=date(2026, 10, 7),
            minutes=90,
            note=mixed,
            started_at=micro,
            ended_at=micro,
            created_at=micro,
        )
    )
    timer = s.scalars(select(ActiveTimer)).one()
    timer.note = mixed
    timer.started_at = micro
    s.flush()
