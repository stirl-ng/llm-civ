from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from .base import ModelAdapter


class OpenAIChat(ModelAdapter):
    """
    OpenAI-compatible chat model adapter (supports OpenAI and compatible servers
    via base_url, e.g., Azure, local vLLM/Ollama with OpenAI API shim).

    Config keys (via constructor or env):
    - model: required (env OPENAI_MODEL)
    - api_key: optional if server doesn’t require (env OPENAI_API_KEY)
    - base_url: override API host (env OPENAI_BASE_URL)
    """

    def __init__(self, model: Optional[str] = None, api_key: Optional[str] = None, base_url: Optional[str] = None):
        try:
            from openai import OpenAI  # type: ignore
        except Exception as e:  # pragma: no cover - import time
            raise ImportError("openai package is required for OpenAIChat") from e

        self._OpenAI = OpenAI
        self._model = model or os.environ.get("OPENAI_MODEL")
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self._base_url = base_url or os.environ.get("OPENAI_BASE_URL")
        if not self._model:
            raise ValueError("model is required (set in config or OPENAI_MODEL)")

        # Initialize client; OpenAI SDK accepts base_url for compat servers
        kwargs: Dict[str, Any] = {}
        if self._api_key:
            kwargs["api_key"] = self._api_key
        if self._base_url:
            kwargs["base_url"] = self._base_url
        self._client = self._OpenAI(**kwargs)

    def name(self) -> str:  # pragma: no cover - trivial
        host = self._base_url or "openai"
        return f"openai:{self._model}@{host}"

    def generate(self, messages: List[Dict[str, str]], **kwargs: Any) -> str:
        temperature = kwargs.get("temperature", 0.2)
        res = self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=temperature,
        )
        msg = res.choices[0].message
        return (msg.content or "").strip()

