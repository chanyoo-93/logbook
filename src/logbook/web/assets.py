"""정적 파일 목록. base.html과 오류 페이지가 함께 쓴다(다른 web 모듈을 import하지 않는다)."""

# 링크 순서가 곧 적용 순서다(뒤 파일이 앞 규칙을 덮어쓴다).
# static/css의 모든 .css가 한 번씩 있어야 한다.
STYLESHEETS: tuple[str, ...] = (
    "app.css",
    "dashboard.css",
    "logs.css",
    "components.css",
    "tasks.css",
    "report.css",
    "settings.css",
    "responsive.css",
)
STATIC_CSS_URL = "/static/css/"
# 설정 글꼴을 CSS 변수로 내는 스타일시트. STYLESHEETS 뒤에 링크한다(static/css 파일이 아니다).
FONTS_CSS_URL = "/fonts.css"
