"""
Civ V LLM Experiment Runner

Uses native LLM tool calling (no regex parsing).
Loop: poll for turns → call LLM with tools → execute tool calls → repeat until end_turn
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

import requests
import yaml

from agent_runtime.models import get_model
from agent_runtime.models.base import GenerateResponse, ToolCall
from agent_runtime.tools.schemas import get_openai_tools
from agent_runtime.prompts import build_system_prompt
from agent_runtime.prompts.personality import get_personality
from agent_runtime.briefing import generate_turn_briefing, generate_reflection_prompt
from agent_runtime.memory import get_journal

# Optional: set turn on message logger for LLM response logging
try:
    from orchestrator.message_logger import get_message_logger
    _message_logger = get_message_logger()
except ImportError:
    _message_logger = None


def load_config(config_arg: str) -> dict[str, Any]:
    """Load config from path or short name (e.g., 'gemini' → configs/experiments/gemini.yaml)."""
    config_path = Path(config_arg)

    if not config_path.is_absolute() and "/" not in config_arg and "\\" not in config_arg:
        python_root = Path(__file__).resolve().parent.parent
        config_path = python_root / "configs" / "experiments" / f"{config_arg}.yaml"

    if not config_path.exists():
        raise FileNotFoundError(f"Config not found: {config_path}")

    with config_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


# --- HTTP Helpers ---

def call_tool(base_url: str, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Call an orchestrator tool via HTTP."""
    response = requests.post(
        f"{base_url}/tool",
        json={"tool": tool, "arguments": arguments},
        timeout=30.0
    )
    response.raise_for_status()
    return response.json()


def check_health(base_url: str) -> bool:
    """Check if orchestrator is running."""
    try:
        r = requests.get(f"{base_url}/health", timeout=5.0)
        return r.ok and r.json().get("status") == "ok"
    except requests.exceptions.RequestException:
        return False


def get_status(base_url: str) -> dict[str, Any] | None:
    """Get current game status from orchestrator."""
    try:
        r = requests.get(f"{base_url}/status", timeout=5.0)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.RequestException:
        return None


# --- Tool Execution ---

def execute_tool(tool_call: ToolCall, base_url: str, turn: int, game_id: int | None = None) -> dict[str, Any]:
    """Execute a single tool call via orchestrator HTTP API or locally.

    Tools like record_lesson and get_lessons are handled locally since
    the journal lives in this Python process, not in the orchestrator.

    Args:
        tool_call: ToolCall object from model response
        base_url: Orchestrator base URL
        turn: Current turn number
        game_id: Current game ID (needed for local journal tools)

    Returns:
        Tool result dict with 'ok' field and optional '_end_turn' flag
    """
    name = tool_call.name
    args = tool_call.arguments

    # Handle journal tools locally (journal lives in this process)
    if name == "record_lesson":
        try:
            journal = get_journal()
            journal.record_lesson(
                content=args.get("lesson", ""),
                game_id=game_id or 0,
                turn=turn,
                category=args.get("category", "general"),
            )
            result = {"ok": True, "message": "Lesson recorded."}
        except Exception as e:
            result = {"ok": False, "error": str(e)}
        return result

    if name == "get_lessons":
        try:
            journal = get_journal()
            lessons = journal.get_lessons(
                category=args.get("category"),
                limit=args.get("limit", 10),
            )
            result = {
                "ok": True,
                "lessons": [
                    {"content": l.content, "category": l.category, "game_id": l.source_game_id}
                    for l in lessons
                ],
            }
        except Exception as e:
            result = {"ok": False, "error": str(e)}
        return result

    if name == "record_recap":
        try:
            journal = get_journal()
            journal.record_turn(game_id=game_id or 0, turn=turn, text=args.get("text", ""))
            result = {"ok": True, "message": "Recap recorded."}
        except Exception as e:
            result = {"ok": False, "error": str(e)}
        return result

    if name == "update_strategy":
        try:
            journal = get_journal()
            journal.update_narrative(game_id=game_id or 0, current_strategy=args.get("strategy", ""))
            result = {"ok": True, "message": "Strategy updated."}
        except Exception as e:
            result = {"ok": False, "error": str(e)}
        return result

    if name == "get_recaps":
        try:
            journal = get_journal()
            recaps = journal.get_recaps(game_id=game_id or 0, limit=args.get("limit", 3))
            result = {
                "ok": True,
                "recaps": [{"turn": r.turn, "text": r.text} for r in recaps],
            }
        except Exception as e:
            result = {"ok": False, "error": str(e)}
        return result

    # Execute via orchestrator
    try:
        result = call_tool(base_url, name, args)
    except Exception as e:
        result = {"ok": False, "error": str(e)}

    # Mark end_turn and force_end_turn calls
    if name in ("end_turn", "force_end_turn"):
        result["_end_turn"] = True

    return result


