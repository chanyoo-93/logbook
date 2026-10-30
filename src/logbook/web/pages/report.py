"""보고서 화면: 표 보기·원문(GET /report), 내려받기(GET /report/download), 특이사항 저장(POST).

특이사항 저장은 화면이 본 값의 버전(notes_version)이 지금 저장된 값과 같을 때만 한다.
Markdown 렌더링(jinja2)은 세션을 닫은 뒤에 한다.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING
from urllib.parse import urlencode

from fastapi import APIRouter
from starlette.requests import Request
from starlette.responses import HTMLResponse, Response

from logbook.core import polish, services
from logbook.core.duration import format_duration, parse_duration
from logbook.core.errors import InvalidInputError
from logbook.core.report import NO_VALUE
from logbook.core.weeks import Week, parse_week, week_heading
from logbook.web.context import Ctx, WebContext
from logbook.web.errors import NOTES_CHANGED, ConflictError, user_message
from logbook.web.htmx import is_htmx
from logbook.web.pages.forms import FormText, QueryText
from logbook.web.pages.panels import NO_CHANGE, RESULT_MARK
from logbook.web.pages.templating import render, render_error
from logbook.web.pages.views import content_version
from logbook.web.reporting import (
    download_name,
    report_data,
    report_markdown,
    report_with_commits,
)

if TYPE_CHECKING:
    from datetime import datetime

    from sqlalchemy.orm import Session

    from logbook.core.models import WeekNote
    from logbook.core.report import ReportData

router = APIRouter()

PAGE_TEMPLATE = "report.html"
BODY_TEMPLATE = "partials/report_body.html"
RESPONSE_TEMPLATE = "partials/report_response.html"
FORM_TEMPLATE = "partials/report_notes_form.html"
DEFAULT_WEEK = "this"
REPORT_PATH = "/report"
NOTES_SAVED = f"{RESULT_MARK} 특이사항·리스크를 저장했습니다: {{week}}"
MARKDOWN_TYPE = "text/markdown; charset=utf-8"
POLISH_CONFIRM = (
    "{week} 보고서 데이터(태스크 제목·특이사항·리스크 포함)를 외부 AI 서비스로 보냅니다. "
    "커밋 내역과 작성자는 보내지 않습니다. 계속할까요?"
)


@dataclass(frozen=True)
class PolishButton:
    provider: str  # 'anthropic' | 'openai'
    label: str  # 'Claude' | 'ChatGPT'


@dataclass(frozen=True)
class NotesValues:
    notes: str
    risks: str
    version: str


@dataclass(frozen=True)
class ReportSheetView:
    """표 보기: 보고서 데이터에 공수 표의 카테고리별 합계 행을 더한 것(Markdown에는 없다)."""

    data: ReportData
    category_totals: tuple[str, ...]  # data.categories 순서, 0이면 "-"


@dataclass(frozen=True)
class ReportBodyView:
    week: str  # '2026-W42'
    heading: str  # week_heading
    markdown: str  # 렌더링 결과(템플릿 오류면 '')
    preview_error: str  # 사용자 템플릿 오류 문구(있으면 원문 대신 보여 준다)
    download_url: str  # '/report/download?week=2026-W42'
    notes: NotesValues
    message: str = ""
    is_error: bool = False
    warnings: tuple[str, ...] = ()  # 커밋 수집 경고(보기 탭 위에 보여 준다)
    polish: tuple[PolishButton, ...] = ()  # 문장 다듬기 버튼(없으면 영역을 숨긴다)
    polish_confirm: str = ""  # 버튼을 누를 때 보여 줄 확인 문구
    sheet: ReportSheetView | None = None  # 표 보기(사용자 템플릿 오류여도 있다)
    notes_unsaved: bool = False  # 입력값이 저장본과 다르다(충돌 응답). 안내를 채워 그린다


@dataclass(frozen=True)
class ReportNavView:
    week: str  # 주차 입력칸에 채울 값
    prev_url: str | None
    next_url: str | None


def category_totals(rows: Sequence[Sequence[str]]) -> tuple[str, ...]:
    """공수 표 셀(시간 표기, 0이면 "-")을 열마다 더한 합계 표기. 행이 없으면 ()."""
    if not rows:
        return ()
    sums = [0] * len(rows[0])
    for row in rows:
        for index, cell in enumerate(row):
            if cell != NO_VALUE:
                sums[index] += parse_duration(cell, max_minutes=None)
    return tuple(format_duration(total) if total else NO_VALUE for total in sums)


def notes_version(note: WeekNote | None) -> str:
    """화면이 본 특이사항이 그사이 바뀌었는지 가리는 값. 저장된 행이 없으면 ''."""
    if note is None:
        return ""
    return content_version(note.week, note.risks, note.notes)


def _week_url(week: Week) -> str:
    return f"{REPORT_PATH}?{urlencode({'week': week.label})}"


def _neighbor_url(week: Week, *, forward: bool) -> str | None:
    try:
        return _week_url(week.next() if forward else week.prev())
    except InvalidInputError:  # 지원 범위의 끝
        return None


def _nav_view(week: Week | None, typed: str) -> ReportNavView:
    if week is None:
        return ReportNavView(typed, None, None)
    return ReportNavView(
        week.label, _neighbor_url(week, forward=False), _neighbor_url(week, forward=True)
    )


def _parse_week(ctx: WebContext, text: str) -> Week:
    return parse_week(
        text.strip() or DEFAULT_WEEK, today=ctx.today(), week_start=ctx.cfg.week_start
    )


def _body_view(
    ctx: WebContext,
    week: Week,
    data: ReportData,
    notes: NotesValues,
    *,
    message: str = "",
    is_error: bool = False,
    warnings: tuple[str, ...] = (),
) -> ReportBodyView:
    """원문을 렌더링해 본문 뷰를 만든다. 세션을 닫은 뒤에 부른다."""
    markdown = ""
    preview_error = ""
    try:
        markdown = report_markdown(ctx, data)
    except InvalidInputError as error:  # 사용자 템플릿 오류: 페이지는 계속 쓸 수 있다
        preview_error = user_message(error)
    return ReportBodyView(
        week=week.label,
        heading=week_heading(week),
        markdown=markdown,
        preview_error=preview_error,
        download_url=f"{REPORT_PATH}/download?{urlencode({'week': week.label})}",
        notes=notes,
        message=message,
        is_error=is_error,
        warnings=warnings,
        polish=_polish_buttons(),
        polish_confirm=POLISH_CONFIRM.format(week=week.label),
        sheet=ReportSheetView(data, category_totals([row.cells for row in data.matrix])),
    )


def _polish_buttons() -> tuple[PolishButton, ...]:
    return tuple(
        PolishButton(provider, polish.PROVIDER_LABELS[provider])
        for provider in polish.available_providers()
    )


def _load(
    s: Session, ctx: WebContext, week: Week, now: datetime
) -> tuple[ReportData, WeekNote | None]:
    return report_data(s, ctx, week, now), services.get_week_note(s, week)


def _saved_values(note: WeekNote | None) -> NotesValues:
    if note is None:
        return NotesValues("", "", notes_version(None))
    return NotesValues(note.notes, note.risks, notes_version(note))


@router.get("/report", response_class=HTMLResponse)
def report_page(request: Request, ctx: Ctx, week: QueryText = "") -> HTMLResponse:
    now = ctx.now()
    try:
        the_week = _parse_week(ctx, week)
    except InvalidInputError as error:
        if is_htmx(request):
            raise  # 알림 영역에 쓴다 (공통 오류 처리)
        context = {"active": "report", "nav": _nav_view(None, week.strip()), "body": None}
        return render_error(
            request, error, PAGE_TEMPLATE, {**context, "error": user_message(error)}
        )
    with ctx.session() as s:
        data, note = _load(s, ctx, the_week, now)
        notes = _saved_values(note)
    data, warnings = report_with_commits(ctx, data, the_week, now)
    body = _body_view(ctx, the_week, data, notes, warnings=warnings)
    context = {"active": "report", "nav": _nav_view(the_week, ""), "body": body}
    if is_htmx(request):
        return render(request, RESPONSE_TEMPLATE, context)
    return render(request, PAGE_TEMPLATE, context)


@router.get("/report/download")
def report_download(ctx: Ctx, week: QueryText = "") -> Response:
    now = ctx.now()
    the_week = _parse_week(ctx, week)
    with ctx.session() as s:
        data = report_data(s, ctx, the_week, now)
    data, _ = report_with_commits(ctx, data, the_week, now)
    markdown = report_markdown(ctx, data)
    headers = {"Content-Disposition": f'attachment; filename="{download_name(the_week)}"'}
    return Response(markdown.encode("utf-8"), media_type=MARKDOWN_TYPE, headers=headers)


def _conflict_response(
    request: Request, ctx: WebContext, the_week: Week, now: datetime, form: NotesValues, error: str
) -> HTMLResponse:
    """저장된 내용으로 표 보기·원문을 다시 그린다. 입력값은 그대로, 버전만 지금 값으로."""
    with ctx.session() as s:
        data, note = _load(s, ctx, the_week, now)
    data, warnings = report_with_commits(ctx, data, the_week, now)
    shown = NotesValues(form.notes, form.risks, notes_version(note))
    body = _body_view(ctx, the_week, data, shown, message=error, is_error=True, warnings=warnings)
    body = replace(body, notes_unsaved=True)
    headers = {"HX-Retarget": "#report-body", "HX-Reswap": "outerHTML", "HX-Push-Url": "false"}
    return render(request, BODY_TEMPLATE, {"body": body}, status_code=409, headers=headers)


def _week_error_response(
    request: Request, week_text: str, form: NotesValues, error: InvalidInputError
) -> HTMLResponse:
    """주차를 읽지 못하면 보고서 없이 특이사항 폼만 입력값 그대로 다시 그린다."""
    body = ReportBodyView(
        week=week_text,
        heading="",
        markdown="",
        preview_error="",
        download_url="",
        notes=form,
        message=user_message(error),
        is_error=True,
    )
    headers = {"HX-Retarget": "#report-notes", "HX-Reswap": "outerHTML", "HX-Push-Url": "false"}
    return render_error(request, error, FORM_TEMPLATE, {"body": body}, headers=headers)


def _save(
    ctx: WebContext, the_week: Week, now: datetime, form: NotesValues
) -> tuple[ReportData, NotesValues, bool]:
    """세션 하나에서 버전 확인 -> 저장 -> 보고서 데이터 다시 만들기. 다르면 ConflictError."""
    with ctx.session() as s:
        before = services.get_week_note(s, the_week)
        if notes_version(before) != form.version:
            raise ConflictError(NOTES_CHANGED.format(week=the_week.label))
        after = services.save_week_note(s, the_week, notes=form.notes, risks=form.risks)
        data = report_data(s, ctx, the_week, now)
        saved = _saved_values(after)
    return data, saved, saved.version != notes_version(before)


@router.post("/report/notes", response_class=HTMLResponse)
def save_notes(
    request: Request,
    ctx: Ctx,
    week: FormText = "",
    notes: FormText = "",
    risks: FormText = "",
    version: FormText = "",
) -> HTMLResponse:
    form = NotesValues(notes, risks, version)
    now = ctx.now()
    try:
        the_week = _parse_week(ctx, week)
    except InvalidInputError as error:
        return _week_error_response(request, week, form, error)
    try:
        data, saved, changed = _save(ctx, the_week, now, form)
    except ConflictError as error:
        return _conflict_response(request, ctx, the_week, now, form, user_message(error))
    message = NOTES_SAVED.format(week=the_week.label) if changed else NO_CHANGE
    data, warnings = report_with_commits(ctx, data, the_week, now)
    body = _body_view(ctx, the_week, data, saved, message=message, warnings=warnings)
    return render(request, BODY_TEMPLATE, {"body": body})
