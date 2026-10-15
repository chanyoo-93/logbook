"""좁은 화면(320px)에서 넘치지 않게 하는 스타일 규칙이 남아 있는지 확인하는 구조 테스트.

실제 폭은 브라우저로 재야 하지만, 규칙을 되돌리는 실수는 여기서 잡는다.
규칙은 서식(공백, 줄바꿈, 선택자 나열 모양)과 상관없이 선택자와 선언 단위로 비교한다.
"""

import re
from pathlib import Path

import pytest

import logbook.web

CSS_ROOT = Path(logbook.web.__file__).parent / "static" / "css"
NARROW_QUERY = "@media (max-width: 719px)"
MIDDLE_QUERY = "@media (min-width: 720px) and (max-width: 1099px)"

_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
_RULE = re.compile(r"([^{}]+)\{([^{}]*)\}")


def _squash(text: str) -> str:
    """연속 공백을 한 칸으로 줄이고, 쉼표·콜론 앞의 공백은 없애고 뒤에는 한 칸을 둔다."""
    text = re.sub(r"\s+", " ", text).strip()
    return re.sub(r"\s*([,:])\s*", r"\1 ", text).strip()


def _read(file_name: str) -> str:
    return _COMMENT.sub("", (CSS_ROOT / file_name).read_text(encoding="utf-8"))


def _media_block(css: str, query: str) -> str:
    """`query {`로 시작하는 첫 @media 블록의 안쪽(중괄호 짝을 세어 찾는다)."""
    start = css.find(query)
    assert start >= 0, f"{query} 블록이 없습니다"
    open_at = css.index("{", start)
    depth = 0
    for position in range(open_at, len(css)):
        depth += {"{": 1, "}": -1}.get(css[position], 0)
        if depth == 0:
            return css[open_at + 1 : position]
    raise AssertionError(f"{query} 블록이 닫히지 않았습니다")


def _declarations(css: str, selector: str) -> set[str]:
    """css에서 선택자가 `selector`인 첫 규칙의 선언 집합(정규화한 'prop: value')."""
    wanted = _squash(selector)
    for match in _RULE.finditer(css):
        if _squash(match.group(1)) == wanted:
            parts = (_squash(part) for part in match.group(2).split(";"))
            return {part for part in parts if part}
    raise AssertionError(f"{selector} 규칙이 없습니다")


TASK_CONTROLS = ".task-form input, .task-form select, .task-form textarea"


@pytest.mark.parametrize(
    ("file_name", "selector", "declaration"),
    [
        ("logs.css", ".week-nav", "flex-wrap: wrap"),
        ("dashboard.css", ".charts", "grid-template-columns: minmax(0, 2fr) minmax(0, 1fr)"),
        ("dashboard.css", ".chart", "min-width: 0"),
        ("tasks.css", ".plan", "padding: var(--space-3)"),
        ("tasks.css", TASK_CONTROLS, "min-height: 2.25rem"),
        (
            "tasks.css",
            TASK_CONTROLS,
            "border: 1px solid var(--control-border)",
        ),
        ("report.css", ".report > .form-message:empty", "margin: 0"),
    ],
)
def test_layout_rule_is_declared(file_name: str, selector: str, declaration: str) -> None:
    assert _squash(declaration) in _declarations(_read(file_name), selector)


def test_dashboard_charts_become_a_single_shrinkable_column_below_720px() -> None:
    # 넓은 화면의 .charts는 dashboard.css가 정하고, 좁은 화면 덮어쓰기는 responsive.css에 있다.
    narrow = _media_block(_read("responsive.css"), NARROW_QUERY)

    assert "grid-template-columns: minmax(0, 1fr)" in _declarations(narrow, ".charts")


def test_task_board_stacks_into_one_column_below_720px() -> None:
    narrow = _media_block(_read("tasks.css"), NARROW_QUERY)

    assert "grid-template-columns: 1fr" in _declarations(narrow, ".board__columns")


def test_task_board_has_four_columns_by_default() -> None:
    assert "grid-template-columns: repeat(4, minmax(0, 1fr))" in _declarations(
        _read("tasks.css"), ".board__columns"
    )


def test_task_board_is_two_by_two_between_720_and_1099px() -> None:
    middle = _media_block(_read("tasks.css"), MIDDLE_QUERY)

    assert "grid-template-columns: repeat(2, minmax(0, 1fr))" in _declarations(
        middle, ".board__columns"
    )


