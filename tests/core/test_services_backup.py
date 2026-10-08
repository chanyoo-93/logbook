"""전체 데이터 JSONL 내보내기(export_records) 테스트."""

import json
from datetime import UTC, date, datetime, timedelta, timezone
from typing import Any

import pytest
from sqlalchemy.orm import Session

from logbook.core import db, services
from logbook.core.models import ActiveTimer, Base, Project, Task, WorkLog
from logbook.core.services import backup
from logbook.core.taskstatus import TaskStatus

NOW = datetime(2026, 10, 8, 3, 0, 0, tzinfo=UTC)
KST = timezone(timedelta(hours=9))
LS = chr(0x2028)
PS = chr(0x2029)
NEL = chr(0x85)

HEADER_LINE = (
    '{"exported_at": "2026-10-08T03:00:00+00:00", "format": 1, '
    f'"schema_version": {db.SCHEMA_VERSION}, "type": "logbook-export"}}'
)


def _rows(lines: list[str]) -> list[dict[str, Any]]:
    return [json.loads(line) for line in lines[1:]]


def _populate(s: Session) -> None:
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
        status=TaskStatus.DOING,
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


def test_빈_DB는_common_프로젝트만_내보낸다(session: Session) -> None:
    services.ensure_common_project(session)
    session.flush()

    lines, counts = services.export_records(session, now=NOW)

    assert lines[0] == HEADER_LINE
    assert len(lines) == 2
    assert json.loads(lines[1])["table"] == "projects"
    assert json.loads(lines[1])["row"]["slug"] == "common"
    assert counts == services.BackupCounts(projects=1, tasks=0, worklogs=0, timers=0)


def test_모든_테이블과_필드를_null까지_내보낸다(session: Session) -> None:
    _populate(session)

    lines, counts = services.export_records(session, now=NOW)

    assert counts == services.BackupCounts(projects=2, tasks=2, worklogs=2, timers=1)
    rows = _rows(lines)
    by_table: dict[str, list[dict[str, Any]]] = {}
    for record in rows:
        by_table.setdefault(record["table"], []).append(record["row"])
    for table, fields in backup.FIELDS.items():
        for row in by_table[table]:
            assert tuple(sorted(row)) == tuple(sorted(fields))
    pay = next(r for r in by_table["projects"] if r["slug"] == "pay")
    assert pay == {
        "id": 5,
        "slug": "pay",
        "name": "결제",
        "description": "설명",
        "color": "#112233",
        "archived": True,
        "created_at": "2026-09-01T00:00:00+00:00",
    }
    assert by_table["tasks"][0] == {
        "id": by_table["tasks"][0]["id"],
        "project_id": 5,
        "title": "전체 필드",
        "description": "설명",
        "status": "doing",
        "category": "dev",
        "estimate_minutes": 90,
        "planned_week": "2026-W41",
        "due_date": "2026-10-09",
        "external_ref": "JIRA-1",
        "created_at": "2026-09-02T01:00:00+00:00",
        "updated_at": "2026-09-03T01:00:00+00:00",
        "done_at": "2026-09-04T01:00:00+00:00",
    }
    sparse = by_table["tasks"][1]
    assert sparse["status"] == "todo"
    assert sparse["description"] is None
    assert sparse["estimate_minutes"] is None
    assert sparse["due_date"] is None
    assert sparse["done_at"] is None
    assert by_table["worklogs"][1]["task_id"] is None
    assert by_table["worklogs"][1]["started_at"] is None
    assert by_table["worklogs"][1]["note"] == ""
    timer = by_table["active_timer"][0]
    assert timer == {
        "id": 1,
        "project_id": 5,
        "task_id": None,
        "category": "dev",
        "note": "타이머",
        "started_at": "2026-10-08T03:00:00+00:00",
    }


def test_한글_따옴표_줄바꿈_메모는_JSON으로_이스케이프된다(session: Session) -> None:
    common = services.ensure_common_project(session)
    note = '한글 "따옴표"\n둘째 줄\t탭\\'
    session.add(
        WorkLog(
            project_id=common.id,
            category="dev",
            date=date(2026, 10, 7),
            minutes=10,
            note=note,
            created_at=NOW,
        )
    )
    session.flush()

    lines, _ = services.export_records(session, now=NOW)

    worklog_line = lines[-1]
    assert "한글" in worklog_line
    assert "\n" not in worklog_line
    assert json.loads(worklog_line)["row"]["note"] == note


def test_줄_순서는_테이블_순서와_id_순이다(session: Session) -> None:
    _populate(session)
    other = Project(id=2, slug="aaa", name="앞", created_at=NOW)
    session.add(other)
    session.flush()

    lines, _ = services.export_records(session, now=NOW)

    records = [json.loads(line) for line in lines[1:]]
    tables = [r["table"] for r in records]
    assert tables == sorted(tables, key=backup.TABLE_ORDER.index)
    for table in backup.TABLE_ORDER:
        ids = [r["row"]["id"] for r in records if r["table"] == table]
        assert ids == sorted(ids)
    assert [r["row"]["id"] for r in records if r["table"] == "projects"] == [1, 2, 5]


