# Unit-Tile Interaction Queries for LLM

This document specifies MCP tools that expose what actions units can perform on tiles, enabling the LLM to make informed decisions about worker task assignments, city founding, great person placement, and unit movement.

## Design Philosophy

From CLAUDE.md: "The LLM should have access to the same information as a human player."

Human players see:
- **Builder lens**: Tiles that can be improved, with which improvements available
- **Movement range**: Highlighted tiles units can reach this turn
- **City founding overlay**: Valid locations for new cities
- **Great person placement**: Where great works/improvements can go

The LLM should query this same information programmatically.

---

## Background: C++ Validation Architecture

### Worker Improvements (Three-Level Hierarchy)

```
CvUnit::canBuild(plot, buildType)
├─ Unit capabilities (builder strength, moves, delay-death)
├─ Player tech/trait requirements
└─ CvPlayer::canBuild(plot, buildType)
   ├─ Tech prerequisites (building & feature removal)
   ├─ Civ-specific improvements
   ├─ Resource requirements
   └─ CvPlot::canBuild(buildType)
      ├─ Terrain/feature compatibility via canHaveImprovement()
      ├─ Existing improvements (overlap rules)
      ├─ Adjacency requirements (luxury, water, city, etc.)
      └─ Ownership/borders validation
```

**Key Files:**
- `CvUnit.cpp:13019` - CvUnit::canBuild()
- `CvPlayer.cpp:16085` - CvPlayer::canBuild()
- `CvPlot.cpp:2917` - CvPlot::canBuild()
- `CvPlot.cpp:2508` - CvPlot::canHaveImprovement()

### City Founding

```
CvUnit::canFoundCity(plot)
├─ Unit can move into plot
├─ Unit has founding capability (IsFound, IsFoundAbroad, etc.)
└─ CvPlayer::canFoundCityExt(plot)
   ├─ Minimum distance from existing cities
   ├─ Happiness available for expansion
   └─ City state relationships
```

**Key Files:**
- `CvUnit.cpp:10548` - CvUnit::canFoundCity()

### Movement

```
CvUnit::canMoveInto(plot, flags)
├─ Attack vs destination validation
├─ Stacking rules
├─ Enemy/visible checks
└─ CvUnit::canEnterTerrain(terrainType, bIgnoreRightOfPassage, etc.)
   ├─ Domain matching (air, sea, land, immobile)
   ├─ Embarkation tech/promotions
   ├─ Impassable terrain exceptions
   ├─ Mountains, ice, ocean crossing
   └─ Route passage, trade unit exceptions
```

**Pathfinding:** A*-based via CvAStar/CvPathFinder with terrain cost functions.

**Key Files:**
- `CvUnit.cpp:4993` - CvUnit::canMoveInto()
- `CvUnit.cpp:4673` - CvUnit::canEnterTerrain()

### Great Person Improvements

Two distinct systems:

**Great Works** (Artists, Writers, Musicians):
- `CvUnit::canCreateGreatWork()` - Finds empire-wide slot availability
- Not tile-specific - finds closest available building with slot
- Slot types: ART_ARTIFACT, LITERATURE, MUSIC, RELIC, FILM

**Tile Improvements** (Scientists, Engineers, Merchants):
- Academy, Manufactory, Customs House
- Use standard worker build system (canBuild validation)

**Key Files:**
- `CvUnit.cpp:9213` - CvUnit::canCreateGreatWork()

---

## Proposed MCP Tools

### 1. `get_unit_build_options`

Query what a worker/builder unit can build on tiles in its vicinity.

**Request:**
```json
{
  "type": "get_unit_build_options",
  "request_id": "req123",
  "unit_id": 5,
  "radius": 5,
  "include_all_tiles": false
}
```

**Parameters:**
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `unit_id` | `int` | Yes | - | Unit ID to query |
| `radius` | `int` | No | 5 | Search radius from unit position |
| `include_all_tiles` | `bool` | No | false | If true, include tiles with no valid builds |

