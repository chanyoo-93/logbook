"""카테고리 색을 꼬리표 CSS 규칙으로 바꾼다. 순수 함수라 DB를 읽지 않는다."""

from collections.abc import Mapping, Sequence

from logbook.core import services
from logbook.core.config import CATEGORY_KEY

HEADER = "/* 카테고리 색(설정 화면에서 고른 색, 없으면 자동 팔레트). 서버가 요청마다 만든다. */\n"
RULE = (
    ".pill--cat-{key} {{ background: color-mix(in srgb, {color} var(--pill-tint), var(--surface)); "
    "color: var(--ink); }}\n"
)


def colors_css(configured: Sequence[str], stored: Mapping[str, str]) -> str:
    """설정 카테고리 전부(설정 순서)와 색이 저장된 그 밖의 키(이름 순)의 꼬리표 규칙.

    키가 형식에 맞지 않거나 색이 '#rrggbb'가 아니면 그 줄을 내지 않는다(CSS 주입 방지).
    """
    # 함수 안에서 import한다: pages 패키지가 이 모듈을 import하므로 맨 위에서 하면 순환이 된다.
    from logbook.web.pages.views import category_color_map

    colors = category_color_map(configured, stored)
    extras = {key: stored[key] for key in sorted(stored) if key not in colors}
    rules = "".join(
        RULE.format(key=key, color=color)
        for key, color in {**colors, **extras}.items()
        if CATEGORY_KEY.fullmatch(key) and services.is_valid_color(color)
    )
    return HEADER + rules
