# Repository Guidelines

## Project Structure & Module Organization
- `dll/`: C++ Civ V DLL mod sources and Visual Studio solution.
- `python/`: Orchestrator, client SDK, and examples.
- `schemas/`: JSON schemas for state and actions (`state.schema.json`, `actions.schema.json`).
- `docs/`: Design notes and troubleshooting.
- `tools/`: Dev scripts (format, lint, packaging).
- Root: `README.md`, `AGENTS.md`.

Note: This repo currently ships documentation; new code should follow the layout above.

## Build, Test, and Development Commands
- DLL build: Open `dll/CvGameCoreExpansion2.sln` in Visual Studio (toolset v120). Select Release | Win32, then Build.
- Python env: `py -3.11 -m venv .venv; .\.venv\Scripts\Activate.ps1; pip install -r python/requirements.txt`.
- Run orchestrator: From `python/`, `python -m orchestrator` (connects to `\\.\pipe\civv_llm`).
- Tests (Python): `pytest -q` in `python/`.
- Format (Python): `black .` (or `ruff format` if configured).
- Lint (C++): `clang-tidy` via `tools/run-clang-tidy.ps1` when available.

## Coding Style & Naming Conventions
- C++: C++14, 4-space indent, PascalCase types, camelCase methods/vars, UPPER_CASE constants. Prefer RAII; avoid raw new/delete.
- Python: PEP 8, 4-space indent, snake_case, type hints; docstrings for public APIs.
- JSON: snake_case keys (e.g., `turn`, `city_orders`, `unit`), minimal payloads, stable ordering for diffs.

## Testing Guidelines
- Python: `pytest` with 80%+ coverage. Unit tests in `python/tests/`; integration tests in `python/tests/integration/`.
- Schemas: Validate all I/O against `schemas/*.json`; reject unknown fields.
- In-game: For DLL changes, provide a short hotseat run log (≥100 turns) and note crashes or desyncs. Attach Python logs from `python/logs/`.

## Commit & Pull Request Guidelines
- Commits: Use Conventional Commits (`feat:`, `fix:`, `refactor:`, `docs:`, `test:`). Current history is informal—adopt this convention going forward.
- PRs: Include purpose, linked issues, repro/validation steps, and before/after notes. Add logs/screenshots for gameplay-impacting changes. Keep PRs focused and small.

## Security & Configuration Tips
- Pipe name: Default `\\.\pipe\civv_llm`; override with `CIVV_PIPE` env var.
- Validation: Never bypass the game’s legality checks; sanitize inbound JSON.
- Concurrency: Keep IO on a background thread; avoid blocking the main game loop.

