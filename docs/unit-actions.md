# Unit Actions

> **v1 tool names.** The DLL commands stay in v2. The LLM-facing tools are redefined in the v2 Game Server. See [`target-architecture.md`](target-architecture.md).

How to list units and execute unit actions via the LLM agent tools.

---

## Listing Units

Use `get_units` with no arguments. Returns all units for the active player.

**Key response fields:**
- `id` — unit identifier; use this in all action tools
- `x`, `y` — current coordinates
- `unit_type_name` — e.g. `"Settler"`, `"Warrior"`
- `moves_remaining` — movement points left this turn
- `can_move` — whether the unit can still act
- `activity` — if `"MISSION"`, unit is already executing a queued path; do not re-command it
- `experience`, `level`, `promotion_ready` — `promotion_ready` means the unit has enough XP to choose a promotion (see [Promotions](#promotions))

---

## Unit Action Tools

Each action is a first-class tool with flat parameters — no nesting.

### `move_unit`

Move a unit to target coordinates. Supports multi-turn A* pathfinding — give the destination, not the next step.

```json
{ "unit_id": 1001, "to": [16, 21] }
```

**Errors:** `UNIT_NOT_FOUND`, `INVALID_PLOT`, `INVALID_COORDINATES`

---

### `unit_found_city`

Found a city with a settler at its current location. Settler is consumed.

```json
{ "unit_id": 1001 }
```

**Errors:** `UNIT_NOT_FOUND`, `UNIT_NOT_OWNED`, `CANNOT_FOUND_CITY`

---

### `unit_sleep`

Put a unit to sleep indefinitely. Unit stays in place until manually woken.

```json
{ "unit_id": 1002 }
```

---

### `unit_skip`

Skip the unit's turn without sleeping. Use to clear the "unit needs orders" state for one turn.

```json
{ "unit_id": 1002 }
```

---

### `unit_alert`

Set a unit to alert stance. Unit will auto-wake if enemies approach.

```json
{ "unit_id": 1002 }
```

---

### `unit_fortify`

Fortify a unit in place. Unit gains stacking defensive bonuses each turn it remains fortified.

```json
{ "unit_id": 1002 }
```

---

### `unit_heal`

Set a unit to heal. Unit skips movement and recovers HP.

```json
{ "unit_id": 1002 }
```

---

## Promotions

A unit with enough XP has `promotion_ready: true` in `get_units`, and the briefing marks it "can promote". Unless the Promotion Saving game option is on, such a unit blocks `end_turn` with `ENDTURN_BLOCKING_UNIT_PROMOTION`, and the error includes `promotion_units[]` (same shape as `get_unit_promotions`). The game never picks a promotion for the LLM.

### `get_unit_promotions`

```json
{ "unit_id": 1002 }
```

`unit_id` is optional; without it, returns every unit that can promote now. Each entry in `units[]` has `unit_id`, `unit_name`, `x`, `y`, `experience`, `experience_needed` (XP for the next level), `level`, `promotion_ready`, `promotions[]` (held: `promotion_id`, `type`, `name`), and `available_promotions[]` (choosable now: also `help`). `available_promotions` is empty unless `promotion_ready`.

### `promote_unit`

```json
{ "unit_id": 1002, "promotion_id": 7 }
```

Takes the promotion. Does not use the unit's moves. The result has `promoted` and the updated `unit`. If the unit has XP for more than one level, it stays `promotion_ready` and can promote again.

**Errors:** `UNIT_NOT_FOUND`, `UNIT_NOT_OWNED`, `PROMOTION_NOT_READY`, `CANNOT_PROMOTE`. A failure includes the unit's current `available_promotions`.

---

## Worker Actions

Workers build tile improvements over multiple turns.

### Workflow

1. Call `get_unit_build_options(unit_id=<worker_id>)` — returns available builds for each nearby tile, with `build_type` IDs and `turns_required`.
2. Call `move_unit` to place the worker on the target tile if it isn't already there.
3. Call `unit_build(unit_id=<worker_id>, build_type=<id>)` — worker starts building and continues automatically on future turns.

### `unit_build`

Build an improvement at the worker's current tile.

```json
{ "unit_id": 1005, "build_type": 3 }
```

**Errors:** `UNIT_NOT_FOUND`, `UNIT_NOT_OWNED`, `CANNOT_BUILD`, `INVALID_BUILD_TYPE`

`build_type` is an opaque integer — always get it from `get_unit_build_options`, never hardcode it.

---

## Typical Turn Flow

1. Call `get_units` — identify units needing orders
2. Skip units with `activity == "MISSION"` (already pathing)
3. For each remaining unit: call the appropriate action tool
4. Call `end_turn` when done

---

## Error Handling

All action tools return `success: true/false`. On failure, an `error` object is included:

```json
{
  "success": false,
  "error": {
    "code": "CANNOT_FOUND_CITY",
    "message": "Unit cannot found a city at this location"
  }
}
```

Common codes: `UNIT_NOT_FOUND`, `UNIT_NOT_OWNED`, `CANNOT_FOUND_CITY`, `INVALID_PLOT`, `INVALID_COORDINATES`

---

## Adding New Unit Actions

1. Add a `msgType` branch in `HandlePipeCommand()` in `CvGame.cpp`
2. Add a handler method and entry in `_TOOLS` in `python/orchestrator/mcp_server.py`
3. Add an OpenAI-format schema in `python/agent_runtime/tools/schemas.py`

Note: `mcp_server._TOOLS` and `schemas.py` must be kept in sync manually — see `docs/systems.md`.
