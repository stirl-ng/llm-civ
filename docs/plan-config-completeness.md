# Plan: Config Completeness

## Overview

Several values important to experiment behavior are hardcoded in source rather than settable per
experiment via YAML config. This plan wires them in and fixes one broken stub.

---

## Findings

### Issue 1 — `temperature=0.2` hardcoded

- **Location**: `run.py:303` — `model.generate(messages, tools=tools, temperature=0.2)`
- `openai_adapter.py` already passes `**kwargs` through to the API call, so it supports temperature.
- Fix: add `agent.temperature` to YAML; thread through `main()` → `run_game_loop()` → `run_turn()` → `generate()`.

### Issue 3 — `generate_reflection_prompt` / `update_knowledge_base` (CLAUDE.md warning is wrong)

- The CLAUDE.md gotcha warning says this function references `update_knowledge_base` which doesn't exist.
- **Actual state**: `briefing.py` correctly references `record_recap`, `update_strategy`, and
  `record_lesson` — all valid tools handled in `run.py`. The function is fine.
- Fix: remove the stale warning from `CLAUDE.md`. No code change needed.

### Issue 4 — `poll_interval` (already in config, just undeclared)

- `run.py` already reads `cfg.get("orchestrator", {}).get("poll_interval", 2.0)` — not hardcoded.
- The YAML files just don't declare it, so the 2.0 default is silently applied.
- Fix: add `poll_interval: 2.0` with a deprecation comment to all three YAML configs.
  (Will be fully removed once SSE push work is done.)

---

## New YAML Structure

```yaml
agent:
  temperature: 0.2      # LLM sampling temperature (0.0–2.0)

orchestrator:
  url: http://localhost:8765
  pipe: "\\.\pipe\civv_llm"
  poll_interval: 2.0    # DEPRECATED: unused once SSE push is in place
```

---

## Files to Change

| File | Change |
|---|---|
| `python/experiments/run.py` | Read `agent.temperature`; thread through |
| `python/configs/experiments/openai.yaml` | Add `agent:` section with temperature |
| `python/configs/experiments/gemini.yaml` | Same |
| `python/configs/experiments/minimal.yaml` | Add explicit `poll_interval` with deprecation note |
| `CLAUDE.md` | Remove stale warning about `update_knowledge_base` in Gotchas section |

---

## Step-by-Step Changes

### `run.py`

In `main()`, after loading config:

```python
agent_cfg = config.get("agent", {})
temperature = agent_cfg.get("temperature", 0.7)
```

Thread `temperature` into `run_game_loop()`:

```python
run_game_loop(
    model, base_url,
    temperature=temperature,
    ...
)
```

`run_game_loop()` signature: add `temperature: float = 0.7`.
Pass to `run_turn()`.

`run_turn()` signature: add `temperature: float = 0.7`.

In `run_turn()`, change the generate call:
```python
# was: model.generate(messages, tools=tools, temperature=0.2)
response = model.generate(messages, tools=tools, temperature=temperature)
```

### Config YAMLs

**`openai.yaml`** — add:
```yaml
agent:
  temperature: 0.7
```

**`gemini.yaml`** — add:
```yaml
agent:
  temperature: 0.7
```

**`minimal.yaml`** — add to `orchestrator:` section:
```yaml
orchestrator:
  ...
  poll_interval: 2.0  # DEPRECATED: will be removed with SSE push implementation
```

### `CLAUDE.md`

In the Gotchas section, remove:

> `generate_reflection_prompt()` in `briefing.py` references `update_knowledge_base` which does not exist — stale, needs fixing before use.

Replace with nothing (or optionally note that it was verified working as of this change).

---

## Verification

1. Change `temperature: 0.0` in config, run a turn — responses should be deterministic/repetitive
2. Run `python experiments/run.py minimal` — smoke test still passes with dummy model
3. Grep for `temperature=0.2` in codebase — should return no results
