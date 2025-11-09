from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict


class Tool(ABC):
    @abstractmethod
    def name(self) -> str:  # pragma: no cover - trivial
        ...

    @abstractmethod
    def run(self, arguments: Dict[str, Any]) -> Any:
        ...

