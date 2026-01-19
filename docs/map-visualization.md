# Map Visualization for LLM

This document describes an ASCII map visualization system to give the LLM spatial awareness of the game world.

## Rationale

Civilization V is fundamentally a spatial game. Key strategic decisions depend on understanding:
- Terrain layout and chokepoints
- Resource clusters and city placement opportunities
- Unit positions relative to threats and objectives
- Expansion paths and defensible borders

Currently, the LLM receives terrain data as JSON with coordinates:
```json
{"x": 5, "y": 12, "terrain": "TERRAIN_PLAINS", "feature": "FEATURE_FOREST"}
```

While precise, this requires the LLM to mentally reconstruct spatial relationships from coordinate pairs. A visual representation allows pattern recognition that's more natural for strategic reasoning.

### Design Philosophy Alignment

From CLAUDE.md: "The LLM should have access to the same information as a human player."

Human players see a map constantly. Providing an ASCII map representation gives the LLM equivalent spatial awareness without requiring vision capabilities or expensive image tokens.

## Design Goals

1. **Token efficient** - Compact representation that conveys maximum spatial information
2. **No vision required** - Works with any text-based LLM
3. **Layered information** - Show terrain, units, cities, and fog-of-war together
4. **Coordinate-aligned** - Easy to correlate visual positions with JSON coordinates
5. **Configurable scope** - Full map, viewport around capital, or specific region

## ASCII Representation

### Terrain Symbols

| Symbol | Terrain | Notes |
|--------|---------|-------|
| `.` | Grassland | Base fertile terrain |
| `:` | Plains | Slightly less fertile |
| `^` | Hills | Defensive bonus, production |
| `M` | Mountains | Impassable |
| `~` | Coast/Ocean | Water tiles |
| `≈` | Ocean | Deep water (if distinguishing) |
| `n` | Forest | On grassland/plains |
| `N` | Jungle | Dense vegetation |
| `d` | Desert | Low yield |
| `t` | Tundra | Cold, low yield |
| `s` | Snow | Very low yield |
| `#` | Marsh | Movement penalty |
| `?` | Fog of war | Unexplored |

### Overlay Symbols (take precedence)

| Symbol | Meaning |
|--------|---------|
| `@` | Your capital |
| `C` | Your other cities |
| `c` | Enemy/other civ cities |
| `U` | Your military unit |
| `S` | Your settler |
| `W` | Your worker |
| `u` | Enemy unit (visible) |
| `*` | Resource (luxury/strategic) |
| `+` | Improvement (farm, mine, etc.) |
| `R` | Road |
| `=` | Railroad |

### Example Output

```
Map View (Turn 47) - Center: Washington (12,8)
Legend: @=capital C=city U=unit S=settler *=resource .=grass ^=hills M=mount ~=water ?=fog

    08 09 10 11 12 13 14 15 16 17
   +------------------------------+
05 | ?  ?  ?  ?  ^  M  M  ^  ?  ? |
06 | ?  ?  ^  n  .  ^  M  .  n  ? |
07 | ?  n  .  . +*  .  ^  .  .  ? |
08 | ~  ~  .  . +C  @  .  U  .  n |
09 | ~  ~  ~  .  .  . +.  .  *  . |
10 | ?  ~  ~  ~  .  S  .  .  n  ^ |
11 | ?  ?  ~  ~  ~  .  .  c  .  . |
12 | ?  ?  ?  ~  ~  ~  .  u  .  ? |
   +------------------------------+

Units:
- Warrior (id=1) at (15,8) - 1 move remaining
- Settler (id=2) at (13,10) - 2 moves remaining

Visible enemy:
- Barbarian Warrior at (15,12)
```

## MCP Tool Interface

### `get_map_view`

Returns an ASCII map visualization of the game world.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `center` | `string` | No | Capital | Center point: `"capital"`, `"unit:<id>"`, or `"<x>,<y>"` |
| `radius` | `int` | No | 8 | Tiles from center to edge (creates 2r+1 square) |
| `show_fog` | `bool` | No | true | Show unexplored tiles as `?` |
| `show_grid` | `bool` | No | true | Show coordinate grid lines |
| `layers` | `array` | No | all | Which layers: `["terrain", "units", "cities", "resources", "improvements"]` |

