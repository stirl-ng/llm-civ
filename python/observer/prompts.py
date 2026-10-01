"""Prompt templates for the observer LLM."""

from __future__ import annotations

import json
from .ledger import TurnRecord


def _format_blockers(blockers: list[dict]) -> str:
    if not blockers:
        return "none"
    parts = []
    for b in blockers:
        name = b.get("unit_name") or b.get("type", "?")
        uid = b.get("unit_id", "")
        x, y = b.get("x", "?"), b.get("y", "?")
        parts.append(f"{name} #{uid} at ({x},{y})")
    return ", ".join(parts)


def _format_args(args: dict) -> str:
    text = json.dumps(args, separators=(",", ":"))
    if len(text) > 120:
        text = text[:120] + "…"
    return text


def _known_issues_section(known_issues: dict | None) -> list[str]:
    if not known_issues:
        return []
    lines = [
        "",
        "## Known recurring issues (already on record — do not re-describe)",
        "For each axis listed below: write 'RECURRING (T{n}–T{m})' and only note new developments.",
        "If the issue has resolved this turn, write 'RESOLVED — No issues.'",
        "",
    ]
    for axis, info in known_issues.items():
        span = f"T{info['first_turn']}" if info['first_turn'] == info['last_turn'] else f"T{info['first_turn']}–T{info['last_turn']}"
        lines.append(f"**{axis}**: \"{info['summary'][:80]}\" — {span}, {info['count']} turn(s)")
    return lines


def build_turn_analysis_prompt(record: TurnRecord, game_summary: str, known_issues: dict | None = None) -> str:
    lines = [
        f"# Observer — Turn {record.turn}",
        "",
        "## Game so far",
        game_summary or "(first turn)",
        "",
        "## This turn",
        f"Outcome: **{record.outcome}** | {record.duration_seconds:.1f}s | "
        f"{len(record.iterations)} iterations | "
        f"{record.total_tool_calls} tool calls | **{record.total_errors} errors**",
        f"Blockers at start: {_format_blockers(record.blockers_at_start)}",
    ]

    if record.error_tools:
        from collections import Counter
        counts = Counter(record.error_tools)
        lines.append(f"⚠ Failed tools this turn: {', '.join(f'{t}×{n}' if n > 1 else t for t, n in counts.items())}")

    lines += [
        "",
        "Briefing sent to agent:",
        "```",
        record.briefing,
        "```",
        "",
        "## Turn trace",
    ]

    for it in record.iterations:
        lines.append(f"\n### Iteration {it.iteration}")
        if it.llm_text:
            preview = it.llm_text[:300].replace("\n", " ")
            if len(it.llm_text) > 300:
                preview += "…"
            lines.append(f"Agent: \"{preview}\"")
        else:
            lines.append("Agent: (no text)")
        if it.tool_calls:
            for tc in it.tool_calls:
                status = "ok" if tc.ok else "FAIL"
                lines.append(f"  - {tc.tool}({_format_args(tc.arguments)}) → {status}: {tc.result_summary}")
        else:
            lines.append("  (no tool calls)")

    lines += _known_issues_section(known_issues)

    lines += [
        "",
        "## Analyze on four axes",
        "",
        "**HARNESS** — pipe/timing/metadata/event-ordering issues?",
        "**PROMPT** — agent confusion, repetition, briefing gaps, missing context?",
        "**MOD** — incomplete or wrong DLL responses, missing fields, incorrect game state?",
        "**MCP TOOLS** — missing tools, bad interfaces, misleading error messages, redundant calls?",
        "",
        "For each axis: write one sentence. Say \"No issues.\" if nothing stands out.",
        "Cite iteration numbers when relevant.",
        "If there were failed tool calls this turn, you MUST address them — do not write 'No issues' for the relevant axis.",
        "",
        "## Halt decision",
        "",
        "Should we HALT the game now to fix something critical before continuing?",
        "Answer YES or NO on the first line.",
        "If YES: one sentence explaining exactly what needs fixing and which axis.",
        "Rules:",
        "- Only YES for issues that will recur every turn without a code/prompt fix.",
        "- Do NOT halt on a successful turn unless the SAME issue is already listed in the known_issues section (i.e., it has recurred across multiple turns). A first-time failure the agent recovered from is not halt-worthy.",
        "- Do NOT halt if the agent self-corrected within this turn (retried and succeeded).",
        "- `end_turn` returning CANNOT_END_TURN can be normal — the agent is expected to clear blockers and retry. This is NOT a harness issue unless it fails even after blockers are cleared.",
        "- Do NOT halt for minor inefficiency (extra tool calls, redundant checks).",
    ]

    return "\n".join(lines)


