"""Per-command smoke tests: each command answers, with the right type and keys."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.smoke

CONTROL_ENDTURN = 13  # ControlTypes in CvEnums.h

UNIT_KEYS = {
    "id", "x", "y", "unit_type", "unit_type_name", "moves_remaining", "max_moves",
    "damage", "experience", "level", "promotion_ready", "activity",
}


def require_keys(obj: dict, keys: set[str], where: str) -> None:
    missing = keys - obj.keys()
    assert not missing, f"{where} is missing {sorted(missing)}: {obj}"


@pytest.fixture(scope="module")
def units(call) -> list[dict]:
    return call("get_units", "units_result")["units"]


# --- Reads --------------------------------------------------------------


def test_ping(call):
    call("ping", "pong")


def test_get_state(call, game):
    state = call("get_state", "state_refresh")["state"]
    assert state["turn"] == game.turn
    assert state["activePlayer"] == game.player_id


def test_get_units(units):
    assert units, "the active player has no units"
    for unit in units:
        require_keys(unit, UNIT_KEYS, f"unit {unit.get('id')}")


def test_get_cities(call, game):
    response = call("get_cities", "cities_result")
    assert response["player_id"] == game.player_id
    assert isinstance(response["cities"], list)


def test_get_player_status(call, game):
    response = call("get_player_status", "player_status_result")
    assert response["turn"] == game.turn
    require_keys(response, {"gold", "science", "culture", "faith", "happiness", "golden_age"}, "player status")


def test_get_turn_blockers(call):
    blockers = call("get_turn_blockers", "turn_blockers_result")["blockers"]
    for blocker in blockers:
        require_keys(blocker, {"type", "type_id"}, "turn blocker")


def test_get_available_techs(call):
    response = call("get_available_techs", "available_techs_result")
    require_keys(response, {"current_research", "available_techs"}, "available techs")


def test_get_available_policies(call):
    response = call("get_available_policies", "available_policies_result")
    require_keys(
        response,
        {"next_policy_cost", "unlockable_branches", "unlocked_branches", "adoptable_policies", "adopted_policies"},
        "available policies",
    )


def test_get_demographics(call, game):
    players = call("get_demographics", "demographics_result")["players"]
    assert any(p["player_id"] == game.player_id for p in players), "active player missing from demographics"
    for player in players:
        require_keys(player, {"player_id", "name", "civ", "stats"}, f"demographics player {player.get('player_id')}")


def test_get_notifications(call):
    response = call("get_notifications", "notifications_result")
    assert response["count"] == len(response["notifications"])


def test_get_visible_tiles(call):
    response = call("get_visible_tiles", "visible_tiles_result")
    width, height = response["map_width"], response["map_height"]
    assert response["tiles"], "no visible tiles"
    for tile in response["tiles"]:
        assert 0 <= tile["x"] < width and 0 <= tile["y"] < height, f"tile off the map: {tile}"


def test_can_do_control(call):
    response = call("can_do_control", "can_do_control_result", control_type=CONTROL_ENDTURN)
    assert response["control_type"] == CONTROL_ENDTURN


def test_get_unit_promotions(call, units):
    for unit in units:
        response = call("get_unit_promotions", "get_unit_promotions_result", unit_id=unit["id"])
        assert [u["unit_id"] for u in response["units"]] == [unit["id"]]


def test_get_reachable_tiles(call, units):
    for unit in units:
        response = call("get_reachable_tiles", "reachable_tiles_result", unit_id=unit["id"])
        here = {"x": unit["x"], "y": unit["y"]}
        assert response["unit_position"] == here
        assert any(t["x"] == here["x"] and t["y"] == here["y"] for t in response["tiles"]), (
            f"unit {unit['id']}'s own tile is not reachable"
        )


def test_get_unit_build_options(call, units):
    for unit in units:
        response = call("get_unit_build_options", "unit_build_options_result", unit_id=unit["id"])
        assert response["unit_id"] == unit["id"]
        assert isinstance(response["tiles"], list)


def test_get_city_production(call, game):
    cities = call("get_cities", "cities_result")["cities"]
    if not cities:
        pytest.skip(f"save '{game.save}' has no cities")
    for city in cities:
        call("get_city_production", "city_production_result", city_id=city["id"])


# --- Bad input (STI-20) ---------------------------------------------------
# Each bad command must get an error reply carrying its request_id (the
# transport only returns a reply that matches it), and the DLL must still
# answer a ping afterwards. Before STI-20 several of these crashed the game.

BAD_INPUT = [
    ("unknown command", {"type": "no_such_command"}, "UNKNOWN_MESSAGE_TYPE"),
    ("player_id too large", {"type": "get_units", "player_id": 999}, "INVALID_PLAYER_ID"),
    ("player_id below -1", {"type": "get_units", "player_id": -5}, "INVALID_PLAYER_ID"),
    ("notifications player_id", {"type": "get_notifications", "player_id": 999}, "INVALID_PLAYER_ID"),
    ("status player_id", {"type": "get_player_status", "player_id": 999}, "INVALID_PLAYER_ID"),
    ("cities player_id", {"type": "get_cities", "player_id": 999}, "INVALID_PLAYER_ID"),
    ("techs player_id", {"type": "get_available_techs", "player_id": 999}, "INVALID_PLAYER_ID"),
    ("ai_player_id", {"type": "trade_respond", "ai_player_id": 999, "accept": False}, "INVALID_PLAYER_ID"),
    ("tech_id", {"type": "choose_tech", "tech_id": 99999}, "INVALID_ARGUMENT"),
    ("policy_id", {"type": "adopt_policy", "policy_id": 99999}, "INVALID_ARGUMENT"),
    ("branch_id", {"type": "adopt_policy", "branch_id": 99999}, "INVALID_ARGUMENT"),
    ("belief_id", {"type": "select_pantheon", "belief_id": 99999}, "INVALID_ARGUMENT"),
    ("control_type", {"type": "do_control", "control_type": 9999}, "INVALID_ARGUMENT"),
    ("promotion_id", {"type": "promote_unit", "unit_id": 1002, "promotion_id": 99999}, "INVALID_ARGUMENT"),
]


@pytest.mark.parametrize("message,code", [(m, c) for _, m, c in BAD_INPUT], ids=[n for n, _, _ in BAD_INPUT])
def test_bad_input_is_rejected(dll, message, code):
    response = dll.request(dict(message))
    assert response.get("type") == "error", f"expected an error reply, got {response}"
    assert response.get("code") == code, f"expected {code}, got {response}"
    assert dll.request({"type": "ping"}).get("type") == "pong", "DLL stopped answering"


def test_production_item_out_of_range(dll):
    response = dll.request({"type": "set_city_production", "city_id": 1, "order_type": 0, "item_id": 99999})
    assert response.get("type") == "set_city_production_result", response
    assert response["error"]["code"] == "INVALID_ITEM", response
    assert dll.request({"type": "ping"}).get("type") == "pong", "DLL stopped answering"
