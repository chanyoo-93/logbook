"""주차별 보고서 특이사항·리스크(보고서 3절) 저장과 조회."""

from sqlalchemy.orm import Session

from logbook.core.models import WeekNote
from logbook.core.weeks import Week


def clean_note_text(text: str) -> str:
    """줄바꿈을 LF로 바꾸고(CRLF, CR), 줄마다 끝 공백을 지우고, 앞뒤 빈 줄을 지운다.

    첫 줄의 앞 공백은 둔다. 공백뿐이면 ''.
    """
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


def get_week_note(s: Session, week: Week) -> WeekNote | None:
    """주차의 특이사항·리스크. 저장한 적이 없으면 None."""
    return s.get(WeekNote, week.label)


def save_week_note(s: Session, week: Week, *, notes: str, risks: str) -> WeekNote | None:
    """두 칸을 clean_note_text로 정리해 저장한다. 둘 다 비면 행을 지우고 None을 돌려준다."""
    clean_notes = clean_note_text(notes)
    clean_risks = clean_note_text(risks)
    note = get_week_note(s, week)
    if not clean_notes and not clean_risks:
        if note is not None:
            s.delete(note)
            s.flush()
        return None
    if note is None:
        note = WeekNote(week=week.label, notes=clean_notes, risks=clean_risks)
        s.add(note)
    else:
        note.notes = clean_notes
        note.risks = clean_risks
    s.flush()
    return note