@pytest.mark.parametrize(
    "selector",
    [".board__col-head--dropped", ".task-card--ghost", ".task-card--chosen"],
)
def test_board_drag_and_dropped_rules_exist(selector: str) -> None:
    assert _declarations(_read("tasks.css"), selector)


def test_board_card_lists_keep_a_min_height_to_receive_drops() -> None:
    declarations = _declarations(_read("tasks.css"), ".board__cards")

    assert any(d.startswith("min-height: ") for d in declarations)


def test_board_card_lists_fill_the_column_to_receive_drops_below_cards() -> None:
    # 짧은 열의 카드 아래 빈 곳에 놓아도 그 열로 들어가게 목록이 열 끝까지 늘어난다.
    css = _read("tasks.css")

    assert {"display: flex", "flex-direction: column"} <= _declarations(css, ".board__col")
    assert "flex: 1 0 auto" in _declarations(css, ".board__cards")


HEAVY_TOP_RULE = "border-top: 2px solid var(--ink)"


@pytest.mark.parametrize(
    ("file_name", "selector"),
    [
        ("dashboard.css", ".panel"),
        ("tasks.css", ".task-form"),
    ],
)
def test_surfaces_use_soft_shadow_instead_of_heavy_top_rule(file_name: str, selector: str) -> None:
    declarations = _declarations(_read(file_name), selector)

    assert _squash(HEAVY_TOP_RULE) not in declarations
    assert "box-shadow: var(--shadow-soft)" in declarations


def test_quick_bar_has_no_heavy_top_rule_but_keeps_raised_shadow() -> None:
    declarations = _declarations(_read("app.css"), ".quick")

    assert _squash(HEAVY_TOP_RULE) not in declarations
    assert "box-shadow: var(--shadow-raised)" in declarations


def test_masthead_uses_hairline_bottom_rule() -> None:
    declarations = _declarations(_read("app.css"), ".masthead")

    assert "border-bottom: 1px solid var(--rule)" in declarations


def test_button_border_uses_rule_strong() -> None:
    assert "border: 1px solid var(--rule-strong)" in _declarations(_read("components.css"), ".btn")


@pytest.mark.parametrize(
    ("file_name", "selector", "declaration"),
    [
        ("dashboard.css", ".grid thead th", "border-bottom-color: var(--rule-strong)"),
        ("logs.css", ".grid tfoot td", "border-top: 1px solid var(--rule-strong)"),
    ],
)
def test_table_head_and_foot_rules_use_rule_strong(
    file_name: str, selector: str, declaration: str
) -> None:
    assert declaration in _declarations(_read(file_name), selector)


@pytest.mark.parametrize(
    ("file_name", "selector"),
    [
        ("app.css", ".quick input:hover, .quick select:hover"),
        ("components.css", ".timer-start input:hover, .timer-start select:hover"),
        ("report.css", ".report-notes textarea:hover"),
        (
            "tasks.css",
            ".task-form input:hover, .task-form select:hover, .task-form textarea:hover",
        ),
    ],
)
def test_control_hover_border_is_darker_than_default(file_name: str, selector: str) -> None:
    assert "border-color: var(--ink-muted)" in _declarations(_read(file_name), selector)


_CONTROL_TAG = re.compile(r"(?<![\w-])(input|select|textarea)(?![\w-])")
MIN_BORDERED_CONTROL_RULES = 7


def test_every_bordered_control_rule_uses_the_control_border_token() -> None:
    bordered: list[tuple[str, str]] = []
    for path in sorted(CSS_ROOT.glob("*.css")):
        for match in _RULE.finditer(_read(path.name)):
            selector = _squash(match.group(1))
            if not _CONTROL_TAG.search(selector):
                continue
            parts = (_squash(part) for part in match.group(2).split(";"))
            bordered.extend(
                (f"{path.name}: {selector}", part)
                for part in parts
                if part.startswith("border: 1px solid")
            )

    assert len(bordered) >= MIN_BORDERED_CONTROL_RULES
    wrong = [(where, part) for where, part in bordered if "var(--control-border)" not in part]
    assert wrong == []


def test_no_control_uses_the_old_muted_border() -> None:
    css = " ".join(_read(path.name) for path in sorted(CSS_ROOT.glob("*.css")))

    assert "border: 1px solid var(--ink-muted)" not in _squash(css)


def _all_css() -> str:
    return " ".join(_read(path.name) for path in sorted(CSS_ROOT.glob("*.css")))


