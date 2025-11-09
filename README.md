# Civ V LLM Hotseat Bridge

This project is a working concept for enabling large language models (LLMs) to play **Civilization V** in hotseat mode.  
It replaces the stock `CvGameCore_Expansion2.dll` with a custom build that exports the game state to an external process (Python) and executes inbound JSON actions.  

The result: automated Civ players driven by an LLM, fully deterministic and hotseat-safe, without relying on fragile UI automation.

---

## Features

- **Deterministic state export**: Cities, units, tech, known tiles, diplomacy.
- **Action intake**: JSON commands for research, policies, city queues, unit movement, and combat.
- **IPC transport**: Windows named pipe (`\\.\pipe\civv_llm`).
- **Safe execution**: All actions validated against the game’s legality checks before applying.
- **Hotseat compatible**: No FireTuner or cheat tools required.
- **Extensible**: Designed for incremental rollout of features (policies, workers, diplomacy, etc.).

---

## Architecture

```

\[ Civ V DLL ]  <--->  \[ Named Pipe ]  <--->  \[ Python Orchestrator ]  <--->  \[ LLM ]

````

- **Custom DLL (C++)**  
  - Hooks into `CvPlayer::doTurn()`.  
  - Exports compact game state as JSON.  
  - Applies validated JSON actions received via the pipe.  
- **Pipe Server (C++ in DLL)**  
  - Background thread manages IO.  
  - Main game thread drains inbound queue during turn execution.  
- **Python Orchestrator**  
  - Runs a named-pipe server at `\\.\pipe\civv_llm` by default.  
  - Receives state snapshots.  
  - Prompts the LLM for next actions.  
  - Validates schema.  
  - Sends back JSON actions.

---

## Build Instructions (DLL)

1. Install **Civilization V SDK** from Steam.
2. Clone the official DLL source (BNW) or use the Community Patch Project (CPP) repo as reference.
3. Open the solution in **Visual Studio 2013** (or newer). See toolset notes below.
4. Add [RapidJSON](https://github.com/Tencent/rapidjson) to the project (header-only).
5. Implement the pipe server (`CreateNamedPipe`, overlapped IO) and the turn hooks as described in `CvPlayer::doTurn()`.
6. Build in **Release** mode.
7. Package as a mod with the custom DLL (see Firaxis documentation on DLL mods).
8. Enable the mod in Civ V and start a hotseat game.

---

## Visual Studio Toolset

- Default projects target the VS2013 toolset (`v120`) only as a fallback. You can override the toolset when building with newer Visual Studio/MSBuild.
- Recommended: use VS 2022 (v143) with Win32/Release.

Retarget options:

- MSBuild (no file edits):
  - `msbuild dll\\CvGameCoreExpansion2.sln /t:Build /p:Configuration=Release /p:Platform=Win32 /p:PlatformToolset=v143`
- Visual Studio IDE:
  - File > Open > Project/Solution… and open `dll\\CvGameCoreExpansion2.sln`.
  - If prompted, click “Retarget projects” and choose `v143` (or `v142`).
  - Or per‑project: Properties > General > Platform Toolset = `v143`.

If VS reports the solution as corrupt, close VS and delete the repo’s `.vs` folder, then open the solution directly (avoid “Open Folder”).

### Output paths and names

- DLL output: `dll\\bin\\Win32\\Release\\CvGameCore_Expansion2.dll`
- Harness output: `dll\\bin\\Win32\\Release\\LLMBridgeHarness.exe`
- Intermediates: under `dll\\obj\\<ProjectName>\\Win32\\Release\\`

Note: The DLL `TargetName` is set to `CvGameCore_Expansion2` to match Civilization V’s expected filename.

---

## Build Instructions (Python)

See `docs/orchestrator.md` for running the Python orchestrator scaffold (`python -m orchestrator`).

---

## JSON Schemas

### State (outbound from DLL)

```json
{
  "kind": "state",
  "data": {
    "turn": 42,
    "gold": 123,
    "cities": [
      {"id": 1, "name": "Capital", "pop": 5, "build": "UNIT_SETTLER"}
    ],
    "units": [
      {"id": 10, "type": "UNIT_WARRIOR", "x": 5, "y": 6, "hp": 100, "moves": 2}
    ]
  }
}
```

### Actions (inbound to DLL)

```json
{
  "kind": "actions",
  "data": {
    "research": "TECH_POTTERY",
    "policy": "POLICY_TRADITION",
    "city_orders": [{"city_id": 1, "order": "UNIT_WORKER"}],
    "unit": [
      {"id": 10, "cmd": "MOVE", "to": [6, 6]},
      {"id": 10, "cmd": "ATTACK", "target_unit": 12}
    ]
  }
}
```

---

## Development Roadmap

1. **Bootstrap**

   * Build DLL and confirm it loads in game.
   * Pipe server accepts connections.
2. **Export**

   * Serialize turn + gold only.
   * Verify Python receives data.
3. **Actions**

   * Support setting research + city production.
   * Add basic unit moves.
4. **Expand**

   * Add combat, promotions, workers, diplomacy.
5. **Stress Test**

   * 2 LLM civs + 1 human in hotseat.
   * Run 100 turns without crash.
6. **Refinement**

   * Enforce JSON schema.
   * Add logging and fallback heuristics.