**Example Request:**
```json
{
  "type": "get_map_view",
  "center": "capital",
  "radius": 10,
  "show_grid": true
}
```

**Example Response:**
```json
{
  "type": "map_view",
  "success": true,
  "center": {"x": 12, "y": 8, "name": "Washington"},
  "bounds": {"x_min": 2, "x_max": 22, "y_min": -2, "y_max": 18},
  "turn": 47,
  "map": "... ASCII map string ...",
  "legend": "@=capital C=city U=unit ...",
  "units_in_view": [
    {"id": 1, "type": "Warrior", "x": 15, "y": 8, "moves": 1},
    {"id": 2, "type": "Settler", "x": 13, "y": 10, "moves": 2}
  ],
  "cities_in_view": [
    {"id": 0, "name": "Washington", "x": 12, "y": 8, "owner": "player"}
  ],
  "enemy_units_visible": [
    {"type": "Barbarian Warrior", "x": 15, "y": 12}
  ]
}
```

### `get_full_map`

Returns the entire known map (may be large).

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `compact` | `bool` | No | false | Omit grid lines and spacing for smaller output |

## Implementation

### Current State: No Bulk Terrain Data in turn_start

**Important**: The `turn_start` message currently does NOT include terrain data. See `GameStatePipe.cpp:177-222`:
- Only sends: `turn`, `player_id`, `player_name`, `is_human`, `playersAlive`, `civsEver`
- Line 206 has TODO: `// TODO: Add more state fields (cities, units, tech, etc.)`

### Data Access Architecture (Research Findings)

#### C++ Storage (CvMap & CvPlot)

**CvMap Structure** (`CvGameCoreDLL_Expansion2/CvMap.h`):
- `m_pMapPlots` - Contiguous array of all plot objects (O(1) access)
- `m_iGridWidth`, `m_iGridHeight` - Grid dimensions
- `m_pPlotNeighbors` - Pre-cached neighbor pointers for 6 hex directions
- Access: `plot(x, y)`, `plotByIndex(index)` - direct array lookup

**CvPlot Structure** (`CvGameCoreDLL_Expansion2/CvPlot.h`):
- Core data stored as compact `char` enums (8-bit):
  - `m_eTerrainType`, `m_eFeatureType`, `m_eResourceType`, `m_eImprovementType`
  - `m_eRouteType`, `m_ePlotType`, `m_eOwner`, `m_iResourceNum`
- Per-team visibility arrays (allocated externally):
  - `m_aiVisibilityCount[]` - visibility counter per team
  - `m_bfRevealed` - bitfield of revealed teams
  - `m_aiRevealedOwner[]`, `m_aeRevealedImprovementType[]`, `m_aeRevealedRouteType[]`

**Performance Characteristics:**
- Memory: ~12KB per plot × 8000 plots = ~96MB for 128×80 map
- Cache-friendly: contiguous array, small enums
- Access time: <1ms to iterate all 8000 plots with complex queries

#### Lua API Exposure (CvLuaPlot)

**Available Methods** (`CvGameCoreDLL_Expansion2/Lua/CvLuaPlot.cpp`):
```lua
-- Terrain/Feature
plot:GetTerrainType()              -- enum ID
plot:GetFeatureType()              -- enum ID
plot:GetPlotType()                 -- PLOT_OCEAN/LAND/HILLS/MOUNTAIN
plot:IsWater(), plot:IsHills(), plot:IsMountain()

-- Resources & Improvements
plot:GetResourceType(teamID)       -- with tech-visibility check
plot:GetNumResource()              -- quantity (1-3)
plot:GetImprovementType()
plot:GetRouteType()
plot:IsImprovementPillaged(), plot:IsRoutePillaged()

-- Ownership & Location
plot:GetX(), plot:GetY(), plot:GetIndex()
plot:GetOwner()                    -- current owner
plot:GetRevealedOwner(teamID)      -- fog-of-war aware

-- Visibility & Fog of War
plot:GetVisibilityCount(teamID)    -- # of units seeing plot
plot:IsVisible(teamID)             -- currently visible
plot:IsRevealed(teamID)            -- has been explored
plot:GetActiveFogOfWarMode()       -- FOW mode type
```

