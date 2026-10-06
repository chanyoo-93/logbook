# logbook

개인 소프트웨어 개발자를 위한 업무 기록·공수 집계·주간업무보고서 생성 도구입니다.

- 상세 요구사항: [docs/SPEC.md](docs/SPEC.md)
- 구현 순서: [docs/ROADMAP.md](docs/ROADMAP.md)

## 개발

[uv](https://docs.astral.sh/uv/)가 필요합니다. 아래 명령은 Windows(PowerShell)와 macOS(zsh)에서 똑같이 실행됩니다.

```
uv sync                       # 의존성 설치
uv run lb --help              # CLI 실행
uv run pytest                 # 테스트
uv run ruff check .           # 린트
uv run ruff format .          # 포맷
uv run mypy src/logbook/core  # 타입 체크
```
