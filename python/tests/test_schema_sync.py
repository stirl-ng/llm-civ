"""
Ensures mcp_server._TOOLS and tools/schemas.py stay in sync.

Rules:
- Every orchestrator tool must have a schema entry (so LLM can call it).
- Every schema entry must have a handler (orchestrator or local in run.py).
- Internal tools must NOT be in schemas.
- Placeholder tools must NOT be in schemas until implemented.

When adding a new tool, update one of the sets below if needed.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from orchestrator.mcp_server import CivMCPServer
from agent_runtime.tools.schemas import get_tool_names

# Tools intentionally excluded from LLM-visible schemas
INTERNAL_TOOLS = {"get_tools", "ping"}

# Tools handled locally in run.py (not routed through orchestrator)
LOCAL_TOOLS = {
    "record_recap", "record_lesson", "get_lessons",
    "get_recaps", "update_strategy", "request_tool",
}


def _get_orchestrator_tool_names() -> set:
    # Instantiate with dummy callbacks to access _TOOLS
    server = CivMCPServer(send_request=lambda r, **kw: {}, game_state=None)
    return set(server._TOOLS.keys()) - INTERNAL_TOOLS


def _get_schema_tool_names() -> set:
    return set(get_tool_names())


def test_orchestrator_tools_have_schemas():
    """Every non-internal orchestrator tool must be visible to the LLM."""
    orch = _get_orchestrator_tool_names()
    schema = _get_schema_tool_names()
    missing = orch - schema - INTERNAL_TOOLS
    assert not missing, (
        f"Tools in _TOOLS but missing from TOOL_SCHEMAS (LLM can't call them):\n"
        + "\n".join(f"  - {t}" for t in sorted(missing))
    )


def test_schema_tools_have_handlers():
    """Every schema tool must have a handler (orchestrator or local)."""
    orch = _get_orchestrator_tool_names()
    schema = _get_schema_tool_names()
    all_handled = orch | LOCAL_TOOLS
    unhandled = schema - all_handled
    assert not unhandled, (
        f"Tools in TOOL_SCHEMAS with no handler in _TOOLS or LOCAL_TOOLS:\n"
        + "\n".join(f"  - {t}" for t in sorted(unhandled))
    )


def test_internal_tools_not_in_schemas():
    """Internal tools must stay hidden from the LLM."""
    schema = _get_schema_tool_names()
    leaked = INTERNAL_TOOLS & schema
    assert not leaked, f"Internal tools leaked into TOOL_SCHEMAS: {leaked}"


def test_placeholder_tools_not_in_schemas():
    """Placeholder (unimplemented) tools must not be in schemas."""
    server = CivMCPServer(send_request=lambda r, **kw: {}, game_state=None)
    placeholders = set(server._PLACEHOLDER_TOOLS.keys())
    schema = _get_schema_tool_names()
    premature = placeholders & schema
    assert not premature, (
        f"Placeholder tools in TOOL_SCHEMAS before implementation: {premature}"
    )
