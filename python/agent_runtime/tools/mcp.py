from __future__ import annotations

from typing import Any, Dict

from .base import Tool


class MCPClientStub(Tool):
    """Stub for Model Context Protocol client. Replace with real MCP later."""

    def __init__(self, endpoint: str | None = None):
        self.endpoint = endpoint or "mcp://stub"

    def name(self) -> str:  # pragma: no cover - trivial
        return "mcp_call"

    def run(self, arguments: Dict[str, Any]) -> Any:
        return {"endpoint": self.endpoint, "status": "not_implemented", "args": arguments}

