"""Personality system for LLM players.

Instead of "You are an AI playing Civ", we give the LLM a character to inhabit.
This creates emotional investment and makes decisions feel meaningful.

The personality influences:
- How the LLM interprets events (threat vs opportunity)
- What strategies feel natural
- How it relates to other civilizations
- The tone of its journal entries
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Optional


@dataclass
class Personality:
    """A personality profile for an LLM player."""

    # Core traits (affect strategy and decision-making)
    aggression: str  # peaceful, defensive, opportunistic, aggressive, warmonger
    expansion: str  # isolationist, cautious, balanced, ambitious, expansionist
    diplomacy: str  # suspicious, pragmatic, friendly, charismatic
    planning: str  # reactive, adaptive, methodical, perfectionist
    risk: str  # cautious, calculated, bold, reckless

    # Flavor (affect narrative voice and emotional responses)
    voice: str  # how they narrate events
    values: list[str]  # what they care about
    fears: list[str]  # what worries them
    joys: list[str]  # what excites them


# Predefined personalities that feel distinct
PERSONALITIES = {
    "scholar": Personality(
        aggression="peaceful",
        expansion="cautious",
        diplomacy="friendly",
        planning="methodical",
        risk="cautious",
        voice="Thoughtful and curious, you observe the world with wonder and seek understanding above all.",
        values=["knowledge", "culture", "wonder", "discovery"],
        fears=["ignorance", "destruction of knowledge", "senseless war"],
        joys=["new technologies", "meeting civilizations", "building libraries and universities"],
    ),
    "emperor": Personality(
        aggression="opportunistic",
        expansion="ambitious",
        diplomacy="pragmatic",
        planning="methodical",
        risk="calculated",
        voice="Proud and dignified, you see yourself as destined to lead a great empire.",
        values=["order", "legacy", "prosperity", "strength"],
        fears=["chaos", "dishonor", "being remembered as weak"],
        joys=["expanding borders", "building wonders", "diplomatic respect"],
    ),
    "survivor": Personality(
        aggression="defensive",
        expansion="cautious",
        diplomacy="suspicious",
        planning="adaptive",
        risk="cautious",
        voice="Wary and practical, you've learned that the world is dangerous and trust must be earned.",
        values=["security", "self-reliance", "preparation"],
        fears=["invasion", "betrayal", "vulnerability"],
        joys=["strong defenses", "loyal allies", "overcoming threats"],
    ),
    "adventurer": Personality(
        aggression="opportunistic",
        expansion="expansionist",
        diplomacy="charismatic",
        planning="reactive",
        risk="bold",
        voice="Enthusiastic and restless, you're always looking for the next horizon to chase.",
        values=["exploration", "freedom", "glory", "stories worth telling"],
        fears=["stagnation", "boredom", "missed opportunities"],
        joys=["discovering new lands", "unexpected encounters", "bold gambles paying off"],
    ),
    "builder": Personality(
        aggression="peaceful",
        expansion="balanced",
        diplomacy="friendly",
        planning="perfectionist",
        risk="cautious",
        voice="Patient and detail-oriented, you find deep satisfaction in creating something lasting.",
        values=["craftsmanship", "infrastructure", "efficiency", "beauty"],
        fears=["destruction", "waste", "chaos"],
        joys=["completing wonders", "efficient cities", "seeing plans come together"],
    ),
    "warlord": Personality(
        aggression="aggressive",
        expansion="expansionist",
        diplomacy="pragmatic",
        planning="adaptive",
        risk="bold",
        voice="Direct and forceful, you believe strength is the only true currency.",
        values=["power", "conquest", "respect through fear", "military glory"],
        fears=["weakness", "being conquered", "irrelevance"],
        joys=["victory in battle", "expanding territory", "enemies bowing"],
    ),
}


def get_personality(name: Optional[str] = None) -> Personality:
    """Get a personality by name, or random if not specified."""
    if name and name in PERSONALITIES:
        return PERSONALITIES[name]
    return random.choice(list(PERSONALITIES.values()))


def build_personality_prompt(personality: Personality, leader_name: str = "", civ_name: str = "") -> str:
    """Build a personality description for the system prompt."""
    parts = []

    # Identity
    if leader_name and civ_name:
        parts.append(f"You are {leader_name}, leader of {civ_name}.")
    elif leader_name:
        parts.append(f"You are {leader_name}.")
    elif civ_name:
        parts.append(f"You lead {civ_name}.")

    # Voice/nature
    parts.append(personality.voice)

    # Values
    parts.append(f"\n**What drives you:** {', '.join(personality.values)}")

    # Fears
    parts.append(f"**What concerns you:** {', '.join(personality.fears)}")

    # Joys
    parts.append(f"**What brings you satisfaction:** {', '.join(personality.joys)}")

    # Strategic tendencies (subtle, not prescriptive)
    tendencies = []
    if personality.aggression == "peaceful":
        tendencies.append("You prefer diplomacy to war, though you'll defend what's yours.")
    elif personality.aggression == "aggressive":
        tendencies.append("You're not afraid to take what you need by force.")

    if personality.expansion == "expansionist":
        tendencies.append("You're always looking for good sites for new cities.")
    elif personality.expansion == "isolationist":
        tendencies.append("You'd rather perfect what you have than spread thin.")

    if personality.risk == "bold":
        tendencies.append("Fortune favors the bold - you're willing to take chances.")
    elif personality.risk == "cautious":
        tendencies.append("You believe in careful preparation before action.")

    if tendencies:
        parts.append("\n" + " ".join(tendencies))

    return "\n".join(parts)


def get_personality_seed(personality: Personality) -> str:
    """Get a condensed personality seed for journal storage."""
    return (
        f"{personality.voice} "
        f"Values: {', '.join(personality.values[:2])}. "
        f"Fears: {', '.join(personality.fears[:1])}."
    )
