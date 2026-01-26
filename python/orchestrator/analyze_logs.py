"""Post-game log analysis for LLM Civ V sessions.

Parses JSONL logs and generates analysis to identify:
1. Where LLM struggles (repeated failures, high tool-call-to-progress ratio)
2. Missing features (not_implemented errors, unknown tools)
3. Error patterns grouped by type

Run: python -m orchestrator.analyze_logs [--game-id ID] [--output json|text]
"""

import argparse
import json
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


LOG_DIR = Path(__file__).parent.parent / "logs"


@dataclass
class TurnStats:
    """Stats for a single turn."""
    turn: int = 0
    tool_calls: int = 0
    tool_errors: int = 0
    llm_requests: int = 0
    tokens_used: int = 0
    blockers_at_start: list = field(default_factory=list)
    blockers_at_end: list = field(default_factory=list)
    duration_seconds: float = 0.0
    first_timestamp: datetime | None = None
    last_timestamp: datetime | None = None
    # For stuck detection
    end_turn_attempts: int = 0
    tool_sequence: list = field(default_factory=list)  # [(tool_name, args_hash), ...]


@dataclass
class AnalysisResult:
    """Complete analysis result."""
    game_id: int
    total_turns: int
    total_tool_calls: int
    total_tool_errors: int
    total_llm_requests: int
    total_tokens: int
    duration_minutes: float

    # Tool-level stats
    tool_counts: dict[str, int] = field(default_factory=dict)
    tool_errors: dict[str, list[str]] = field(default_factory=dict)
    tool_success_rate: dict[str, float] = field(default_factory=dict)

    # Error analysis
    error_categories: dict[str, int] = field(default_factory=dict)
    unique_errors: list[dict] = field(default_factory=list)

    # Struggle detection
    stuck_turns: list[dict] = field(default_factory=list)  # Turns with high tool calls but no progress
    repeated_failures: list[dict] = field(default_factory=list)  # Same error multiple times

    # Per-turn breakdown
    turn_stats: list[TurnStats] = field(default_factory=list)

    # Feature gaps
    missing_features: list[str] = field(default_factory=list)
    unknown_tools: list[str] = field(default_factory=list)


def parse_timestamp(ts_str: str) -> datetime | None:
    """Parse ISO timestamp from log."""
    if not ts_str:
        return None
    try:
        return datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
    except ValueError:
        return None


def categorize_error(error_msg: str) -> str:
    """Categorize an error message into a bucket."""
    error_lower = error_msg.lower()

    if "not implemented" in error_lower or "not_implemented" in error_lower:
        return "not_implemented"
    if "unknown" in error_lower and "tool" in error_lower:
        return "unknown_tool"
    if "unit" in error_lower and ("moves" in error_lower or "movement" in error_lower):
        return "unit_movement"
    if "blocked" in error_lower or "blocker" in error_lower:
        return "turn_blocked"
    if "invalid" in error_lower:
        return "invalid_parameter"
    if "not found" in error_lower:
        return "not_found"
    if "timeout" in error_lower:
        return "timeout"
    if "connection" in error_lower or "pipe" in error_lower:
        return "connection"

    return "other"


