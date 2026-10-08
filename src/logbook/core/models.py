"""SQLAlchemy 모델: projects, tasks, worklogs, active_timer, schema_version.

관계는 다대일(자식 → 부모)만 둔다. 부모 삭제 시의 처리(거부, task_id NULL)는
ORM이 아니라 DB 외래 키 규칙이 맡는다.
"""

import datetime as dt
import enum

from sqlalchemy import CheckConstraint, DateTime, Dialect, ForeignKey, String, Text, false
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

from logbook.core.taskstatus import TaskStatus as TaskStatus  # 기존 import 경로 유지(재노출)


def utcnow() -> dt.datetime:
    """현재 시각 (timezone-aware UTC)."""
    return dt.datetime.now(dt.UTC)


class UTCDateTime(TypeDecorator[dt.datetime]):
    """aware datetime을 UTC 기준 naive 값으로 저장하고, 읽을 때 UTC tzinfo를 붙인다."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: dt.datetime | None, dialect: Dialect) -> dt.datetime | None:
        if value is None:
            return None
        if value.utcoffset() is None:
            # 시간대를 추측하지 않는다.
            raise ValueError(f"naive datetime cannot be stored, attach a tzinfo: {value!r}")
        return value.astimezone(dt.UTC).replace(tzinfo=None)

    def process_result_value(
        self, value: dt.datetime | None, dialect: Dialect
    ) -> dt.datetime | None:
        if value is None:
            return None
        return value.replace(tzinfo=dt.UTC)


def _enum_values(enum_class: type[enum.Enum]) -> list[str]:
    """DB에 멤버 이름(TODO)이 아니라 값("todo")을 저장하게 한다."""
    return [str(member.value) for member in enum_class]


class Base(DeclarativeBase):
    # Mapped[dt.datetime] 컬럼은 모두 UTCDateTime으로 저장한다.
    type_annotation_map = {dt.datetime: UTCDateTime}


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    color: Mapped[str | None] = mapped_column(String(7))
    archived: Mapped[bool] = mapped_column(default=False, server_default=false())
    created_at: Mapped[dt.datetime] = mapped_column(default=utcnow)


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[TaskStatus] = mapped_column(
        SAEnum(
            TaskStatus,
            native_enum=False,
            length=16,
            values_callable=_enum_values,
            create_constraint=True,
            name="ck_tasks_status",
        ),
        default=TaskStatus.TODO,
    )
    category: Mapped[str | None] = mapped_column(String(32))
    estimate_minutes: Mapped[int | None]
    planned_week: Mapped[str | None] = mapped_column(String(8), index=True)
    due_date: Mapped[dt.date | None]
    external_ref: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[dt.datetime] = mapped_column(default=utcnow, onupdate=utcnow)
    done_at: Mapped[dt.datetime | None]

    project: Mapped[Project] = relationship()


class WorkLog(Base):
    __tablename__ = "worklogs"
    __table_args__ = (CheckConstraint("minutes >= 1", name="ck_worklogs_minutes_positive"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    task_id: Mapped[int | None] = mapped_column(
        ForeignKey("tasks.id", ondelete="SET NULL"), index=True
    )
    category: Mapped[str] = mapped_column(String(32))
    date: Mapped[dt.date] = mapped_column(index=True)
    minutes: Mapped[int]
    note: Mapped[str] = mapped_column(Text)
    started_at: Mapped[dt.datetime | None]
    ended_at: Mapped[dt.datetime | None]
    created_at: Mapped[dt.datetime] = mapped_column(default=utcnow)

    project: Mapped[Project] = relationship()
    task: Mapped[Task | None] = relationship()


class ActiveTimer(Base):
    """진행 중인 타이머. 항상 id = 1인 행 하나만 존재할 수 있다."""

    __tablename__ = "active_timer"
    __table_args__ = (CheckConstraint("id = 1", name="ck_active_timer_single_row"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False, default=1)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    task_id: Mapped[int | None] = mapped_column(ForeignKey("tasks.id", ondelete="SET NULL"))
    category: Mapped[str] = mapped_column(String(32))
    note: Mapped[str] = mapped_column(Text)
    started_at: Mapped[dt.datetime]

    project: Mapped[Project] = relationship()
    task: Mapped[Task | None] = relationship()


class SchemaVersion(Base):
    """마이그레이션 버전을 담는 단일 행 테이블."""

    __tablename__ = "schema_version"

    version: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
