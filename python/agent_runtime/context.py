from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TurnContext:
    base_url: str
    turn: int
    game_id: int | None
    player_name: str | None = None