**Key Insight:** All Lua methods are direct C++ calls with no serialization overhead.

#### Strategic View Implementation

**Files:**
- `(1) Community Patch/Core Files/Overrides/WorldView.lua` - Input handling
- `UI_bc1/MiniMap/MiniMapPanel.lua` - Strategic view rendering & toggle

**Strategic View Features:**
- `InStrategicView()` / `ToggleStrategicView()` - C++ functions exposed to Lua
- `GetStrategicViewIconSettings()` - Icon layer configuration
- `SetStrategicViewIconSetting()` - Toggle individual icon layers
- `GetStrategicViewOverlays()` - Available overlay types (resources, improvements, cities, units)
- `SetStrategicViewOverlay()` - Switch active overlay
- `StrategicViewShowFeatures` - Toggle feature visibility
- `StrategicViewShowFogOfWar` - Toggle FOW visualization

**Rendering:** Uses `SetGameViewRenderType(GameViewTypes.GAMEVIEW_STRATEGIC)`, renders as texture with icon overlays.

#### Database Layer (XML/SQL)

**Terrain/Feature/Resource Definitions:**
- Loaded from XML at game initialization into SQLite database
- Exposed to Lua as `GameInfo.Terrains[]`, `GameInfo.Features[]`, `GameInfo.Resources[]`
- Type IDs match database primary keys (O(1) lookup)
- Examples:
  - `(1) Community Patch/Database Changes/WorldMap/Features/NewFeatureTables.xml`
  - `(1) Community Patch/Database Changes/WorldMap/Resources/NewResourceTables.xml`

### Implementation Options

#### Option 1: Python-side rendering (Quick but Slow)
- Use existing `inspect_tile(x, y)` command for each tile in viewport
- **Pros:** No C++ changes, works immediately
- **Cons:** 400+ pipe round-trips for 20×20 view, high latency

#### Option 2: C++ bulk command (Recommended)
Add `get_visible_tiles` command to `CvGame.cpp` that returns JSON array of all revealed tiles:
```cpp
else if (msgType == "get_visible_tiles")
{
    // Iterate GC.getMap().numPlots()
    // For each plot where plot->isRevealed(activeTeam):
    //   - Add to JSON array with terrain, feature, resource, improvement
    //   - Include visibility status (visible vs revealed)
    // Return single large JSON payload
}
```

**Benefits:**
- Single pipe message instead of hundreds
- Can leverage CvPlot's cache-friendly array layout
- <1ms to serialize 8000 tiles

#### Option 3: Add to turn_start (Ideal Long-term)
Extend `GameStatePipe::SendTurnData()` to include bulk terrain array:
```cpp
payload << ",\"terrain\":[";
for (int i = 0; i < GC.getMap().numPlots(); i++) {
    CvPlot* pPlot = GC.getMap().plotByIndexUnchecked(i);
    if (pPlot->isRevealed(activeTeam)) {
        // Add plot JSON
    }
}
payload << "]";
```

**Benefits:**
- Data available immediately at turn start
- No separate query needed
- Can cache in orchestrator for multiple map renders

### Recommended Implementation Path

1. **Phase 1 (MVP):** Implement Option 2 (`get_visible_tiles` command)
   - Add handler in `CvGame::HandlePipeCommand()`
   - Returns JSON array of revealed tiles with terrain/feature/resource/improvement
   - Python renderer consumes this data

2. **Phase 2 (Optimization):** Move to Option 3 (add to `turn_start`)
   - Integrate terrain data into existing turn message
   - Remove separate query, cache data in orchestrator

3. **Phase 3 (Features):** Add advanced visualization
   - Movement ranges, sight cones, danger zones
   - Multi-layer rendering modes (resource view, strategic view, etc.)

