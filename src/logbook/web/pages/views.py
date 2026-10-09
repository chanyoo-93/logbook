"""화면이 쓰는 뷰 데이터: 기록 행, 타이머, 기록 한 줄 문구, 기록 버전.

서비스가 돌려준 ORM 객체는 세션 안에서 이 모듈의 불변 값으로 바꾼다. 템플릿은 세션을 닫은 뒤 그린다.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

from logbook.core import services
from logbook.core.duration import format_duration
from logbook.core.taskstatus import TaskStatus
from logbook.core.weeks import clock_label, day_label, full_day

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from logbook.core.config import Config
    from logbook.core.models import ActiveTimer, WorkLog

RECENT_LIMIT = 10
NO_TASK = "-"
# 버전 문자열에서 필드를 가르는 구분자(필드 값에 나올 수 없는 제어 문자)
_FIELD_SEPARATOR = "\x1f"
_VERSION_LENGTH = 16


@dataclass(frozen=True)
class LogRowView:
    id: int
    day: str  # '10-01 (목)'
    full_day: str  # '2026-10-01 (목)' (삭제 확인 문구)
    iso_date: str  # '2026-10-01' (편집 행의 date 입력)
    project: str
    category: str
    duration: str
    note: str
    task: str  # '#42' 또는 '-'
    version: str  # worklog_version


@dataclass(frozen=True)
class TimerView:
    scope: str  # 'payment/design'
    note: str
    task: str | None  # '#43'
    started: str  # 오늘이면 '09:30', 아니면 '09-30 (수) 22:10'
    elapsed: str  # '1h 25m'


def worklog_version(log: WorkLog) -> str:
    """화면이 본 기록이 그사이 바뀌었는지 가리는 값.

    id·date·minutes·note·project_id·category·task_id·created_at를 구분자로 이어 sha256한 앞 16자.
    SQLite가 id를 다시 쓰는 경우에도 created_at이 달라서 다른 기록으로 가려진다.
    """
    fields = (
        log.id,
        log.date.isoformat(),
        log.minutes,
        log.note,
        log.project_id,
        log.category,
        log.task_id,
        log.created_at.isoformat(),
    )
    text = _FIELD_SEPARATOR.join("" if value is None else str(value) for value in fields)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:_VERSION_LENGTH]


def record_text(log: WorkLog, *, with_date: bool) -> str:
    """기록 한 줄: '#128 payment/dev 2h — 메모'. with_date면 날짜가 id 뒤에 붙는다.

    예: '#128 2026-10-01 (목) payment/dev 2h — 메모'
    """
    date_part = f"{full_day(log.date)} " if with_date else ""
    scope = f"{log.project.slug}/{log.category}"
    return f"#{log.id} {date_part}{scope} {format_duration(log.minutes)} — {log.note}"


def log_row(log: WorkLog) -> LogRowView:
    return LogRowView(
        id=log.id,
        day=day_label(log.date),
        full_day=full_day(log.date),
        iso_date=log.date.isoformat(),
        project=log.project.slug,
        category=log.category,
        duration=format_duration(log.minutes),
        note=log.note,
        task=f"#{log.task_id}" if log.task_id is not None else NO_TASK,
        version=worklog_version(log),
    )


def timer_view(timer: ActiveTimer, now: datetime) -> TimerView:
    """진행 중인 타이머. DB의 시각은 UTC라서 now의 시간대로 바꿔 표기한다."""
    return TimerView(
        scope=f"{timer.project.slug}/{timer.category}",
        note=timer.note,
        task=f"#{timer.task_id}" if timer.task_id is not None else None,
        started=clock_label(timer.started_at.astimezone(now.tzinfo), now.date()),
        elapsed=format_duration(services.elapsed_minutes(timer.started_at, now)),
    )


@dataclass(frozen=True)
class Choice:
    value: str
    label: str


@dataclass(frozen=True)
class QuickFormOptions:
    projects: tuple[Choice, ...]  # 보관하지 않은 프로젝트: Choice('payment', 'payment — 결제 서버')
    categories: tuple[Choice, ...]  # 설정 순서: Choice('dev', 'dev — 개발')
    # 보관하지 않은 프로젝트의 todo·doing: Choice('42', '#42 payment · 제목')
    tasks: tuple[Choice, ...]


@dataclass(frozen=True)
class QuickFormValues:
    """빠른 기록 폼에 채워 둘 값. 모두 입력 문자열 그대로이고 비어 있으면 '자동'이다."""

    duration: str = ""
    note: str = ""
    project: str = ""
    category: str = ""
    task: str = ""


def quick_form_options(s: Session, cfg: Config) -> QuickFormOptions:
    """빠른 기록 폼의 선택지. 세션 안에서 불러 일반 값으로 바꾼다."""
    projects = tuple(Choice(p.slug, f"{p.slug} — {p.name}") for p in services.list_projects(s))
    categories = tuple(Choice(key, f"{key} — {label}") for key, label in cfg.categories.items())
    open_tasks = services.list_tasks(s, statuses=(TaskStatus.TODO, TaskStatus.DOING))
    tasks = tuple(Choice(str(t.id), f"#{t.id} {t.project.slug} · {t.title}") for t in open_tasks)
    return QuickFormOptions(projects=projects, categories=categories, tasks=tasks)
