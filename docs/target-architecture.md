# Target Architecture (v2)

**This document is the source of truth for the project's direction.** The code in the repo today is v1. Docs that describe v1 have a banner that points here. If another doc contradicts this document, this document is correct. Fix the other doc.

Written 2026-09-30.

---

## Summary

```
 Game host (Windows now; Proton later is possible)     Any host (Windows / WSL / Linux)
┌─────────────────────────────┐   TCP, JSON lines   ┌──────────────────────────────┐
│ 1. Game Bridge              │   protocol v2       │ 2. Game Server               │
│    Civ V + Community Patch  │◄───────────────────►│    state model               │
│    DLL (C++), Lua popups    │   push events +     │    perception views          │
│    raw facts + commands     │   commands          │    real MCP server           │
└─────────────────────────────┘                     └──────────────┬───────────────┘
                                                          MCP      │
                                 ┌──────────────────┬──────────────┴───┐
                                 ▼                  ▼                  ▼
                           3. Agent: Pi       Claude Code         Codex
                           (default)          (comparison)        (comparison)
                           + agent workspace (instructions + memory files)

 4. Tooling (offline): scorecard, replay viewer, log analysis   ← reads Game Server logs
```

v1 had four Python processes and a custom agent loop. v2 has one Python process (the Game Server). The agent loop comes from existing harnesses.

---

## Decisions

Status: **Decided** = agreed; do not reopen without the user. **Proposed** = the recommended design, not yet confirmed. **Open** = unknown.

