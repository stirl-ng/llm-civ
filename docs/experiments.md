Experiments: Models x Tools x Strategies
=======================================

This repo supports running controlled experiments that swap model backends, tool suites (RAG/Web/MCP), and decision strategies.

Quickstart
----------

- Create venv and install deps:
  - `py -3.11 -m venv .venv`
  - `.\.venv\Scripts\Activate.ps1`
  - `pip install -r python/requirements.txt`

- Dry run the experiment runner (no game needed):
  - `python -m experiments.run --config minimal --dry-run`
  - Or use full path: `python -m experiments.run --config python/configs/experiments/minimal.yaml --dry-run`

- Live run (wired to orchestrator/pipe):
  - Start the orchestrator: `cd python && python -m orchestrator`
  - Build and enable the DLL mod in Civ V (BNW).
  - Run: `python -m experiments.run --config minimal`
  - Or use short names: `python -m experiments.run --config gemini`

Config Schema
-------------

- Schema: `python/schemas/experiment.schema.json`
- Key sections:
  - `backend`: model adapter (`kind: dummy` for offline testing).
  - `tools`: list of tools (`kind: rag|web|mcp`) with per-tool params.
  - `strategy`: decision policy (`name: vanilla`, `temperature`).
  - `orchestrator.pipe`: named pipe (defaults to `\\.\pipe\civv_llm`).

Extending
---------

- Models: add a new adapter under `python/agent_runtime/models/` and register it in `registry.py`.
- Tools: implement `Tool` in `python/agent_runtime/tools/` and add to `registry.py`.
- Strategies: implement in `python/agent_runtime/strategies/` and expose via `experiments/run.py`.

Testing
-------

- Run `pytest -q` from `python/`.

Notes
-----

- The `dummy` model and tool stubs keep tests deterministic and offline.
- Real backends (OpenAI/Azure/HF/Ollama), RAG stores, and MCP should be added behind the same interfaces without changing the orchestrator.

