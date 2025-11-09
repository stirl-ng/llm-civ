from __future__ import annotations

from typing import Any, Dict, List, Optional


class Agent:
    """
    Agent composes a model backend, a set of tools, and a decision strategy.

    It exposes a simple step() that takes a game state dict and returns an
    actions dict. The contract is governed by schemas/state.schema.json and
    schemas/actions.schema.json (validation is handled externally by the
    orchestrator or experiment runner).
    """

    def __init__(self, model: Any, tools: List[Any], strategy: Any):
        self.model = model
        self.tools = tools
        self.strategy = strategy

        # Inform the model about available tools (if supported)
        if hasattr(self.model, "register_tools"):
            self.model.register_tools(self.tools)

    def step(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Produce an actions payload for a single turn from a state payload."""
        return self.strategy.decide(self.model, self.tools, state)

    def name(self) -> str:
        m = getattr(self.model, "name", lambda: type(self.model).__name__)()
        s = getattr(self.strategy, "name", lambda: type(self.strategy).__name__)()
        return f"{m}+{s}"

