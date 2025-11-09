from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List


class Strategy(ABC):
    @abstractmethod
    def name(self) -> str:  # pragma: no cover - trivial
        ...

    @abstractmethod
    def decide(self, model: Any, tools: List[Any], state: Dict[str, Any]) -> Dict[str, Any]:
        ...

