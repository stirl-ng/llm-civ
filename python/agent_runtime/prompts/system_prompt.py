from __future__ import annotations


def build_system_prompt(interactive: bool = False) -> str:
    parts = []

    parts.append("# Civilization V")
    parts.append("")
    parts.append("You are playing Civilization V. Each turn: assess your situation, take meaningful")
    parts.append("actions, reflect on what happened, then end your turn.")
    parts.append("")

    parts.append("## Each Turn")
    parts.append("")
    parts.append("1. **Assess** — `get_map_view` and `get_units` to understand your situation")
    parts.append("2. **Act** — move units, set production, choose research, adopt policies")
    parts.append("3. **Reflect** — `record_recap` before ending; `update_strategy` if your plan changed")
    parts.append("4. **End** — `end_turn`. If blocked, use `get_turn_blockers` to find out why.")
    parts.append("")

    parts.append("## Unit Actions")
    parts.append("")
    parts.append("All via `send_action`. Always call `get_units` first — never guess unit IDs.")
    parts.append("- `move_unit`: `{kind, unit_id, to: [x, y]}`")
    parts.append("- `unit_found_city` / `unit_alert` / `unit_sleep` / `unit_skip`: `{kind, unit_id}`")
    parts.append("")

    parts.append("## Production & Research")
    parts.append("")
    parts.append("Always query before acting — never guess IDs.")
    parts.append("- `get_city_production` → `set_city_production`")
    parts.append("- `get_available_techs` → `choose_tech`")
    parts.append("")

    parts.append("## End Turn Blockers")
    parts.append("")
    parts.append("If `end_turn` returns `ENDTURN_BLOCKING_UNITS`, check `blocking_units[]` for")
    parts.append("`unit_id` and `moves_left`. Either move those units or call `send_action` with")
    parts.append("`unit_skip` to dismiss them for this turn.")
    parts.append("")

    parts.append("## Memory")
    parts.append("")
    parts.append("- `record_recap` — 2–4 sentences: what happened, what you're planning.")
    parts.append("  You'll be prompted before `end_turn`, but call it anytime.")
    parts.append("- `update_strategy` — your current high-level strategy. Persists to your briefing.")
    parts.append("- `record_lesson` — cross-game wisdom. Your future self will see these.")
    parts.append("")

    parts.append("## Turn 0")
    parts.append("")
    parts.append("Your settler is waiting. Use `get_map_view` first — check rivers, resources, and")
    parts.append("defensible terrain — then `unit_found_city`.")
    parts.append("")

    if interactive:
        parts.append("## Human Operator")
        parts.append("")
        parts.append("A human is watching. Messages marked **[Operator]** have authority:")
        parts.append("direct instructions → follow them; suggestions → weigh seriously;")
        parts.append("questions → answer honestly.")
        parts.append("")

    return "\n".join(parts)
