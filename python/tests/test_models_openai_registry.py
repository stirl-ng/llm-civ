import pytest

from agent_runtime.models.registry import get_model


def test_registry_rejects_unknown():
    with pytest.raises(ValueError):
        get_model({"kind": "nope"})


def test_openai_registry_import_guard():
    try:
        import openai  # noqa: F401
    except Exception:
        pytest.skip("openai not installed")

    # Pass a dummy key so the client constructs without OPENAI_API_KEY in env.
    m = get_model({"kind": "openai", "model": "gpt-4o-mini", "api_key": "sk-dummy"})
    assert "openai:" in m.name()

