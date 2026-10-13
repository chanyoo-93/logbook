"""화면 라우트가 공유하는 요청 값 타입. 폼·쿼리 값은 문자열로 받아 core 파서로 검증한다."""

from typing import Annotated

from fastapi import Form, Query

FormText = Annotated[str, Form()]
QueryText = Annotated[str, Query()]
