# Phase 9 보완: 접근성 남은 것 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 대시보드 기록 집중(PR #27)에서 SPEC 후속 항목으로 남긴 세 가지를 고친다.
1. 밝은 테마 주 이동 링크(기록·보고서의 `← 지난 주`·`다음 주 →`)가 바탕(`--bg` `#f6f5f4`) 위에서 4.2:1이다(기준 4.5:1). 원인은 `--accent` `#0075de`.
2. 오류 페이지(`web/errors.py`의 `_error_page`)에 h1이 없다. 다른 화면은 숨긴 h1이 있다.
3. 320px 폭에서 타이머 메모 안내 글자 "무엇을 하나요 (태스크를 고르면 생략)"가 잘린다.

**기준:** develop 3e7e996(PR #28 병합)에서 갈라진 브랜치 `fix/a11y-leftovers`

**진행:** 계획서 승인 → Task 순서대로(테스트 먼저 RED) → Task마다 전후 스크린샷과 사용자 승인 → 문서·전체 검증·최종 리뷰 1회(`final-reviewer`, Sonnet high) → PR(develop) → QA 세션 자동 점검. 변경이 작아 구현은 메인 세션이 직접 한다.

**Tech Stack:** 기존과 같다. 새 의존성·스키마·JS 변경 없음.

---

## 결정 (2026-10-26 결정 게이트, 사용자 확정)

| ID | 결정 |
|---|---|
| F1 | 밝은 테마 `--accent`를 `#0075de` → **`#006bce`**로. 대비(WCAG 상대 휘도 계산): `--bg` 4.83:1, `--surface` 5.26:1, `--accent-soft` 4.56:1, 흰 글자(`--accent-ink`) on 강조색 5.26:1. 링크·포커스 윤곽선·주 버튼이 함께 바뀐다. `--accent-hover` `#005bab`은 그대로(여전히 더 진함). → 최종 리뷰에서 hover 변화가 약해졌다는 지적(명도 대비 1.29:1)을 받아, 사용자가 비교 페이지에서 직접 보고 `#004f96`(1.56:1, 흰 글자 8.21:1)으로 정했다(2026-10-26). 어두운 테마는 그대로. |
| F2 | 오류 페이지에 **숨긴 h1 "오류"**(`<h1 class="visually-hidden">오류</h1>`)를 `<main>` 맨 앞에. 보이는 화면은 그대로. |
| F3 | 타이머 메모 안내 글자를 **"무엇을 하나요"**로 줄이고, 입력 칸에 말풍선 `title="태스크를 고르면 비워도 됩니다."`를 단다(선택 상자 말풍선과 같은 방식). |

---

## Task 1: 강조색 (F1)

**파일:** `static/css/app.css`(밝은 `:root`의 `--accent` 한 줄), `tests/web/test_theme.py`

- **테스트 먼저(RED):** `CONTRAST_PAIRS`에 `("--accent", "--bg")`와 `("--accent", "--accent-soft")`를 더한다. 밝은 테마에서 지금 값으로 실패하는지 확인한다(4.19, 3.96). 어두운 테마는 이미 통과해야 한다.
- 구현: `--accent: #006bce;`.
- **확인:** 대시보드·기록·보고서 1280·320 밝은 테마 전후 스크린샷, 어두운 테마는 픽셀 차이 없음. CDP 검사(`impeccable detect --cdp`)로 밝은 테마 5개 화면 low-contrast 0건.

## Task 2: 오류 페이지 h1과 타이머 안내 글자 (F2, F3)

**파일:** `web/errors.py`, `templates/partials/timer.html`, `tests/web/test_errors.py`, `tests/web/test_timer_actions.py`

- **테스트 먼저(RED):**
  - 오류 페이지(브라우저 요청의 404 등)에 h1이 하나이고 글자가 "오류", class가 `visually-hidden`이며 `<main>`의 첫 요소인지.
  - 타이머 메모 칸의 placeholder가 "무엇을 하나요", title이 "태스크를 고르면 비워도 됩니다."인지(기존 placeholder 테스트를 고친다).
- **확인:** 대시보드 320·375 전후 스크린샷(안내 글자가 잘리지 않음), 오류 페이지 1280 전후(보이는 화면 그대로).

## Task 3: 문서와 마무리

- `docs/SPEC.md`: 디자인 토큰 또는 다크모드 부근에 밝은 `--accent` 값과 대비, 접근성 줄에 오류 페이지 h1, 타이머 문단에 안내 글자와 말풍선. 후속 항목의 "대시보드 기록 집중의 남은 것" 줄을 지운다.
- `docs/ROADMAP.md`: 항목 체크.
- 전체 검증: `uv run pytest`(timeout 600000으로 1회, 포트 8765가 비었는지 먼저 확인), `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy src/logbook/core`.
- `final-reviewer` 1회 → 지적 반영 → PR(develop) → "logbook QA" 세션에 자동 점검 인계.
- 사용자에게 알릴 것: 저장소 밖 `SCREENS.md`의 타이머 메모 안내 글자.

## 위험과 대응

| 위험 | 대응 |
|---|---|
| 강조색 변경이 사용자 지정 색·차트 색과 겹침 | `--accent`는 링크·포커스·주 버튼 전용이고 차트 팔레트(`CHART_PALETTE`)와 무관하다. 스크린샷으로 확인한다. |
| `title` 말풍선은 터치에서 안 보임 | D2와 같이 데스크톱 전용 도구라 받아들인다. 짧은 안내 글자만으로도 입력은 된다. |