| # | Decision | Status | Reason |
|---|---|---|---|
| D1 | The game is **Civilization V** with the Community Patch DLL. Do not propose Unciv, Freeciv, or a custom game. | Decided | People know Civ V. "An LLM plays Civ V" means something. A clone or an invented game does not. |
| D2 | Development runs on the Windows host. **No VM** for now. | Decided | Civ V needs a real DirectX GPU. A VM makes development harder and gives nothing now. VMs or Proton containers are a possible later step for unattended runs. |
| D3 | Transport: **TCP** replaces the named pipe (localhost now; another host later). | Decided | The pipe forces the Python side onto the same Windows machine. It cannot cross machines, VMs, or the Wine/Proton boundary. Many games need many game hosts, so pipes cannot scale. See [TCP feasibility](#tcp-feasibility). |
| D4 | **Protocol v2**: versioned, handshake on connect, written spec, no `session_id`. The DLL sends raw facts only (no presentation). There is a push event for every state change. | Decided | The protocol is the contract between the game and everything else. |
| D5 | **Game Server** replaces the orchestrator. It is a **real MCP server**. Each tool is defined once, and clients get the schemas from `tools/list`. | Decided | The v1 "MCP" is a custom HTTP API. It needed the manual `_TOOLS` ↔ `schemas.py` sync. |
| D6 | The Game Server keeps a **state model** that push events update. It can also send **on-demand reads** to the DLL to confirm ground truth. | Decided | See [Push, not poll](#push-not-poll). |
| D7 | **Perception views** are designed as the human UI: top bar, city screen, map region, unit panel, diplomacy screen, "next action" list. `docs/information-gaps.md` is the spec. The ASCII map is removed. | Decided | The v1 ASCII map failed. The LLM could not see foreign units, gold, or happiness. |
| D8 | **No custom agent runtime.** The agents are existing harnesses. **Pi** is the default. **Claude Code** and **Codex** are for comparison. All connect to the Game Server through MCP. | Decided | These harnesses already do the loop, context compaction, and model support. Pi has built-in MCP (pi.dev, 2026). |
| D9 | **The LLM plays like a human.** The harness and the Game Server never make choices for it: no automatic skip or fortify, no automatic promotions. Nothing is mandatory (strategy, recaps, notes). Influence comes only from the instruction text. | Decided | Agency is part of the project. Autopilot hides units from the LLM. See `MODEL_WELFARE.md`. |
| D10 | **Turn delivery**: `end_turn` blocks until this player's next turn starts, then returns the next turn's briefing. One long harness session plays the whole game. | Proposed | This is push-based and needs no driver process. The harness does its own compaction. Risk: tool-call timeouts (see Open questions). |
| D11 | **Agent memory = files in the agent workspace**, written with the harness's own file tools. The workspace instruction file (`AGENTS.md` / `CLAUDE.md`) is the system prompt. The v1 journal tools are removed. | Proposed | All harnesses can do this already. There is no memory API to maintain. |
| D12 | **Game lifecycle automation** (start Civ, load a game, quit) is **not planned**. Games are started by hand. | Decided (for now) | The DLL loads only after the mod is enabled in the Mods menu. Possibly impossible, and it is not the largest problem. |
| D13 | **The observer is removed** (per-turn LLM analysis, halt, watchdog). The JSONL parsing (`observer/ledger.py`) can move into the tooling. | Decided | It checked harness health, not play quality, and it used polling. |
| D15 | **Heartbeat**: the DLL pushes a heartbeat (it already does, every 5 s). The Game Server treats silence longer than a timeout as "game stalled or gone" and pushes that to agents. The heartbeat is for liveness only; state comes from events. | Decided | TCP cannot detect a peer that hangs without closing the connection. The v1 server ignores heartbeats and also syncs the turn number from them, which hid missing events. |
| D16 | **Topology**: **one Game Server per game** (per DLL connection). Several agents in one game (hotseat) = several MCP sessions to that one server, each bound to one `player_id`. The server filters every view by that player's visibility (fog of war) and blocks each player's `end_turn` until that player's next turn. There is no central server for all games. | Proposed | One Civ V process = one game, and each game host runs one Civ V. A server per game keeps each state model simple and isolates crashes. Scale = more processes. A list of running games, if ever needed, is a small separate registry. |
| D14 | **Evaluation**: a per-game scorecard (cities, population, techs, demographics ranks at fixed turns) and a replay viewer made from the logs. | Decided | Without results, nothing shows that a change improved play. |

---

## Components

### 1. Game Bridge (C++ DLL + Lua)
- Evolve the existing DLL. Do not rewrite it.
- It is thin: it reports facts and runs commands. It does no formatting or summaries for the LLM.
- One command registry in `HandlePipeCommand()`. Lua is only for popups (see `docs/popups.md`).
- Protocol v2 spec: a JSON Schema for each message, a version number, and a `hello` handshake.

### 2. Game Server (Python, one process)
- **Transport**: a TCP listener on localhost. The DLL connects to it (the DLL is the client now, too).
- **State model**: push events update it. It has one owner and is the only cache.
- **Perception views**: builds human-UI views from the state model. The views are the product.
- **MCP**: a Streamable HTTP MCP server. Tools = views + commands. One definition per tool.
- **Logging**: per-game JSONL (continues from v1).

### 3. Agent (existing harness + workspace)
- A workspace directory for each agent: an instruction file (rules, how to play, turn-0 text) + memory files that the agent owns.
- An MCP config for each harness that points at the Game Server.
- Pi is the default. Claude Code and Codex use the same workspace and change only the instruction file name.

### 4. Tooling (offline)
- **Scorecard**: JSONL + demographics → a results table for each game.
- **Replay viewer**: v1 `dashboard.py` becomes a viewer that reads the logs.
- **Log analysis**: `analyze_logs.py` stays if it is useful.

---

## Push, not poll

"Polling" means a timed loop that asks for state that may have changed. It stays banned.

These are **not** polling, and they are allowed:
- an on-demand read to the DLL while the Game Server answers a tool call (for example, to confirm ground truth before it returns a view)
- an on-demand read after a reconnect, to rebuild the state model
- the DLL's heartbeat (D15). It is pushed, not requested. It carries liveness only, and no state must be taken from it.

Heartbeat detail: the DLL sends the heartbeat from the game's main thread (`GameStatePipe::ProcessCommands`). If the main thread is busy (for example, a long AI turn), heartbeats stop. So the DLL must push an event when it starts and ends long work (for example `ai_turns_started` / `ai_turns_ended`). The server can then tell "busy" from "hung", and the timeout applies only when the game is not busy.

---

## TCP feasibility

TCP is not blocked by the DLL. The named pipe was a choice, not a requirement.

- The DLL is already the **client**. It opens the pipe with `CreateFileA` and does `ReadFile` / `WriteFile` on a worker thread (`GameStatePipe.cpp:374`, `:622`). A Winsock client socket fits the same design: `connect` / `recv` / `send` on the same thread.
- Winsock is a normal Windows DLL (`ws2_32.dll`). Any DLL can use it. Civ V multiplayer already uses networking.
- Changes: add `ws2_32.lib` to the linker inputs in the `.vcxproj`, and include `winsock2.h` **before** `windows.h`. This is the likely problem, because of the precompiled header `CvGameCoreDLLPCH.h` and the old v90 toolset.
- Connect to `127.0.0.1` only, so the firewall does not prompt.
- WSL2 forwards `localhost` from Windows to WSL, so the Game Server can run in WSL. Verify this on this machine.
- Wine/Proton implements Winsock, so the Proton path stays possible.

---

## Open questions

1. **Tool-call timeouts for a blocking `end_turn` (D10).** AI turns can take a minute or more late in the game. Find and set the timeout for each harness (Claude Code MCP tool timeout, Codex tool timeout, Pi). If a harness cannot wait that long, the fallback is a small driver that reacts to `turn_start` and prompts the harness (Pi RPC mode, or the headless resume mode of each CLI).
2. **Context over hundreds of turns.** The harness does its own compaction. Verify that the memory files and the instruction file are enough for the agent to stay oriented after compaction.
3. **Game lifecycle automation (D12).** Parked.
4. **Multiple agents in one game (D16).** After a single agent plays well. The DLL must give per-player visibility, so the server can filter views. Commands must act for the calling player, not only for the "active" player.
5. **How the DLL finds its Game Server.** With several games, each DLL needs a host:port. Options: a config file next to the mod, or an environment variable set by the launcher. The default stays `127.0.0.1` + a fixed port.

---

## v1 → v2 mapping

| v1 | v2 |
|---|---|
| Named pipe, `pipe_server.py` | TCP transport in the Game Server |
| `mcp_server.py` (`_TOOLS`), `mcp_http_server.py` | Game Server MCP tools + views |
| `agent_runtime/tools/schemas.py` | Removed (schemas come from MCP `tools/list`) |
| `agent_runtime/` runner, turn loop, model adapters | Removed (Pi / Claude Code / Codex) |
| `agent_runtime/briefing.py` | The "turn briefing" view, returned by `end_turn` |
| `agent_runtime/prompts/system_prompt.py` | The workspace instruction file |
| `agent_runtime/memory/journal.py` + journal tools | Workspace memory files |
| `observer/` | Removed. `ledger.py` can move into the tooling. |
| `orchestrator/dashboard.py` | Replay viewer |
| `orchestrator/map_renderer.py` (ASCII) | Removed |
| `launch.py` | Rewritten: Game Server + harness launch |
| Lua popup handlers | Kept |

## Build order

1. Protocol v2 spec + TCP transport (DLL, and a minimal Python listener).
2. Game Server: state model, MCP, first views (turn briefing, empire, units, cities, map region).
3. Agent workspace + Pi connection. Play a first game. Then Claude Code and Codex.
4. The remaining views from `docs/information-gaps.md`.
5. Tooling: scorecard, replay viewer.
6. Remove the v1 code (`agent_runtime/`, `observer/`, old orchestrator parts) when v2 has replaced each part.

## Do not
- Propose a game other than Civ V (D1).
- Add harness-side autopilot or mandatory agent steps (D9).
- Build a new custom agent loop or model adapters (D8).
- Add timed polling (see [Push, not poll](#push-not-poll)).
- Add features to v1 components that v2 replaces. Fix v1 only when something blocks you.