def analyze_game(game_id: int) -> AnalysisResult | None:
    """Analyze a single game's logs."""
    log_file = LOG_DIR / f"game_{game_id}.jsonl"

    if not log_file.exists():
        print(f"Error: Log file not found: {log_file}", file=sys.stderr)
        return None

    messages = []
    with open(log_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                messages.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    if not messages:
        print(f"Error: No valid messages in log file", file=sys.stderr)
        return None

    # Initialize result
    result = AnalysisResult(
        game_id=game_id,
        total_turns=0,
        total_tool_calls=0,
        total_tool_errors=0,
        total_llm_requests=0,
        total_tokens=0,
        duration_minutes=0.0,
    )

    # Track per-turn stats
    turns: dict[int, TurnStats] = defaultdict(TurnStats)

    # Track tool calls and errors
    tool_calls: dict[str, int] = defaultdict(int)
    tool_successes: dict[str, int] = defaultdict(int)
    tool_error_msgs: dict[str, list[str]] = defaultdict(list)

    # Track all errors for deduplication
    all_errors: list[dict] = []
    error_counts: dict[str, int] = defaultdict(int)

    # Track timestamps
    first_ts = None
    last_ts = None

    for msg in messages:
        msg_type = msg.get("type", "")
        turn = msg.get("turn", 0)
        ts = parse_timestamp(msg.get("timestamp", ""))

        if ts:
            if first_ts is None:
                first_ts = ts
            last_ts = ts

        # Initialize turn stats
        if turn not in turns:
            turns[turn] = TurnStats(turn=turn)
        turn_stat = turns[turn]

        if ts:
            if turn_stat.first_timestamp is None:
                turn_stat.first_timestamp = ts
            turn_stat.last_timestamp = ts

        # Track turn start blockers
        if msg_type == "turn_start":
            blockers = msg.get("blockers", [])
            turn_stat.blockers_at_start = [b.get("type", "?") for b in blockers]

        # Track LLM requests
        if msg_type == "llm_request":
            result.total_llm_requests += 1
            turn_stat.llm_requests += 1

        # Track tokens
        if msg_type == "llm_response":
            tokens = msg.get("total_tokens", 0) or 0
            result.total_tokens += tokens
            turn_stat.tokens_used += tokens

        # Track tool responses
        if msg_type == "tool_response":
            tool_name = msg.get("tool", "unknown")
            tool_result = msg.get("result", {})
            tool_args = msg.get("arguments", {})

            result.total_tool_calls += 1
            turn_stat.tool_calls += 1
            tool_calls[tool_name] += 1

            # Track end_turn attempts
            if tool_name == "end_turn":
                turn_stat.end_turn_attempts += 1

            # Track tool sequence for loop detection (hash args for comparison)
            args_hash = hash(json.dumps(tool_args, sort_keys=True, default=str))
            turn_stat.tool_sequence.append((tool_name, args_hash))

            # Check for errors
            is_error = False
            error_msg = ""

            if tool_result.get("status") == "error":
                is_error = True
                error_msg = tool_result.get("message", "Unknown error")
            elif tool_result.get("error"):
                is_error = True
                err = tool_result.get("error")
                if isinstance(err, dict):
                    error_msg = err.get("message", str(err))
                else:
                    error_msg = str(err)
            elif tool_result.get("success") is False:
                is_error = True
                error_msg = tool_result.get("message", "Operation failed")

            if is_error:
                result.total_tool_errors += 1
                turn_stat.tool_errors += 1
                tool_error_msgs[tool_name].append(error_msg)

                # Track error
                category = categorize_error(error_msg)
                error_counts[category] += 1
                all_errors.append({
                    "tool": tool_name,
                    "turn": turn,
                    "message": error_msg[:200],
                    "category": category,
                })
            else:
                tool_successes[tool_name] += 1

        # Track turn complete (check end blockers)
        if msg_type == "turn_complete":
            # The turn completed, so blockers were resolved
            turn_stat.blockers_at_end = []

    # Compute derived stats
    result.total_turns = len(turns)

    # Duration
    if first_ts and last_ts:
        result.duration_minutes = (last_ts - first_ts).total_seconds() / 60

    # Tool success rates
    for tool, count in tool_calls.items():
        successes = tool_successes.get(tool, 0)
        result.tool_success_rate[tool] = successes / count if count > 0 else 0.0

    result.tool_counts = dict(tool_calls)
    result.tool_errors = {k: v[:5] for k, v in tool_error_msgs.items()}  # Top 5 errors per tool
    result.error_categories = dict(error_counts)

    # Deduplicate errors
    seen_errors = set()
    for err in all_errors:
        key = (err["tool"], err["message"][:50])
        if key not in seen_errors:
            seen_errors.add(key)
            result.unique_errors.append(err)
    result.unique_errors = result.unique_errors[:20]  # Top 20 unique errors

    # Detect stuck turns using multiple heuristics
    for turn_num, stat in sorted(turns.items()):
        if stat.first_timestamp and stat.last_timestamp:
            stat.duration_seconds = (stat.last_timestamp - stat.first_timestamp).total_seconds()

        stuck_reasons = []

        # Heuristic 1: Multiple end_turn attempts (trying to end but blocked)
        if stat.end_turn_attempts >= 3:
            stuck_reasons.append(f"repeated_end_turn ({stat.end_turn_attempts}x)")

        # Heuristic 2: High error rate (>50% of calls failed)
        if stat.tool_calls > 5 and stat.tool_errors / stat.tool_calls > 0.5:
            stuck_reasons.append(f"high_error_rate ({stat.tool_errors}/{stat.tool_calls})")

        # Heuristic 3: Repeated identical tool calls (loop detection)
        if len(stat.tool_sequence) >= 4:
            # Count consecutive repeated calls
            repeated_count = 0
            max_repeated = 0
            last_call = None
            for call in stat.tool_sequence:
                if call == last_call:
                    repeated_count += 1
                    max_repeated = max(max_repeated, repeated_count)
                else:
                    repeated_count = 1
                last_call = call

            if max_repeated >= 3:
                stuck_reasons.append(f"repeated_identical_calls ({max_repeated}x)")

            # Also check for repeated tool (even with different args)
            tool_counts_this_turn: dict[str, int] = defaultdict(int)
            for tool_name, _ in stat.tool_sequence:
                tool_counts_this_turn[tool_name] += 1

            for tool_name, count in tool_counts_this_turn.items():
                # Ignore query tools - repeated queries are often fine
                if count >= 5 and tool_name not in ("get_units", "get_cities", "get_turn_blockers", "get_map_view"):
                    stuck_reasons.append(f"repeated_{tool_name} ({count}x)")

        # Only flag as stuck if we have actual evidence of struggling
        if stuck_reasons:
            result.stuck_turns.append({
                "turn": turn_num,
                "tool_calls": stat.tool_calls,
                "errors": stat.tool_errors,
                "end_turn_attempts": stat.end_turn_attempts,
                "duration_seconds": stat.duration_seconds,
                "reasons": stuck_reasons,
            })

        result.turn_stats.append(stat)

    # Detect repeated failures (same error 3+ times)
    error_msg_counts: dict[str, int] = defaultdict(int)
    for err in all_errors:
        error_msg_counts[err["message"][:100]] += 1

    for msg, count in error_msg_counts.items():
        if count >= 3:
            result.repeated_failures.append({
                "message": msg,
                "count": count,
            })

    # Detect missing features
    for err in all_errors:
        if err["category"] == "not_implemented":
            if err["message"] not in result.missing_features:
                result.missing_features.append(err["message"][:100])
        if err["category"] == "unknown_tool":
            tool = err.get("tool", "?")
            if tool not in result.unknown_tools:
                result.unknown_tools.append(tool)

    return result


def format_text_report(result: AnalysisResult) -> str:
    """Format analysis result as human-readable text."""
    lines = []

    lines.append("=" * 60)
    lines.append(f"  LLM CIV V SESSION ANALYSIS - Game {result.game_id}")
    lines.append("=" * 60)
    lines.append("")

    # Summary
    lines.append("## SUMMARY")
    lines.append(f"  Turns played:      {result.total_turns}")
    lines.append(f"  Duration:          {result.duration_minutes:.1f} minutes")
    lines.append(f"  LLM requests:      {result.total_llm_requests}")
    lines.append(f"  Total tokens:      {result.total_tokens:,}")
    lines.append(f"  Tool calls:        {result.total_tool_calls}")
    lines.append(f"  Tool errors:       {result.total_tool_errors} ({100*result.total_tool_errors/max(1,result.total_tool_calls):.1f}%)")
    lines.append("")

    # Tool breakdown
    lines.append("## TOOL USAGE")
    sorted_tools = sorted(result.tool_counts.items(), key=lambda x: -x[1])
    for tool, count in sorted_tools[:15]:
        success_rate = result.tool_success_rate.get(tool, 1.0)
        status = "✓" if success_rate >= 0.9 else "⚠" if success_rate >= 0.5 else "✗"
        lines.append(f"  {status} {tool}: {count} calls ({100*success_rate:.0f}% success)")
    lines.append("")

    # Errors by category
    if result.error_categories:
        lines.append("## ERROR CATEGORIES")
        for cat, count in sorted(result.error_categories.items(), key=lambda x: -x[1]):
            lines.append(f"  {cat}: {count}")
        lines.append("")

    # Stuck turns
    if result.stuck_turns:
        lines.append("## STUCK TURNS (possible struggles)")
        for stuck in result.stuck_turns:
            reasons = ", ".join(stuck.get("reasons", ["unknown"]))
            lines.append(f"  Turn {stuck['turn']}: {stuck['tool_calls']} calls, {stuck['errors']} errors")
            lines.append(f"    → {reasons}")
        lines.append("")

    # Repeated failures
    if result.repeated_failures:
        lines.append("## REPEATED FAILURES")
        for fail in result.repeated_failures[:10]:
            lines.append(f"  [{fail['count']}x] {fail['message'][:70]}")
        lines.append("")

    # Missing features
    if result.missing_features:
        lines.append("## MISSING FEATURES (not_implemented)")
        for feat in result.missing_features:
            lines.append(f"  - {feat}")
        lines.append("")

    # Unknown tools
    if result.unknown_tools:
        lines.append("## UNKNOWN TOOLS")
        for tool in result.unknown_tools:
            lines.append(f"  - {tool}")
        lines.append("")

    # Unique errors
    if result.unique_errors:
        lines.append("## UNIQUE ERRORS (sample)")
        for err in result.unique_errors[:10]:
            lines.append(f"  [{err['tool']}] T{err['turn']}: {err['message'][:60]}")
        lines.append("")

    # Actionable insights
    lines.append("## INSIGHTS FOR NEXT SESSION")

    # Generate insights based on analysis
    insights = []

    if result.total_tool_errors / max(1, result.total_tool_calls) > 0.2:
        insights.append("- High error rate (>20%). Review tool usage patterns.")

    if result.stuck_turns:
        turns_list = ", ".join(str(s["turn"]) for s in result.stuck_turns[:5])
        # Summarize common reasons
        all_reasons = []
        for s in result.stuck_turns:
            all_reasons.extend(s.get("reasons", []))
        if any("end_turn" in r for r in all_reasons):
            insights.append(f"- Struggled on turns: {turns_list}. Repeated end_turn failures suggest unresolved blockers.")
        else:
            insights.append(f"- Struggled on turns: {turns_list}. Consider checking state before acting.")

    low_success_tools = [t for t, r in result.tool_success_rate.items() if r < 0.7 and result.tool_counts[t] > 3]
    if low_success_tools:
        insights.append(f"- Frequently failing tools: {', '.join(low_success_tools[:5])}")

    if result.missing_features:
        insights.append(f"- {len(result.missing_features)} features not yet implemented.")

    if not insights:
        insights.append("- Session completed without major issues.")

    for insight in insights:
        lines.append(f"  {insight}")

    lines.append("")
    lines.append("=" * 60)

    return "\n".join(lines)


def format_json_report(result: AnalysisResult) -> str:
    """Format analysis result as JSON for programmatic use."""
    # Convert to serializable dict
    data = {
        "game_id": result.game_id,
        "summary": {
            "total_turns": result.total_turns,
            "duration_minutes": round(result.duration_minutes, 2),
            "llm_requests": result.total_llm_requests,
            "total_tokens": result.total_tokens,
            "tool_calls": result.total_tool_calls,
            "tool_errors": result.total_tool_errors,
            "error_rate": round(result.total_tool_errors / max(1, result.total_tool_calls), 3),
        },
        "tool_success_rates": {k: round(v, 3) for k, v in result.tool_success_rate.items()},
        "tool_counts": result.tool_counts,
        "error_categories": result.error_categories,
        "stuck_turns": result.stuck_turns,
        "repeated_failures": result.repeated_failures,
        "missing_features": result.missing_features,
        "unknown_tools": result.unknown_tools,
        "unique_errors": result.unique_errors,
    }
    return json.dumps(data, indent=2)


def format_briefing_summary(result: AnalysisResult) -> str:
    """Format a compact summary suitable for including in LLM briefing."""
    lines = []
    lines.append("Previous session issues:")

    if result.stuck_turns:
        # Summarize struggle reasons
        all_reasons = []
        for s in result.stuck_turns:
            all_reasons.extend(s.get("reasons", []))

        if any("end_turn" in r for r in all_reasons):
            lines.append(f"- Struggled on {len(result.stuck_turns)} turns: repeated end_turn failures (check blockers before ending)")
        elif any("repeated_" in r for r in all_reasons):
            lines.append(f"- Struggled on {len(result.stuck_turns)} turns: repeated tool calls (possible loop)")
        else:
            lines.append(f"- Struggled on {len(result.stuck_turns)} turns")

    low_success = [(t, r) for t, r in result.tool_success_rate.items() if r < 0.7 and result.tool_counts[t] > 3]
    if low_success:
        tools_str = ", ".join(f"{t} ({100*r:.0f}%)" for t, r in sorted(low_success, key=lambda x: x[1])[:3])
        lines.append(f"- Low success rate tools: {tools_str}")

    if result.repeated_failures:
        lines.append(f"- {len(result.repeated_failures)} repeated error patterns")

    if result.missing_features:
        lines.append(f"- {len(result.missing_features)} not-implemented features encountered")

    if len(lines) == 1:
        lines.append("- No major issues detected")

    return "\n".join(lines)


def list_games() -> list[tuple[int, int, str]]:
    """List available game logs."""
    if not LOG_DIR.exists():
        return []

    games = []
    for log_file in LOG_DIR.glob("game_*.jsonl"):
        try:
            game_id = int(log_file.stem.split("_")[1])
            mtime = log_file.stat().st_mtime
            mtime_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
            msg_count = sum(1 for _ in open(log_file, 'r'))
            games.append((game_id, msg_count, mtime_str))
        except (ValueError, IndexError):
            continue

    return sorted(games, key=lambda x: x[0], reverse=True)


def main():
    parser = argparse.ArgumentParser(description="Analyze LLM Civ V session logs")
    parser.add_argument("--game-id", "-g", type=int, help="Game ID to analyze (default: most recent)")
    parser.add_argument("--output", "-o", choices=["text", "json", "briefing"], default="text",
                        help="Output format (default: text)")
    parser.add_argument("--list", "-l", action="store_true", help="List available games")

    args = parser.parse_args()

    if args.list:
        games = list_games()
        if not games:
            print("No game logs found.")
            return

        print(f"Available games in {LOG_DIR}:")
        print(f"{'Game ID':<12} {'Messages':<10} {'Modified'}")
        print("-" * 40)
        for game_id, msg_count, mtime in games:
            print(f"{game_id:<12} {msg_count:<10} {mtime}")
        return

    # Find game to analyze
    game_id = args.game_id
    if game_id is None:
        games = list_games()
        if not games:
            print("No game logs found.", file=sys.stderr)
            sys.exit(1)
        game_id = games[0][0]

    # Run analysis
    result = analyze_game(game_id)
    if result is None:
        sys.exit(1)

    # Output
    if args.output == "json":
        print(format_json_report(result))
    elif args.output == "briefing":
        print(format_briefing_summary(result))
    else:
        print(format_text_report(result))


if __name__ == "__main__":
    main()