**Response:**
```json
{
  "type": "unit_build_options_result",
  "request_id": "req123",
  "unit_id": 5,
  "unit_type": "Worker",
  "unit_position": {"x": 10, "y": 12},
  "tiles": [
    {
      "x": 11,
      "y": 12,
      "terrain_type": 0,
      "feature_type": 0,
      "resource_type": 5,
      "resource_name": "Wheat",
      "current_improvement": -1,
      "available_builds": [
        {
          "build_type": 2,
          "build_name": "Farm",
          "turns_required": 6,
          "requires_tech": -1,
          "yields": {"food": 1, "production": 0, "gold": 0}
        },
        {
          "build_type": 10,
          "build_name": "Road",
          "turns_required": 3,
          "requires_tech": -1
        }
      ]
    },
    {
      "x": 10,
      "y": 13,
      "terrain_type": 2,
      "feature_type": -1,
      "resource_type": -1,
      "current_improvement": -1,
      "available_builds": [
        {
          "build_type": 2,
          "build_name": "Farm",
          "turns_required": 6,
          "requires_tech": -1,
          "yields": {"food": 1, "production": 0, "gold": 0}
        }
      ]
    }
  ]
}
```

**C++ Implementation Strategy:**
```cpp
else if (msgType == "get_unit_build_options")
{
    int unitId = msg.get("unit_id").asInt();
    int radius = msg.get("radius").asInt(5);
    bool includeAllTiles = msg.get("include_all_tiles").asBool(false);

    CvUnit* pUnit = FindUnitById(unitId);
    if (!pUnit) {
        SendError("UNIT_NOT_FOUND");
        return;
    }

    CvPlot* pUnitPlot = pUnit->plot();
    int centerX = pUnitPlot->getX();
    int centerY = pUnitPlot->getY();

    std::ostringstream os;
    os << "{\"type\":\"unit_build_options_result\"";
    os << ",\"unit_id\":" << unitId;
    os << ",\"tiles\":[";

    bool first = true;
    for (int dx = -radius; dx <= radius; dx++) {
        for (int dy = -radius; dy <= radius; dy++) {
            CvPlot* pPlot = plotXYWithRangeCheck(centerX, centerY, dx, dy, radius);
            if (!pPlot) continue;

            // Check all build types
            std::vector<BuildTypes> validBuilds;
            for (int i = 0; i < GC.getNumBuildInfos(); i++) {
                BuildTypes eBuild = (BuildTypes)i;
                if (pUnit->canBuild(pPlot, eBuild)) {
                    validBuilds.push_back(eBuild);
                }
            }

            if (validBuilds.empty() && !includeAllTiles) continue;

            if (!first) os << ",";
            first = false;

            // Serialize tile with available builds
            SerializeTileWithBuilds(os, pPlot, validBuilds);
        }
    }

    os << "]}";
    m_kGameStatePipe.SendLine(os.str());
}
```

**Performance:** For radius=5 (11×11 grid = 121 tiles), ~30 build types, ~3630 `canBuild()` calls. Estimated time: 5-10ms.

---

### 2. `get_builder_ai_tasks`

Expose the AI's BuilderTaskingAI system to get prioritized recommendations.

**Request:**
```json
{
  "type": "get_builder_ai_tasks",
  "request_id": "req124",
  "unit_id": 5,
  "max_tasks": 10
}
```

**Parameters:**
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `unit_id` | `int` | Yes | - | Worker unit ID |
| `max_tasks` | `int` | No | 10 | Maximum tasks to return |

**Response:**
```json
{
  "type": "builder_ai_tasks_result",
  "request_id": "req124",
  "unit_id": 5,
  "tasks": [
    {
      "directive_type": "BUILD_IMPROVEMENT_ON_RESOURCE",
      "x": 11,
      "y": 12,
      "build_type": 2,
      "build_name": "Farm",
      "resource_type": 5,
      "resource_name": "Wheat",
      "score": 850,
      "turns_to_complete": 6,
      "turns_to_reach": 1,
      "total_turns": 7
    },
    {
      "directive_type": "BUILD_ROUTE",
      "x": 10,
      "y": 11,
      "build_type": 10,
      "build_name": "Road",
      "score": 420,
      "turns_to_complete": 3,
      "turns_to_reach": 0,
      "total_turns": 3
    }
  ]
}
```

