# Protocol Documentation Comparison

This document compares `Community-Patch-DLL/docs/GameStatePipePlan.md` (DLL-side implementation plan) with `docs/protocol.md` (orchestrator-side documentation).

## Key Divergences

### 1. **Request/Response Correlation**

**GameStatePipePlan.md** (DLL):
- All requests require `request_id` for correlation
- All responses include `request_id` to match requests
- Example: `{"type": "action", "request_id": "abc123", "action": {...}}`

**protocol.md** (Orchestrator):
- No mention of `request_id`
- Simpler request/response model without explicit correlation

### 2. **Message Types - Outgoing (DLL → Client)**

**GameStatePipePlan.md** has many more message types:
- ✅ `turn_start` (both have)
- ✅ `action_result` (both have, but different structure)
- ❌ `turn_complete` (only in GameStatePipePlan)
- ❌ `notification` (only in GameStatePipePlan)
- ❌ `popup` (only in GameStatePipePlan)
- ❌ `diplomatic_message` (only in GameStatePipePlan)
- ❌ `tech_researched` (only in GameStatePipePlan)
- ❌ `state_refresh` (only in GameStatePipePlan)
- ❌ `notifications_result` (only in GameStatePipePlan)
- ❌ `demographics_result` (only in GameStatePipePlan)
- ❌ `economic_overview_result` (only in GameStatePipePlan)
- ❌ `player_status_result` (only in GameStatePipePlan)
- ❌ `units_result` (only in GameStatePipePlan)
- ❌ `tile_info_result` (only in GameStatePipePlan)
- ❌ `cities_result` (only in GameStatePipePlan)
- ❌ `control_executed` (only in GameStatePipePlan)
- ❌ `can_do_control_result` (only in GameStatePipePlan)
- ❌ `turn_end_ack` (only in GameStatePipePlan)
- ❌ `turn_end_initiated` (only in GameStatePipePlan)
- ❌ `error` (structured error messages in GameStatePipePlan)

### 3. **Message Types - Incoming (Client → DLL)**

**GameStatePipePlan.md** has query commands:
- ✅ `action` (both have, but different structure)
- ✅ `end_turn` (both have)
- ❌ `get_state` (only in GameStatePipePlan)
- ❌ `get_notifications` (only in GameStatePipePlan)
- ❌ `get_demographics` (only in GameStatePipePlan)
- ❌ `get_economic_overview` (only in GameStatePipePlan)
- ❌ `get_player_status` (only in GameStatePipePlan)
- ❌ `get_units` (only in GameStatePipePlan)
- ❌ `inspect_tile` (only in GameStatePipePlan)
- ❌ `get_cities` (only in GameStatePipePlan)
- ❌ `do_control` (only in GameStatePipePlan)
- ❌ `can_do_control` (only in GameStatePipePlan)
- ❌ `forced_end_turn` (only in GameStatePipePlan)

### 4. **Action Structure**

**GameStatePipePlan.md**:
```json
{
  "type": "action",
  "request_id": "abc123",
  "action": {
    "kind": "move_unit",
    "unit_id": 5,
    "to": [10, 15]
  }
}
```

**protocol.md**:
```json
{
  "type": "action",
  "action": {
    "command": "move_unit",
    "unit_id": 5,
    "x": 10,
    "y": 15
  }
}
```

**Differences:**
- GameStatePipePlan uses `action.kind` vs protocol.md uses `action.command`
- GameStatePipePlan uses `to: [x, y]` array vs protocol.md uses separate `x`, `y` fields
- GameStatePipePlan requires `request_id`, protocol.md doesn't

### 5. **Action Types Available**

**GameStatePipePlan.md** (only 2 documented):
- `move_unit` - move units to target coordinates
- `select_unit` - select units in the game

**protocol.md** (many more, but different format):
- `move_unit` - move unit
- `attack` - unit attack
- `research` - research technology
- `produce` - city production
- `adopt_policy` - adopt policy
- `found_city` - found city
- `fortify` - fortify unit
- `skip` - skip unit
- `build` - build improvement

**Note:** GameStatePipePlan mentions these as "Future Enhancements":
- `set_city_production`
- `execute_mission`
- Additional unit actions (attack, fortify, etc.)

### 6. **Error Handling**

**GameStatePipePlan.md**:
- Structured error codes: `CANNOT_END_TURN`, `AI_NOT_READY`, `TURN_ALREADY_ENDED`, `UNIT_NOT_FOUND`, etc.
- Error messages include `code` and `message` fields
- Example: `{"type": "error", "code": "UNIT_NOT_FOUND", "message": "...", "request_id": "abc123"}`

**protocol.md**:
- Simple error strings in `action_result.error`
- Example: `{"type": "action_result", "success": false, "error": "Unit cannot move..."}`

### 7. **Turn Management**

**GameStatePipePlan.md**:
- `end_turn` - end current turn
- `forced_end_turn` - force end turn (bypasses some blocks)
- `turn_end_ack` - acknowledgment that turn ended
- `turn_end_initiated` - notification that turn end is in progress
- `turn_complete` - sent when turn processing finishes

**protocol.md**:
- `end_turn` - end current turn (simple)

### 8. **State Schema**

**GameStatePipePlan.md**:
- `get_state` returns full state (placeholder implementation)
- Detailed schemas for query responses (notifications, demographics, cities, units, tiles)
- `state_delta` in `action_result` for incremental updates

**protocol.md**:
- `turn_start` includes full `state` object
- Suggested state schema with cities, units, technology, resources, diplomacy
- `action_result` can optionally include updated `state`

### 9. **Control Commands**

**GameStatePipePlan.md**:
- `do_control` - execute control commands
- `can_do_control` - check if control can be executed
- `control_executed` - response to do_control
- `can_do_control_result` - response to can_do_control

**protocol.md**:
- No control commands mentioned

## Summary

The **GameStatePipePlan.md** appears to be a more comprehensive, implementation-focused document that describes:
- A richer protocol with query/response patterns
- Request/response correlation via `request_id`
- Many more message types for events and queries
- Structured error handling
- More granular turn management

The **protocol.md** appears to be a simpler, higher-level overview that:
- Focuses on basic turn flow
- Uses simpler action structure
- Lists many action types that may not be implemented yet
- Has a suggested state schema

## Recommendations

1. **Synchronize the documents** - Decide which is the source of truth
2. **Align action structure** - Choose between `action.kind` vs `action.command` and `to: [x,y]` vs `x, y`
3. **Add request_id** - If the DLL implementation uses `request_id`, protocol.md should document it
4. **Document query commands** - If the DLL supports queries like `get_units`, `get_cities`, etc., protocol.md should document them
5. **Unify error handling** - Decide on structured error codes vs simple error strings
6. **Update action types** - Align the list of available actions between both documents

