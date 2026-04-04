"""Turn Journal - Persistent narrative memory across turns.

The journal stores the LLM's own thoughts, reflections, and experiences
as it plays the game. This creates continuity and allows the LLM to
maintain a coherent identity and narrative across the stateless turn loop.

Philosophy:
- The LLM is not a tool executor, it's a player experiencing a game
- Memories should be in the LLM's own voice, not dry data
- Recent memories matter more than ancient ones
- The journal is the LLM's inner monologue made persistent

Identity:
- Each model (opus, sonnet, gemini, llama, etc.) is a distinct player
- Memories and lessons are scoped to player_id
- Opus doesn't read Llama's lessons; they're different minds
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


def normalize_player_id(model_name: str) -> str:
    """Normalize model name to a consistent player ID.

    Examples:
        "openai:gpt-4o@openai" -> "openai_gpt-4o"
        "gemini:gemini-2.0-flash-exp" -> "gemini_gemini-2.0-flash-exp"
        "claude-opus-4-20250514" -> "claude-opus-4"

    We strip version dates and normalize separators for cleaner grouping.
    """
    # Remove URL/host suffixes
    if "@" in model_name:
        model_name = model_name.split("@")[0]

    # Replace colons with underscores
    model_name = model_name.replace(":", "_")

    # Remove date suffixes (e.g., -20250514)
    import re
    model_name = re.sub(r'-\d{8}$', '', model_name)

    return model_name.lower()


@dataclass
class Lesson:
    """A lesson learned that persists across games.

    Lessons are meta-knowledge: things the player (not the leader) has learned.
    """
    content: str  # The lesson itself
    source_game_id: int  # Which game taught this lesson
    turn_learned: int  # When it was learned
    category: str = ""  # Optional: diplomacy, military, economy, etc.
    confidence: float = 1.0  # How sure are we? Can decay or strengthen
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class TurnRecap:
    """A single turn's recap - freeform text written by the LLM."""
    turn: int
    text: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class GameNarrative:
    """The overarching narrative of a game - who we are and our journey."""
    game_id: int
    player_id: str = ""  # Which model played this game
    leader_name: str = ""
    civ_name: str = ""
    personality_seed: str = ""  # Core personality traits established at game start
    story_so_far: str = ""  # Cumulative narrative summary, updated periodically
    current_strategy: str = ""
    relationships: dict[str, str] = field(default_factory=dict)  # civ_name -> relationship description
    memories: list[TurnRecap] = field(default_factory=list)


@dataclass
class PlayerProfile:
    """A player's identity and cross-game learning.

    Each model is a distinct player with their own:
    - Lessons learned across games
    - Play style tendencies
    - Historical record
    """
    player_id: str  # Normalized model identifier
    lessons: list[Lesson] = field(default_factory=list)
    games_played: int = 0
    total_turns: int = 0
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def add_lesson(
        self,
        content: str,
        game_id: int,
        turn: int,
        category: str = ""
    ) -> None:
        """Add a new lesson learned."""
        self.lessons.append(Lesson(
            content=content,
            source_game_id=game_id,
            turn_learned=turn,
            category=category,
        ))

    def get_lessons(self, category: Optional[str] = None, limit: int = 10) -> list[Lesson]:
        """Get recent lessons, optionally filtered by category."""
        lessons = self.lessons
        if category:
            lessons = [l for l in lessons if l.category == category]
        return lessons[-limit:]


