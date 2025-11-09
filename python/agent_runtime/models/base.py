from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class ModelAdapter(ABC):
    """Abstract interface for model backends supporting optional tool use."""

    @abstractmethod
    def name(self) -> str:  # pragma: no cover - trivial
        ...

    @abstractmethod
    def generate(self, messages: List[Dict[str, str]], **kwargs: Any) -> str:
        """Return assistant text given a chat message list."""
        ...

    # Optional tool support
    def register_tools(self, tools: List[Any]) -> None:  # pragma: no cover
        self._tools = tools

    def tool_call(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        for t in getattr(self, "_tools", []) or []:
            if getattr(t, "name")() == tool_name:
                return t.run(arguments)
        raise ValueError(f"Unknown tool: {tool_name}")