def build_stuck_turn_prompt(record: TurnRecord, game_summary: str, elapsed_seconds: float, known_issues: dict | None = None) -> str:
    lines = [
        f"# Observer — Turn {record.turn} (STUCK, {elapsed_seconds:.0f}s elapsed)",
        "",
        "## Game so far",
        game_summary or "(first turn)",
        "",
        "## This turn so far",
        f"Still running | {elapsed_seconds:.0f}s elapsed | "
        f"{len(record.iterations)} iterations | "
        f"{record.total_tool_calls} tool calls ({record.total_errors} errors)",
        f"Blockers at start: {_format_blockers(record.blockers_at_start)}",
        "",
        "Briefing sent to agent:",
        "```",
        record.briefing,
        "```",
        "",
        "## Turn trace (partial — turn still running)",
    ]

    for it in record.iterations:
        lines.append(f"\n### Iteration {it.iteration}")
        if it.llm_text:
            preview = it.llm_text[:300].replace("\n", " ")
            if len(it.llm_text) > 300:
                preview += "…"
            lines.append(f"Agent: \"{preview}\"")
        else:
            lines.append("Agent: (no text)")
        if it.tool_calls:
            for tc in it.tool_calls:
                status = "ok" if tc.ok else "FAIL"
                lines.append(f"  - {tc.tool}({_format_args(tc.arguments)}) → {status}: {tc.result_summary}")
        else:
            lines.append("  (no tool calls)")

    lines += _known_issues_section(known_issues)

    lines += [
        "",
        "## Analyze on four axes",
        "",
        "This turn has exceeded the expected time limit and has not yet called end_turn.",
        "Based on what you see, diagnose why it may be stuck or looping.",
        "",
        "**HARNESS** — pipe/timing/metadata/event-ordering issues?",
        "**PROMPT** — agent confusion, repetition, briefing gaps, missing context?",
        "**MOD** — incomplete or wrong DLL responses, missing fields, incorrect game state?",
        "**MCP TOOLS** — missing tools, bad interfaces, misleading error messages, redundant calls?",
        "",
        "For each axis: write one sentence. Say \"No issues.\" if nothing stands out.",
        "Cite iteration numbers when relevant.",
        "",
        "## Halt decision",
        "",
        "Should we HALT the game now to fix something critical before continuing?",
        "Answer YES or NO on the first line.",
        "If YES: one sentence explaining exactly what needs fixing and which axis.",
        "Rules:",
        "- Only YES for issues that will recur every turn without a code/prompt fix.",
        "- Do NOT halt if the agent self-corrected within this turn (retried and succeeded).",
        "- `end_turn` returning CANNOT_END_TURN due to blocking units is normal — the agent is expected to move those units and retry. This is NOT a harness issue unless it fails even after blockers are cleared.",
        "- Do NOT halt for minor inefficiency (extra tool calls, redundant checks).",
    ]

    return "\n".join(lines)


_QUERY_TOOLS = [
    "get_game_state",
    "get_cities",
    "get_city_production",
    "get_units",
    "get_notifications",
    "get_visible_tiles",
    "get_map_view",
    "get_reachable_tiles",
    "get_unit_build_options",
    "get_available_techs",
    "get_available_policies",
    "get_turn_blockers",
]

_LARGE_FIELDS = {"tiles", "map", "map_raw"}


def _format_result(result: dict, max_value_len: int = 400) -> str:
    """Format a tool result, replacing huge list fields with a count."""
    slim: dict = {}
    for k, v in result.items():
        if k in _LARGE_FIELDS and isinstance(v, list):
            slim[f"{k}_count"] = len(v)
        else:
            slim[k] = v
    text = json.dumps(slim, indent=2)
    if len(text) > max_value_len:
        text = text[:max_value_len] + "\n…"
    return text


