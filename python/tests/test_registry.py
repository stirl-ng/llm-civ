from agent_runtime.models.registry import get_model
from agent_runtime.tools.registry import build_tools


def test_get_model_dummy():
    m = get_model({"kind": "dummy", "seed": 7})
    assert "dummy:7" in m.name()


def test_build_tools_ok():
    tools = build_tools([
        {"kind": "rag", "corpus": ["a", "b"]},
        {"kind": "web"},
        {"kind": "mcp", "endpoint": "mcp://x"},
    ])
    assert len(tools) == 3