def test_radius_tokens_have_the_planned_values() -> None:
    declarations = _declarations(_read("app.css"), ":root")

    assert "--radius-xs: 4px" in declarations
    assert "--radius-sm: 8px" in declarations
    assert "--radius-md: 12px" in declarations
    assert "--radius-full: 999px" in declarations


def test_old_single_radius_token_is_gone() -> None:
    css = _all_css()

    assert "var(--radius)" not in css
    assert "--radius:" not in css


@pytest.mark.parametrize(
    ("file_name", "selector", "radius"),
    [
        ("components.css", ".btn", "var(--radius-sm)"),
        ("tasks.css", ".task-card", "var(--radius-sm)"),
        ("dashboard.css", ".panel", "var(--radius-md)"),
        ("app.css", ".quick", "var(--radius-md)"),
        ("tasks.css", ".task-form", "var(--radius-md)"),
        ("tasks.css", ".board__col-head", "var(--radius-md)"),
        ("app.css", ".config-notice", "var(--radius-md)"),
        ("report.css", ".report__preview", "var(--radius-md)"),
        ("report.css", ".report-polish", "var(--radius-md)"),
        ("app.css", ".quick input, .quick select", "var(--radius-xs)"),
        ("components.css", ".timer-start input, .timer-start select", "var(--radius-xs)"),
        (
            "logs.css",
            ".filters input, .filters select, .grid .is-editing input, .grid .is-editing select",
            "var(--radius-xs)",
        ),
        ("report.css", ".report-notes textarea", "var(--radius-xs)"),
        (
            "settings.css",
            '.project-form input[type="text"], .grid--projects .is-editing input[type="text"]',
            "var(--radius-xs)",
        ),
        ("tasks.css", TASK_CONTROLS, "var(--radius-xs)"),
        ("app.css", ".skip-link", "var(--radius-xs)"),
    ],
)
def test_corner_radius_uses_the_step_for_the_element(
    file_name: str, selector: str, radius: str
) -> None:
    assert f"border-radius: {radius}" in _declarations(_read(file_name), selector)


def test_flash_notice_uses_medium_radius() -> None:
    declarations = _declarations(_read("components.css"), '.flash, main > p[role="alert"]')

    assert "border-radius: var(--radius-md)" in declarations


def test_table_buttons_draw_the_focus_ring_inside_so_the_scroll_box_does_not_clip_it() -> None:
    # .table-wrap(overflow-x: auto)이 마지막 행 버튼의 바깥 윤곽선을 잘랐다(설정 화면 프로젝트 표).
    declarations = _declarations(_read("dashboard.css"), ".grid .btn:focus-visible")

    assert "outline-offset: -2px" in declarations


def test_table_color_inputs_draw_the_focus_ring_inside_too() -> None:
    # 카테고리 색 표 마지막 행의 색 고르기 칸 윤곽선이 .table-wrap에 0.9px 잘렸다
    # (Task 8-9 포커스 측정).
    declarations = _declarations(_read("dashboard.css"), '.grid input[type="color"]:focus-visible')

    assert "outline-offset: -2px" in declarations


def test_panel_clips_overflow_so_corners_stay_round() -> None:
    assert "overflow: clip" in _declarations(_read("dashboard.css"), ".panel")


def test_button_press_effect_and_transition() -> None:
    css = _read("components.css")

    assert "transform: scale(0.97)" in _declarations(css, ".btn:active")
    assert "transition: transform 80ms ease-out, background-color 120ms ease-out" in _declarations(
        css, ".btn"
    )


_HEADING_SELECTORS = [
    ("app.css", ".masthead__brand", "letter-spacing: var(--tracking-display)"),
    ("dashboard.css", ".panel__title", "letter-spacing: var(--tracking-title)"),
    ("tasks.css", ".board__title", "letter-spacing: var(--tracking-title)"),
    ("tasks.css", ".board__col-title", "letter-spacing: var(--tracking-title)"),
    ("tasks.css", ".plan__title", "letter-spacing: var(--tracking-title)"),
    ("report.css", ".report__title, .report-notes__title", "letter-spacing: var(--tracking-title)"),
    ("dashboard.css", ".stat__value", "letter-spacing: var(--tracking-display)"),
]


@pytest.mark.parametrize(("file_name", "selector", "tracking"), _HEADING_SELECTORS)
def test_headings_and_big_numbers_use_heading_font_and_tracking(
    file_name: str, selector: str, tracking: str
) -> None:
    declarations = _declarations(_read(file_name), selector)

    assert "font-family: var(--font-heading)" in declarations
    assert tracking in declarations