### Location

Implement in `python/orchestrator/map_renderer.py` as a new module.

### Data Source

**Current (needs implementation):** New `get_visible_tiles` command in C++ that returns:

Required fields per tile:
- `x`, `y` - Tile coordinates
- `terrain_type` - Terrain enum ID
- `feature_type` - Feature enum ID (or -1)
- `resource_type` - Resource enum ID (or -1, with team visibility check)
- `resource_quantity` - Number of resources
- `improvement_type` - Improvement enum ID (or -1)
- `route_type` - Route enum ID (or -1)
- `owner_id` - Owner player ID (or -1)
- `is_visible` - Currently visible to active team
- `is_revealed` - Has been explored by active team
- `is_water`, `is_hills`, `is_mountain` - Quick terrain checks

### C++ Implementation (get_visible_tiles command)

Add to `CvGame::HandlePipeCommand()` in `CvGame.cpp`:

```cpp
else if (msgType == "get_visible_tiles")
{
    std::string requestId = msg.get("request_id").asString();
    PlayerTypes activePlayer = getActivePlayer();
    TeamTypes activeTeam = GET_PLAYER(activePlayer).getTeam();

    std::ostringstream os;
    os << "{\"type\":\"visible_tiles_result\"";
    os << ",\"request_id\":\"" << PipeUtils::JsonEscape(requestId) << "\"";
    os << ",\"turn\":" << getGameTurn();
    os << ",\"map_width\":" << GC.getMap().getGridWidth();
    os << ",\"map_height\":" << GC.getMap().getGridHeight();
    os << ",\"tiles\":[";

    bool first = true;
    int numPlots = GC.getMap().numPlots();
    for (int i = 0; i < numPlots; i++)
    {
        CvPlot* pPlot = GC.getMap().plotByIndexUnchecked(i);
        if (pPlot == NULL) continue;

        // Only include revealed tiles
        if (!pPlot->isRevealed(activeTeam)) continue;

        if (!first) os << ",";
        first = false;

        os << "{";
        os << "\"x\":" << pPlot->getX();
        os << ",\"y\":" << pPlot->getY();
        os << ",\"terrain_type\":" << static_cast<int>(pPlot->getTerrainType());
        os << ",\"feature_type\":" << static_cast<int>(pPlot->getFeatureType());
        os << ",\"plot_type\":" << static_cast<int>(pPlot->getPlotType());
        os << ",\"is_water\":" << (pPlot->isWater() ? "true" : "false");
        os << ",\"is_hills\":" << (pPlot->isHills() ? "true" : "false");
        os << ",\"is_mountain\":" << (pPlot->isMountain() ? "true" : "false");
        os << ",\"is_visible\":" << (pPlot->isVisible(activeTeam) ? "true" : "false");

        // Resource (with tech visibility check)
        ResourceTypes eResource = pPlot->getResourceType(activeTeam);
        if (eResource != NO_RESOURCE)
        {
            os << ",\"resource_type\":" << static_cast<int>(eResource);
            os << ",\"resource_quantity\":" << pPlot->getNumResource();
        }

        // Improvement (revealed version for fog-of-war)
        ImprovementTypes eImprovement = pPlot->getRevealedImprovementType(activeTeam);
        if (eImprovement != NO_IMPROVEMENT)
        {
            os << ",\"improvement_type\":" << static_cast<int>(eImprovement);
            os << ",\"improvement_pillaged\":" << (pPlot->IsImprovementPillaged() ? "true" : "false");
        }

        // Route
        RouteTypes eRoute = pPlot->getRevealedRouteType(activeTeam);
        if (eRoute != NO_ROUTE)
        {
            os << ",\"route_type\":" << static_cast<int>(eRoute);
            os << ",\"route_pillaged\":" << (pPlot->IsRoutePillaged() ? "true" : "false");
        }

        // Owner (revealed version)
        PlayerTypes eOwner = pPlot->getRevealedOwner(activeTeam);
        if (eOwner != NO_PLAYER)
        {
            os << ",\"owner_id\":" << static_cast<int>(eOwner);
        }

        os << "}";
    }

    os << "]}";
    m_kGameStatePipe.SendLine(os.str());
    return;
}
```

