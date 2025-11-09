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

    # Constructing should succeed if openai is present; we won't call the API.
    m = get_model({"kind": "openai", "model": "gpt-4o-mini"})
    assert "openai:" in m.name()