**C++ Implementation Strategy:**
```cpp
else if (msgType == "get_builder_ai_tasks")
{
    int unitId = msg.get("unit_id").asInt();
    int maxTasks = msg.get("max_tasks").asInt(10);

    CvUnit* pUnit = FindUnitById(unitId);
    if (!pUnit) {
        SendError("UNIT_NOT_FOUND");
        return;
    }

    CvPlayer& kPlayer = GET_PLAYER(pUnit->getOwner());

    // Use existing builder AI to evaluate tasks
    CvBuilderTaskingAI* pBuilderAI = kPlayer.GetBuilderTaskingAI();
    if (!pBuilderAI) {
        SendError("BUILDER_AI_NOT_AVAILABLE");
        return;
    }

    // Get prioritized directive list
    pBuilderAI->Update();
    CvBuilderDirective directive = pBuilderAI->GetAssignedDirective(pUnit);

    // TODO: Need to expose multiple directives, not just assigned one
    // May require extending CvBuilderTaskingAI to return top-N directives

    std::ostringstream os;
    os << "{\"type\":\"builder_ai_tasks_result\"";
    os << ",\"unit_id\":" << unitId;
    os << ",\"tasks\":[";

    // Serialize directive
    SerializeBuilderDirective(os, directive);

    os << "]}";
    m_kGameStatePipe.SendLine(os.str());
}
```

**Limitation:** Current `CvBuilderTaskingAI` only returns single assigned directive per unit. May need to extend API to return top-N directives for LLM to evaluate.

---

### 3. `get_reachable_tiles`

Query which tiles a unit can move to this turn.

**Request:**
```json
{
  "type": "get_reachable_tiles",
  "request_id": "req125",
  "unit_id": 8,
  "include_attacks": true
}
```

**Parameters:**
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `unit_id` | `int` | Yes | - | Unit ID to query |
| `include_attacks` | `bool` | No | true | Include tiles unit can attack (not just move into) |

**Response:**
```json
{
  "type": "reachable_tiles_result",
  "request_id": "req125",
  "unit_id": 8,
  "unit_position": {"x": 15, "y": 10},
  "moves_remaining": 2,
  "tiles": [
    {
      "x": 16,
      "y": 10,
      "movement_cost": 1,
      "can_enter": true,
      "can_attack": false,
      "is_enemy_unit": false
    },
    {
      "x": 17,
      "y": 10,
      "movement_cost": 2,
      "can_enter": true,
      "can_attack": false,
      "is_enemy_unit": false
    },
    {
      "x": 16,
      "y": 11,
      "movement_cost": 999,
      "can_enter": false,
      "can_attack": true,
      "is_enemy_unit": true,
      "enemy_unit_type": "Warrior"
    }
  ]
}
```

