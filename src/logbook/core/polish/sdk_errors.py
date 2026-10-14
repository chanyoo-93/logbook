"""Anthropic·OpenAI SDK 예외를 사용자 문구의 ExternalServiceError로 바꾼다.

두 SDK가 같은 이름의 예외 클래스를 쓰므로 하나의 함수로 판정한다.
"""

from types import ModuleType

from logbook.core.errors import ExternalServiceError
from logbook.core.polish import KEY_ENV, PROVIDER_LABELS

BAD_KEY = "{label} API 키가 올바르지 않거나 권한이 없습니다. 확인할 환경변수: {env}."
MODEL_UNAVAILABLE = (
    "{label} 모델을 쓸 수 없습니다: {model}. 설정 [llm].{provider}_model을 확인하세요."
)
RATE_LIMITED = "{label} 요청 한도를 넘었습니다. 잠시 후 다시 시도하세요."
TIMED_OUT = "{label} 응답이 {timeout:.0f}초 안에 오지 않았습니다. 잠시 후 다시 시도하세요."
CONNECTION_FAILED = "{label} 서버에 연결하지 못했습니다. 인터넷 연결을 확인하세요."
REQUEST_FAILED = "{label} 요청이 실패했습니다 (HTTP {status}). 잠시 후 다시 시도하세요."


def to_external_error(
    error: Exception, sdk: ModuleType, *, provider: str, model: str, timeout: float
) -> ExternalServiceError | None:
    """SDK 예외를 문구가 있는 ExternalServiceError로 바꾼다. 해당하지 않으면 None.

    timeout은 호출한 제공자 모듈의 TIMEOUT_SECONDS다. 검사 순서가 중요하다:
    인증·권한·없음·한도는 APIStatusError의 하위, APITimeoutError는 APIConnectionError의 하위다.
    """
    label = PROVIDER_LABELS[provider]
    if isinstance(error, (sdk.AuthenticationError, sdk.PermissionDeniedError)):
        message = BAD_KEY.format(label=label, env=KEY_ENV[provider])
    elif isinstance(error, sdk.NotFoundError):
        message = MODEL_UNAVAILABLE.format(label=label, model=model, provider=provider)
    elif isinstance(error, sdk.RateLimitError):
        message = RATE_LIMITED.format(label=label)
    elif isinstance(error, sdk.APITimeoutError):
        message = TIMED_OUT.format(label=label, timeout=timeout)
    elif isinstance(error, sdk.APIConnectionError):
        message = CONNECTION_FAILED.format(label=label)
    elif isinstance(error, sdk.APIStatusError):
        message = REQUEST_FAILED.format(label=label, status=error.status_code)
    else:
        return None
    return ExternalServiceError(message)
