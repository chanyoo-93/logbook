# develop에 남은 대비 검사 지적 셋 정리 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** PR #40·#41 QA의 대비 검사(impeccable)에서 develop에도 있던 지적 셋을 없앤다.

| 지적 | 화면·폭 | 지금 모습 |
|---|---|---|
| `unbalanced-heading` | 태스크 다음 주 계획 `h3.plan__project`, 320·375px | `프로젝트 (예상 6h)` 제목이 줄을 넘길 때 마지막 줄이 짧게 남는다. 카드 제목(`.panel__title`)은 PR #41에서 `text-wrap: balance`를 받았지만 이 소제목은 빠졌다. |
| `straggler` | 보고서 표 보기 `#sheet-meta`, 320px | `작성자 … · 2026-W46 · 2026-11-09 ~ 2026-11-15`가 줄을 넘길 때 마지막 줄에 날짜 한 조각만 남는다. |
| `repeated-container-text` | 설정 정보 글꼴 세 줄 | 제목·문서·본문 글꼴 미리보기가 모두 `가나다 ABC 123 · 8h 55m`이다. |

**기준:** develop 87cd4a8(PR #41 병합)에서 갈라진 브랜치 `fix/detector-leftovers`.

**진행:** 계획서 승인 → Task 순서대로, 테스트 먼저(RED). Task마다 전후 스크린샷(375px 밝음·어두움, 320px 밝음, 설정은 1280px도)을 비교 HTML 한 장으로 보여 드리고 승인을 받은 뒤 커밋한다. 끝에 문서·전체 검증·최종 리뷰 1회(`final-reviewer`, Sonnet high) → PR(develop) → "logbook QA" 세션 점검. 새 의존성 없음.

---

## 결정 (2026-11-09 결정 게이트, 사용자 확정)

| ID | 결정 |
|---|---|
| D1 | **글꼴 미리보기는 쓰임별 문구.** 각 글꼴이 실제로 쓰이는 곳의 문구로 바꾼다. 셋 다 한글·영문·숫자를 담아 글꼴 비교는 그대로 된다. |
| D2 | **보고서 메타 줄은 조각 단위로 줄바꿈.** 작성자·주차·기간을 각각 줄바꿈 없는 조각으로 감싸 ` · ` 자리에서만 줄이 바뀐다. |

계획서에서 정한 것(승인 때 확인 부탁):

| ID | 제안 |
|---|---|
| D3 | **계획 패널 프로젝트 소제목은 `text-wrap: balance`.** 카드 제목과 같은 방법이라 따로 묻지 않았다. |
| D4 | **미리보기 문구:** 제목 `이번 주 공수 38h 20m`, 문서 `결제 승인 오류 수정 · 2026-W46`, 본문 `기록 7건 · 8h 55m`. 고정 문구(실제 데이터 아님). |

## 설계

- **D3:** `tasks.css`의 `.plan__project`에 `text-wrap: balance`. 지원하지 않는 브라우저는 지금과 같다.
- **D2:** `report_sheet.html`의 `#sheet-meta` 안을 `<span class="sheet__meta-part">작성자 …</span> · <span …>주차</span> · <span …>시작 ~ 끝</span>`로 감싼다. `report.css`에 `.sheet__meta-part { white-space: nowrap; }`. 조각 하나가 줄보다 길 일은 없다(가장 긴 기간 조각 약 23자, 320px 줄 폭에 들어감, 작성자 이름이 아주 길면 그 조각만 넘칠 수 있어 작성자 조각은 nowrap에서 뺄지 구현 때 320px로 확인).
  - 복사: `report.js`는 `<p>`를 `textContent` 한 줄로 가져가므로 복사본 글자는 그대로다(테스트로 확인: 메타 줄 텍스트가 지금과 같음).
- **D1·D4:** `FontRowView`에 `preview: str`을 더하고 `info_view`가 세 문구를 넣는다. `settings.html`은 `{{ font.preview }}`를 쓴다. SPEC의 설정 화면 글꼴 줄 문장도 고친다.

## Task

### Task 1: 계획 패널 소제목 균형 (D3)
- [ ] 테스트(RED): `tests/web/test_card_titles.py`에 `.plan__project` 선언에 `text-wrap: balance`가 있는지.
- [ ] 구현 → GREEN, 전후 스크린샷(태스크 320·375px, 긴 프로젝트 이름) → 승인 → 커밋 `fix: 다음 주 계획 프로젝트 소제목 줄을 고르게 나눈다`

### Task 2: 보고서 메타 줄 조각 줄바꿈 (D2)
- [ ] 테스트(RED): `tests/web/test_report_sheet.py`에 `#sheet-meta` 안에 `sheet__meta-part` 조각(작성자 있으면 셋, 없으면 둘), 메타 줄 전체 텍스트는 지금과 같음, `report.css`의 `.sheet__meta-part`에 `white-space: nowrap`.
- [ ] 구현 → GREEN, 전후 스크린샷(보고서 320·375px, 작성자 있음) → 승인 → 커밋 `fix: 보고서 메타 줄은 조각 사이에서만 줄을 바꾼다`

### Task 3: 글꼴 미리보기 쓰임별 문구 (D1·D4)
- [ ] 테스트(RED): `tests/web/test_settings_page.py`의 미리보기 문구 기대값을 세 줄 각각의 문구로 바꾸고, 세 문구가 서로 다름을 확인.
- [ ] 구현 → GREEN, 전후 스크린샷(설정 1280·375px) → 승인 → 커밋 `fix: 설정 글꼴 미리보기를 글꼴별 쓰임 문구로 바꾼다`

### Task 4: 문서·검증·리뷰·PR
- [ ] SPEC(설정 화면 글꼴 줄 문장, 보고서 표 보기 메타 줄), ROADMAP 보완 항목 한 줄
- [ ] 전체 pytest·ruff·mypy(core), 대비 검사로 세 지적이 사라졌는지 확인
- [ ] `final-reviewer` 1회 → 반영 → PR(develop) → "logbook QA" 세션 점검 요청
