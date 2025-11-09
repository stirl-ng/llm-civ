DLL Bridge Overview

- Purpose: Provide a Civ V DLL-side bridge to the orchestrator via a Windows named pipe (`\\.\pipe\civv_llm` by default, overridable with `CIVV_PIPE`).
- Status: Initial scaffold with background IO, logging, and exported C API entry points.

Build

- Open `dll/CvGameCoreExpansion2.sln` in Visual Studio 2013 (toolset v120).
- Select `Release | Win32` and Build.
- Output: `dll/bin/Release/CvGameCoreExpansion2.dll`.

Key Components

- `LLMBridge` (C API):
  - `bool LLMBridge_Initialize()` – starts the bridge, spawns IO threads.
  - `void LLMBridge_Shutdown()` – stops IO and cleans up.
  - `bool LLMBridge_Send(const char* json_utf8)` – queues JSON to send.
  - `bool LLMBridge_IsConnected()` – returns pipe connection status.

- `NamedPipeClient`:
  - Background reader/writer threads; non-blocking to game loop.
  - Auto-reconnect with simple backoff; 1 MB message cap.
  - Basic JSON sanity checks (TODO: schema validation).

- Logging:
  - Appends to `%LOCALAPPDATA%\LLMCiv\llmbridge.log`.

Configuration

- `CIVV_PIPE`: override named pipe (e.g., `\\\\.\\pipe\\custom_pipe`).

Next Steps

- Schema validation against `schemas/state.schema.json` and `schemas/actions.schema.json`.
- In-game dispatch: translate inbound actions into Civ V game events.
- Robust error handling and metrics.
- Unit tests for message handling and queueing.

Harness (Optional)

- Project: `LLMBridgeHarness` builds a console app to exercise the bridge.
- Output: `dll/bin/Release/LLMBridgeHarness.exe`.
- Usage:
  - Client mode (default):
    - Start orchestrator: from `python/`, `python -m orchestrator`.
    - Run: `LLMBridgeHarness.exe` or override pipe via `--pipe \\.\\pipe\\civv_llm`.
    - Custom JSON: `--json '{"kind":"ping","source":"harness"}'`.
  - Server mode (loopback without orchestrator):
    - Terminal A (server): `LLMBridgeHarness.exe --server --pipe \\.\\pipe\\civv_llm`
    - Terminal B (client): `LLMBridgeHarness.exe --pipe \\.\\pipe\\civv_llm --json '{"kind":"ping"}'`
    - `--once` makes the server handle one client then exit.
