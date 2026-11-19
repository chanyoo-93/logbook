# 보고서 머리의 긴 작성자 이름 말줄임 계획서

> 브랜치 `fix/long-author-name` (develop fa78cff에서). PR #42 QA INFO 3 후속.

## 문제

설정 `[report] author`에 띄어쓰기 없는 긴 영문(QA는 50자)을 넣으면 320px 보고서 화면에서 머리 글 묶음 `.sheet__head-text`가 303px로 카드 밖으로 나간다(페이지 가로 넘침은 0). develop부터 있던 문제다. 줄을 바꿀 자리가 없어 작성자 조각의 최소 폭이 이름 전체 폭이 되기 때문이다.

## 결정

- **L1 (2026-11-17 사용자):** 작성자 조각은 한 줄로 두고, 칸보다 길면 끝을 `…`로 자른다(글자 단위 줄바꿈 대신). 2026-11-09 D2의 "작성자는 조각 안에서도 줄바꿈"을 대신한다.
  - 화면(인쇄 포함)만 자른다. 복사본(`text/plain`, `text/html`)과 DOM 글자는 이름 전체 그대로다(화면 읽기 프로그램도 전체를 읽는다).
  - 주차·기간 조각은 그대로(조각 안 줄바꿈 없음).
  - 칸에 들어가는 이름(한글 이름, 짧은 영문)은 지금과 같아 보인다.

## Task 1: 작성자 조각 말줄임 (76e112e, 사용자 승인)

- [x] RED: `tests/web/test_report_sheet.py`의 `test_author_part_may_wrap_inside`를 `test_long_author_part_is_truncated_with_ellipsis`로 바꾼다.
  - 작성자 조각 글자는 전체 그대로(`작성자 ` + 50자 영문)
  - `.sheet__meta-part--author` 선언에 `white-space: nowrap`, `overflow: hidden`, `text-overflow: ellipsis`, `max-width: 100%`, `display: inline-block`(인라인 요소에는 말줄임이 걸리지 않음)
  - `.sheet__head-text`에 `min-width: 0`(flex 항목이 이름 폭만큼 넓어지지 않게)
- [x] GREEN: `report.css`의 `.sheet__meta-part--author`와 `.sheet__head-text`를 고치고 주석을 L1로 바꾼다. `report_sheet.html`의 템플릿 주석도 맞춘다.
- [x] 전후 스크린샷: 작성자 없음·`김개발`·50자 영문 × 320·375·768 × 밝은·어두운. 카드 밖 넘침 0, 50자 영문만 `…`로 끝나는지 본다.
- [x] 화면 검사기 320·375px `/report` 0건.
- [x] 사용자 승인 뒤 커밋.

## Task 2: 문서

- [x] SPEC 383줄의 "작성자는 길이를 몰라 조각 안에서도 바뀔 수 있다, D2"를 "작성자는 한 줄이고 칸보다 길면 화면에서만 `…`로 자른다(복사본은 전체), 2026-11-17 결정 L1"로 바꾼다.
- [x] ROADMAP에 완료 항목 한 줄.

## 마무리

- [x] 전체 pytest(3362 passed), ruff check·format, mypy core
- [x] final-reviewer 1회(Sonnet high): 병합 가능(MEDIUM 1, LOW 4). 반영: 테스트가 말줄임 선언을 작성자 규칙에서만 찾고 두 class를 확인, 문구를 "화면(인쇄 포함)"으로. 그대로 둠: 잘린 이름 title(복사 HTML에 속성이 늘어남), 구분점이 줄 맨 앞에 오는 모양(D2부터, 고치면 복사 글자가 바뀜)
- [ ] PR(develop) → logbook QA 점검 요청