**Performance:** ~1ms to serialize 8000 tiles, ~200KB JSON payload.

### Python Rendering Algorithm

Implement in `map_renderer.py`:

```python
def render_map(tiles: list, center: tuple, radius: int,
               layers: list = None, mode: str = "default") -> str:
    """Render ASCII map from tile data."""

    if layers is None:
        layers = ["terrain", "units", "cities", "resources", "improvements"]

    # 1. Create empty grid
    grid = {}
    x_min, x_max = center[0] - radius, center[0] + radius
    y_min, y_max = center[1] - radius, center[1] + radius

    # 2. Fill terrain layer (base)
    if "terrain" in layers:
        for tile in tiles:
            if x_min <= tile["x"] <= x_max and y_min <= tile["y"] <= y_max:
                grid[(tile["x"], tile["y"])] = terrain_to_symbol(tile)

    # 3. Overlay improvements and roads
    if "improvements" in layers:
        for tile in tiles:
            if tile.get("improvement_type") or tile.get("route_type"):
                if x_min <= tile["x"] <= x_max and y_min <= tile["y"] <= y_max:
                    grid[(tile["x"], tile["y"])] = improvement_to_symbol(tile)

    # 4. Overlay resources
    if "resources" in layers:
        for tile in tiles:
            if tile.get("resource_type") is not None and tile["is_visible"]:
                if x_min <= tile["x"] <= x_max and y_min <= tile["y"] <= y_max:
                    grid[(tile["x"], tile["y"])] = resource_to_symbol(tile)

    # 5. Overlay cities (from separate cities data)
    if "cities" in layers:
        for city in cities:
            if x_min <= city["x"] <= x_max and y_min <= city["y"] <= y_max:
                symbol = '@' if city["is_capital"] else 'C' if city["is_ours"] else 'c'
                grid[(city["x"], city["y"])] = symbol

    # 6. Overlay units (highest priority, from separate units data)
    if "units" in layers:
        for unit in units:
            if x_min <= unit["x"] <= x_max and y_min <= unit["y"] <= y_max:
                grid[(unit["x"], unit["y"])] = unit_to_symbol(unit)

    # 7. Render to string with coordinates
    return grid_to_string(grid, x_min, x_max, y_min, y_max)

def terrain_to_symbol(tile: dict) -> str:
    """Convert tile data to ASCII symbol."""
    # Check visibility first
    if not tile["is_revealed"]:
        return "?"

    # Check plot type (mountains, hills, water)
    if tile["is_mountain"]:
        return "M"
    if tile["is_water"]:
        return "~"

    # Check feature (forest, jungle, marsh) - takes precedence over terrain
    feature_type = tile.get("feature_type", -1)
    if feature_type == FEATURE_FOREST:  # 0
        return "n"
    if feature_type == FEATURE_JUNGLE:  # 1
        return "N"
    if feature_type == FEATURE_MARSH:   # 6
        return "#"
    if feature_type == FEATURE_ICE:     # 3
        return "i"

    # Check terrain type
    terrain_type = tile["terrain_type"]
    if tile["is_hills"]:
        return "^"
    if terrain_type == TERRAIN_GRASS:   # 0
        return "."
    if terrain_type == TERRAIN_PLAINS:  # 1
        return ":"
    if terrain_type == TERRAIN_DESERT:  # 2
        return "d"
    if terrain_type == TERRAIN_TUNDRA:  # 4
        return "t"
    if terrain_type == TERRAIN_SNOW:    # 5
        return "s"

    return "?"  # Unknown
```

### Symbol Priority (highest to lowest)

