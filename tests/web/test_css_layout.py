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


@pytest.mark.parametrize(
    ("file_name", "selector", "declaration"),
    [
        ("logs.css", ".week-nav", "flex-wrap: wrap"),
        ("dashboard.css", ".charts", "grid-template-columns: minmax(0, 2fr) minmax(0, 1fr)"),
        ("dashboard.css", ".chart", "min-width: 0"),
        ("tasks.css", ".plan", "padding: var(--space-3)"),
        ("tasks.css", ".task-edit input, .task-edit select", "min-height: 2.25rem"),
        ("tasks.css", ".task-edit input, .task-edit select", "border: 1px solid var(--ink-muted)"),
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
