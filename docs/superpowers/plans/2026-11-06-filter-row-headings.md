# 평가 P3: 화면마다 다른 필터 줄과 제목 단계 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 기록·태스크·보고서의 필터 줄을 한 모양으로 맞추고, 화면 제목을 모두 카드 머리 안의 같은 단계로 둔다. 남은 잔손질 셋(설정 카테고리 색 빈 공간, 404 머리 이번 주, 새 태스크 폼 폭)도 함께 한다.

2026-11-04 재평가(28/40)의 P3 "화면 간 필터 줄·제목 단계 불일치"를 다룬다. 2026-11-06 develop 8c06b5e를 CDP로 1280·375px에서 찍어 확인한 지금 모습:

- **필터 줄:**
  - 기록: `◀ 이전 주 · 주차 · 다음 주 ▶` 뒤에 프로젝트·카테고리 select. 프로젝트 select가 가장 긴 선택지(32자 slug + 이름) 폭까지 넓어져 1280px에서 약 350px이다. 375px에서는 세 줄로 쌓여(높이 180px) 페이지가 가로로 넘친다(PR #40 QA: 375px 14px, 320px 69px).
  - 태스크: 프로젝트 select 하나만 있고, 같은 이유로 넓다(1280px 약 350px, 기록과 같음).
  - 보고서: 주 이동만 있다. 마크업이 기록과 다르다(기록은 `week_nav.html`, 보고서는 `report_nav.html` 안의 `.week-nav`).
- **제목:**
  - 기록·보고서·설정·대시보드·다음 주 계획: 카드 안 h2, 20px.
  - 태스크 보드: 카드 밖 h2(`.board__title`), 버튼은 오른쪽. 열 네 개가 카드 없이 바탕 위에 있다.
  - 새 태스크·태스크 수정: 카드 밖 h2(`.task-page__title`), 아래에 폼 카드.
  - 404: 카드 안이지만 17px(`.error-card__title`).
  - 320px 기록 화면 제목 `2026-W45 (11-02 ~ 11-08)`이 한 글자만 다음 줄로 넘어간다(PR #40 QA 대비 검사 `unbalanced-heading`, develop도 같음).
- **잔손질:**
  - 설정 카테고리 색: 제목 아래 결과 줄 자리(`form-message--slot`)가 비어 있어도 높이를 차지해, 제목과 표 사이가 다른 카드보다 한 줄 넓다.
  - 404: 머리에 `이번 주 2026-W45 (…)`가 없다. 오류 페이지는 DB가 잠겨도 뜨도록 DB·설정을 읽지 않기 때문이다.
  - 새 태스크: 폼 카드가 48rem이라 1280px에서 오른쪽 약 470px가 비어 있다.

**기준:** develop 8c06b5e(PR #40 병합)에서 갈라진 브랜치 `feat/filter-row-headings`.

**진행:** 계획서 승인 → Task 순서대로, 테스트 먼저(RED). Task마다 전후 스크린샷(1280px 밝음, 375px 밝음·어두움, 320px 밝음)을 비교 HTML 한 장으로 보여 드리고 승인을 받은 뒤 커밋한다. 끝에 문서·전체 검증·최종 리뷰 1회(`final-reviewer`, Sonnet high) → PR(develop) → "logbook QA" 세션 점검. 새 의존성 없음.

---

## 결정 (2026-11-05 결정 게이트, 사용자 확정)

| ID | 결정 |
|---|---|
| F1 | **필터 줄은 카드 위 공용 줄.** 태스크·기록·보고서 모두 지금 자리(카드 위)에 두고 생김새를 하나로 맞춘다. |
| F2 | **제목은 모두 카드 머리 안.** 태스크 보드·새 태스크·태스크 수정도 카드 머리 안 h2(같은 글자 단계), 새 태스크 버튼은 보드 카드 제목 줄 오른쪽. |
| F3 | **잔손질 셋 포함:** 설정 카테고리 색 빈 공간, 404 머리 이번 주, 새 태스크 폼 폭. |

계획서에서 정한 것(승인 때 확인 부탁):

| ID | 제안 |
|---|---|
| F4 | **새 태스크 폼 폭은 유지(48rem).** 제목·프로젝트·설명을 한눈에 읽기 좋은 폭이고, 1280px 전체 폭으로 늘리면 제목 칸이 1,100px가 된다. 대신 제목이 카드 머리 안으로 들어가 한 덩어리로 보이므로 오른쪽 빈 곳은 페이지 여백으로 읽힌다. 전체 폭을 원하시면 3열 칸을 4열로 늘려 맞춘다. |
| F5 | **PR #40 QA에서 넘어온 둘을 이 PR에서 고친다:** 필터 select가 페이지를 넘치는 것(F1에 포함), 320px 제목 한 글자 넘김(F2에 포함). |

## 설계

- **공용 필터 줄(F1):**
  - 마크업: 세 화면 모두 `<form class="filters">` 하나에 `주 이동 묶음(있으면) → select들` 순서. 주 이동은 `week_nav.html` 하나로 합치고 대상(`#log-table`·`#report-body`)과 이름을 인자로 받는 매크로로 만든다. 보고서의 따로 만든 `report_nav.html` 주 이동 마크업은 이 매크로를 쓴다. 태스크의 select도 기록의 `filter_select` 매크로를 같이 쓴다(공용 파일 `partials/filters.html`로 옮김).
  - 폭: select는 내용 폭을 따르되 최대 16rem(`max-width`), 넘는 선택지 이름은 브라우저가 줄임표로 자른다. 주차 칸은 지금 폭.
  - 좁은 폭(720px 미만): 주 이동 묶음이 한 줄, 그 아래 select들은 두 열 격자(`repeat(auto-fit, minmax(9rem, 1fr))`)로 나란히. select 폭은 칸에 맞춘다(100%). 320px에서도 페이지 가로 넘침 0.
  - HTMX 동작(`hx-get`, `hx-target`, `hx-push-url`, OOB로 주 이동 갱신)은 바꾸지 않는다. id(`log-filters`, `task-filters`, `report-nav`, `filter-week`, `report-week`, `week-nav`)도 그대로 둔다(테스트·JS가 쓴다).
- **카드 머리 안 제목(F2):**
  - 태스크 보드: `section#task-board`를 `panel`로, 머리를 `panel__head`(h2 `panel__title` + 오른쪽 `새 태스크` 버튼)로. 열 네 개는 카드 안쪽 여백 안에 둔다. 끌어 놓기(SortableJS)·포커스(`data-focus`) 동작은 그대로.
  - 다음 주 계획: h2를 `panel__head` 안 `panel__title`로.
  - 새 태스크·태스크 수정: `section.task-page`를 `panel`로, 제목을 `panel__head` 안으로. 폼은 카드 안에 바로 두고 폼 자체의 테두리·그림자는 뺀다(카드 안 카드 없음).
  - 보고서: `report__title`을 `panel__title`로 바꾼다(지금도 같은 크기, 클래스만 공용으로). 문서 제목(`주간업무보고 (…)`)은 보고서 본문이므로 그대로.
  - 404: 제목을 `panel__head` 안으로, 크기는 `panel__title`(20px). 경고 아이콘과 위험 색은 유지.
  - `panel__title`에 `text-wrap: balance`를 두어 좁은 폭에서 한 글자만 넘어가지 않게 한다.
- **설정 카테고리 색(F3):** 결과 줄을 카드 머리(`panel__head`) 오른쪽으로 옮긴다. 자리를 늘 두는 이유(처음 저장할 때 표가 밀려 다음 클릭이 옆 행에 들어가지 않게)는 머리 줄 안이라 높이가 바뀌지 않으므로 그대로 지켜진다. `role="status"`, id `category-result` 유지. 좁은 폭에서 머리 줄이 두 줄이 되면 결과 줄은 제목 아래로 내려가되 비어 있으면 높이 0.
- **404 머리 이번 주(F3):** 오류 페이지를 그릴 때 요청의 WebContext로 이번 주를 계산해 넘긴다(시계와 설정의 `week_start`만 쓰고 DB는 읽지 않음). 컨텍스트가 없거나 계산이 실패하면(설정 오류 등) 지금처럼 빼고 그린다. 최소 페이지(`_plain_error_page`)는 그대로.
- **새 태스크 폼 폭(F4):** 카드 폭 48rem 유지, 제목만 카드 안으로(위 F2).

## Task 1: 공용 필터 줄(F1)

**Files:** `templates/partials/filters.html`(새), `log_filters.html`, `task_filters.html`, `week_nav.html`, `report_nav.html`, `static/css/logs.css`(필터 규칙을 `components.css`로 옮길지 저장소 관례대로), `responsive.css`, 테스트 `tests/web/test_filter_row.py`(새)와 기존 필터·주 이동 테스트

- [ ] RED: 테스트를 쓰고 실패를 확인한다.
  - 기록·태스크·보고서의 필터 form이 모두 `filters` 클래스이고, 주 이동이 같은 구조(`.week-nav` 안 이전·주차·다음)다.
  - 세 화면의 select가 같은 매크로 결과(라벨-select 짝, `filters__field`)다.
  - CSS: `.filters select`에 `max-width`, 좁은 폭에서 select 묶음이 격자이고 select가 `width: 100%`.
  - 기존 HTMX 속성·id가 그대로다(기존 테스트가 지킨다).
- [ ] 구현 → GREEN
- [ ] CDP 확인: 세 화면 필터 줄 높이·간격이 같다. 375·320px 페이지 `scrollWidth == innerWidth`(32자 slug 프로젝트가 있는 DB). 주 이동·필터 변경이 지금처럼 동작한다(표·보드·보고서 갱신, 주소 변경).
- [ ] 전후 스크린샷 → 비교 HTML → 사용자 승인 → 커밋 `feat: 기록·태스크·보고서의 필터 줄을 한 모양으로 맞춘다`

## Task 2: 제목을 모두 카드 머리 안으로(F2)

**Files:** `templates/partials/task_board.html`, `task_plan.html`, `task_new.html`, `task_edit.html`, `partials/task_form.html`, `partials/report_body.html`, `error.html`, `static/css/tasks.css`·`report.css`·`dashboard.css`(`.panel__title`)·`components.css`(오류 카드), 테스트 `tests/web/test_tasks*.py`·`test_errors*.py` 등(이름은 저장소에 맞춤)

- [ ] RED: 테스트를 쓰고 실패를 확인한다.
  - 태스크 보드·다음 주 계획·새 태스크·태스크 수정·보고서·404의 h2가 `.panel` 안 `.panel__head` 안의 `panel__title`이다.
  - 태스크 보드 머리에 `새 태스크` 버튼이 h2와 같은 머리 줄에 있다.
  - CSS: `.panel__title`에 `text-wrap: balance`. 폼(`.task-form`)이 카드 안에서 테두리·그림자를 따로 갖지 않는다.
- [ ] 구현 → GREEN
- [ ] CDP 확인: 각 화면 h2 글자 크기가 같다(20px). 태스크 끌어 놓기·카드 열기·이월 버튼이 동작한다. 320px 기록 제목이 한 글자만 넘어가지 않는다. 대비 검사 0건.
- [ ] 전후 스크린샷 → 비교 HTML → 사용자 승인 → 커밋 `feat: 태스크·새 태스크·오류 화면 제목도 카드 머리 안에 둔다`

## Task 3: 잔손질 셋(F3·F4)

**Files:** `templates/partials/category_section.html`, `static/css/settings.css`, `web/errors.py`, `templates/error.html`, 테스트 `tests/web/test_settings*.py`, `tests/web/test_errors*.py`

- [ ] RED: 테스트를 쓰고 실패를 확인한다.
  - 카테고리 색 결과 줄(`#category-result`)이 `panel__head` 안에 있고 `role="status"`다. 색을 저장하면 결과 문구가 그 자리에 나온다.
  - 404 페이지 머리에 `이번 주 …`가 있고 대시보드 머리와 같은 문구다. 설정의 `week_start`가 일요일이면 그에 맞는 주다. 컨텍스트 계산이 실패하면 머리 이번 주 없이 오류 페이지가 그려진다.
- [ ] 구현 → GREEN
- [ ] CDP 확인: 카테고리 색 카드 제목-표 간격이 프로젝트 카드와 같다. 색을 바꿔도 표가 밀리지 않는다(저장 전후 첫 행 y 같음). 404 머리에 이번 주.
- [ ] 전후 스크린샷 → 비교 HTML → 사용자 승인 → 커밋 `feat: 카테고리 색 결과 줄을 카드 머리로 옮기고 오류 페이지 머리에 이번 주를 보인다`

## Task 4: 문서와 PR

- [ ] SPEC을 고친다: 기록·태스크·보고서 필터 줄 설명, 태스크 보드·새 태스크 화면 제목 위치, 설정 카테고리 색 결과 줄 위치, 오류 페이지 머리 이번 주(오류 페이지는 DB를 읽지 않는다는 설명은 유지, 설정·시계만 쓴다고 더함). CLAUDE.md의 error.html 설명(`DB·설정을 읽지 않으므로 이번 주 표기…는 없다`)도 맞춘다
- [ ] ROADMAP Phase 9 보완 줄을 더하고 체크한다
- [ ] 전체 검증: `ruff check`, `ruff format --check`, `mypy src/logbook/core`, 전체 `pytest`
- [ ] 최종 리뷰 1회(`final-reviewer`) → 지적 반영
- [ ] PR(develop) 생성, "logbook QA" 세션에 점검 요청
