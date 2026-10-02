# Active Issues

These are known problems and pending work. Not a graveyard — remove entries when resolved.

---

## Unhandled popups
Some popups still block `end_turn`. See `docs/popups.md` for current status.

Intermittent "leaderboard" (Who's Winning) blocks were a stale installed `.modinfo`, fixed in STI-5. See the popups.md table.

---

## Human-gated choice popups

The LLM player is registered as human, so it gets the choice popups that the C++ shows only to `isHuman()` players. The AI resolves the same choices inline. Rule (D9 in `target-architecture.md`): send the options over the pipe, add a tool, and never auto-pick in Lua or C++.

Audit of `AddPopup` inside `isHuman()` branches in `CvPlayer.cpp` / `CvGame.cpp` (STI-6):

- `BUTTONPOPUP_CHOOSE_GOODY_HUT_REWARD` (`CvPlayer::doGoody`) — **done**: `choose_goody_hut_reward` tool; the old Lua auto-pick is gone.
- `BUTTONPOPUP_MODDER_9` (single-choice event result), `BUTTONPOPUP_MODDER_4` (victory randomization) — informational, not choices.
- `BUTTONPOPUP_CHOOSEPOLICY` in `CvGame::doControl` — opened by the policies-screen hotkey, not by the game; `adopt_policy` covers the choice.

Still open, outside that audit: choices that a **notification** opens (`CvNotifications::Activate`) and that block `end_turn` through the notification blocker, with no tool yet — free / faith great person (`BUTTONPOPUP_CHOOSE_FREE_GREAT_PERSON`, `_FAITH_GREAT_PERSON`), Maya bonus, archaeology, ideology, and player / city event choices (`NOTIFICATION_EVENT_CHOICE`, `BUTTONPOPUP_MODDER_10` / `_8`). Each needs its own tool.

---

## Notification timing / missed events
Notifications sometimes appear at the end of the turn that generated them but are only visible at the start of the next. A worker being killed may go unacknowledged because the LLM only sees the notification one turn late. Need a better notification delivery model — options include buffering pending notifications into the next turn's briefing explicitly, or including prior-turn notifications in the briefing with a "from last turn" label.

---

## Promotions not exposed
`get_available_promotions` and other promotion-related tools do not exist. Units that have enough XP to promote are likely blocking end_turn or being silently ignored.

---

## x/y coordinate correctness unverified across map types
Tile coordinates passed to and from tools (e.g. `move_unit`, `get_map_view`) have not been verified to be consistent across all map types and sizes. A mismatch between Lua, C++, and Python coordinate conventions could cause units to move to wrong tiles or tool calls to fail silently. Needs a deliberate test across at least two map sizes before coordinate-sensitive features are trusted.

---

## Per-tile yields missing from get_map_view
`get_visible_tiles` (C++) does not emit yield data per tile. `get_map_view` therefore cannot include `yields: {food, production, gold, ...}` in the `tiles` JSON it returns. To fix: extend the `get_visible_tiles` handler in `CvGame.cpp` to compute and emit yields for each plot (using `pPlot->calculateYield()` or similar), then surface them in the `tiles` array in `mcp_server._get_map_view`.

---

## Turn number mismatch on end_turn (v1)
In game 598630335, `end_turn` failed 5 times with "requested to end turn 20, but the current turn is 22" (`mcp_server.py:486`). The runner's turn number and the DLL's turn number are out of sync. Fix only if it blocks v1 testing. v2 must take the turn number from the state model.

---

## Superseded by the v2 redesign
These v1 issues are closed by [`target-architecture.md`](target-architecture.md), or no longer apply:

- **Multi-agent not yet supported**: Open question 4 (after a single agent plays well)
- **Tool schema bifurcation**: D5: the MCP server defines each tool once
- **System prompt is monolithic**: D11: the instruction file is the prompt
- **Cross-game lesson review not implemented**: D9/D11: no forced review; memory is agent-owned files
- **Interactive mode blocks unsupervised runs**: D8: the custom runner is removed
- **Multi-model config has no convention**: D8: harnesses handle models
- **session_id leaks into game-layer messages**: D4: protocol v2 removes session_id
- **LLM unaware of new tools**: D5: clients read MCP `tools/list`
- **Long-game context compression not implemented**: D10/D11: harness compaction + workspace files
- **unit-actions.md response schema unverified**: verified: `state_delta` is present in the logs of game 598630335
