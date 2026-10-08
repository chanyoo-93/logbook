"""core 테스트 공용 fixture."""

import pytest
from sqlalchemy.orm import Session

from logbook.core import services


@pytest.fixture
def fresh(session: Session) -> Session:
    """lb init 직후와 같은 DB(common 프로젝트만 있음)."""
    services.ensure_common_project(session)
    session.flush()
    return session