def build_chatbot_prompt(messages: list[dict], question: str, available_tool_names: list[str] | None = None) -> str:
    """Build a prompt for the chatbot to answer a developer's debugging question."""
    if available_tool_names is None:
        available_tool_names = _QUERY_TOOLS

    briefing = ""
    turn_num = None
    current_iteration = 0
    iterations_map: dict[int, dict] = {}  # iteration -> {llm_text, tool_calls}

    for msg in messages:
        mtype = msg.get("type")
        if mtype == "turn_start":
            turn_num = msg.get("turn")
        elif mtype == "turn_start_messages":
            briefing = msg.get("briefing", "")
        elif mtype == "iteration_start":
            n = msg.get("iteration", current_iteration + 1)
            current_iteration = n
            iterations_map.setdefault(n, {"llm_text": "", "tool_calls": []})
        elif mtype == "llm_response":
            n = current_iteration or 1
            iterations_map.setdefault(n, {"llm_text": "", "tool_calls": []})
            iterations_map[n]["llm_text"] = msg.get("response", "") or ""
        elif mtype == "tool_result":
            n = msg.get("iteration", current_iteration or 1)
            iterations_map.setdefault(n, {"llm_text": "", "tool_calls": []})
            iterations_map[n]["tool_calls"].append({
                "tool": msg.get("tool", "?"),
                "arguments": msg.get("arguments", {}),
                "result": msg.get("result", {}),
                "ok": msg.get("ok", True),
            })

    called_tools = {
        tc["tool"]
        for it in iterations_map.values()
        for tc in it["tool_calls"]
    }
    not_called = [t for t in available_tool_names if t not in called_tools]

    lines = [f"# Agent trace — Turn {turn_num}"]

    if briefing:
        lines += ["", "## Briefing sent to agent", "```", briefing.strip(), "```"]

    lines += ["", "## Turn trace (so far)"]
    for n in sorted(iterations_map):
        it = iterations_map[n]
        lines.append(f"\n### Iteration {n}")
        text = it["llm_text"].strip()
        if text:
            lines.append(f"Agent reasoning:\n{text}")
        else:
            lines.append("Agent reasoning: (none)")
        if it["tool_calls"]:
            for tc in it["tool_calls"]:
                status = "ok" if tc["ok"] else "FAIL"
                args_text = json.dumps(tc["arguments"], separators=(",", ":"))
                if len(args_text) > 120:
                    args_text = args_text[:120] + "…"
                result_text = _format_result(tc["result"])
                lines.append(f"\n  {tc['tool']}({args_text}) → {status}")
                lines.append(f"  Result: {result_text}")
        else:
            lines.append("  (no tool calls)")

    lines += [
        "",
        "## Information the agent has NOT retrieved this turn",
    ]
    if not_called:
        lines.append("These query tools were not called — so the agent does not have this data:")
        for t in not_called:
            lines.append(f"  - {t}")
    else:
        lines.append("All standard query tools were called at least once.")

    lines += ["", "---", "", f"Question: {question}"]

    return "\n".join(lines)


def build_game_recommendations_prompt(
    records: list[TurnRecord],
    per_turn_observations: list[str],
    game_id: int | None,
) -> str:
    total_turns = len(records)
    total_tools = sum(r.total_tool_calls for r in records)
    total_errors = sum(r.total_errors for r in records)
    outcomes = {}
    for r in records:
        outcomes[r.outcome] = outcomes.get(r.outcome, 0) + 1

    from collections import Counter
    error_tool_counts = Counter(t for r in records for t in r.error_tools)
    top_errors = error_tool_counts.most_common(10)

    lines = [
        f"# End-of-Game Observer Report — game_id {game_id}",
        "",
        "## Aggregate stats",
        f"Turns: {total_turns} | Tool calls: {total_tools} | Errors: {total_errors} "
        f"({100 * total_errors // max(total_tools, 1)}% error rate)",
        f"Outcomes: {', '.join(f'{k}: {v}' for k,v in outcomes.items())}",
    ]

    if top_errors:
        lines += [
            "",
            "Most-failed tools:",
            *[f"  - {tool}: {count} failures" for tool, count in top_errors],
        ]

    lines += [
        "",
        "## Per-turn observations",
        "",
    ]
    for i, obs in enumerate(per_turn_observations):
        turn_num = records[i].turn if i < len(records) else i
        lines.append(f"### Turn {turn_num}")
        lines.append(obs)
        lines.append("")

    lines += [
        "## Your task",
        "",
        "Synthesize the per-turn observations into a prioritized recommendations document.",
        "Organize by the four axes: HARNESS, PROMPT, MOD, MCP TOOLS.",
        "Under each axis, list findings from most to least impactful.",
        "Be specific: name the tool, prompt section, DLL message type, or code path.",
        "Skip axes with no actionable findings.",
    ]

    return "\n".join(lines)
