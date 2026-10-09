"""core와 CLI 테스트가 함께 쓰는 도우미 (fixture가 아닌 함수)."""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

from sqlalchemy import Connection, Engine, inspect, select, text
from sqlalchemy.orm import Session

from logbook.core import db
from logbook.core.models import Project

SUBPROCESS_TIMEOUT_SECONDS = 60

# CLI·웹 테스트의 '지금'. 목요일, today fixture(2026-10-01)와 같은 날, 고정 오프셋 UTC+9.
FIXED_NOW = datetime(2026, 10, 1, 9, 30, tzinfo=timezone(timedelta(hours=9)))


class Clock:
    """runtime.now()가 돌려줄 시각. advance()로 옮긴다."""

    def __init__(self, now: datetime = FIXED_NOW) -> None:
        self.now = now

    def advance(self, **delta: float) -> datetime:
        """timedelta 인자만큼 시각을 옮기고 새 시각을 돌려준다 (예: advance(minutes=85))."""
        self.now += timedelta(**delta)
        return self.now


@contextmanager
def hold_lock(db_path: Path, mode: Literal["IMMEDIATE", "EXCLUSIVE"]) -> Iterator[None]:
    """다른 프로세스처럼 별도 연결로 DB 잠금을 잡고 있는 동안 본문을 실행한다.

    IMMEDIATE는 쓰기만, EXCLUSIVE는 읽기까지 막는다 (롤백 저널 모드 기준).
    잠금을 잡지 못하면 그 잠금 오류를 그대로 던진다.
    """
    conn = sqlite3.connect(db_path, timeout=0, isolation_level=None)
    try:
        conn.execute(f"BEGIN {mode}")
        try:
            yield
        finally:
            conn.execute("ROLLBACK")
    finally:
        conn.close()


def add_extra_column(conn: Connection) -> None:
    """테스트용 마이그레이션: projects에 extra 열을 추가한다."""
    conn.exec_driver_sql("ALTER TABLE projects ADD COLUMN extra TEXT")


def column_names(engine: Engine, table: str) -> set[str]:
    return {column["name"] for column in inspect(engine).get_columns(table)}


def project_slugs(engine: Engine) -> list[str]:
    with Session(engine) as session:
        return list(session.scalars(select(Project.slug).order_by(Project.slug)))


def add_project(engine: Engine, slug: str = "payment") -> None:
    with db.session_scope(engine) as session:
        session.add(Project(slug=slug, name="결제 시스템"))


def set_version(engine: Engine, version: int) -> None:
    with engine.begin() as conn:
        conn.execute(text("UPDATE schema_version SET version = :v"), {"v": version})
