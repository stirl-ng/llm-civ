"""Turn Journal - Persistent narrative memory across turns.

Stores the LLM's reflections and lessons as it plays. Gives continuity
across the stateless turn loop — the LLM knows who it is, what it planned,
and what it's learned.

Storage layout:
    game_journal/
        players/{player_id}.json   — cross-game lessons per model
        games/{game_id}.json       — per-game recaps and strategy

Each model is a distinct player. Opus doesn't read Llama's lessons.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional


def normalize_player_id(model_name: str) -> str:
    """Normalize model name to a consistent player ID.

    Examples:
        "openai:gpt-4o@openai" -> "openai_gpt-4o"
        "gemini:gemini-2.0-flash-exp" -> "gemini_gemini-2.0-flash-exp"
        "claude-opus-4-20250514" -> "claude-opus-4"
    """
    if "@" in model_name:
        model_name = model_name.split("@")[0]
    model_name = model_name.replace(":", "_")
    model_name = re.sub(r'-\d{8}$', '', model_name)
    return model_name.lower()


@dataclass
class Lesson:
    content: str
    source_game_id: int
    turn_learned: int
    category: str = ""
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class TurnRecap:
    turn: int
    text: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class GameNarrative:
    game_id: int
    player_id: str = ""
    leader_name: str = ""
    civ_name: str = ""
    current_strategy: str = ""
    memories: list[TurnRecap] = field(default_factory=list)


@dataclass
class PlayerProfile:
    player_id: str
    lessons: list[Lesson] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def add_lesson(self, content: str, game_id: int, turn: int, category: str = "") -> None:
        self.lessons.append(Lesson(
            content=content,
            source_game_id=game_id,
            turn_learned=turn,
            category=category,
        ))

    def get_lessons(self, category: Optional[str] = None, limit: int = 10) -> list[Lesson]:
        lessons = self.lessons
        if category:
            lessons = [l for l in lessons if l.category == category]
        return lessons[-limit:]


class TurnJournal:
    """Manages persistent narrative memory across turns and games."""

    def __init__(self, storage_dir: Optional[Path] = None):
        self.storage_dir = storage_dir or Path("game_journal")
        self._players: dict[str, PlayerProfile] = {}
        self._narratives: dict[int, GameNarrative] = {}
        self._current_player_id: Optional[str] = None

    def _player_path(self, player_id: str) -> Path:
        return self.storage_dir / "players" / f"{player_id}.json"

    def _game_path(self, game_id: int) -> Path:
        return self.storage_dir / "games" / f"{game_id}.json"

    def _load_player(self, player_id: str) -> PlayerProfile:
        path = self._player_path(player_id)
        if path.exists():
            try:
                data = json.loads(path.read_text())
                lessons = [Lesson(**l) for l in data.pop("lessons", [])]
                return PlayerProfile(**data, lessons=lessons)
            except (json.JSONDecodeError, KeyError, TypeError):
                pass
        return PlayerProfile(player_id=player_id)

    def _load_game(self, game_id: int) -> GameNarrative:
        path = self._game_path(game_id)
        if path.exists():
            try:
                data = json.loads(path.read_text())
                memories = [TurnRecap(**m) for m in data.pop("memories", [])]
                return GameNarrative(**data, memories=memories)
            except (json.JSONDecodeError, KeyError, TypeError):
                pass
        return GameNarrative(game_id=game_id)

    def _save_player(self, player_id: str) -> None:
        player = self._players.get(player_id)
        if not player:
            return
        path = self._player_path(player_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {k: v for k, v in asdict(player).items() if k != "lessons"}
        data["lessons"] = [asdict(l) for l in player.lessons]
        path.write_text(json.dumps(data, indent=2))

    def _save_game(self, game_id: int) -> None:
        narrative = self._narratives.get(game_id)
        if not narrative:
            return
        path = self._game_path(game_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {k: v for k, v in asdict(narrative).items() if k != "memories"}
        data["memories"] = [asdict(m) for m in narrative.memories]
        path.write_text(json.dumps(data, indent=2))

    def _get_or_create_player(self, player_id: str) -> PlayerProfile:
        if player_id not in self._players:
            self._players[player_id] = self._load_player(player_id)
        return self._players[player_id]

    def set_current_player(self, model_name: str) -> str:
        self._current_player_id = normalize_player_id(model_name)
        self._get_or_create_player(self._current_player_id)
        return self._current_player_id

    def get_current_player(self) -> Optional[PlayerProfile]:
        if self._current_player_id:
            return self._players.get(self._current_player_id)
        return None

    def get_or_create_narrative(self, game_id: int, player_id: Optional[str] = None) -> GameNarrative:
        if game_id not in self._narratives:
            narrative = self._load_game(game_id)
            if not narrative.player_id:
                narrative.player_id = player_id or self._current_player_id or "unknown"
            self._narratives[game_id] = narrative
        return self._narratives[game_id]

    def record_turn(self, game_id: int, turn: int, text: str) -> None:
        narrative = self.get_or_create_narrative(game_id)
        existing_idx = next(
            (i for i, m in enumerate(narrative.memories) if m.turn == turn),
            None,
        )
        recap = TurnRecap(turn=turn, text=text)
        if existing_idx is not None:
            narrative.memories[existing_idx] = recap
        else:
            narrative.memories.append(recap)
            narrative.memories.sort(key=lambda m: m.turn)
        self._save_game(game_id)

    def record_lesson(
        self,
        content: str,
        game_id: int,
        turn: int,
        category: str = "",
        player_id: Optional[str] = None,
    ) -> None:
        player_id = player_id or self._current_player_id
        if not player_id:
            return
        player = self._get_or_create_player(player_id)
        player.add_lesson(content, game_id, turn, category)
        self._save_player(player_id)

    def get_lessons(
        self,
        category: Optional[str] = None,
        limit: int = 10,
        player_id: Optional[str] = None,
    ) -> list[Lesson]:
        player_id = player_id or self._current_player_id
        if not player_id:
            return []
        player = self._players.get(player_id)
        if not player:
            return []
        return player.get_lessons(category=category, limit=limit)

    def update_narrative(
        self,
        game_id: int,
        leader_name: Optional[str] = None,
        civ_name: Optional[str] = None,
        current_strategy: Optional[str] = None,
    ) -> None:
        narrative = self.get_or_create_narrative(game_id)
        if leader_name is not None:
            narrative.leader_name = leader_name
        if civ_name is not None:
            narrative.civ_name = civ_name
        if current_strategy is not None:
            narrative.current_strategy = current_strategy
        self._save_game(game_id)

    def get_recaps(self, game_id: int, limit: int = 3) -> list[TurnRecap]:
        narrative = self.get_or_create_narrative(game_id)
        return narrative.memories[-limit:] if narrative.memories else []

    def build_context_summary(
        self,
        game_id: int,
        current_turn: int,
        include_lessons: bool = True,
    ) -> str:
        """Build narrative context for the turn briefing."""
        narrative = self.get_or_create_narrative(game_id)
        parts = []

        if narrative.leader_name or narrative.civ_name:
            identity = f"You are {narrative.leader_name}" if narrative.leader_name else "You lead"
            if narrative.civ_name:
                identity += f" of {narrative.civ_name}"
            parts.append(identity + ".")

        if include_lessons:
            lessons = self.get_lessons(limit=5)
            if lessons:
                parts.append("\n**Wisdom from Past Games:**")
                for lesson in lessons:
                    parts.append(f"- {lesson.content}")

        if narrative.current_strategy:
            parts.append(f"\n**Current Strategy:** {narrative.current_strategy}")

        recent = self.get_recaps(game_id, limit=3)
        if recent:
            parts.append("\n**Recent Turns:**")
            for mem in recent:
                parts.append(f"Turn {mem.turn}: {mem.text}")

        return "\n".join(parts) if parts else ""


# Global journal instance
_journal: Optional[TurnJournal] = None


def get_journal(storage_dir: Optional[Path] = None) -> TurnJournal:
    global _journal
    if _journal is None:
        _journal = TurnJournal(storage_dir)
    return _journal
