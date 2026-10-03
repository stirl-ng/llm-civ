"""Turn cycle and soak: end turns and check the DLL pushes the next turn_start.

The turn-cycle test ends one turn. The soak test (`--soak-turns N`) ends N
turns and fails at the turn where the DLL crashed, hung, or stopped pushing
events. Both run last, after the read and write tests.
"""

from __future__ import annotations

import time

import pytest

from dlltest.transport import DllTransport, TransportError

AI_TURN_TIMEOUT = 180.0  # seconds; AI turns get slow later in a game
HEARTBEAT_TIMEOUT = 12.0  # the DLL pushes one every 5 s


def current_turn(call) -> int:
    return call("get_state", "state_refresh")["state"]["turn"]


def wait_for_turn_start(dll: DllTransport, turn: int, timeout: float = AI_TURN_TIMEOUT) -> dict:
    """Wait for the turn_start of `turn`, skipping older events still queued."""
    deadline = time.monotonic() + timeout
    while True:
        remaining = deadline - time.monotonic()
        try:
            event = dll.next_event(types=("turn_start",), timeout=max(remaining, 0.1))
        except TransportError as e:
            raise AssertionError(f"no turn_start for turn {turn}: {e}") from e
        if event.get("turn") == turn:
            return event


def force_end_turn(dll: DllTransport, call) -> int:
    """Clear the blockers a test can clear, force the turn to end, and return the new turn."""
    turn = current_turn(call)
    for _ in range(5):
        response = dll.request({"type": "force_end_turn"})
        if response.get("type") == "force_end_turn_ack":
            break
        if response.get("code") == "CANNOT_FORCE_END_TURN" and clear_blocker(call, response.get("blocking_type")):
            continue
        raise AssertionError(f"turn {turn}: cannot end the turn: {response}")
    else:
        raise AssertionError(f"turn {turn}: still blocked after clearing blockers")

    event = wait_for_turn_start(dll, turn + 1)
    assert event["player_id"] == call("get_state", "state_refresh")["state"]["activePlayer"]
    return turn + 1


def clear_blocker(call, blocking_type: str | None) -> bool:
    """Make the first available choice for a blocker. Test harness only: an agent always chooses."""
    if blocking_type == "ENDTURN_BLOCKING_RESEARCH":
        techs = call("get_available_techs", "available_techs_result")["available_techs"]
        return bool(techs) and call("choose_tech", "choose_tech_result", tech_id=techs[0]["id"])["success"]
    if blocking_type == "ENDTURN_BLOCKING_PRODUCTION":
        for city in call("get_cities", "cities_result")["cities"]:
            if not city.get("production"):
                options = call("get_city_production", "city_production_result", city_id=city["id"])
                unit = options["trainable_units"][0]
                call("set_city_production", "set_city_production_result",
                     city_id=city["id"], order_type=0, item_id=unit["id"])
        return True
    if blocking_type in ("ENDTURN_BLOCKING_POLICY", "ENDTURN_BLOCKING_FREE_POLICY"):
        policies = call("get_available_policies", "available_policies_result")
        if policies["adoptable_policies"]:
            return call("adopt_policy", "adopt_policy_result", policy_id=policies["adoptable_policies"][0]["id"])["success"]
        if policies["unlockable_branches"]:
            return call("adopt_policy", "adopt_policy_result", branch_id=policies["unlockable_branches"][0]["id"])["success"]
    return False


@pytest.mark.smoke
def test_end_turn_requires_turn_number(dll):
    response = dll.request({"type": "end_turn"})
    assert (response.get("type"), response.get("code")) == ("error", "MISSING_PARAMETER"), response


@pytest.mark.smoke
def test_end_turn_rejects_bad_turn_number(dll):
    response = dll.request({"type": "end_turn", "turn": -3})
    assert (response.get("type"), response.get("code")) == ("error", "INVALID_PARAMETER"), response


@pytest.mark.smoke
def test_turn_cycle(dll, call):
    new_turn = force_end_turn(dll, call)
    assert current_turn(call) == new_turn
    # The heartbeat keeps coming once the player's turn has started.
    beat = dll.next_event(types=("heartbeat",), timeout=HEARTBEAT_TIMEOUT)
    assert beat["turn"] == new_turn


@pytest.mark.soak
def test_soak(dll, call, pytestconfig):
    turns = pytestconfig.getoption("--soak-turns")
    if turns <= 0:
        pytest.skip("pass --soak-turns N to end N turns")
    for _ in range(turns):
        turn = force_end_turn(dll, call)
        assert call("ping", "pong")
        print(f"turn {turn} ok")
