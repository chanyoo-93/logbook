"""사용자에게 보여줄 한국어 메시지를 담는 도메인 오류."""


class LogbookError(Exception):
    """사용자에게 그대로 보여줄 수 있는 한국어 메시지를 가진 오류."""


class InvalidInputError(LogbookError, ValueError):
    """사용자 입력 형식이 잘못되었을 때의 오류."""


class NotFoundError(LogbookError, LookupError):
    """요청한 대상(프로젝트, 할 일 등)이 없을 때의 오류."""


class DatabaseNotInitializedError(LogbookError):
    """DB 파일이 없거나 스키마가 없어 'lb init'이 필요한 경우."""


class DatabaseBusyError(LogbookError):
    """다른 프로세스가 DB 잠금을 잡고 있어 작업하지 못한 경우. Web(Phase 5)은 503으로 매핑한다."""