@pytest.mark.parametrize(
    "selector",
    [".report__preview", ".report-polish__text"],
)
def test_report_text_uses_document_font(selector: str) -> None:
    assert "font-family: var(--font-document)" in _declarations(_read("report.css"), selector)


def test_report_preview_sets_document_font_after_font_inherit() -> None:
    css = _squash(_read("report.css"))
    block = css[css.index(".report__preview { padding") :]
    block = block[: block.index("}")]

    assert block.index("font: inherit") < block.index("font-family: var(--font-document)")


def test_report_preview_uses_body_size() -> None:
    # 보고서 미리보기는 본문 크기(15px)를 쓴다(2026-10-14 사용자 결정).
    declarations = _declarations(_read("report.css"), ".report__preview")

    assert "font-size: var(--text-base)" in declarations
    assert "font-size: var(--text-sm)" not in declarations


def test_tracking_tokens_are_in_root() -> None:
    declarations = _declarations(_read("app.css"), ":root")

    assert "--tracking-title: -0.01em" in declarations
    assert "--tracking-display: -0.035em" in declarations


@pytest.mark.parametrize(
    ("column", "background", "ink"),
    [
        ("todo", "--tag-bg", "--ink-muted"),
        ("doing", "--accent-soft", "--accent-hover"),
        ("done", "--ok-soft", "--ok"),
    ],
)
def test_board_column_head_uses_state_color(column: str, background: str, ink: str) -> None:
    declarations = _declarations(_read("tasks.css"), f".board__col-head--{column}")

    assert f"background: var({background})" in declarations
    assert f"color: var({ink})" in declarations


def test_board_column_has_no_surface_of_its_own() -> None:
    declarations = _declarations(_read("tasks.css"), ".board__col")

    assert not any(d.startswith(("background", "border", "box-shadow")) for d in declarations)


def test_task_card_is_a_white_card_without_a_left_band() -> None:
    css = _read("tasks.css")
    declarations = _declarations(css, ".task-card")

    assert "background: var(--surface)" in declarations
    assert "box-shadow: var(--shadow-soft)" in declarations
    assert "border: 1px solid var(--rule)" in declarations
    assert "border-left" not in css


def test_task_card_over_and_editing_have_no_left_band_rules() -> None:
    css = _read("tasks.css")

    assert ".task-card--over {" not in css
    assert ".task-card.is-editing {" not in css
    assert ".task-edit" not in css


def test_progress_bar_rules_exist() -> None:
    css = _read("tasks.css")

    assert "fill: var(--accent)" in _declarations(css, ".progress__fill")
    assert "fill: var(--rule)" in _declarations(css, ".progress__track")
    assert "fill: var(--danger)" in _declarations(css, ".progress--over .progress__fill")


def test_task_card_link_fills_the_card_and_keeps_a_focus_ring() -> None:
    css = _read("tasks.css")

    assert "display: flex" in _declarations(css, ".task-card__link")
    assert "text-decoration: none" in _declarations(css, ".task-card__link")
    assert "outline-offset: -2px" in _declarations(css, ".task-card__link:focus-visible")


def test_task_form_fields_wrap_in_a_responsive_grid_with_full_width_title_and_description() -> None:
    css = _read("tasks.css")

    assert "display: grid" in _declarations(css, ".task-form__fields")
    full = _declarations(css, ".task-form__field--title, .task-form__field--description")
    assert "grid-column: 1 / -1" in full


def test_running_timer_is_an_inverted_band() -> None:
    css = _read("components.css")
    band = _declarations(css, ".timer--running")

    assert "background: var(--band-bg)" in band
    assert "color: var(--band-ink)" in band
    assert not any(d.startswith("border-left") for d in band)


def test_running_timer_buttons_use_band_colors() -> None:
    declarations = _declarations(_read("components.css"), ".timer--running .btn")

    assert "background: transparent" in declarations
    assert "color: var(--band-ink)" in declarations
    assert "border-color: var(--band-muted)" in declarations


def test_running_timer_secondary_text_and_dot_are_readable_on_the_band() -> None:
    css = _read("components.css")

    assert "color: var(--band-muted)" in _declarations(css, ".timer--running .timer__time")
    assert "background: var(--band-ink)" in _declarations(css, ".timer--running .timer__dot")


def test_today_progress_done_fill_uses_ok_color() -> None:
    css = _read("dashboard.css")

    assert "fill: var(--ok)" in _declarations(css, ".progress--done .progress__fill")
    assert "display: flex" in _declarations(css, ".stat__progress")