**C++ Implementation Strategy:**
```cpp
else if (msgType == "get_reachable_tiles")
{
    int unitId = msg.get("unit_id").asInt();
    bool includeAttacks = msg.get("include_attacks").asBool(true);

    CvUnit* pUnit = FindUnitById(unitId);
    if (!pUnit) {
        SendError("UNIT_NOT_FOUND");
        return;
    }

    // Use pathfinder to get reachable set
    ReachablePlots reachablePlots;
    pUnit->GetAllReachablePlotsInRange(pUnit->getMoves(), reachablePlots);

    std::ostringstream os;
    os << "{\"type\":\"reachable_tiles_result\"";
    os << ",\"unit_id\":" << unitId;
    os << ",\"moves_remaining\":" << pUnit->getMoves();
    os << ",\"tiles\":[";

    bool first = true;
    for (ReachablePlots::iterator it = reachablePlots.begin();
         it != reachablePlots.end(); ++it)
    {
        CvPlot* pPlot = GC.getMap().plotByIndexUnchecked(it->iPlotIndex);
        if (!pPlot) continue;

        if (!first) os << ",";
        first = false;

        os << "{\"x\":" << pPlot->getX();
        os << ",\"y\":" << pPlot->getY();
        os << ",\"movement_cost\":" << it->iMoveCost;
        os << ",\"can_enter\":" << (pUnit->canMoveInto(*pPlot, MOVEFLAG_DESTINATION) ? "true" : "false");

        if (includeAttacks) {
            bool canAttack = pUnit->canMoveInto(*pPlot, MOVEFLAG_ATTACK);
            os << ",\"can_attack\":" << (canAttack ? "true" : "false");

            if (canAttack) {
                // Check for enemy unit
                CvUnit* pDefender = pPlot->getBestDefender(NO_PLAYER, pUnit->getOwner());
                if (pDefender) {
                    os << ",\"is_enemy_unit\":true";
                    os << ",\"enemy_unit_type\":\"" << PipeUtils::JsonEscape(pDefender->getName()) << "\"";
                }
            }
        }

        os << "}";
    }

    os << "]}";
    m_kGameStatePipe.SendLine(os.str());
}
```

**Note:** May need to expose `CvUnit::GetAllReachablePlotsInRange()` or use pathfinder API directly.

---

### 4. `get_city_founding_sites`

Query valid city founding locations in a region.

**Request:**
```json
{
  "type": "get_city_founding_sites",
  "request_id": "req126",
  "settler_unit_id": 3,
  "radius": 10,
  "min_score": 50
}
```

**Parameters:**
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `settler_unit_id` | `int` | No | - | If provided, center on settler and check foundAbroad |
| `center` | `[x, y]` | No | Capital | Center point if no settler specified |
| `radius` | `int` | No | 10 | Search radius |
| `min_score` | `int` | No | 0 | Minimum founding score to include |

**Response:**
```json
{
  "type": "city_founding_sites_result",
  "request_id": "req126",
  "sites": [
    {
      "x": 20,
      "y": 15,
      "can_found": true,
      "distance_to_nearest_city": 5,
      "is_coastal": true,
      "has_fresh_water": true,
      "nearby_resources": [
        {"type": 5, "name": "Wheat", "distance": 2},
        {"type": 12, "name": "Iron", "distance": 3}
      ],
      "founding_score": 780
    },
    {
      "x": 18,
      "y": 12,
      "can_found": true,
      "distance_to_nearest_city": 4,
      "is_coastal": false,
      "has_fresh_water": false,
      "nearby_resources": [],
      "founding_score": 320
    }
  ]
}
```

**C++ Implementation Strategy:**
```cpp
else if (msgType == "get_city_founding_sites")
{
    int settlerId = msg.get("settler_unit_id").asInt(-1);
    int radius = msg.get("radius").asInt(10);
    int minScore = msg.get("min_score").asInt(0);

    CvUnit* pSettler = NULL;
    int centerX, centerY;

    if (settlerId >= 0) {
        pSettler = FindUnitById(settlerId);
        if (!pSettler) {
            SendError("UNIT_NOT_FOUND");
            return;
        }
        centerX = pSettler->getX();
        centerY = pSettler->getY();
    } else {
        // Use capital as center
        CvCity* pCapital = GET_PLAYER(getActivePlayer()).getCapitalCity();
        if (!pCapital) {
            SendError("NO_CAPITAL");
            return;
        }
        centerX = pCapital->getX();
        centerY = pCapital->getY();
    }

    std::ostringstream os;
    os << "{\"type\":\"city_founding_sites_result\"";
    os << ",\"sites\":[";

    bool first = true;
    for (int dx = -radius; dx <= radius; dx++) {
        for (int dy = -radius; dy <= radius; dy++) {
            CvPlot* pPlot = plotXYWithRangeCheck(centerX, centerY, dx, dy, radius);
            if (!pPlot) continue;

            // Check if can found
            bool canFound = (pSettler != NULL)
                ? pSettler->canFoundCity(pPlot)
                : GET_PLAYER(getActivePlayer()).canFoundCityExt(pPlot->getX(), pPlot->getY());

            if (!canFound) continue;

            // Calculate founding score (use AI's city site evaluator)
            CvCitySiteEvaluator* pEvaluator = GET_PLAYER(getActivePlayer()).GetCitySiteEvaluator();
            int score = pEvaluator ? pEvaluator->PlotFoundValue(pPlot) : 0;

            if (score < minScore) continue;

            if (!first) os << ",";
            first = false;

            // Serialize site info
            SerializeCityFoundingSite(os, pPlot, score);
        }
    }

    os << "]}";
    m_kGameStatePipe.SendLine(os.str());
}
```

