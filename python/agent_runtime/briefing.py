"""Turn briefing generator - minimal announcement to start LLM turn."""
from __future__ import annotations

from typing import Any


def generate_turn_briefing(turn_number: int, blockers: list[dict[str, Any]] | None = None) -> str: # TODO what the heck is this stub lol?
    """Generate turn announcement.

    The LLM should proactively query game state via tools (get_units, get_cities, etc.)
    rather than having it pre-fetched here. This follows the design philosophy that
    the LLM plays like a human: gathering info when needed, not waiting for briefings.

    Args:
        turn_number: Current turn number
        blockers: Deprecated parameter (ignored, kept for backward compatibility)
    """
    msg = f"Turn {turn_number}. Query game state and take your actions." 
    user_input = input('User Input: ')
    if user_input:
        msg += f"\n{user_input}"
    return msg

