# Testing the DLL

`python/dlltest/` is a pytest suite that drives the DLL directly over the pipe, with no LLM. Run it after every DLL change instead of letting an agent play. A full run takes about 30 seconds.

The harness takes the orchestrator's place on the pipe, so stop `launch.py` first; the harness refuses to start while another process owns the pipe.

## The loop

1. Build and deploy: `.\scripts\build-and-deploy.ps1` (close Civ V first; the game locks the DLL).
2. Start Civ V and go to **Mods → Next → Load Game → `dlltest_base`**.
   - The save must be loaded through **Mods**. Modded games save to `ModdedSaves\`, not `Saves\`; a save from `Saves\` loads without the mod and turns it off.
   - The "Continue your journey" screen closes by itself after about 2 seconds when the mod is running. If it waits for a click, the base-game DLL is loaded.
3. Run the suite from `python/`:

```bash
.venv/Scripts/python.exe -m pytest dlltest -v
```

4. Before the next run, reload the save. The write and turn tests change the game; the harness skips the snapshot and write tests, or stops, when it finds the game moved on.

First time on a machine: `.\scripts\install-test-saves.ps1` copies the test saves into `ModdedSaves\single\dlltest_*`.

## What runs

| Module | Marker | Needs the game | Checks |
|---|---|---|---|
| `test_coverage.py` | | no | Every `msgType` in `HandlePipeCommand()` has a test |
| `test_snapshots.py` | `snapshot` | fresh save | Read replies match `snapshots/<save>/*.json` |
| `test_commands.py` | `smoke` | yes | Each read answers with its type and keys; bad input gets an error with its `request_id`, and the DLL still answers a ping |
| `test_writes.py` | `smoke` | fresh save | Each write command, then a read-back of the game; commands the save cannot carry out are refused |
| `test_turns.py` | `smoke`, `soak` | yes | Ending a turn pushes the next `turn_start` and heartbeats keep coming |

Every reply and pushed event is also checked against `schemas/<type>.json` (JSON Schema). The schemas are the first draft of the protocol v2 message spec.

Useful options:

| Option | Effect |
|---|---|
| `-m smoke` / `-m snapshot` | Run only that group |
| `--soak-turns 20` | Also end 20 turns and report the turn where the DLL hangs or crashes |
| `--update-schemas` | Merge every message seen into its schema instead of checking it. Review the diff before committing |
| `--update-snapshots` | Rewrite the snapshots from this run. Commit them with the DLL change that caused them |
| `--connect-timeout 60` | Wait longer for the DLL to connect |

The run order is fixed in `conftest.py`: coverage, snapshots, reads, writes, turns.

## When something fails

- Each run logs the full exchange (requests, replies, events) to `python/logs/dlltest/game_<game_id>.jsonl`.
- The DLL's own log is `Documents/My Games/Sid Meier's Civilization 5/Logs/LLMCiv/game_state_pipe.log`.
- "The loaded game is not a known test save": load a `dlltest_*` save, or add the new save to `python/dlltest/saves.yaml`.
- "No connection": check that the mod's DLL is the one loaded. The pipe starts only after the load screen closes (`CvGame::DoGameStarted()`).
- A test marked `xfail` names a Linear issue for a known DLL bug. When the bug is fixed the test passes, `strict=True` then fails the run, and the mark comes off.

## Adding to it

- **New pipe command:** `test_coverage.py` fails until a test sends it. Add a read test to `test_commands.py` or a write test with a read-back to `test_writes.py`, then run once with `--update-schemas` and review the new schema.
- **New test save:** make it in a modded game, copy it to `python/dlltest/saves/<name>.Civ5Save`, and add its `game_id` and turn to `saves.yaml`. The harness prints the `game_id` of whatever game is loaded.
- **Tests that need a rare situation** (pantheon available, city capture, goody hut choice) need their own save; gate them on `game.save`.
