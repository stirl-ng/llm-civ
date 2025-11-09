from __future__ import annotations

from typing import Any, Dict

from .dummy import DummyModel
from .openai_adapter import OpenAIChat


def get_model(config: Dict[str, Any]):
    """Instantiate a model backend from config."""
    kind = (config.get("kind") or config.get("type") or "dummy").lower()
    if kind == "dummy":
        return DummyModel(seed=int(config.get("seed", 0)))
    if kind == "openai":
        return OpenAIChat(
            model=config.get("model"),
            api_key=config.get("api_key"),
            base_url=config.get("base_url"),
        )

    # Placeholders for future backends (OpenAI/Azure/HF/Ollama)
    # Use environment variables and per-backend sub-configs when implemented.
    raise ValueError(f"Unsupported model kind: {kind}")
