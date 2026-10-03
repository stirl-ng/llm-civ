"""Snapshot tests: read replies on the freshly loaded save must match stored copies.

The stored copies are snapshots/<save>/<name>.json. A DLL change that alters
any read reply fails here and shows the difference; if the change is
intended, rerun with --update-snapshots and commit the new files, so the
diff records what the change did to the output. Runs before the write tests,
on the save as loaded.
"""

from __future__ import annotations

import difflib
import json
from pathlib import Path

import pytest

pytestmark = [pytest.mark.snapshot, pytest.mark.usefixtures("fresh_save")]

SNAPSHOT_DIR = Path(__file__).resolve().parent / "snapshots"

# Differ on every call, so they are not part of the reply's content.
VOLATILE_KEYS = {"request_id", "session_id", "timestamp", "uuid"}

READS = [
    "get_state",
    "get_units",
    "get_cities",
    "get_player_status",
    "get_turn_blockers",
    "get_available_techs",
    "get_available_policies",
    "get_demographics",
    "get_notifications",
    "get_visible_tiles",
]
PER_UNIT_READS = ["get_unit_promotions", "get_reachable_tiles", "get_unit_build_options"]


def normalize(value):
    if isinstance(value, dict):
        return {k: normalize(v) for k, v in sorted(value.items()) if k not in VOLATILE_KEYS}
    if isinstance(value, list):
        return [normalize(v) for v in value]
    return value


@pytest.fixture
def snapshot(game, pytestconfig):
    update = pytestconfig.getoption("--update-snapshots")

    def compare(name: str, response: dict) -> None:
        path = SNAPSHOT_DIR / game.save / f"{name}.json"
        actual = json.dumps(normalize(response), indent=2) + "\n"
        if update:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(actual, encoding="utf-8")
            return
        if not path.exists():
            pytest.fail(f"no snapshot {path.relative_to(SNAPSHOT_DIR)}; run with --update-snapshots to create it")
        expected = path.read_text(encoding="utf-8")
        if actual != expected:
            diff = "".join(difflib.unified_diff(
                expected.splitlines(keepends=True), actual.splitlines(keepends=True),
                fromfile=f"snapshot {name}", tofile="this run", n=2,
            ))
            pytest.fail(f"{name} differs from its snapshot (--update-snapshots if intended):\n{diff[:6000]}")

    return compare


@pytest.mark.parametrize("command", READS)
def test_read_matches_snapshot(dll, snapshot, command):
    snapshot(command, dll.request({"type": command}))


@pytest.mark.parametrize("command", PER_UNIT_READS)
def test_unit_read_matches_snapshot(dll, call, snapshot, command):
    for unit in call("get_units", "units_result")["units"]:
        snapshot(f"{command}_{unit['id']}", dll.request({"type": command, "unit_id": unit["id"]}))


def test_city_production_matches_snapshot(dll, call, snapshot):
    for city in call("get_cities", "cities_result")["cities"]:
        snapshot(f"get_city_production_{city['id']}", dll.request({"type": "get_city_production", "city_id": city["id"]}))
