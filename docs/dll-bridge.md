# DLL ←→ Orchestrator Bridge Plan

This document replaces the previous placeholder and lays out a pragmatic plan for streaming Civ V state into the orchestrator and receiving actions back from Python services.

## Objectives
- Emit a dependable stream of framed JSON payloads that capture turn-level context plus targeted incremental updates.
- Accept low-latency action messages from the orchestrator without stalling the main game thread.
- Keep everything additive: the bridge must fail soft (no saves corrupted, no desyncs) if the external stack is offline.

## Architecture Overview

| Layer | Responsibilities |
| --- | --- |
| GameCore DLL (`CvGame`) | Produce structured state, enqueue outbound messages, surface action hooks. |
| Bridge Runtime (`GameStatePipe` → `LLMBridge`) | Maintain named-pipe connections, framing, back-pressure, logging. |
| Orchestrator (Python) | Consume state, invoke LLMs/agents, send actions. |

- **Transport**: Named pipe (`\\.\pipe\CivVPGameState` by default, overridable via `CIVV_PIPE`). Message framing is newline-delimited UTF-8 JSON to stay tooling-friendly.
- **Threads**: Keep Civ’s main thread free by queuing outbound messages and having a lightweight worker flush them. Inbound actions are posted to `CvDllContext::QueueGameMessage` so they run during normal update ticks.
- **Schema**:
  - `state.turn`: `{ turn:int, playersAlive:int, civsEver:int, summary:{ ... } }`
  - `state.snapshot`: coarse but deterministic data (city list, resources, diplo standings) emitted on demand.
  - `action.request`: orchestrator → DLL order (unit moves, research choices, etc.).

## Implementation Plan

### Phase 0 – Baseline Pipe (done now)
1. Embed `GameStatePipe` in `CvGame` (constructor/destructor + `SendTurnData` after `DoGameStarted` and every `doTurn`).
2. Emit minimal JSON so downstream tooling can confirm the plumbing.

### Phase 1 – Bridge Manager
1. Wrap `GameStatePipe` in an `LLMBridge` singleton that owns:
   - lock-free ring buffers for outbound/inbound messages,
   - a background flusher thread (Win32 handle + event).
2. Surface a small C API (`LLMBridge_Initialize`, `LLMBridge_Shutdown`, `LLMBridge_Send`, `LLMBridge_PollAction`).
3. Add logging to `%LOCALAPPDATA%\LLMCiv\llmbridge.log` with throttled error spam.

### Phase 2 – State Schema & Dispatch
1. Define JSON schema files (`schemas/state.turn.json`, `schemas/state.snapshot.json`) and keep them under `docs/schemas/`.
2. Implement serializers in the DLL:
   - Turn summary (already streaming).
   - Optional snapshot builder (triggered via hotkey or orchestrator request).
3. In orchestrator, author a `StateIngestor` module that validates payloads and fans them out to agents.

### Phase 3 – Action Intake
1. Allow orchestrator to push commands:
   - Named pipe message `{ "kind":"action.request", "id":"uuid", "payload":{...} }`.
   - Bridge enqueues to a thread-safe queue drained during `CvGame::update`.
2. Map high-level verbs to game APIs (e.g., `move_unit`, `choose_research`, `policy_pick`).
3. Return `{ "kind":"action.result", "id":... }` so orchestrator can correlate futures.

### Phase 4 – Reliability & Tooling
1. Add per-message sequence numbers and timestamps for replay/debug.
2. Expose a developer HUD panel (Lua) showing connection status and last action.
3. Ship a Python harness (`scripts/pipe_probe.py`) to smoke-test the bridge without launching Civ.

### Phase 5 – Testing & Release
1. Unit-test bridge serialization using GoogleTest (no game dependency).
2. Integration-test via automated hotseat save that runs 5 turns with orchestrator loopback.
3. Document build/run instructions in `docs/orchestrator.md`.

## Immediate Next Steps
1. Promote the current `GameStatePipe` helper into a reusable `LLMBridge` module (Phase 1).
2. Flesh out the JSON schema + orchestrator consumer (Phase 2).
3. Iterate on action intake once state streaming is stable.

This plan balances incremental delivery (you already have live turn data) with a clear path to a fully bidirectional bridge. Update this doc as milestones land.***
