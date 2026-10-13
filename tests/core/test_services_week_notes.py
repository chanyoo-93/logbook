"""logbook.core.services.week_notes 단위 테스트."""

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from logbook.core import services
from logbook.core.models import WeekNote
from logbook.core.weeks import Week

W40 = Week(2026, 40)
W41 = Week(2026, 41)


def _row_count(s: Session) -> int:
    return s.scalar(select(func.count()).select_from(WeekNote)) or 0


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("a\r\nb  \r\n\r\n", "a\nb"),
        ("a\rb", "a\nb"),
        ("\n  \n- x\n", "- x"),
        ("   ", ""),
        ("", ""),
        ("  들여쓴 줄", "  들여쓴 줄"),
    ],
)
def test_clean_note_text(text: str, expected: str) -> None:
    assert services.clean_note_text(text) == expected


def test_save_creates_row_and_get_returns_same_values(session: Session) -> None:
    saved = services.save_week_note(session, W40, notes="배포 일정 확정", risks="")

    found = services.get_week_note(session, W40)

    assert saved is not None
    assert found is not None
    assert (found.week, found.notes, found.risks) == ("2026-W40", "배포 일정 확정", "")


def test_get_returns_none_when_never_saved(session: Session) -> None:
    assert services.get_week_note(session, W40) is None


def test_save_both_empty_deletes_existing_row(session: Session) -> None:
    services.save_week_note(session, W40, notes="내용", risks="위험")

    result = services.save_week_note(session, W40, notes="  ", risks="\n")

    assert result is None
    assert services.get_week_note(session, W40) is None
    assert _row_count(session) == 0


def test_save_both_empty_without_row_does_nothing(session: Session) -> None:
    result = services.save_week_note(session, W40, notes="", risks="")

    assert result is None
    assert _row_count(session) == 0


def test_save_updates_same_row(session: Session) -> None:
    services.save_week_note(session, W40, notes="처음", risks="")

    services.save_week_note(session, W40, notes="바뀜", risks="위험 있음")

    assert _row_count(session) == 1
    found = services.get_week_note(session, W40)
    assert found is not None
    assert (found.notes, found.risks) == ("바뀜", "위험 있음")


def test_save_cleans_text(session: Session) -> None:
    services.save_week_note(session, W40, notes="a\r\nb  \r\n", risks="\n\n- r\n")

    found = services.get_week_note(session, W40)
    assert found is not None
    assert (found.notes, found.risks) == ("a\nb", "- r")


def test_notes_are_kept_per_week(session: Session) -> None:
    services.save_week_note(session, W40, notes="40주", risks="")

    assert services.get_week_note(session, W41) is None
