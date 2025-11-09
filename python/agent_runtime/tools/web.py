from __future__ import annotations

from typing import Any, Dict

from .base import Tool


class WebSearchStub(Tool):
    """Offline web search stub to allow strategy composition without network."""

    def name(self) -> str:  # pragma: no cover - trivial
        return "web_search"

    def run(self, arguments: Dict[str, Any]) -> Any:
        query = arguments.get("query", "")
        return {"query": query, "results": []}

