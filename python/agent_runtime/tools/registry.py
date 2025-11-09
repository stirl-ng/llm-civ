from __future__ import annotations

from typing import Any, Dict, List

from .rag import LocalRAG
from .web import WebSearchStub
from .mcp import MCPClientStub


def build_tools(configs: List[Dict[str, Any]] | None) -> List[Any]:
    tools: List[Any] = []
    for cfg in configs or []:
        kind = (cfg.get("kind") or cfg.get("type") or "").lower()
        if kind == "rag":
            tools.append(LocalRAG(corpus=cfg.get("corpus", [])))
        elif kind == "web":
            tools.append(WebSearchStub())
        elif kind == "mcp":
            tools.append(MCPClientStub(endpoint=cfg.get("endpoint")))
        else:
            raise ValueError(f"Unsupported tool kind: {kind}")
    return tools