# --- Message Building ---

def build_assistant_message(response: GenerateResponse) -> dict[str, Any]:
    """Build assistant message dict from model response.

    For OpenAI-style conversation history, assistant messages with tool calls
    need to include the tool_calls in a specific format.
    """
    msg: dict[str, Any] = {"role": "assistant", "content": response.text or None}

    if response.tool_calls:
        msg["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.name,
                    "arguments": json.dumps(tc.arguments),
                },
            }
            for tc in response.tool_calls
        ]

    return msg


def build_tool_result_message(tool_call: ToolCall, result: dict[str, Any]) -> dict[str, Any]:
    """Build tool result message for conversation history."""
    return {
        "role": "tool",
        "tool_call_id": tool_call.id,
        "name": tool_call.name,
        "content": json.dumps(result),
    }


# --- Core Turn Loop ---

def prompt_operator(turn: int, iteration: int = 0) -> str | None:
    """Prompt the human operator for optional input.

    Returns the operator's message, or None if they just pressed Enter.
    This also serves as a natural pause point for watching the game.
    """
    try:
        label = f"  [Turn {turn}]" if iteration == 0 else f"  [Turn {turn}.{iteration}]"
        user_input = input(f"{label} Operator (Enter to continue): ").strip()
        return user_input if user_input else None
    except EOFError:
        return None


