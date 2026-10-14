"""core와 CLI 테스트가 함께 쓰는 도우미 (fixture가 아닌 함수)."""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone, tzinfo
from pathlib import Path
from typing import Literal

from sqlalchemy import Connection, Engine, inspect, select, text
from sqlalchemy.orm import Session

from logbook.core import db
from logbook.core.config import GitConfig
from logbook.core.gitcollect import RepoCommits
from logbook.core.models import Project
from logbook.core.weeks import Week

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


# develop 44ddf9f(스키마 버전 1)에서 `lb init`으로 만든 DB의 sqlite_master DDL (테이블과 인덱스).
# 지금의 스키마에서 파생하지 않고 고정해 두어야 스키마가 바뀌어도 이 DB가 v1로 남는다.
V1_DDL = (
    "CREATE TABLE projects (\n\tid INTEGER NOT NULL, \n\tslug VARCHAR(32) NOT NULL, \n"
    "\tname TEXT NOT NULL, \n\tdescription TEXT, \n\tcolor VARCHAR(7), \n"
    "\tarchived BOOLEAN DEFAULT 0 NOT NULL, \n\tcreated_at DATETIME NOT NULL, \n"
    "\tPRIMARY KEY (id)\n)",
    "CREATE UNIQUE INDEX ix_projects_slug ON projects (slug)",
    "CREATE TABLE schema_version (\n\tversion INTEGER NOT NULL, \n\tPRIMARY KEY (version)\n)",
    "CREATE TABLE tasks (\n\tid INTEGER NOT NULL, \n\tproject_id INTEGER NOT NULL, \n"
    "\ttitle TEXT NOT NULL, \n\tdescription TEXT, \n\tstatus VARCHAR(16) NOT NULL, \n"
    "\tcategory VARCHAR(32), \n\testimate_minutes INTEGER, \n\tplanned_week VARCHAR(8), \n"
    "\tdue_date DATE, \n\texternal_ref TEXT, \n\tcreated_at DATETIME NOT NULL, \n"
    "\tupdated_at DATETIME NOT NULL, \n\tdone_at DATETIME, \n\tPRIMARY KEY (id), \n"
    "\tFOREIGN KEY(project_id) REFERENCES projects (id), \n"
    "\tCONSTRAINT ck_tasks_status CHECK (status IN ('todo', 'doing', 'done', 'dropped'))\n)",
    "CREATE INDEX ix_tasks_planned_week ON tasks (planned_week)",
    "CREATE INDEX ix_tasks_project_id ON tasks (project_id)",
    "CREATE TABLE worklogs (\n\tid INTEGER NOT NULL, \n\tproject_id INTEGER NOT NULL, \n"
    "\ttask_id INTEGER, \n\tcategory VARCHAR(32) NOT NULL, \n\tdate DATE NOT NULL, \n"
    "\tminutes INTEGER NOT NULL, \n\tnote TEXT NOT NULL, \n\tstarted_at DATETIME, \n"
    "\tended_at DATETIME, \n\tcreated_at DATETIME NOT NULL, \n\tPRIMARY KEY (id), \n"
    "\tCONSTRAINT ck_worklogs_minutes_positive CHECK (minutes >= 1), \n"
    "\tFOREIGN KEY(project_id) REFERENCES projects (id), \n"
    "\tFOREIGN KEY(task_id) REFERENCES tasks (id) ON DELETE SET NULL\n)",
    "CREATE INDEX ix_worklogs_project_id ON worklogs (project_id)",
    "CREATE INDEX ix_worklogs_task_id ON worklogs (task_id)",
    "CREATE INDEX ix_worklogs_date ON worklogs (date)",
    "CREATE TABLE active_timer (\n\tid INTEGER NOT NULL, \n\tproject_id INTEGER NOT NULL, \n"
    "\ttask_id INTEGER, \n\tcategory VARCHAR(32) NOT NULL, \n\tnote TEXT NOT NULL, \n"
    "\tstarted_at DATETIME NOT NULL, \n\tPRIMARY KEY (id), \n"
    "\tCONSTRAINT ck_active_timer_single_row CHECK (id = 1), \n"
    "\tFOREIGN KEY(project_id) REFERENCES projects (id), \n"
    "\tFOREIGN KEY(task_id) REFERENCES tasks (id) ON DELETE SET NULL\n)",
)


def make_v1_database(path: Path) -> None:
    """스키마 버전 1인 DB를 만든다(고정한 V1_DDL과 schema_version 행 1). 엔진은 닫는다."""
    engine = db.create_engine_for(path)
    try:
        with engine.begin() as conn:
            for statement in V1_DDL:
                conn.exec_driver_sql(statement)
            conn.execute(text("INSERT INTO schema_version (version) VALUES (1)"))
    finally:
        engine.dispose()


class FakeCollect:
    """gitcollect.collect_commits 대역: 정해 둔 결과를 돌려주고 받은 인자를 기록한다."""

    def __init__(self, results: tuple[RepoCommits, ...]) -> None:
        self.results = results
        self.calls: list[tuple[GitConfig, Week, tzinfo]] = []

    def __call__(
        self, git: GitConfig, week: Week, *, tz: tzinfo, run: object = None
    ) -> tuple[RepoCommits, ...]:
        self.calls.append((git, week, tz))
        return self.results
