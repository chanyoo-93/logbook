"""lb 명령 모듈. 각 모듈은 register(app: typer.Typer) -> None을 제공한다(CommandModule).

명령은 @app.command(cls=LogbookCommand)로, 하위 그룹은 typer.Typer(cls=LogbookGroup)로 만든다
(logbook.cli.group). 하위 명령의 인자 파싱(--help 등)에서 닫힌 출력 파이프를 처리하려는 것으로,
tests/cli/test_entry.py가 명령 트리 전체를 검사한다.

명령 모듈은 상단에서 typer만 import하고, core.config/db/services와 rich는 함수 안에서
지연 import한다. Typer가 시그니처를 런타임에 평가하므로 `from __future__ import annotations`를
쓰지 않는다.
"""

from typing import Protocol

import typer


class CommandModule(Protocol):
    """명령 모듈의 계약: register(app)이 자기 명령을 app에 등록한다."""

    def register(self, app: typer.Typer) -> None: ...