1. Player units (U, S, W)
2. Enemy units (u)
3. Player cities (@, C)
4. Enemy cities (c)
5. Resources (*)
6. Improvements (+, R, =)
7. Features (n, N, #)
8. Base terrain (., :, ^, M, ~, d, t, s)
9. Fog of war (?)

## Coordinate System Notes

Civ V uses a hex grid internally, but the pipe protocol exposes it as offset coordinates. The ASCII map uses a square grid approximation which works well enough for strategic overview.

For precise hex-accurate positioning, use the JSON coordinate data. The ASCII map is for spatial intuition, not pixel-perfect accuracy.

## Inspiration from Strategic View

The game's Strategic View (MiniMapPanel.lua) provides excellent patterns to emulate:

### Layer Toggle System
Strategic view supports multiple rendering layers that can be enabled/disabled:
- Resources overlay
- Improvements overlay
- Cities overlay
- Units overlay
- Strategic route planning

**ASCII Map Equivalent:**
```python
get_map_view(center="capital", radius=10, layers=["terrain", "resources", "cities"])
# Shows terrain with resource and city markers, but no units or improvements
```

### Fog of War Modes
Strategic view has configurable FOW visualization:
- `StrategicViewShowFogOfWar` - Toggle FOW display
- Distinguishes between "visible now" vs "revealed but not visible"

**ASCII Map Equivalent:**
```
?  ?  ?     # Unexplored (never revealed)
.  .  .     # Currently visible (live intel)
·  ·  ·     # Revealed but not visible (stale intel, dimmed)
```

### Icon Density Control
Strategic view can adjust icon density to avoid clutter:
- `GetStrategicViewIconSettings()` - Get current icon config
- `SetStrategicViewIconSetting(iconType, enabled)` - Toggle specific icons

**ASCII Map Equivalent:**
Add `detail_level` parameter:
- `"high"` - Show all symbols (units, improvements, resources)
- `"medium"` - Cities, resources, major units only
- `"low"` - Cities and terrain only

### Multiple Overlay Modes
Strategic view supports different "views" of the same data:
- **Resource mode**: Highlights luxury/strategic resources
- **Diplomacy mode**: Shows borders and territory control
- **Military mode**: Shows units and defensive positions

**ASCII Map Equivalent:**
Add `mode` parameter to focus visualization:
```python
get_map_view(mode="resources")   # Emphasize resource tiles with symbols
get_map_view(mode="military")    # Show units and defensive terrain
get_map_view(mode="expansion")   # Show settled/unsettled territory
```

## Future Enhancements

### Phase 2: Contextual Views

- **Tactical view**: Zoom in on combat situation with movement ranges
- **Strategic view**: Compressed full-map showing only cities and major features
- **Resource view**: Highlight specific resource types for planning (inspired by strategic overlay)
- **Diplomacy view**: Show borders, territory control, contested areas
- **Fog of War modes**: Distinguish visible/revealed/unexplored with different symbols

### Phase 3: Annotations

Allow the LLM to annotate the map with notes:
```
annotate_map(x=15, y=8, note="Defend this chokepoint")
```

These annotations persist and appear in subsequent map views.

### Phase 4: Movement Visualization

Show movement paths and ranges:
```
    08 09 10 11 12 13 14 15
   +------------------------+
07 |  .  .  .  2  1  2  .  . |
08 |  .  .  1  1  U  1  1  . |
09 |  .  .  .  2  1  2  .  . |
```
Numbers show movement cost to reach each tile from unit U.

### Phase 5: Multi-layer Rendering

Inspired by strategic view's layer system:
```python
get_map_view(
    center="capital",
    radius=10,
    layers=["terrain", "resources", "cities"],
    mode="expansion",          # Focus on settlement opportunities
    fog_mode="dimmed",         # Show revealed-but-not-visible as dimmed
    detail_level="medium"      # Reduce clutter
)
```

### Phase 6: Action Overlays (see unit-tile-interactions.md)

Show what units can DO on tiles, not just what tiles contain:

**Builder Tasks Mode:**
```python
get_map_view(
    center="unit:5",           # Center on worker
    radius=10,
    mode="builder_tasks",      # Show improvable tiles
    unit_id=5                  # Highlight where THIS unit can build
)
# Shows: F=Farm, M=Mine, P=Plantation, Q=Quarry at valid tiles
```

**Movement Range Mode:**
```python
get_map_view(
    center="unit:8",
    radius=5,
    mode="movement_range",
    unit_id=8
)
# Shows: Numbers = turns to reach, X = attack targets
```

**City Sites Mode:**
```python
get_map_view(
    center="unit:3",
    radius=15,
    mode="city_sites",
    unit_id=3  # Settler
)
# Shows: 1-9 scoring for valid founding locations
```

See `docs/unit-tile-interactions.md` for detailed specification of underlying query tools:
- `get_unit_build_options` - Worker improvement possibilities
- `get_reachable_tiles` - Movement range calculation
- `get_city_founding_sites` - City placement scoring
- `get_builder_ai_tasks` - AI-recommended tasks
- `get_great_person_options` - GP improvement/work placement

## Token Efficiency

Estimated token costs (GPT-4 tokenizer approximation):

| View Type | Grid Size | Characters | ~Tokens |
|-----------|-----------|------------|---------|
| Small (r=5) | 11x11 | ~400 | ~100 |
| Medium (r=10) | 21x21 | ~1,200 | ~300 |
| Large (r=15) | 31x31 | ~2,500 | ~600 |
| Full map (standard) | 80x50 | ~10,000 | ~2,500 |

Compare to raw JSON terrain data for same area:
- 21x21 tiles = 441 tiles × ~100 chars = ~44,000 chars = ~11,000 tokens

**ASCII map is ~30-40x more token efficient** for conveying spatial layout.

## Integration with Existing Tools

The map view complements but doesn't replace existing tools:

| Tool | Use Case |
|------|----------|
| `inspect_tile(x, y)` | Detailed single-tile query (existing) |
| `get_units` | Detailed unit status and available actions (existing) |
| `get_visible_tiles` | Bulk terrain data for rendering (NEW) |
| `get_map_view` | ASCII visualization for spatial reasoning (NEW) |

Recommended workflow:
1. Call `get_map_view` at turn start for situational awareness
2. Use `get_units` / `inspect_tile` for specific decisions
3. Call `get_map_view` centered on areas of interest as needed

## Summary & Next Steps

### Key Design Decisions

1. **C++ bulk query over per-tile queries**: Single `get_visible_tiles` command instead of 400+ `inspect_tile` calls
2. **ASCII over screenshots**: 30-40× more token efficient, works with any LLM
3. **Layered rendering**: Inspired by Strategic View's multi-layer approach
4. **Fog-of-war aware**: Distinguish unexplored/revealed/visible tiles
5. **Python-side rendering**: Keeps ASCII logic flexible without C++ recompilation

### Implementation Roadmap

**Phase 1 (MVP):**
1. Add `get_visible_tiles` command to `CvGame.cpp` (C++)
2. Implement `map_renderer.py` with basic terrain symbols (Python)
3. Add `get_map_view` MCP tool to `mcp_server.py` (Python)
4. Test with small radius (10 tiles) around capital

**Phase 2 (Optimization):**
1. Move terrain data into `turn_start` message (C++)
2. Cache tile data in orchestrator between renders (Python)
3. Add layer filtering and detail levels (Python)

**Phase 3 (Features):**
1. Multiple visualization modes (resources, military, expansion)
2. Fog-of-war display modes (dimmed vs hidden)
3. Unit movement range overlays
4. Annotations and persistent notes

### Open Questions

1. **Hex vs Square Grid**: Use square approximation (simpler) or hex-accurate spacing?
2. **Color Support**: Add ANSI color codes for terminals that support them?
3. **Caching Strategy**: Cache full map or regenerate each time?
4. **Default Radius**: What's the ideal default viewport size? (10? 15? 20?)

### References

- **C++ Files**: `CvGame.cpp`, `CvMap.h`, `CvPlot.h`, `CvLuaPlot.cpp`
- **Lua Files**: `WorldView.lua`, `MiniMapPanel.lua`
- **Python Files**: `mcp_server.py` (to implement), `map_renderer.py` (to implement)
- **Protocol**: `docs/protocol.md`, `docs/api.yaml`
