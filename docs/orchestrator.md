Orchestrator
============

Bridges the Civ V DLL (named pipe) and the Agent runtime. Reads state JSON lines, validates against `schemas/state.schema.json`, calls the agent, validates actions against `schemas/actions.schema.json`, then writes action JSON lines back.

Run
---

- With pipe (default `\\.\pipe\civv_llm` or `CIVV_PIPE`):
  - `python -m orchestrator --agent-config python/configs/experiments/minimal.yaml`

- With stdio (for testing without the game):
  - `python -m orchestrator --stdio --once --agent-config python/configs/experiments/minimal.yaml`
  - Then paste one line of JSON matching `state.schema.json`; the orchestrator outputs one line of actions.

Config
------

- Reuses the experiment config shape for `backend`, `tools`, and `strategy`.
- Pipe can be set via config `orchestrator.pipe` or `CIVV_PIPE` env var.

Notes
-----

- Windows named pipes can be opened by Python as a binary file; the orchestrator retries connect for up to ~30s.
- On validation failure, the orchestrator returns a no-op action with error notes to keep the game loop safe.

