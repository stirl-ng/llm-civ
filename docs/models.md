Model Backends
==============

OpenAI-Compatible Adapter
-------------------------

- Adapter: `OpenAIChat` in `python/agent_runtime/models/openai_adapter.py`.
- Supports OpenAI and compatible servers via `base_url` (Azure, vLLM, Ollama with OpenAI API shim).

Config
------

- In config (`backend`):
  - `kind`: `openai`
  - `model`: model name (required)
  - `api_key`: optional if server requires
  - `base_url`: optional; set for compatible servers (e.g., `http://localhost:11434/v1` for Ollama)

- Or via env vars:
  - `OPENAI_MODEL`, `OPENAI_API_KEY`, `OPENAI_BASE_URL`

Example
-------

- `python -m experiments.run --config python/configs/experiments/openai.yaml --dry-run`
- Or orchestrator: `python -m orchestrator --agent-config python/configs/experiments/openai.yaml`

Install
-------

- Requires `openai` Python package (already listed in `python/requirements.txt`).
- Provide `OPENAI_API_KEY` for OpenAI; for local compat servers, set `OPENAI_BASE_URL` and use appropriate `model`.