def test_시각은_UTC로_표기된다(session: Session) -> None:
    common = services.ensure_common_project(session)
    session.add(
        WorkLog(
            project_id=common.id,
            category="dev",
            date=date(2026, 10, 8),
            minutes=10,
            note="x",
            started_at=datetime(2026, 10, 8, 12, 0, 0, tzinfo=KST),
            created_at=NOW,
        )
    )
    session.flush()

    lines, _ = services.export_records(session, now=datetime(2026, 10, 8, 12, 0, 0, tzinfo=KST))

    assert json.loads(lines[0])["exported_at"] == "2026-10-08T03:00:00+00:00"
    assert json.loads(lines[-1])["row"]["started_at"] == "2026-10-08T03:00:00+00:00"


def test_마이크로초가_보존된다(session: Session) -> None:
    common = services.ensure_common_project(session)
    stamp = datetime(2026, 10, 8, 3, 0, 0, 123456, tzinfo=UTC)
    session.add(
        WorkLog(
            project_id=common.id,
            category="dev",
            date=date(2026, 10, 8),
            minutes=10,
            note="x",
            started_at=stamp,
            created_at=stamp,
        )
    )
    session.flush()

    lines, _ = services.export_records(session, now=stamp)

    assert json.loads(lines[0])["exported_at"] == "2026-10-08T03:00:00.123456+00:00"
    row = json.loads(lines[-1])["row"]
    assert row["started_at"] == "2026-10-08T03:00:00.123456+00:00"
    assert row["created_at"] == "2026-10-08T03:00:00.123456+00:00"


def test_모든_줄은_splitlines로_한_줄이다(session: Session) -> None:
    _populate(session)

    lines, _ = services.export_records(session, now=NOW)

    for line in lines:
        assert line.splitlines() == [line]


def test_키는_이름순으로_정렬된다(session: Session) -> None:
    _populate(session)

    lines, _ = services.export_records(session, now=NOW)

    assert lines[0] == HEADER_LINE
    for line in lines[1:]:
        record = json.loads(line)
        assert list(record) == ["row", "table"]
        assert list(record["row"]) == sorted(record["row"])
        assert line.startswith('{"row": {')


def test_줄_구분_문자는_이스케이프되고_값은_보존된다(session: Session) -> None:
    common = services.ensure_common_project(session)
    mixed = f"앞{LS}가운데{PS}가운데{NEL}뒤"
    task = Task(
        project_id=common.id,
        title=mixed + "T",
        description=mixed + "D",
        created_at=NOW,
        updated_at=NOW,
    )
    session.add(task)
    session.flush()
    session.add(
        WorkLog(
            project_id=common.id,
            task_id=task.id,
            category="dev",
            date=date(2026, 10, 8),
            minutes=10,
            note=mixed + "N",
            created_at=NOW,
        )
    )
    session.add(ActiveTimer(project_id=common.id, category="dev", note=mixed + "M", started_at=NOW))
    session.flush()

    lines, _ = services.export_records(session, now=NOW)

    for line in lines:
        assert line.splitlines() == [line]
        for ch in (LS, PS, NEL):
            assert ch not in line
    rows = {r["table"]: r["row"] for r in _rows(lines)}
    assert rows["tasks"]["title"] == mixed + "T"
    assert rows["tasks"]["description"] == mixed + "D"
    assert rows["worklogs"]["note"] == mixed + "N"
    assert rows["active_timer"]["note"] == mixed + "M"
    joined = "".join(lines)
    assert "\\u2028" in joined
    assert "\\u2029" in joined
    assert "\\u0085" in joined


def test_필드_목록은_모델_컬럼과_같다() -> None:
    models = {
        "projects": Project,
        "tasks": Task,
        "worklogs": WorkLog,
        "active_timer": ActiveTimer,
    }
    for table, model in models.items():
        assert set(backup.FIELDS[table]) == set(model.__table__.columns.keys()), table
        assert list(backup.FIELDS[table]) == list(model.__table__.columns.keys()), table
    assert set(backup.TABLE_ORDER) == set(Base.metadata.tables) - {"schema_version"}
    assert set(backup.FIELDS) == set(backup.TABLE_ORDER)
    assert backup.FORMAT_VERSION == 1


def test_구분자_이스케이프_표는_세_문자만_바꾼다() -> None:
    assert backup.SEPARATOR_ESCAPES == {
        0x2028: "\\u2028",
        0x2029: "\\u2029",
        0x85: "\\u0085",
    }


@pytest.mark.parametrize(
    "name", ["export_records", "BackupCounts", "FORMAT_VERSION", "TABLE_ORDER"]
)
def test_공개_이름이_services에서_보인다(name: str) -> None:
    assert name in services.__all__
    assert hasattr(services, name)
