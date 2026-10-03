"""Write-command smoke tests: send the command, then read the game back.

These change the game, so they need a freshly loaded save: they skip when a
unit has already moved or acted. Reload the save before each full run. They
run after the read tests (see conftest.pytest_collection_modifyitems).
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.smoke, pytest.mark.usefixtures("fresh_save")]


CONTROL_CENTERONSELECTION = 0  # ControlTypes in CvEnums.h


def units_by_id(call) -> dict[int, dict]:
    return {u["id"]: u for u in call("get_units", "units_result")["units"]}


def unit_named(call, type_name: str) -> dict:
    for unit in units_by_id(call).values():
        if unit["unit_type_name"] == type_name:
            return unit
    pytest.skip(f"no {type_name} in this save")


def result(call, msg_type: str, **args) -> dict:
    """Send a write command and return its reply. The reply type is <msg_type>_result."""
    return call(msg_type, f"{msg_type}_result", **args)


def assert_refused(response: dict, code: str) -> None:
    assert response.get("success") is False, f"expected a refusal, got {response}"
    assert response["error"]["code"] == code, f"expected {code}, got {response}"



# --- Units -----------------------------------------------------------------


def test_select_unit(call):
    warrior = unit_named(call, "Warrior")
    assert result(call, "select_unit", unit_id=warrior["id"])["success"] is True


def test_unit_fortify(call):
    warrior = unit_named(call, "Warrior")
    assert result(call, "unit_fortify", unit_id=warrior["id"])["success"] is True
    # The engine stores fortify as ACTIVITY_SLEEP.
    assert units_by_id(call)[warrior["id"]]["activity"] == "SLEEP"


def test_unit_alert(call):
    warrior = unit_named(call, "Warrior")
    assert result(call, "unit_alert", unit_id=warrior["id"])["success"] is True
    assert units_by_id(call)[warrior["id"]]["activity"] == "SENTRY"


def test_unit_heal_refused_at_full_health(call):
    warrior = unit_named(call, "Warrior")
    assert warrior["damage"] == 0
    assert_refused(result(call, "unit_heal", unit_id=warrior["id"]), "CANNOT_HEAL")


def test_unit_skip(call):
    worker = unit_named(call, "Worker")
    assert result(call, "unit_skip", unit_id=worker["id"])["success"] is True
    assert units_by_id(call)[worker["id"]]["activity"] == "HOLD"


def test_unit_sleep(call):
    worker = unit_named(call, "Worker")
    assert result(call, "unit_sleep", unit_id=worker["id"])["success"] is True
    assert units_by_id(call)[worker["id"]]["activity"] == "SLEEP"


def test_move_unit(call):
    scout = unit_named(call, "Scout")
    tiles = call("get_reachable_tiles", "reachable_tiles_result", unit_id=scout["id"])["tiles"]
    here = (scout["x"], scout["y"])
    target = next(
        (t for t in tiles if (t["x"], t["y"]) != here and t["can_enter"] and t["moves_left"] > 0 and not t["can_attack"]),
        None,
    )
    assert target, f"scout {scout['id']} has no reachable tile"

    response = result(call, "move_unit", unit_id=scout["id"], to=[target["x"], target["y"]])
    assert response["success"] is True, response
    moved = units_by_id(call)[scout["id"]]
    assert (moved["x"], moved["y"]) == (target["x"], target["y"])
    assert moved["moves_remaining"] == target["moves_left"]


def test_unit_auto_explore(call):
    scout = unit_named(call, "Scout")
    assert result(call, "unit_auto_explore", unit_id=scout["id"])["success"] is True


def test_unit_build(call):
    worker = unit_named(call, "Worker")
    options = call("get_unit_build_options", "unit_build_options_result", unit_id=worker["id"])
    reachable = call("get_reachable_tiles", "reachable_tiles_result", unit_id=worker["id"])["tiles"]
    # Tiles the worker can stand on this turn with moves left to start building.
    usable = {(t["x"], t["y"]) for t in reachable if t["can_enter"] and t["moves_left"] > 0}
    tile = next((t for t in options["tiles"] if t["available_builds"] and (t["x"], t["y"]) in usable), None)
    if tile is None:
        pytest.skip(f"worker {worker['id']} cannot reach a buildable tile this turn")

    if (tile["x"], tile["y"]) != (worker["x"], worker["y"]):
        assert result(call, "move_unit", unit_id=worker["id"], to=[tile["x"], tile["y"]])["success"] is True
    build = tile["available_builds"][0]["build_type"]
    assert result(call, "unit_build", unit_id=worker["id"], build_type=build)["success"] is True


# --- Refusals: valid commands the base save cannot carry out ---------------
# The DLL must answer with a clear error, not crash or hang.


def test_promote_unit_refused_without_xp(call):
    warrior = unit_named(call, "Warrior")
    assert_refused(result(call, "promote_unit", unit_id=warrior["id"], promotion_id=0), "PROMOTION_NOT_READY")


def test_unit_found_city_refused_for_warrior(call):
    warrior = unit_named(call, "Warrior")
    assert_refused(result(call, "unit_found_city", unit_id=warrior["id"]), "CANNOT_FOUND_CITY")


def test_unit_pillage_refused_without_improvement(call):
    warrior = unit_named(call, "Warrior")
    assert_refused(result(call, "unit_pillage", unit_id=warrior["id"]), "CANNOT_PILLAGE")


def test_unit_ranged_attack_refused_for_melee(call):
    warrior = unit_named(call, "Warrior")
    target = [warrior["x"] + 1, warrior["y"]]
    response = result(call, "unit_ranged_attack", unit_id=warrior["id"], target=target)
    assert response.get("success") is False, response


def test_declare_war_on_self_refused(call, game):
    response = call("declare_war", "declare_war_result", player_id=game.player_id)
    assert response.get("success") is False, response


def test_adopt_policy_refused_without_culture(call):
    policies = call("get_available_policies", "available_policies_result")
    if policies["adoptable_policies"] or policies["unlockable_branches"]:
        pytest.skip("a policy is adoptable in this save")
    response = result(call, "adopt_policy", policy_id=1)
    assert response.get("success") is False, response


STI_21 = pytest.mark.xfail(strict=True, reason="STI-21: the DLL skips the faith / Great Prophet requirements")


@pytest.mark.parametrize(
    "msg_type,args",
    [
        pytest.param("select_pantheon", {"belief_id": 0}, marks=STI_21),
        pytest.param("found_religion", {"religion_id": 1, "founder_belief_id": 0, "follower_belief_id": 0}, marks=STI_21),
        ("enhance_religion", {"enhancer_belief_id": 0}),
        ("city_capture_decision", {"city_id": 1, "action": "puppet"}),
        ("trade_respond", {"ai_player_id": 1, "accept": False}),
        ("choose_goody_hut_reward", {"goody_id": 0}),
    ],
)
def test_choice_command_refused_when_nothing_pending(call, msg_type, args):
    response = result(call, msg_type, **args)
    assert response.get("success") is False, response


# --- City, research, controls ------------------------------------------------


def test_set_city_production(call):
    city = call("get_cities", "cities_result")["cities"][0]
    options = call("get_city_production", "city_production_result", city_id=city["id"])
    current = options["current_production"]
    unit = next(u for u in options["trainable_units"] if current.get("order_type") != 0 or u["id"] != current.get("item_id"))

    response = result(call, "set_city_production", city_id=city["id"], order_type=0, item_id=unit["id"])
    assert response["success"] is True, response
    now = call("get_city_production", "city_production_result", city_id=city["id"])["current_production"]
    assert (now["order_type"], now["item_id"]) == (0, unit["id"])


def test_choose_tech(call):
    techs = call("get_available_techs", "available_techs_result")
    current = (techs["current_research"] or {}).get("id")
    tech = next(t for t in techs["available_techs"] if t["id"] != current)

    assert result(call, "choose_tech", tech_id=tech["id"])["success"] is True
    now = call("get_available_techs", "available_techs_result")["current_research"]
    assert now and now["id"] == tech["id"], now


def test_do_control_agrees_with_can_do_control(call, dll):
    can_do = call("can_do_control", "can_do_control_result", control_type=CONTROL_CENTERONSELECTION)["can_do"]
    response = dll.request({"type": "do_control", "control_type": CONTROL_CENTERONSELECTION})
    if can_do:
        assert response.get("type") == "control_executed", response
    else:
        assert (response.get("type"), response.get("code")) == ("error", "CANNOT_DO_CONTROL"), response


# --- Last: removes a unit ------------------------------------------------------


def test_unit_delete(call):
    worker = unit_named(call, "Worker")
    assert result(call, "unit_delete", unit_id=worker["id"])["success"] is True
    assert worker["id"] not in units_by_id(call)
