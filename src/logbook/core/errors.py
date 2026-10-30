"""사용자에게 보여줄 한국어 메시지를 담는 도메인 오류."""


class LogbookError(Exception):
    """사용자에게 그대로 보여줄 수 있는 한국어 메시지를 가진 오류.

    str(error)는 CLI 문구('lb ...' 명령 안내)다. 웹 화면의 동작(버튼·화면)으로 안내할 문구가
    따로 있으면 web_message에 둔다. 웹 화면은 web_message를, 없으면 str(error)를 보인다.
    """

    def __init__(self, message: str, *, web_message: str | None = None) -> None:
        super().__init__(message)
        self.web_message = web_message


class InvalidInputError(LogbookError, ValueError):
    """사용자 입력 형식이 잘못되었을 때의 오류."""


class NotFoundError(LogbookError, LookupError):
    """요청한 대상(프로젝트, 할 일 등)이 없을 때의 오류."""


class DatabaseNotInitializedError(LogbookError):
    """DB 파일이 없거나 스키마가 없어 'lb init'이 필요한 경우."""


class DatabaseBusyError(LogbookError):
    """다른 프로세스가 DB 잠금을 잡고 있어 작업하지 못한 경우. Web(Phase 5)은 503으로 매핑한다."""


class ExternalServiceError(LogbookError):
    """외부 명령(git, gh)이나 외부 API(Anthropic, OpenAI)가 실패한 경우. Web은 502로 매핑한다."""