class TurnJournal:
    """Manages persistent narrative memory across turns and games.

    The journal serves as the LLM's long-term memory, storing not just
    what happened but how it felt and what it means for the story.

    Memory is scoped by player_id (model identity):
    - Each model has its own PlayerProfile with cross-game lessons
    - Each game is associated with the player who played it
    - Opus's lessons don't leak to Llama and vice versa
    """

    def __init__(self, storage_path: Optional[Path] = None):
        """Initialize the journal.

        Args:
            storage_path: Where to persist journal data. Defaults to ./game_journal.json
        """
        self.storage_path = storage_path or Path("game_journal.json")
        self._players: dict[str, PlayerProfile] = {}
        self._narratives: dict[int, GameNarrative] = {}
        self._current_player_id: Optional[str] = None
        self._load()

    def set_current_player(self, model_name: str) -> str:
        """Set the current player based on model name.

        Args:
            model_name: Raw model name (e.g., "openai:gpt-4o@openai")

        Returns:
            Normalized player_id
        """
        self._current_player_id = normalize_player_id(model_name)
        self._get_or_create_player(self._current_player_id)
        return self._current_player_id

    def _get_or_create_player(self, player_id: str) -> PlayerProfile:
        """Get or create a player profile."""
        if player_id not in self._players:
            self._players[player_id] = PlayerProfile(player_id=player_id)
            self._save()
        return self._players[player_id]

    def _load(self) -> None:
        """Load journal from disk."""
        if self.storage_path.exists():
            try:
                data = json.loads(self.storage_path.read_text())

                # Load players
                for player_id, player_data in data.get("players", {}).items():
                    lessons = [Lesson(**l) for l in player_data.pop("lessons", [])]
                    self._players[player_id] = PlayerProfile(**player_data, lessons=lessons)

                # Load games
                for game_id_str, narrative_data in data.get("games", {}).items():
                    game_id = int(game_id_str)
                    memories = [TurnRecap(**m) for m in narrative_data.pop("memories", [])]
                    self._narratives[game_id] = GameNarrative(**narrative_data, memories=memories)

            except (json.JSONDecodeError, KeyError, TypeError) as e:
                # Start fresh on corruption
                self._players = {}
                self._narratives = {}

    def _save(self) -> None:
        """Persist journal to disk."""
        data = {
            "players": {
                player_id: {
                    **{k: v for k, v in asdict(player).items() if k != "lessons"},
                    "lessons": [asdict(l) for l in player.lessons]
                }
                for player_id, player in self._players.items()
            },
            "games": {
                str(game_id): {
                    **{k: v for k, v in asdict(narrative).items() if k != "memories"},
                    "memories": [asdict(m) for m in narrative.memories]
                }
                for game_id, narrative in self._narratives.items()
            }
        }
        self.storage_path.write_text(json.dumps(data, indent=2))

    def get_or_create_narrative(self, game_id: int, player_id: Optional[str] = None) -> GameNarrative:
        """Get the narrative for a game, creating if needed.

        Args:
            game_id: The game ID
            player_id: Optional player ID (uses current player if not specified)
        """
        player_id = player_id or self._current_player_id or "unknown"

        if game_id not in self._narratives:
            self._narratives[game_id] = GameNarrative(game_id=game_id, player_id=player_id)
            self._save()
        return self._narratives[game_id]

    def get_current_player(self) -> Optional[PlayerProfile]:
        """Get the current player's profile."""
        if self._current_player_id:
            return self._players.get(self._current_player_id)
        return None

    def record_turn(self, game_id: int, turn: int, text: str) -> None:
        """Record a turn recap.

        Args:
            game_id: Current game ID
            turn: Turn number
            text: Freeform recap text written by the LLM
        """
        narrative = self.get_or_create_narrative(game_id)

        existing_idx = next(
            (i for i, m in enumerate(narrative.memories) if m.turn == turn),
            None
        )

        recap = TurnRecap(turn=turn, text=text)

        if existing_idx is not None:
            narrative.memories[existing_idx] = recap
        else:
            narrative.memories.append(recap)
            narrative.memories.sort(key=lambda m: m.turn)

        # Update player stats
        if self._current_player_id:
            player = self._get_or_create_player(self._current_player_id)
            player.total_turns += 1

        self._save()

    def record_lesson(
        self,
        content: str,
        game_id: int,
        turn: int,
        category: str = "",
        player_id: Optional[str] = None
    ) -> None:
        """Record a lesson learned (persists across games).

        Args:
            content: The lesson content
            game_id: Which game this lesson came from
            turn: Which turn
            category: Optional category (diplomacy, military, economy, etc.)
            player_id: Optional player ID (uses current player if not specified)
        """
        player_id = player_id or self._current_player_id
        if not player_id:
            return

        player = self._get_or_create_player(player_id)
        player.add_lesson(content, game_id, turn, category)
        self._save()

    def get_lessons(
        self,
        category: Optional[str] = None,
        limit: int = 10,
        player_id: Optional[str] = None
    ) -> list[Lesson]:
        """Get lessons for a player.

        Args:
            category: Optional category filter
            limit: Max lessons to return
            player_id: Optional player ID (uses current player if not specified)
        """
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
        personality_seed: Optional[str] = None,
        story_so_far: Optional[str] = None,
        current_strategy: Optional[str] = None,
        relationships: Optional[dict[str, str]] = None
    ) -> None:
        """Update the game's overarching narrative."""
        narrative = self.get_or_create_narrative(game_id)

        if leader_name is not None:
            narrative.leader_name = leader_name
        if civ_name is not None:
            narrative.civ_name = civ_name
        if personality_seed is not None:
            narrative.personality_seed = personality_seed
        if story_so_far is not None:
            narrative.story_so_far = story_so_far
        if current_strategy is not None:
            narrative.current_strategy = current_strategy
        if relationships is not None:
            narrative.relationships.update(relationships)

        self._save()

    def get_recaps(self, game_id: int, limit: int = 3) -> list[TurnRecap]:
        """Get most recent turn recaps."""
        narrative = self.get_or_create_narrative(game_id)
        return narrative.memories[-limit:] if narrative.memories else []

    def build_context_summary(
        self,
        game_id: int,
        current_turn: int,
        include_lessons: bool = True
    ) -> str:
        """Build a narrative summary for inclusion in turn briefing.

        This is the heart of continuity - it tells the LLM who it is,
        what's happened, and what it's been thinking.

        Args:
            game_id: Current game ID
            current_turn: Current turn number
            include_lessons: Whether to include cross-game lessons
        """
        narrative = self.get_or_create_narrative(game_id)
        parts = []

        # Identity
        if narrative.leader_name or narrative.civ_name:
            identity = f"You are {narrative.leader_name}" if narrative.leader_name else "You lead"
            if narrative.civ_name:
                identity += f" of {narrative.civ_name}"
            parts.append(identity + ".")

        # Personality
        if narrative.personality_seed:
            parts.append(f"\n{narrative.personality_seed}")

        # Cross-game lessons (wisdom from past games)
        if include_lessons:
            lessons = self.get_lessons(limit=5)
            if lessons:
                parts.append("\n**Wisdom from Past Games:**")
                for lesson in lessons:
                    parts.append(f"- {lesson.content}")

        # Story so far (condensed narrative)
        if narrative.story_so_far:
            parts.append(f"\n**Your Journey:**\n{narrative.story_so_far}")

        # Current strategy
        if narrative.current_strategy:
            parts.append(f"\n**Current Strategy:** {narrative.current_strategy}")

        # Relationships
        if narrative.relationships:
            rel_lines = [f"- {civ}: {desc}" for civ, desc in narrative.relationships.items()]
            parts.append(f"\n**Relationships:**\n" + "\n".join(rel_lines))

        # Recent turn recaps
        recent = self.get_recaps(game_id, limit=3)
        if recent:
            parts.append("\n**Recent Turns:**")
            for mem in recent:
                parts.append(f"Turn {mem.turn}: {mem.text}")

        return "\n".join(parts) if parts else ""


# Global journal instance
_journal: Optional[TurnJournal] = None


def get_journal(storage_path: Optional[Path] = None) -> TurnJournal:
    """Get the global journal instance."""
    global _journal
    if _journal is None:
        _journal = TurnJournal(storage_path)
    return _journal
