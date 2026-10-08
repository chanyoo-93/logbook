"""전체 데이터 JSONL 내보내기(export_records) 테스트."""

import json
from datetime import UTC, date, datetime, timedelta, timezone
from types import MappingProxyType
from typing import Any

import pytest
from sqlalchemy.orm import Session

from logbook.core import db, services
from logbook.core.models import ActiveTimer, Base, Project, Task, WorkLog
from logbook.core.services import backup

from .backup_helpers import LS, NEL, NOW, PS, populate

KST = timezone(timedelta(hours=9))

HEADER_LINE = (
    '{"exported_at": "2026-10-08T03:00:00+00:00", "format": 1, '
    f'"schema_version": {db.SCHEMA_VERSION}, "type": "logbook-export"}}'
)


def _rows(lines: list[str]) -> list[dict[str, Any]]:
    return [json.loads(line) for line in lines[1:]]


def test_empty_db_exports_only_common_project(session: Session) -> None:
    services.ensure_common_project(session)
    session.flush()

    lines, counts = services.export_records(session, now=NOW)

    assert lines[0] == HEADER_LINE
    assert len(lines) == 2
    assert json.loads(lines[1])["table"] == "projects"
    assert json.loads(lines[1])["row"]["slug"] == "common"
    assert counts == services.BackupCounts(projects=1, tasks=0, worklogs=0, timers=0)


def test_exports_all_tables_and_fields_including_nulls(session: Session) -> None:
    populate(session)

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
        "status": "done",
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


def test_korean_quotes_and_newlines_in_note_are_json_escaped(session: Session) -> None:
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


def test_lines_follow_table_order_then_id(session: Session) -> None:
    populate(session)
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


def test_timestamps_are_written_in_utc(session: Session) -> None:
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


def test_microseconds_are_preserved(session: Session) -> None:
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


def test_every_line_is_one_line_for_splitlines(session: Session) -> None:
    populate(session)

    lines, _ = services.export_records(session, now=NOW)

    for line in lines:
        assert line.splitlines() == [line]


def test_keys_are_sorted_by_name(session: Session) -> None:
    populate(session)

    lines, _ = services.export_records(session, now=NOW)

    assert lines[0] == HEADER_LINE
    for line in lines[1:]:
        record = json.loads(line)
        assert list(record) == ["row", "table"]
        assert list(record["row"]) == sorted(record["row"])
        assert line.startswith('{"row": {')


def test_line_separators_are_escaped_and_values_preserved(session: Session) -> None:
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


def test_field_tuples_match_model_columns() -> None:
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


def test_separator_escapes_cover_exactly_three_characters() -> None:
    assert backup.SEPARATOR_ESCAPES == {
        0x2028: "\\u2028",
        0x2029: "\\u2029",
        0x85: "\\u0085",
    }


def test_models_mapping_follows_table_order() -> None:
    assert tuple(backup.MODELS) == backup.TABLE_ORDER
    assert backup.MODELS["projects"] is Project
    assert backup.MODELS["tasks"] is Task
    assert backup.MODELS["worklogs"] is WorkLog
    assert backup.MODELS["active_timer"] is ActiveTimer


def test_constant_tables_are_read_only() -> None:
    for table in (backup.FIELDS, backup.SEPARATOR_ESCAPES, backup.MODELS):
        assert isinstance(table, MappingProxyType)


def test_naive_now_is_rejected_as_programming_error(session: Session) -> None:
    services.ensure_common_project(session)
    session.flush()

    with pytest.raises(ValueError, match="timezone-aware"):
        services.export_records(session, now=datetime(2026, 10, 8, 3, 0, 0))


@pytest.mark.parametrize(
    "name", ["export_records", "import_records", "BackupCounts", "FORMAT_VERSION", "TABLE_ORDER"]
)
def test_public_names_are_exported_from_services(name: str) -> None:
    assert name in services.__all__
    assert hasattr(services, name)
