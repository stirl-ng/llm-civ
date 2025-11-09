from __future__ import annotations

from typing import Any, Dict, List

from .base import Strategy


class VanillaStrategy(Strategy):
    """Single-pass prompt that may call tools via simple keywords."""

    def __init__(self, temperature: float = 0.2):
        self.temperature = float(temperature)

    def name(self) -> str:  # pragma: no cover - trivial
        return f"vanilla@{self.temperature}"

    def decide(self, model: Any, tools: List[Any], state: Dict[str, Any]) -> Dict[str, Any]:
        # Build a minimal message list with state summary
        turn = state.get("turn", 0)
        prompt = f"You are a Civ V assistant at turn {turn}. Propose safe default actions."
        reply = model.generate([
            {"role": "system", "content": "You produce JSON actions only."},
            {"role": "user", "content": prompt},
        ], temperature=self.temperature)

        # Very conservative default: do nothing, so the pipeline stays safe
        return {"turn": turn, "actions": [], "notes": reply}

