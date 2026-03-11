# Repository Guidelines

## Project Structure & Module Organization
This repository is a multi-project workspace with four primary modules:
- `OpenSandbox/`: sandbox platform. Core backend is in `OpenSandbox/server/src`, with unit/integration tests in `OpenSandbox/server/tests` and cross-SDK E2E tests in `OpenSandbox/tests/`.
- `Pageindex/`: document indexing service. Core package is `Pageindex/pageindex`, entry scripts are `run_pageindex.py` and `server.py`, and sample test assets live in `Pageindex/tests/`.
- `mymanus/`: agent application (`main.py`, `server.py`, `agent.py`, `tools.py`) plus web UI in `mymanus/web/`.
- `ocr/`: OCR + retrieval service with code in `ocr/engine`, `ocr/utils`, and API entry in `ocr/server.py`.

## Build, Test, and Development Commands
Run commands from each module directory:
- `uv sync`: install dependencies (`mymanus/`, `ocr/`, `OpenSandbox/server/`, `OpenSandbox/tests/python/`).
- `uv run server.py`: start `mymanus` or `ocr` local API.
- `./start.sh`: start Pageindex web/API stack.
- `uv run python -m src.main`: run OpenSandbox server.
- `uv run pytest`: run Python tests (OpenSandbox server or Python E2E tests).
- `uv run pytest --cov=src --cov-report=html`: OpenSandbox server coverage report.
- `pnpm test` (in `OpenSandbox/tests/javascript/`): run JavaScript E2E tests.

## Coding Style & Naming Conventions
- Python: 4-space indentation, `snake_case` for functions/modules, `PascalCase` for classes, explicit type hints for new/changed code.
- OpenSandbox enforces Ruff (`uv run ruff check`, `uv run ruff format`) with max line length 100.
- JavaScript/TypeScript tests use ESLint (`pnpm run lint`).
- Keep scripts and API handlers small and composable; place shared helpers under each module’s `utils`/`services` package.

## Testing Guidelines
- Python tests follow `test_*.py`, `Test*`, and `test_*` naming.
- Add tests next to the affected module (`OpenSandbox/server/tests`, `OpenSandbox/tests/python/tests`).
- For web/API behavior changes, include at least one happy-path test and one failure-path test.

## Commit & Pull Request Guidelines
- Recent history favors short, direct summaries (often Chinese), e.g. `ocr性能优化`, `支持Zvec原生混合检索`.
- Preferred commit format: `<scope>: <summary>` (example: `ocr: 优化混合检索召回`).
- PRs should include: changed module(s), why the change is needed, commands run for validation, config/env changes, and screenshots for UI updates.

## Security & Configuration Tips
- Never commit secrets (`.env`, API keys, private tokens).
- Start from `.env.example` where available, and document any new environment variables in the target module README.