**Note:** Uses `CvCitySiteEvaluator::PlotFoundValue()` - the AI's city placement scoring system.

---

### 5. `get_great_person_options`

Query where a great person can place improvements or create works.

**Request:**
```json
{
  "type": "get_great_person_options",
  "request_id": "req127",
  "unit_id": 12
}
```

**Parameters:**
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `unit_id` | `int` | Yes | - | Great person unit ID |

**Response (Great Work):**
```json
{
  "type": "great_person_options_result",
  "request_id": "req127",
  "unit_id": 12,
  "unit_type": "Great Artist",
  "great_work_type": "ART_ARTIFACT",
  "can_create_great_work": true,
  "available_slots": [
    {
      "city_name": "Washington",
      "city_id": 0,
      "building_name": "Museum",
      "distance": 3
    },
    {
      "city_name": "Boston",
      "city_id": 1,
      "building_name": "Museum",
      "distance": 8
    }
  ],
  "tile_improvements": []
}
```

**Response (Tile Improvement):**
```json
{
  "type": "great_person_options_result",
  "request_id": "req127",
  "unit_id": 15,
  "unit_type": "Great Scientist",
  "great_work_type": null,
  "can_create_great_work": false,
  "available_slots": [],
  "tile_improvements": [
    {
      "x": 10,
      "y": 12,
      "build_type": 8,
      "build_name": "Academy",
      "yields": {"food": 0, "science": 5, "production": 0}
    },
    {
      "x": 11,
      "y": 12,
      "build_type": 8,
      "build_name": "Academy",
      "yields": {"food": 0, "science": 5, "production": 0}
    }
  ]
}
```

**C++ Implementation Strategy:**
```cpp
else if (msgType == "get_great_person_options")
{
    int unitId = msg.get("unit_id").asInt();

    CvUnit* pUnit = FindUnitById(unitId);
    if (!pUnit) {
        SendError("UNIT_NOT_FOUND");
        return;
    }

    std::ostringstream os;
    os << "{\"type\":\"great_person_options_result\"";
    os << ",\"unit_id\":" << unitId;

    // Check for great work capability
    GreatWorkType eGreatWork = pUnit->GetGreatWork();
    if (eGreatWork != NO_GREAT_WORK) {
        os << ",\"can_create_great_work\":"
           << (pUnit->canCreateGreatWork() ? "true" : "false");

        if (pUnit->canCreateGreatWork()) {
            // Find available slots in empire
            os << ",\"available_slots\":[";
            SerializeGreatWorkSlots(os, GET_PLAYER(pUnit->getOwner()), eGreatWork);
            os << "]";
        }
    }

    // Check for tile improvement capability (Academy, Manufactory, etc.)
    os << ",\"tile_improvements\":[";
    bool first = true;
    for (int i = 0; i < GC.getNumBuildInfos(); i++) {
        BuildTypes eBuild = (BuildTypes)i;
        CvBuildInfo* pBuildInfo = GC.getBuildInfo(eBuild);
        if (!pBuildInfo) continue;

        // Check if this is a great person improvement
        if (pBuildInfo->IsKill()) {  // Great person improvements consume unit
            CvPlot* pPlot = pUnit->plot();
            if (pUnit->canBuild(pPlot, eBuild)) {
                if (!first) os << ",";
                first = false;
                SerializeTileImprovement(os, pPlot, eBuild);
            }
        }
    }
    os << "]";

    os << "}";
    m_kGameStatePipe.SendLine(os.str());
}
```