def run_turn(
    model,
    base_url: str,
    turn: int,
    game_id: int | None = None,
    player_name: str | None = None,
    civ_name: str | None = None,
    timeout: float | None = None,
    interactive: bool = True,
    temperature: float = 0.7,
    personality=None,
) -> dict[str, Any]:
    """Run a single turn: LLM → execute tools → repeat until end_turn.

    Args:
        model: Model adapter instance
        base_url: Orchestrator base URL
        turn: Current turn number
        game_id: Current game ID for journal context
        player_name: Leader name
        civ_name: Civilization name
        timeout: Optional timeout in seconds. None means no timeout.
        interactive: Whether to pause for human operator input between iterations.

    Returns:
        Dict with turn results
    """
    start_time = time.time()

    # Get tool schemas
    tools = get_openai_tools()

    # Prompt operator at turn start (also serves as pause)
    operator_msg = None
    if interactive:
        operator_msg = prompt_operator(turn)

    # Build initial messages with narrative context
    system_prompt = build_system_prompt(personality=personality, interactive=interactive)
    briefing = generate_turn_briefing(
        turn_number=turn,
        game_id=game_id,
        player_name=player_name,
        civ_name=civ_name,
        user_message=operator_msg,
    )

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": briefing}
    ]

    iterations = 0
    tool_calls_total = 0
    reflection_done = False

    print(f"  Starting turn {turn}...")

    # Tell logger about current turn
    if _message_logger:
        _message_logger.set_turn(turn)
        _message_logger.log({
            "type": "turn_start_messages",
            "system_prompt": system_prompt,
            "briefing": briefing,
        }, direction="outgoing")

    while True:
        # Check timeout
        if timeout is not None and time.time() - start_time >= timeout:
            print(f"  ⚠️  Turn timeout ({timeout}s)")
            break

        iterations += 1

        # Call LLM with tools
        try:
            response = model.generate(messages, tools=tools, temperature=temperature)
            preview = response.text[:150] + "..." if len(response.text) > 150 else response.text
            if preview:
                print(f"  [{iterations}] LLM: {preview}")
            if response.tool_calls:
                print(f"  [{iterations}] Tool calls: {[tc.name for tc in response.tool_calls]}")
        except Exception as e:
            print(f"  ✗ LLM error: {e}")
            break

        # Add assistant message to history
        messages.append(build_assistant_message(response))

        # No tool calls - check if we should prompt
        if not response.tool_calls:
            if iterations >= 3:
                print(f"  ⚠️  No tool calls after {iterations} iterations")
                break
            messages.append({"role": "user", "content": "Please call a tool or end_turn when ready."})
            continue

        # Operator pause between iterations (after seeing what LLM wants to do)
        if interactive and iterations > 1:
            mid_turn_msg = prompt_operator(turn, iterations)
            if mid_turn_msg:
                messages.append({"role": "user", "content": f"**[Operator]:** {mid_turn_msg}"})

        # Execute each tool call
        inject_reflection = False
        for tool_call in response.tool_calls:
            tool_calls_total += 1

            try:
                # Reflection gate: intercept first end_turn call to prompt reflection
                if tool_call.name in ("end_turn", "force_end_turn") and not reflection_done:
                    print(f"    ↩ {tool_call.name} intercepted — prompting reflection")
                    result = {
                        "ok": True,
                        "message": "Before ending your turn, please reflect. See the message below.",
                        "reflection_needed": True,
                    }
                    messages.append(build_tool_result_message(tool_call, result))
                    inject_reflection = True
                    continue

                result = execute_tool(tool_call, base_url, turn, game_id=game_id)
                is_ok = result.get("ok", True)
                print(f"    {'✓' if is_ok else '✗'} {tool_call.name}")

                # Add tool result to messages
                messages.append(build_tool_result_message(tool_call, result))

                # Check for end_turn
                if result.get("_end_turn"):
                    if not is_ok:
                        error = result.get("blocking_type") or result.get("message") or "blocked"
                        print(f"    ⚠️  end_turn blocked: {error}")
                        # Continue loop - model will see the error and try to fix
                    else:
                        # Wait for turn to actually advance
                        print(f"    ⏳ Waiting for turn to advance", end="", flush=True)
                        turn_advanced = False
                        for _ in range(20):  # Wait up to 10 seconds
                            print(".", end="", flush=True)
                            time.sleep(0.5)
                            status = get_status(base_url)
                            if status and status.get("turn") != turn:
                                turn_advanced = True
                                break

                        if turn_advanced:
                            print(f"  ✓ Turn {turn} ended")
                            return {"turn": turn, "iterations": iterations, "tool_calls": tool_calls_total, "success": True}
                        else:
                            print(f"    ⚠️  turn_end_ack received but turn didn't advance")
                            messages.append({
                                "role": "user",
                                "content": json.dumps({
                                    "error": "turn_not_advanced",
                                    "message": "end_turn was acknowledged but turn didn't advance. Something may still be blocking."
                                })
                            })

            except Exception as e:
                print(f"    ✗ {tool_call.name}: {e}")
                messages.append(build_tool_result_message(
                    tool_call,
                    {"ok": False, "error": str(e)}
                ))

        # After processing all tool calls, inject reflection prompt if needed
        if inject_reflection:
            messages.append({"role": "user", "content": generate_reflection_prompt(turn)})
            reflection_done = True

    return {"turn": turn, "iterations": iterations, "tool_calls": tool_calls_total, "success": False}


