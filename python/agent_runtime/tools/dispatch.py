from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import requests

from agent_runtime.context import TurnContext
from agent_runtime.http_client import call_tool
from agent_runtime.memory import get_journal
from agent_runtime.models.base import ToolCall

_LOG_DIR = Path(__file__).parent.parent.parent / "logs"


# --- Local (journal) handlers ---

def _record_lesson(args: dict[str, Any], ctx: TurnContext) -> dict[str, Any]:
    journal = get_journal()
    journal.record_lesson(
        content=args.get("lesson", ""),
        game_id=ctx.game_id or 0,
        turn=ctx.turn,
        category=args.get("category", "general"),
    )
    return {"ok": True, "message": "Lesson recorded."}


def _get_lessons(args: dict[str, Any], ctx: TurnContext) -> dict[str, Any]:
    journal = get_journal()
    lessons = journal.get_lessons(
        category=args.get("category"),
        limit=args.get("limit", 10),
    )
    return {
        "ok": True,
        "lessons": [
            {"content": l.content, "category": l.category, "game_id": l.source_game_id}
            for l in lessons
        ],
    }


def _record_recap(args: dict[str, Any], ctx: TurnContext) -> dict[str, Any]:
    journal = get_journal()
    journal.record_turn(game_id=ctx.game_id or 0, turn=ctx.turn, text=args.get("text", ""))
    return {"ok": True, "message": "Recap recorded."}


def _update_strategy(args: dict[str, Any], ctx: TurnContext) -> dict[str, Any]:
    journal = get_journal()
    journal.update_narrative(game_id=ctx.game_id or 0, current_strategy=args.get("strategy", ""))
    return {"ok": True, "message": "Strategy updated."}


def _get_recaps(args: dict[str, Any], ctx: TurnContext) -> dict[str, Any]:
    journal = get_journal()
    recaps = journal.get_recaps(game_id=ctx.game_id or 0, limit=args.get("limit", 3))
    return {
        "ok": True,
        "recaps": [{"turn": r.turn, "text": r.text} for r in recaps],
    }


def _halt_handler(args: dict[str, Any], ctx: TurnContext) -> dict[str, Any]:
    reason = args.get("reason", "Agent requested halt")
    try:
        requests.post(
            f"{ctx.base_url}/observer/halt",
            json={"reason": reason},
            timeout=3,
        )
    except Exception:
        pass
    return {"ok": True, "_kill_runner": True, "reason": reason}


def _wish_handler(args: dict[str, Any], ctx: TurnContext) -> dict[str, Any]:
    description = args.get("description", "")
    if ctx.game_id:
        log_path = _LOG_DIR / f"observer_{ctx.game_id}.jsonl"
        record = {
            "type": "observer_wish",
            "turn": ctx.turn,
            "game_id": ctx.game_id,
            "description": description,
            "timestamp": datetime.utcnow().isoformat(),
        }
        try:
            with log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\n")
        except Exception:
            pass
    return {"ok": True, "message": "Wish recorded."}


LOCAL_HANDLERS: dict[str, Callable[[dict[str, Any], TurnContext], dict[str, Any]]] = {
    "record_lesson": _record_lesson,
    "get_lessons": _get_lessons,
    "record_recap": _record_recap,
    "update_strategy": _update_strategy,
    "get_recaps": _get_recaps,
    "halt": _halt_handler,
    "wish": _wish_handler,
}


# --- Dispatch ---

def execute_tool(tool_call: ToolCall, ctx: TurnContext) -> dict[str, Any]:
    """Execute a single tool call — locally for journal tools, via HTTP for everything else."""
    name = tool_call.name
    args = tool_call.arguments

    if name in LOCAL_HANDLERS:
        try:
            return LOCAL_HANDLERS[name](args, ctx)
        except Exception as e:
            return {"ok": False, "error": str(e)}

    try:
        result = call_tool(ctx.base_url, name, args)
    except Exception as e:
        return {"ok": False, "error": str(e)}

    if name in ("end_turn", "force_end_turn"):
        result["_end_turn"] = True

    return result
