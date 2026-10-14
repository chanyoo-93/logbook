"""설정 글꼴을 CSS 변수로 바꾼다. 글꼴 이름은 설정에서 이미 검증된 값이다."""

from logbook.core.config import WebConfig

HEADER = "/* 설정 [web]의 글꼴. PC에 설치되지 않은 글꼴이면 다음 글꼴로 넘어간다. */\n"


def fonts_css(web: WebConfig) -> str:
    """빈 값은 줄을 내지 않아 app.css의 기본값이 남는다."""
    rules = (
        ("--font-heading", web.heading_font, "--font-sans"),
        ("--font-document", web.document_font, "--font-serif"),
        ("--font-body", web.body_font, "--font-sans"),
    )
    lines = "".join(
        f'  {token}: "{name}", var({fallback});\n' for token, name, fallback in rules if name
    )
    return f"{HEADER}:root {{\n{lines}}}\n"