def run_game_loop(
    model,
    base_url: str,
    poll_interval: float = 2.0,  # kept for backward compat — no longer used
    turn_timeout: float | None = None,
    interactive: bool = False,
    temperature: float = 0.7,
    personality=None,
):
    """Main loop: subscribe to SSE turn events, run each turn.

    poll_interval kept for backward compatibility but is no longer used.
    The loop now blocks on the /events SSE stream and wakes immediately on
    each turn_start event pushed by the orchestrator.

    Args:
        model: Model adapter instance
        base_url: Orchestrator base URL
        poll_interval: Deprecated. Kept for backward compatibility.
        turn_timeout: Optional timeout per turn in seconds
        interactive: Whether to pause for human operator input between iterations
        temperature: LLM sampling temperature
        personality: Optional Personality instance for character voice
    """
    last_game_id = None

    try:
        while True:  # reconnect loop
            if not check_health(base_url):
                print("Waiting for orchestrator...")
                time.sleep(2)
                continue

            print("Connecting to event stream...")
            try:
                resp = requests.get(
                    f"{base_url}/events",
                    stream=True,
                    timeout=(10, None),  # (connect_timeout, read_timeout=None -> no timeout)
                )
                resp.raise_for_status()
            except requests.exceptions.RequestException as e:
                print(f"SSE connect failed: {e}. Retrying in 2s...")
                time.sleep(2)
                continue

            print("Subscribed. Waiting for turns.")
            event_type = None

            try:
                for raw in resp.iter_lines(chunk_size=1):
                    line = raw.decode() if isinstance(raw, bytes) else raw
                    if not line:
                        # Blank line = end of one SSE event block; reset event type
                        event_type = None
                        continue
                    if line.startswith(":"):
                        continue  # keepalive comment, ignore
                    if line.startswith("event:"):
                        event_type = line[6:].strip()
                    elif line.startswith("data:") and event_type == "turn_start":
                        try:
                            event = json.loads(line[5:].strip())
                        except json.JSONDecodeError:
                            continue

                        current_turn = event.get("turn")
                        current_game_id = event.get("game_id")
                        player_name = event.get("player_name")

                        if last_game_id is not None and current_game_id != last_game_id:
                            print(f"\nNEW GAME ({last_game_id} -> {current_game_id})")
                        last_game_id = current_game_id

                        if _message_logger:
                            _message_logger.set_turn(current_turn, current_game_id)

                        print(f"\n{'='*50}\nTURN {current_turn} (game_id: {current_game_id})\n{'='*50}")
                        result = run_turn(
                            model,
                            base_url,
                            current_turn,
                            game_id=current_game_id,
                            player_name=player_name,
                            timeout=turn_timeout,
                            interactive=interactive,
                            temperature=temperature,
                            personality=personality,
                        )
                        print(f"\nSummary: {result['iterations']} iterations, {result['tool_calls']} tool calls")

            except KeyboardInterrupt:
                raise
            except requests.exceptions.RequestException as e:
                print(f"SSE stream lost: {e}. Reconnecting in 2s...")
                time.sleep(2)

    except KeyboardInterrupt:
        print("\nInterrupted")


def main():
    parser = argparse.ArgumentParser(description="Run Civ V LLM experiment")
    parser.add_argument("--config", required=True, help="Config file or short name (e.g., 'gemini')")
    parser.add_argument("--interactive", action="store_true", help="Enable operator input")
    args = parser.parse_args()

    cfg = load_config(args.config)

    # Build model
    base_url = cfg.get("orchestrator", {}).get("url", "http://localhost:8765")
    model = get_model(cfg.get("backend", {}))

    # Set current player in journal for memory scoping
    journal = get_journal()
    player_id = journal.set_current_player(model.name())

    print(f"Model: {model.name()}")
    print(f"Player ID: {player_id}")
    print(f"Orchestrator: {base_url}")
    print(f"Using native tool calling")
    print()

    poll_interval = cfg.get("orchestrator", {}).get("poll_interval", 2.0)
    turn_timeout = cfg.get("orchestrator", {}).get("turn_timeout", None)
    interactive = cfg.get("orchestrator", {}).get("interactive", False)
    if args.interactive:
        interactive = True

    agent_cfg = cfg.get("agent", {})
    temperature = agent_cfg.get("temperature", 0.7)
    personality_name = agent_cfg.get("personality")
    personality = get_personality(personality_name) if personality_name else None

    # Wait for orchestrator
    print(f"Connecting to {base_url}", end="", flush=True)
    while not check_health(base_url):
        print(".", end="", flush=True)
        time.sleep(1)
    print("  Connected!")

    print(f"Interactive: {interactive}")
    print(f"Temperature: {temperature}")
    if personality:
        print(f"Personality: {personality_name}")
    run_game_loop(model, base_url, poll_interval, turn_timeout, interactive, temperature=temperature, personality=personality)


if __name__ == "__main__":
    main()
