from __future__ import annotations

import json
from typing import Any, Dict, Optional

import requests

from .base import Tool


class MCPClientTool(Tool):
    """HTTP client for Model Context Protocol (orchestrator tools).
    
    Calls orchestrator's /tool endpoint to execute game tools.
    """

    def __init__(self, base_url: str = "http://localhost:8765"):
        """Initialize the MCP client tool.
        
        Args:
            base_url: Base URL of the orchestrator HTTP server
        """
        self.base_url = base_url.rstrip("/")
        self._tool_endpoint = f"{self.base_url}/tool"

    def name(self) -> str:
        return "mcp_call"

    def run(self, arguments: Dict[str, Any]) -> Any:
        """Execute a tool call via orchestrator HTTP API.
        
        Args:
            arguments: Dict with:
                - tool: Tool name (required)
                - arguments: Tool arguments dict (optional)
        
        Returns:
            Tool result dict with status and result
        """
        tool_name = arguments.get("tool")
        if not tool_name:
            return {
                "status": "error",
                "error": "Missing required parameter 'tool'"
            }
        
        tool_args = arguments.get("arguments", {})
        
        try:
            response = requests.post(
                self._tool_endpoint,
                json={"tool": tool_name, "arguments": tool_args},
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {
                "status": "error",
                "error": f"Failed to call tool '{tool_name}': {e}"
            }
        except json.JSONDecodeError as e:
            return {
                "status": "error",
                "error": f"Invalid JSON response from orchestrator: {e}"
            }

