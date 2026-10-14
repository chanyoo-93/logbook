"""문장 다듬기 요청의 프롬프트·보낼 데이터·응답 정리. 제공자에 상관없이 같다."""

import json
from dataclasses import asdict

from logbook.core.report import ReportData

SYSTEM_PROMPT = (
    "당신은 소프트웨어 개발자의 주간업무보고서에 넣을 실적 요약을 쓰는 도우미입니다. "
    "사용자가 보내는 JSON(한 주의 공수 표, 프로젝트별 태스크, 특이사항·리스크, 다음 주 계획)만 "
    "근거로 한국어 문단 하나를 3~5문장으로 쓰세요. "
    "시간·건수는 데이터의 값을 그대로 쓰고, 데이터에 없는 "
    "사실이나 평가를 지어내지 마세요. 제목·목록·Markdown 서식 없이 '~했습니다' 체의 평문만 쓰세요."
)

# 외부로 보내지 않는 필드(커밋 제목과 작성자 이름은 보내지 않는다)
_UNSENT_FIELDS = ("summary", "commits", "author")

SCOPE_WITH_NOTES = "특이사항·리스크 포함"
SCOPE_WITHOUT_NOTES = "특이사항·리스크 없음"
SCOPE = "{week} 보고서 데이터(프로젝트 {projects}개, 태스크 {tasks}건, {notes})"

REFUSED = "{label} 모델이 요약을 거절했습니다. 다른 제공자로 다시 시도하세요."
EMPTY_RESPONSE = "{label} 응답에 요약 문장이 없습니다. 다시 시도하세요."
TRUNCATED = "{label} 응답이 길이 제한에 걸려 끝까지 오지 않았습니다. 다시 시도하세요."


def report_payload(data: ReportData) -> str:
    """보낼 JSON: 보고서 데이터에서 summary·commits·author를 뺀 것(키 정렬, 한글 그대로)."""
    fields = {key: value for key, value in asdict(data).items() if key not in _UNSENT_FIELDS}
    return json.dumps(fields, ensure_ascii=False, sort_keys=True, indent=None)


def send_scope(data: ReportData) -> str:
    """확인 문구용 보낼 범위 요약. 커밋 내역과 작성자는 보내지 않는다."""
    has_notes = bool(data.notes or data.risks)
    return SCOPE.format(
        week=data.week_label,
        projects=len(data.matrix),
        tasks=sum(len(section.tasks) for section in data.sections),
        notes=SCOPE_WITH_NOTES if has_notes else SCOPE_WITHOUT_NOTES,
    )


def clean_summary(text: str) -> str:
    """앞뒤 공백을 지우고 줄바꿈을 한 칸 공백으로 합쳐 문단 하나로 만든다. 비면 ''."""
    return " ".join(line.strip() for line in text.splitlines() if line.strip())
