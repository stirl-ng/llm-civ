"""JSON Schemas for DLL messages: check replies and events, or draft them from samples.

One schema per message type, in schemas/<type>.json. With --update-schemas
the harness merges every message it sees into the schema for its type, so
the first run drafts them. Review the draft in the diff and commit it; after
that, a message that drops a required key or changes a type fails the test.
Drafted schemas allow extra keys, so adding a field does not break them.
These are the first draft of the protocol v2 message spec (D4).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

import jsonschema

SCHEMA_DIR = Path(__file__).resolve().parent / "schemas"

# Fields that are per-message noise rather than protocol shape.
_IGNORED_KEYS = {"timestamp", "uuid", "direction"}


def _type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    return "object"


def infer(value: Any) -> dict:
    """Schema that accepts exactly the shape of one sample."""
    kind = _type_name(value)
    if kind == "object":
        keys = [k for k in value if k not in _IGNORED_KEYS]
        return {
            "type": "object",
            "properties": {k: infer(value[k]) for k in keys},
            "required": sorted(keys),
        }
    if kind == "array":
        items: Optional[dict] = None
        for element in value:
            items = infer(element) if items is None else merge(items, infer(element))
        return {"type": "array", "items": items} if items else {"type": "array"}
    return {"type": kind}


def _types(schema: dict) -> list[str]:
    t = schema.get("type", [])
    return [t] if isinstance(t, str) else list(t)


def merge(a: dict, b: dict) -> dict:
    """Schema that accepts everything a or b accepts (keys required only if both require them)."""
    types = sorted(set(_types(a)) | set(_types(b)))
    if "number" in types and "integer" in types:
        types.remove("integer")
    out: dict[str, Any] = {"type": types[0] if len(types) == 1 else types}

    if "object" in types:
        props_a, props_b = a.get("properties", {}), b.get("properties", {})
        props = {}
        for key in sorted(set(props_a) | set(props_b)):
            if key in props_a and key in props_b:
                props[key] = merge(props_a[key], props_b[key])
            else:
                props[key] = props_a.get(key) or props_b[key]
        out["properties"] = props
        # A key is required only if every sample of an object had it.
        if "object" in _types(a) and "object" in _types(b):
            out["required"] = sorted(set(a.get("required", [])) & set(b.get("required", [])))
        else:
            out["required"] = (a if "object" in _types(a) else b).get("required", [])

    if "array" in types:
        items_a, items_b = a.get("items"), b.get("items")
        if items_a and items_b:
            out["items"] = merge(items_a, items_b)
        elif items_a or items_b:
            out["items"] = items_a or items_b
    return out


class SchemaBook:
    """Loads, checks against, and (in update mode) drafts the per-type schemas."""

    def __init__(self, update: bool):
        self.update = update
        self._schemas: dict[str, dict] = {}
        self._dirty: set[str] = set()

    def _path(self, msg_type: str) -> Path:
        return SCHEMA_DIR / f"{msg_type}.json"

    def _load(self, msg_type: str) -> Optional[dict]:
        if msg_type not in self._schemas:
            path = self._path(msg_type)
            if path.exists():
                self._schemas[msg_type] = json.loads(path.read_text(encoding="utf-8"))
        return self._schemas.get(msg_type)

    def check(self, message: dict) -> None:
        """Validate a message against its type's schema (or merge it in, in update mode)."""
        msg_type = message.get("type", "unknown")
        schema = self._load(msg_type)
        if self.update:
            sample = infer(message)
            self._schemas[msg_type] = merge(schema, sample) if schema else sample
            self._dirty.add(msg_type)
            return
        if schema is None:
            raise AssertionError(f"no schema for '{msg_type}' messages; run with --update-schemas to draft one")
        try:
            jsonschema.validate(message, schema)
        except jsonschema.ValidationError as e:
            where = "/".join(str(p) for p in e.absolute_path) or "(top level)"
            raise AssertionError(f"'{msg_type}' does not match schemas/{msg_type}.json at {where}: {e.message}") from None

    def save(self) -> list[str]:
        SCHEMA_DIR.mkdir(exist_ok=True)
        for msg_type in sorted(self._dirty):
            schema = dict(self._schemas[msg_type])
            schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
            schema["title"] = msg_type
            self._path(msg_type).write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
        return sorted(self._dirty)
