"""CLI 오류 경계: 루트 그룹의 invoke와 모든 그룹·명령의 인자 파싱(make_context).

루트 LogbookGroup.invoke가 하위 그룹·명령·콜백 실행 중의 예외를 처리하고, 실행 전에 일어나는
인자 파싱(즉시 옵션 콜백, --help, 인자 없는 그룹의 help)은 _ParseBoundary가 처리한다.
"""

import contextlib
from typing import TYPE_CHECKING, Any, NoReturn

import typer
from typer.core import TyperCommand, TyperGroup

from logbook.cli import console
from logbook.core.errors import LogbookError

if TYPE_CHECKING:
    from collections.abc import Iterator

EXIT_ERROR = 1


def _exit_silently() -> NoReturn:
    console.silence_stdout()
    raise typer.Exit(EXIT_ERROR) from None


@contextlib.contextmanager
def _error_boundary(*, os_broken_pipe: bool = False) -> "Iterator[None]":
    """LogbookError는 '오류: …' 한 줄과 exit 1로, 닫힌 출력 파이프는 조용한 exit 1로 바꾼다.

    os_broken_pipe=True면 is_broken_pipe인 OSError도 닫힌 파이프로 본다. 우리 출력 함수를
    거치지 않는 Typer help 출력(Windows는 EINVAL)을 위한 것으로, 설정·DB에 접근하지 않는
    인자 파싱 단계에서만 켠다.
    """
    try:
        yield
    except LogbookError as error:
        console.print_error(str(error))
        raise typer.Exit(EXIT_ERROR) from None
    except console.OutputClosedError:
        _exit_silently()
    except OSError as error:
        if os_broken_pipe and console.is_broken_pipe(error):
            _exit_silently()
        raise


class _ParseBoundary:
    """make_context(인자 파싱)를 오류 경계로 감싸는 믹스인.

    즉시(eager) 옵션 콜백(--version, --help)과 인자 없는 그룹의 help는 invoke보다 먼저
    make_context에서 실행된다. 하위 명령과 하위 그룹의 make_context는 부모 invoke 안에서
    불리지만 그 경계는 OSError를 파이프 끊김으로 보지 않으므로, 모든 명령과 그룹이 이 믹스인을
    가져야 한다(그룹은 LogbookGroup, 명령은 LogbookCommand).
    """

    def make_context(
        self, info_name: str | None, args: list[str], parent: Any = None, **extra: Any
    ) -> Any:
        with _error_boundary(os_broken_pipe=True):
            return super().make_context(info_name, args, parent=parent, **extra)  # type: ignore[misc]


class LogbookGroup(_ParseBoundary, TyperGroup):
    """도메인 오류를 stderr의 '오류: …' 한 줄(exit 1)로, 닫힌 출력 파이프를 조용한 exit 1로 바꾼다.

    루트 invoke가 하위 그룹·명령·콜백 실행 중의 예외까지 감싼다. 인자 파싱(make_context)은
    _ParseBoundary가 감싼다. 그 밖의 예외는 버그로 보고 그대로 전파한다.
    하위 그룹도 typer.Typer(cls=LogbookGroup)로 만든다.
    """

    def invoke(self, ctx: Any) -> Any:
        with _error_boundary():
            return super().invoke(ctx)


class LogbookCommand(_ParseBoundary, TyperCommand):
    """명령의 인자 파싱(--help 포함)에서 닫힌 출력 파이프를 조용한 exit 1로 바꾼다.

    실행 중의 예외는 루트 LogbookGroup.invoke가 처리한다. 명령은 @app.command(cls=LogbookCommand)로
    등록한다.
    """
