import pytest

from agent_runtime.models.registry import get_model
from agent_runtime.tools.registry import build_tools


def test_get_model_dummy():
    m = get_model({"kind": "dummy", "seed": 7})
    assert "dummy:7" in m.name()


def test_build_tools_ok():
    tools = build_tools([{"kind": "mcp", "endpoint": "mcp://x"}])
    # Always includes RequestToolTool + the mcp tool
    assert len(tools) == 2


def test_build_tools_rejects_unknown():
    with pytest.raises(ValueError):
        build_tools([{"kind": "rag"}])

