# Information Gaps

What a human player can see in the Civ V UI, compared with what the LLM can see.

**This is the spec for the v2 Game Server perception views** (D7 in [`target-architecture.md`](target-architecture.md)). The **Tool** and **Brief** columns describe v1 (`schemas.py`, `briefing.py`). In v2, each row becomes data in a view. The **DLL** column shows what the Game Bridge must provide.

Audited 2026-09-30 against `CvGame.cpp::HandlePipeCommand`, `mcp_server._TOOLS` / `_PLACEHOLDER_TOOLS`, `schemas.py`, `briefing.py`, and responses in `python/logs/game_598630335.jsonl`.

**Columns**
- **DLL**: the C++ emits the data.
- **Tool**: the LLM can get the data through a tool in `schemas.py`.
- **Brief**: the turn briefing shows the data without a tool call.

`yes` = present. `no` = absent. `partial` = see the note.

---

## The DLL has it, v1 does not expose it

| Command | What it returns | Why it is hidden |
|---|---|---|
| `get_player_status` | gold + per turn, happiness excess / empire unhappy, golden age progress / threshold / turns left, culture + next policy cost, faith, science, trade routes used / available | Listed in `_PLACEHOLDER_TOOLS` as "not yet implemented" (incorrect) |
| `get_demographics` | rankings (population, food, production, gold, land, military, approval, literacy) with best / worst / average | Not referenced in the orchestrator |
| `unit_ranged_attack` | action | Not in `_TOOLS` or `schemas.py` |
| `unit_pillage` | action | Not in `_TOOLS` or `schemas.py` |
| `unit_auto_explore` | action | Not in `_TOOLS` or `schemas.py` |
| `unit_delete` | action | Not in `_TOOLS` or `schemas.py` |
| `trade_respond` | action (answer an AI trade offer) | Not in `_TOOLS` or `schemas.py` |

In 58 turns, the LLM never saw its gold, happiness, or culture.

---

## Empire (top bar)

| Info | DLL | Tool | Brief | Note |
|---|---|---|---|---|
| Gold, gold per turn | yes | no | no | `get_player_status` |
| Happiness / unhappiness | yes | no | no | `get_player_status` |
| Golden age progress | yes | no | no | `get_player_status` |
| Science per turn | yes | no | no | `get_player_status` |
| Culture, turns to next policy | yes | partial | no | `get_available_policies` has culture + cost |
| Faith | yes | no | no | `get_player_status` |
| Strategic / luxury resource counts | no | no | no | `get_resources` is a placeholder |
| Score, rank against rivals | partial | no | no | `get_demographics` has rankings; no score |
| Victory progress | no | no | no | `get_victory_progress` is a placeholder |
| Era, turn date | partial | no | no | `turn_string` is in `get_player_status` |

## Cities

| Info | DLL | Tool | Brief | Note |
|---|---|---|---|---|
| Name, id, position, population | yes | yes | partial | Briefing has no position |
| Current production + turns | yes | yes | yes | |
| Food stored / threshold / turns to growth | yes | yes | no | In `get_cities`; the briefing drops it (also in `todo.md`) |
| Yields per turn (food, prod, gold, sci, culture, faith) | yes | yes | no | `*_times100` fields; the LLM must divide by 100 |
| City strength | yes | yes | no | |
| City HP / damage | ? | no | no | Not seen in responses |
| Built buildings | ? | no | no | Not seen in responses |
| Worked tiles, specialists | no | no | no | |
| Border growth (turns to next tile) | no | no | no | |
| Buy with gold | no | no | no | No purchase command |

## Units

| Info | DLL | Tool | Brief | Note |
|---|---|---|---|---|
| Type, id, position | yes | yes | yes | |
| Moves left, HP, XP, level | yes | yes | no | |
| Activity / mission | yes | yes | no | Added 2026-05-28; the briefing does not show it, so the LLM cannot see which units are idle |
| Territory / trespass / embarked | yes | yes | no | Added 2026-05-28 |
| Promotion ready / available promotions | yes | yes | partial | `get_unit_promotions`, `promote_unit`, `end_turn` `promotion_units[]` (STI-9). The briefing marks units that can promote; it does not list the choices |
| **Foreign units** (barbarians, rivals) | no | no | no | `get_map_view` shows only our units. The LLM cannot see threats. |

## Map

| Info | DLL | Tool | Brief | Note |
|---|---|---|---|---|
| Terrain, feature, hills, river | yes | yes | no | |
| Resource + quantity | yes | yes | no | |
| Improvement, route, pillaged | yes | yes | no | |
| Tile owner | yes | yes | no | Only the `owner_id` number, without a civ name |
| Fog / visible | yes | yes | no | |
| **Tile yields** | no | no | no | Also in `issues.md` |
| **Foreign cities** | no | no | no | Only our cities come from `get_cities` |
| **City site quality** | no | no | no | `CvPlayer::GetBestSettlePlot`, `CvCitySiteEvaluator::PlotFoundValue` exist and are not exposed |
| Output format | | | | `get_map_view` returns the ASCII grid **and** structured `tiles`. The ASCII does not have coordinates and costs about 9k chars. Remove it and keep `tiles`. |

## Other civs and diplomacy

| Info | DLL | Tool | Brief | Note |
|---|---|---|---|---|
| Known civs and city-states | no | no | no | `get_diplomacy` is a placeholder |
| War / peace status | no | no | no | |
| AI opinion / approach | no | no | no | |
| City-state friendship, quests | no | no | no | |
| Diplomatic messages, war warnings | yes | partial | partial | Arrive as notifications |

## Research, policies, religion

| Info | DLL | Tool | Brief | Note |
|---|---|---|---|---|
| Current research, available techs | yes | yes | yes | |
| What a tech unlocks | no | no | no | The LLM chooses techs by name only |
| Full tech tree | no | no | no | `get_tech_tree` is a placeholder |
| Policies adoptable / adopted | yes | yes | no | |
| Pantheon / religion choices | yes | yes | no | |

## Pending decisions

| Info | DLL | Tool | Brief | Note |
|---|---|---|---|---|
| Idle units, idle cities, tech / policy due | partial | partial | partial | Idle cities are flagged. The other blockers show only after `end_turn` fails (47 of 101 calls in the last game). A human sees these in the "next action" button before trying to end the turn. |

---

## Turn briefing view: what to include

These are candidates for the view that `end_turn` returns (D10). Every item is information, not an instruction. The LLM still decides.

1. An empire line from `get_player_status`: gold (+/turn), happiness, science, culture to next policy, golden age.
2. City growth and yields in the existing city line.
3. Unit activity / moves in the existing unit line, so the LLM can see which units are idle.
4. Pending decisions from `get_turn_blockers`, listed before the LLM tries `end_turn`.
5. Visible foreign units near our territory.
