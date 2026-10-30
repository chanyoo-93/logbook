"""웹 화면에 나올 수 있는 core 오류의 웹 문구(2026-10-29 G1).

str(error)는 CLI 문구('lb ...' 안내) 그대로이고, error.web_message는 웹 화면의 동작을 안내한다.
"""

from datetime import timedelta

import pytest
from sqlalchemy.orm import Session

from logbook.core import services
from logbook.core.errors import LogbookError, NotFoundError
from tests.core.test_services_timer import T0, _start


@pytest.fixture
def seeded(session: Session) -> Session:
    services.ensure_common_project(session)
    services.create_project(session, "payment", "결제 서버")
    return session


def _raised(action: object) -> LogbookError:
    with pytest.raises(LogbookError) as excinfo:
        action()  # type: ignore[operator]
    return excinfo.value


def test_error_without_web_message_falls_back_to_none() -> None:
    error = NotFoundError("문구")

    assert str(error) == "문구"
    assert error.web_message is None


def test_timer_already_running(seeded: Session) -> None:
    _start(seeded)

    error = _raised(lambda: _start(seeded, now=T0 + timedelta(minutes=5)))

    assert str(error).endswith("'lb stop'으로 저장하거나 'lb cancel'로 버리세요.")
    assert error.web_message == (
        "이미 진행 중인 타이머가 있습니다: payment/design '설계' (09:30 시작). "
        "대시보드의 정지로 저장하거나 취소로 버리세요."
    )


def test_timer_under_one_minute(seeded: Session) -> None:
    _start(seeded)

    error = _raised(lambda: services.stop_timer(seeded, now=T0 + timedelta(seconds=29)))

    assert str(error) == "1분이 지나지 않아 기록하지 않았습니다. 버리려면 'lb cancel'을 실행하세요."
    assert error.web_message == "1분이 지나지 않아 기록하지 않았습니다. 버리려면 취소를 누르세요."


def test_timer_over_24_hours(seeded: Session) -> None:
    _start(seeded)

    error = _raised(lambda: services.stop_timer(seeded, now=T0 + timedelta(hours=25)))

    assert str(error).endswith("'lb cancel'로 버린 뒤 'lb add'로 날짜별로 나눠 기록하세요.")
    assert error.web_message == (
        "타이머가 24시간을 넘었습니다 (시작 10-01 09:30). "
        "취소로 버린 뒤 빠른 기록으로 기록하고, 날짜는 기록 화면에서 고치세요."
    )


def test_no_timer(seeded: Session) -> None:
    error = _raised(lambda: services.stop_timer(seeded, now=T0))

    assert str(error) == services.NO_TIMER_MESSAGE
    assert error.web_message == services.NO_TIMER_WEB_MESSAGE
    assert services.NO_TIMER_WEB_MESSAGE == (
        "진행 중인 타이머가 없습니다. 빠른 기록의 타이머 시작 버튼을 누르세요."
    )


def test_worklog_not_found(seeded: Session) -> None:
    error = _raised(lambda: services.get_worklog(seeded, 99))

    assert str(error) == "기록을 찾을 수 없습니다: #99. 'lb log'로 확인하세요."
    assert error.web_message == "기록을 찾을 수 없습니다: #99. 기록 화면에서 확인하세요."


def test_task_not_found(seeded: Session) -> None:
    error = _raised(lambda: services.get_task(seeded, 99))

    assert str(error) == "태스크를 찾을 수 없습니다: #99. 'lb task list'로 확인하세요."
    assert error.web_message == "태스크를 찾을 수 없습니다: #99. 태스크 화면에서 확인하세요."


def test_project_not_found(seeded: Session) -> None:
    error = _raised(lambda: services.get_project(seeded, "nope"))

    assert str(error).startswith("프로젝트를 찾을 수 없습니다: 'nope'. 'lb project list'")
    assert error.web_message == (
        "프로젝트를 찾을 수 없습니다: 'nope'. 설정 화면의 프로젝트 목록에서 확인하거나 추가하세요."
    )


def test_project_duplicate(seeded: Session) -> None:
    error = _raised(lambda: services.create_project(seeded, "payment", "또 결제"))

    assert str(error) == "이미 존재하는 프로젝트입니다: 'payment'. 'lb project list'로 확인하세요."
    assert error.web_message == (
        "이미 존재하는 프로젝트입니다: 'payment'. 설정 화면의 프로젝트 목록에서 확인하세요."
    )
