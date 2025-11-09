from __future__ import annotations

from typing import Any, Dict, List

from .base import Tool


class LocalRAG(Tool):
    """
    Minimal local RAG stub. In a real setup, this would load a vector store.
    Here we accept a small in-memory corpus at construction and return the
    best matching snippet by simple substring/length heuristic.
    """

    def __init__(self, corpus: List[str] | None = None):
        self.corpus = corpus or []

    def name(self) -> str:  # pragma: no cover - trivial
        return "rag_search"

    def run(self, arguments: Dict[str, Any]) -> Any:
        query = str(arguments.get("query", "")).lower()
        if not query:
            return {"matches": []}
        scored = []
        for doc in self.corpus:
            text = doc.lower()
            score = text.count(query) * 2 + (len(set(query.split()) & set(text.split())))
            if score:
                scored.append((score, doc))
        scored.sort(reverse=True, key=lambda x: x[0])
        return {"matches": [d for _, d in scored[:3]]}

