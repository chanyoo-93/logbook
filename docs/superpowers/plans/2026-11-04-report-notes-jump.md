# Phase 9 보완: 보고서 3절과 특이사항 입력 사이의 왕복 없애기 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 보고서 표 보기 3절(특이사항 / 리스크)에서 한 번에 입력 폼으로 가고, 저장하면 3절로 돌아와 결과를 그 자리에서 본다.

2026-11-04 UI 재평가(28/40)의 P1이다. 지금은 3절에 흐린 `(작성하세요)`만 있고 입력 폼(`partials/report_notes_form.html`)은 보고서 패널 맨 아래(원문 접기 상자 다음)에 있다. 저장하면 포커스와 결과 줄이 폼에 머물러, 3절에 들어갔는지 보려면 다시 올라가야 한다.

**기준:** develop 435d020(PR #37 병합)에서 갈라진 브랜치 `feat/report-notes-jump`.

**진행:** 계획서 승인 → Task 순서대로, 테스트 먼저(RED). Task마다 전후 스크린샷을 비교 HTML 한 장으로 보여 드리고 승인 → 커밋. 끝에 문서·전체 검증·최종 리뷰 1회(`final-reviewer`, Sonnet high) → PR(develop) → "logbook QA" 세션 점검. 새 의존성 없음.

---

## 결정 (2026-11-04 결정 게이트, 사용자 확정)

| ID | 결정 |
|---|---|
| K1 | **3절에 쓰기 링크.** 폼 위치는 그대로(맨 아래). 3절 머리의 `복사` 옆에 링크를 둔다. 3절이 비었으면 `쓰기`, 내용이 있으면 `고치기`. 빈 3절의 `(작성하세요)`도 같은 곳으로 가는 링크가 된다. 누르면 폼으로 내려가 특이사항 칸에 포커스가 간다. |
| K2 | **저장에 성공하면 3절로 이동.** 3절 제목에 포커스를 주고(스크롤 포함), 결과 줄(`✔ 특이사항·리스크를 저장했습니다: 2026-W45`, 바뀐 것이 없으면 `바뀐 내용이 없습니다.`)은 3절 머리 아래에 나온다. 오류(주차 오류, 409 충돌)는 지금처럼 폼에 남는다. |

## 설계

- **링크(K1):** `<a href="#report-notes-text" class="btn btn--small sheet__notes-jump" data-notes-jump data-copy-skip>쓰기</a>`. `href`만으로도 JS 없이 폼 칸으로 스크롤된다. `report.js`가 `[data-notes-jump]` 클릭을 가로채 `#report-notes-text`에 `focus()`한다(브라우저가 스크롤). 원문 탭이 열려 있어도 폼은 탭 밖이라 그대로 동작한다.
  - 접근성 이름: 글자 `쓰기`/`고치기` 그대로에 `aria-label="특이사항 / 리스크 쓰기"`(고치기도 같은 형식). 복사 버튼과 같은 `btn--small`.
  - 빈 3절의 `(작성하세요)`는 `<p class="sheet__empty" data-copy-skip><a href="#report-notes-text" data-notes-jump>(작성하세요)</a></p>`. 복사본에서는 지금처럼 빠진다.
- **저장 뒤(K2):** `report_body.html`이 성공 응답(`body.message`가 있고 `is_error`가 아님)일 때만
  - 3절 제목 `h4#sheet-notes-title`에 `tabindex="-1" data-focus`를 단다. 폼 제목의 `data-focus`는 이때 뺀다(영역마다 하나 규칙, `app.js` 2번: 2xx POST면 대상 안의 `[data-focus]`로 포커스).
  - 결과 줄 `<p id="sheet-notes-result" class="form-message" role="status" data-copy-skip>`를 3절 머리 아래에 그린다. 폼 안의 `#report-notes-result`는 오류일 때만 그린다.
  - 오류 응답(주차 오류는 `#report-notes`로 다시 겨눔, 409는 본문 전체)은 지금과 같다: 폼 제목에 `data-focus`, 결과 줄은 폼 안.
- 서버 코드(`pages/report.py`)는 바꾸지 않는다. 템플릿이 `body.message`·`body.is_error`로 고른다.
- 표 보기가 없는 경우(`body.sheet` 없음)는 없다(사용자 템플릿이 깨져도 표 보기는 그려짐). 그래도 템플릿은 `body.sheet`가 없으면 지금처럼 폼에 결과를 그린다.

## Task 1: 3절 쓰기·고치기 링크(K1)

**Files:** `templates/partials/report_sheet.html`, `static/js/report.js`, `static/css/report.css`(필요하면), 테스트 `tests/web/test_report_sheet.py`

- [ ] RED: 테스트를 쓰고 실패를 확인한다.
  - 특이사항·리스크가 비었으면 3절 머리에 `쓰기` 링크(`href="#report-notes-text"`, `data-notes-jump`, `data-copy-skip`)가 있고 `(작성하세요)`도 같은 링크다.
  - 둘 중 하나라도 있으면 링크 글자가 `고치기`다.
  - 다른 절(1·2·4·부록)에는 이 링크가 없다.
- [ ] 구현 → GREEN
- [ ] 브라우저 확인(헤드리스 Edge, 1280·375, 밝음·어두움): 링크를 누르면 특이사항 칸에 포커스가 가고 보인다(뷰포트 안). 3절 복사본에 `쓰기`·`(작성하세요)`가 없다.
- [ ] 전후 스크린샷(3절 머리) 비교 HTML → 사용자 승인 → 커밋 `feat: 보고서 3절에 특이사항 쓰기·고치기 링크를 둔다`

## Task 2: 저장하면 3절로 돌아오기(K2)

**Files:** `templates/partials/report_sheet.html`, `templates/partials/report_notes_form.html`, 테스트 `tests/web/test_report_notes.py`

- [ ] RED: 테스트를 쓰고 실패를 확인한다.
  - 저장 성공 응답: `#sheet-notes` 안에 결과 줄 `✔ 특이사항·리스크를 저장했습니다: 2026-Www`(`role="status"`, `data-copy-skip`)가 있고, `data-focus`는 `#sheet-notes-title`에만 있다. 폼 안에는 결과 줄이 없다.
  - 바뀐 것 없이 저장: 같은 자리에 `바뀐 내용이 없습니다.`.
  - 409 충돌·주차 오류: 결과 줄은 폼 안(`role="alert"`), `data-focus`는 폼 제목. 3절에는 결과 줄이 없다.
  - 처음 열기(GET)와 주 이동: 3절에 결과 줄이 없다.
- [ ] 구현 → GREEN
- [ ] 브라우저 확인(1280·375, 밝음·어두움): 맨 아래에서 저장하면 3절 제목이 뷰포트 안에 오고 포커스가 있으며 결과 줄과 새 내용이 보인다. 3절 복사본에 결과 줄이 없다. 409 때는 폼에 머문다.
- [ ] 전후 스크린샷(저장 직후 화면) 비교 HTML → 사용자 승인 → 커밋 `feat: 특이사항을 저장하면 보고서 3절로 돌아와 결과를 보인다`

## Task 3: 문서와 PR

- [ ] SPEC 보고서 절(6장 `/report`)에 3절 링크와 저장 뒤 이동을 적는다
- [ ] README 보고서 화면 설명에 한 줄
- [ ] ROADMAP Phase 9에 보완 줄을 더하고 체크한다
- [ ] 전체 검증: `ruff check`, `ruff format --check`, `mypy src/logbook/core`, 전체 `pytest`
- [ ] 최종 리뷰 1회(`final-reviewer`) → 지적 반영
- [ ] PR(develop) 생성, "logbook QA" 세션에 점검 요청
