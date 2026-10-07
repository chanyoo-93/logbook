"""tests/helpers.py 도우미 자체의 동작 테스트."""

import sqlite3
from pathlib import Path

import pytest

from tests.helpers import hold_lock


def make_sqlite_file(path: Path) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.execute("CREATE TABLE t (x INTEGER)")
        conn.commit()
    finally:
        conn.close()


def test_hold_lock_reports_lock_conflict_and_closes_connection(tmp_path: Path) -> None:
    path = tmp_path / "logbook.db"
    make_sqlite_file(path)

    # 잠금을 잡지 못하면 ROLLBACK 오류가 아니라 원래의 잠금 오류가 보여야 한다.
    with (
        hold_lock(path, "EXCLUSIVE"),
        pytest.raises(sqlite3.OperationalError, match="database is locked") as excinfo,
        hold_lock(path, "EXCLUSIVE"),
    ):
        pass

    assert excinfo.value.__context__ is None
    # 두 연결이 모두 닫혀야 Windows에서 파일을 지울 수 있다.
    path.unlink()