---

## Map Visualization Integration

These query tools complement ASCII map visualization by adding **action overlays**:

### Action Overlay Modes

Extend `get_map_view` with new modes:

```python
get_map_view(
    center="unit:5",        # Center on worker unit
    radius=10,
    mode="builder_tasks",   # Show valid improvements
    unit_id=5               # Highlight where this unit can build
)
```

**Mode: `builder_tasks`**
- Shows tiles with improvement symbols where unit can build
- Symbol legend: `F`=Farm, `M`=Mine, `P`=Plantation, `Q`=Quarry, `R`=Road
- Highlight highest-scored tasks from builder AI

**Mode: `movement_range`**
- Shows reachable tiles with movement cost overlay
- Numbers show turns to reach each tile
- Highlight attack targets with `X`

**Mode: `city_sites`**
- Shows valid city founding locations with scores
- `1`=low score, `5`=medium, `9`=high
- Highlight optimal expansion locations

**Mode: `great_person`**
- Shows where great person can place improvements
- Highlight closest great work slots

### Symbol Priority (extended)

1. Action targets (where unit can act)
2. Player units (U, S, W)
3. Enemy units (u)
4. Player cities (@, C)
5. Enemy cities (c)
6. Resources (*)
7. Improvements (+, R, =)
8. Features (n, N, #)
9. Base terrain (., :, ^, M, ~, d, t, s)
10. Fog of war (?)

---

## Performance Considerations

### Expensive Operations

| Query | Complexity | Estimated Time |
|-------|------------|----------------|
| `get_unit_build_options` | O(tiles × builds) | 5-10ms for r=5 |
| `get_builder_ai_tasks` | O(empire tiles) | 10-50ms (already cached by AI) |
| `get_reachable_tiles` | O(tiles) with pathfinding | 5-20ms |
| `get_city_founding_sites` | O(tiles × evaluation) | 20-100ms for r=10 |
| `get_great_person_options` | O(builds) or O(cities) | <5ms |

### Caching Strategies

1. **Builder options**: Cache per unit until it moves or player researches new tech
2. **Reachable tiles**: Cache per unit until it moves or combat occurs
3. **City founding sites**: Cache per player until new city founded or borders expand
4. **Great person options**: Recompute each query (fast enough, state changes frequently)

---

## Open Questions

1. **Should builder AI expose top-N tasks?** Currently returns only assigned directive. May need to extend `CvBuilderTaskingAI` API.

2. **Movement pathfinding API**: Is `GetAllReachablePlotsInRange()` public? May need to call pathfinder directly.

3. **City founding score transparency**: Should we expose individual scoring factors (yields, resources, defensive terrain) or just final score?

4. **Great person tile improvements**: Some GPs can build improvements (Academy) while others create great works. Should these be separate tools or unified?

5. **Action overlay performance**: Should map visualization pre-query action options, or request them on-demand?

---

## Implementation Roadmap

### Phase 1: Query Tools (C++ + MCP)
1. Add `get_unit_build_options` to `CvGame.cpp`
2. Add `get_reachable_tiles` to `CvGame.cpp`
3. Expose in `mcp_server.py` as MCP tools

### Phase 2: AI Integration
1. Extend `CvBuilderTaskingAI` to return top-N directives
2. Add `get_builder_ai_tasks` command
3. Add `get_city_founding_sites` using `CvCitySiteEvaluator`

### Phase 3: Map Overlays
1. Add action overlay modes to `map_renderer.py`
2. Integrate with `get_map_view` MCP tool
3. Symbol priority system for combined overlays

### Phase 4: Great Person Support
1. Add `get_great_person_options` command
2. Support both great works and tile improvements
3. Add `great_person` overlay mode

---

---

## CRITICAL: Movement Must Be Purposeful and Efficient

### The Problem: Random Movement Without Purpose

**Common LLM Behavior Issue:**
The LLM tends to move units randomly without clear objectives, resulting in:
- Units retreading already-explored ground
- Movement commands that waste turns
- No strategic positioning or tactical thinking
- Units moving "just to do something" rather than toward specific goals

**Human players move units with PURPOSE:**
- Scouts move to EXPLORE specific unexplored regions
- Warriors move to DEFEND specific cities or choke points
- Settlers move to SPECIFIC city founding locations
- Workers move to SPECIFIC tiles to improve them
- Military units move to ATTACK specific targets or form defensive lines

### The Solution: Always Specify Destination Tiles

**GOOD - Specific destination with purpose:**
```json
{
  "type": "move_unit",
  "unit_id": 5,
  "to": [23, 18],
  "reason": "Move worker to wheat tile at (23,18) to build farm"
}
```

**BAD - Vague or aimless movement:**
```json
{
  "type": "move_unit",
  "unit_id": 5,
  "to": [11, 13],
  "reason": "Move worker northeast"
}
```

### Multi-Turn Auto-Pathing (Already Supported!)

**Key Discovery:** The game's `MISSION_MOVE_TO` system **already handles multi-turn movement automatically**.

**How It Works:**

1. **Path Caching** - When you issue `move_unit` to a distant tile:
   - Game calculates full A* path to destination
   - Path is cached in `CvUnit::m_kLastPath` with turn counts
   - Unit moves as far as possible this turn

2. **Auto-Continuation** - On subsequent turns:
   - `AutoMission()` checks if unit has active `MISSION_MOVE_TO`
   - Unit automatically resumes path following
   - Continues until destination reached or path becomes invalid

3. **Path Preservation** - Between turns:
   - Cached path persists in mission queue
   - Turn counters decrement each turn
   - No need to re-issue move commands

**Example:**
```python
# Turn 5: Issue move command to distant tile (15 tiles away, 8 turns at unit's speed)
send_action("move_unit", unit_id=3, to=[40, 25])

# Turn 6-12: Unit automatically continues following path
# No additional commands needed!

# Turn 13: Unit arrives at (40, 25)
```

**This means:**
- ✅ LLM can issue long-distance move commands
- ✅ Game handles pathfinding efficiently (A* algorithm)
- ✅ Unit auto-continues across multiple turns
- ✅ LLM doesn't need to micro-manage each tile

### Best Practices for LLM Movement Decisions

#### 1. Use Spatial Queries to Choose Destinations

**Don't:** Move units randomly hoping to find something useful
**Do:** Query map state first, then move toward specific objectives

```python
# GOOD: Query unexplored areas, then move scout there
map_view = get_map_view(center="unit:5", radius=15)
# Identify unexplored region at (30, 20)
send_action("move_unit", unit_id=5, to=[30, 20])

# BAD: Move scout randomly
send_action("move_unit", unit_id=5, to=[12, 15])  # Why? No reason!
```

#### 2. Combine with Action Queries

**Don't:** Move worker to random tile and hope to find something to improve
**Do:** Query build options first, move to highest-value tile

```python
# GOOD: Query best tasks, move to top priority
tasks = get_builder_ai_tasks(unit_id=3, max_tasks=5)
best_task = tasks[0]
send_action("move_unit", unit_id=3, to=[best_task["x"], best_task["y"]])

# BAD: Move worker in random direction
send_action("move_unit", unit_id=3, to=[10, 11])  # Why? What's there?
```

#### 3. Define Clear Objectives per Unit Type

| Unit Type | Primary Objective | Movement Strategy |
|-----------|-------------------|-------------------|
| Scout | Explore unexplored tiles | Move to fog-of-war boundaries |
| Warrior (early) | City defense | Position at choke points near cities |
| Settler | Found new city | Move to high-value founding site from `get_city_founding_sites` |
| Worker | Improve tiles | Move to tile from `get_builder_ai_tasks` or `get_unit_build_options` |
| Archer/Ranged | Support & defense | Position 2-3 tiles from frontline units |
| Cavalry | Flanking & pursuit | Move to attack vulnerable enemy units |

#### 4. Use Movement Ranges to Plan Realistically

```python
# Query where unit can actually reach this turn
reachable = get_reachable_tiles(unit_id=8)

# Choose destination within reach if urgent
# OR choose distant destination if strategic movement can span multiple turns
if threat_imminent:
    # Move to reachable defensive position THIS TURN
    send_action("move_unit", unit_id=8, to=closest_defense_tile)
else:
    # Issue long-distance move to strategic objective (auto-continues)
    send_action("move_unit", unit_id=8, to=distant_objective)
```

#### 5. Don't Re-Issue Commands for Units in Transit

**Don't:** Re-command unit every turn if it's already on a multi-turn path
**Do:** Track which units have active missions, let them complete

```python
# Turn 5: Issue command
send_action("move_unit", unit_id=5, to=[40, 25])

# Turn 6-12: DON'T issue new move commands!
# The unit is already following its path

# Turn 13: Unit arrives, NOW issue new command
send_action("move_unit", unit_id=5, to=[45, 30])  # Next objective
```

**Check unit status:**
- Units with `activity == "MISSION"` are executing missions
- Don't interrupt unless circumstances change (enemy spotted, new priority)

---

## Movement Command Enhancements (Future)

The current `move_unit` implementation could be enhanced:

### 1. Movement Flags

Expose movement flags for advanced control:
```json
{
  "type": "move_unit",
  "unit_id": 5,
  "to": [23, 18],
  "flags": {
    "approximate_target": true,      // MOVEFLAG_APPROX_TARGET_RING1 - get close, not exact
    "ignore_danger": false,           // Avoid dangerous tiles if possible
    "ignore_fog": false               // Stop at fog-of-war boundary
  }
}
```

### 2. Mission AI Types

Tag moves with strategic purpose for better AI decision-making:
```json
{
  "type": "move_unit",
  "unit_id": 5,
  "to": [23, 18],
  "mission_ai": "EXPLORE"  // MISSIONAI_EXPLORE, MISSIONAI_BUILD, MISSIONAI_TACTMOVE
}
```

This helps the game's AI systems understand the LLM's intent.

### 3. ETA in Response

Return estimated turn count to destination:
```json
{
  "type": "move_unit_result",
  "success": true,
  "unit_id": 5,
  "destination": {"x": 23, "y": 18},
  "eta_turns": 3,               // How many turns until arrival
  "path_length": 8,             // Number of tiles in path
  "current_position": {"x": 20, "y": 15}
}
```

### 4. Waypoint Chaining

Queue multiple destinations with `append=true`:
```json
{
  "type": "move_unit",
  "unit_id": 5,
  "waypoints": [
    {"x": 20, "y": 15},  // First stop
    {"x": 25, "y": 18},  // Second stop
    {"x": 30, "y": 20}   // Final destination
  ]
}
```

This would use `PushMission(bAppend=true)` to queue multiple moves.

---

## Summary

These five new MCP tools expose the same information human players use to make unit action decisions:

1. **get_unit_build_options** - What can I build here? (worker lens)
2. **get_builder_ai_tasks** - What should I build? (AI recommendations)
3. **get_reachable_tiles** - Where can I move? (movement range)
4. **get_city_founding_sites** - Where should I settle? (city sites)
5. **get_great_person_options** - Where can I place this? (GP placement)

Combined with ASCII map visualization, the LLM gains spatial awareness AND action awareness - the two key inputs for strategic decision-making.

**Critical for LLM success:**
- Always move units to SPECIFIC destinations with CLEAR purpose
- Use spatial/action queries to identify objectives BEFORE moving
- Trust multi-turn auto-pathing - don't micro-manage
- Different unit types need different movement strategies
