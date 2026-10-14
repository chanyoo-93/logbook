"""lb report: 주간업무보고 Markdown을 stdout, 파일, 클립보드로 내보낸다."""

from datetime import UTC, tzinfo
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, NamedTuple

import typer

from logbook.cli import console, render, runtime
from logbook.cli.group import LogbookCommand
from logbook.core import platform

if TYPE_CHECKING:
    from logbook.core.config import Config
    from logbook.core.report import ReportData
    from logbook.core.weeks import Week

COPY_FAILED_MESSAGE = "클립보드에 복사하지 못했습니다."
PROVIDER_WITHOUT_POLISH = "--provider 옵션은 --polish와 함께 쓰세요."
POLISH_CONFIRM = (
    "보낼 내용: {scope}. 커밋 내역과 작성자는 보내지 않습니다.\n{label}({model})로 보낼까요?"
)
POLISH_CANCELLED = "문장 다듬기를 취소했습니다. 보고서를 만들지 않았습니다."
POLISH_NO_INPUT = "확인 입력이 없습니다. 보내려면 --yes를 붙이세요."
POLISH_REQUESTING = " {label}에 요약을 요청하는 중입니다…"


class ReportBuild(NamedTuple):
    """보고서 데이터와 그것을 만든 설정·주차·시간대."""

    cfg: "Config"
    week: "Week"
    tz: tzinfo
    data: "ReportData"


def _build_data(week: str | None) -> ReportBuild:
    """주차를 해석하고 DB에서 보고서 데이터를 모은다. 세션은 닫고 돌려준다."""
    from logbook.core.weeks import parse_week

    cfg = runtime.settings()
    the_week = parse_week(
        week if week is not None else "this", today=runtime.today(), week_start=cfg.week_start
    )

    # services는 SQLAlchemy를 로드하므로 주차 검증이 끝난 뒤에 import한다.
    from logbook.core import services

    now = runtime.now()
    tz = now.tzinfo or UTC
    with runtime.session(cfg) as s:
        data = services.weekly_report(
            s,
            the_week,
            tz=tz,
            title_format=cfg.report.title_format,
            author=cfg.report.author,
            category_labels=cfg.categories,
        )
    return ReportBuild(cfg, the_week, tz, data)


def _with_commits(build: ReportBuild) -> "ReportData":
    """git 커밋 부록을 채운 데이터. 수집 경고는 한 줄씩 stderr에 쓴다(보고서는 그대로 만든다)."""
    from dataclasses import replace

    from logbook.core import gitcollect

    commits, warnings = gitcollect.report_commits(build.cfg, build.week, tz=build.tz)
    for warning in warnings:
        console.print_warning(warning)
    return replace(build.data, commits=commits)


def _render(data: "ReportData") -> str:
    """사용자 템플릿이 있으면 그것으로 Markdown을 렌더링한다."""
    # 렌더링(jinja2 로드)은 세션을 닫은 뒤에 한다.
    from logbook.core.config import config_path
    from logbook.core.report import render_markdown, user_template_path

    return render_markdown(data, template_path=user_template_path(config_path()))


def _check_polish_options(polish: bool, provider: str | None) -> None:
    """--provider 사용과 제공자 이름을 검사한다. DB·설정·SDK 없이 하는 검증이다."""
    from logbook.core.errors import InvalidInputError

    if provider is None:
        return
    if not polish:
        raise InvalidInputError(PROVIDER_WITHOUT_POLISH)

    from logbook.core import polish as polish_core
    from logbook.core.duration import echo_input

    if provider not in polish_core.PROVIDERS:
        raise InvalidInputError(polish_core.UNKNOWN_PROVIDER.format(echo=echo_input(provider)))


def _polished(
    build: ReportBuild,
    data: "ReportData",
    provider: str | None,
    *,
    out_path: Path | None,
    yes: bool,
) -> "ReportData":
    """제공자를 고르고 확인을 모두 받은 뒤 요약을 요청해 summary를 채운 데이터를 돌려준다.

    비용이 드는 요청 전에 거절할 수 있는 확인(보낼 내용, --out 덮어쓰기)을 먼저 다 받는다.
    """
    from dataclasses import replace

    from logbook.core import polish
    from logbook.core.polish import prompt

    chosen = polish.choose_provider(build.cfg.llm, provider)
    label = polish.PROVIDER_LABELS[chosen]
    model = polish.model_for(build.cfg.llm, chosen)
    if not yes:
        runtime.require_confirmation(
            POLISH_CONFIRM.format(scope=prompt.send_scope(data), label=label, model=model),
            cancelled=POLISH_CANCELLED,
            no_input=POLISH_NO_INPUT,
        )
        if out_path is not None:
            runtime.confirm_overwrite(out_path)
    console.print_notice(render.info_mark(), POLISH_REQUESTING.format(label=label))
    result = polish.polish_report(data, build.cfg.llm, chosen)
    return replace(data, summary=result.summary)


def _deliver(
    markdown: str,
    out_path: Path | None,
    *,
    copy: bool,
    yes: bool,
    overwrite_confirmed: bool = False,
) -> None:
    """파일 저장, 클립보드 복사, stdout 출력을 처리한다."""
    if out_path is not None:
        from rich.text import Text

        runtime.write_text_file(out_path, markdown, yes=yes or overwrite_confirmed)
        console.print_line(render.ok_mark(), " 보고서를 저장했습니다: ", Text(str(out_path)))

    copied = platform.copy_to_clipboard(markdown) if copy else False
    if copied:
        console.print_line(render.ok_mark(), " 보고서를 클립보드에 복사했습니다.")
    elif copy and out_path is not None:
        console.print_warning(f"{COPY_FAILED_MESSAGE} 보고서는 파일로 저장했습니다: {out_path}")
    elif copy:
        console.print_warning(f"{COPY_FAILED_MESSAGE} --out으로 파일에 저장하세요.")

    # 저장도 복사도 하지 않았거나, 복사에 실패했는데 저장한 파일이 없으면 보고서를 stdout에 쓴다.
    if out_path is None and not copied:
        console.print_raw(markdown)


def report(
    week: runtime.WeekOpt = None,
    out: runtime.OutOpt = None,
    copy: Annotated[bool, typer.Option("--copy", help="클립보드에 복사합니다.")] = False,
    yes: runtime.YesOpt = False,
    polish: Annotated[
        bool,
        typer.Option(
            "--polish", help="AI로 요약 문단을 만들어 넣습니다(보고서 데이터가 외부로 전송됨)."
        ),
    ] = False,
    provider: Annotated[
        str | None, typer.Option("--provider", help="--polish에 쓸 제공자: anthropic, openai")
    ] = None,
) -> None:
    """주간업무보고를 Markdown으로 만듭니다. 기본은 이번 주를 stdout에 출력합니다."""
    # DB·설정 없이 끝나는 검증을 먼저 한다.
    _check_polish_options(polish, provider)
    out_path = runtime.prepare_output_path(out) if out is not None else None
    build = _build_data(week)
    data = _with_commits(build)
    if polish:
        data = _polished(build, data, provider, out_path=out_path, yes=yes)
    markdown = _render(data)
    # 요약을 요청했다면 덮어쓰기 확인은 요청 전에 이미 끝났다.
    _deliver(markdown, out_path, copy=copy, yes=yes, overwrite_confirmed=polish)


def register(app: typer.Typer) -> None:
    app.command("report", cls=LogbookCommand)(report)
