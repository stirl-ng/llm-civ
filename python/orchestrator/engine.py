from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

from .logging_setup import get_logger


try:
    import jsonschema
except Exception:  # pragma: no cover - optional dep at runtime
    jsonschema = None  # type: ignore


Validator = Callable[[dict[str, Any]], None]


def _load_schema(path: Path) -> Optional[dict[str, Any]]:
    try:
        if path.is_file():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return None


@dataclass
class OrchestratorEngine:
    """Processes inbound JSON and returns optional replies.

    - Validates against schemas if present and `jsonschema` is installed.
    - Provides a minimal request/response for pings.
    """

    def __post_init__(self) -> None:
        self.log = get_logger()
        base = Path(__file__).resolve().parents[2]  # repo root
        self.schemas_dir = base / "schemas"
        self._state_schema = _load_schema(self.schemas_dir / "state.schema.json")
        self._actions_schema = _load_schema(self.schemas_dir / "actions.schema.json")

        if jsonschema and (self._state_schema or self._actions_schema):
            self.log.info("Schema validation enabled")
        else:
            self.log.info("Schema validation disabled (schemas missing or jsonschema not installed)")

    def _validate(self, payload: Any) -> None:
        if not jsonschema:
            return
        if not isinstance(payload, dict):
            # Only dict payloads are schema-validated here.
            return
        # Heuristic: validate by 'kind'
        kind = payload.get("kind")
        schema = None
        if kind in {"state", "turn_state"}:
            schema = self._state_schema
        else:
            schema = self._actions_schema
        if schema:
            jsonschema.validate(instance=payload, schema=schema)

    def handle_message(self, data: bytes) -> Optional[bytes]:
        """Handle a single inbound message.

        Returns an optional response (bytes). If None, no reply is sent.
        """
        try:
            text = data.decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            self.log.error("Dropped non-UTF8 message")
            return None

        text = text.strip()
        if not text:
            return None

        try:
            obj = json.loads(text)
        except json.JSONDecodeError as e:
            self.log.error(f"JSON parse error: {e}")
            return None

        # Validate if possible
        try:
            self._validate(obj)
        except Exception as e:
            self.log.error(f"Schema validation failed: {e}
Payload: {text}")
            return None

        # Minimal protocol: respond to ping
        if isinstance(obj, dict) and obj.get("kind") == "ping":
            reply = {"kind": "pong", "server": "orchestrator", "echo": obj}
            return json.dumps(reply, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

        # No reply by default
        self.log.info(f"RX: {text}")
        return None

