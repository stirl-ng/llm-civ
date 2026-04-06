"""Triple-char hex offset ASCII map renderer for LLM spatial awareness.

Converts tile/unit/city data into an ASCII map using 3-char cells with hex-correct
row offset, giving the LLM accurate spatial relationships for Civ V's hex grid.

Format example (triple-char offset, format G):
    GRS  ~~~  PLN  ^^^  DST
      ~~~  nGR  [C]  PLN  ~~~
    GRS  ~~~  PLN  IRO  /M\\
      ~~~  GRS  PLN  [W]  MNT

Coordinate system: Civ V uses odd-r offset coords.
    xToHexspaceX(x, y) = x - (y >> 1)
Odd y-rows are visually offset right by 0.5 cells → 2-space indent in ASCII.
"""

from typing import Dict, List, Optional, Tuple

from .map_legend import (
    CITY_SYMBOL_NAMES,
    CITY_SYMBOLS,
    FEATURE_PREFIX,
    FEATURE_PREFIX_NAMES,
    FEATURE_SOLO,
    FOG,
    PLOT_ABBREVS,
    TERRAIN_ABBREVS,
    UNIT_SYMBOL_NAMES,
    UNIT_SYMBOLS,
    generate_legend_text,
    name_to_abbrev,
)


def _to_display_x(x: int, y: int) -> int:
    """Convert Civ V storage x to hex-space display column.

    Implements xToHexspaceX from CvGameCoreUtils.h:
        display_x = x - (y >> 1)
    """
    return x - (y >> 1)


def _tile_cell(tile: Dict, abbrev_registry: dict, seen: dict) -> str:
    """Derive the 3-char cell string for a single tile.

    Priority (highest first):
      1. Unrevealed fog
      2. Mountain
      3. Ocean/water
      4. Ice feature (standalone)
      5. Hills
      6. Resource (if visible)
      7. Improvement
      8. Feature+terrain (forest/jungle/marsh prefix)
      9. Base terrain
    """
    if not tile.get("is_revealed", True):
        seen.setdefault(FOG, "Unexplored")
        return FOG

    plot_type = tile.get("plot_type", 1)
    is_water = tile.get("is_water", False)
    is_mountain = tile.get("is_mountain", False)
    is_hills = tile.get("is_hills", False)
    feature_type = tile.get("feature_type", -1)
    terrain_type = tile.get("terrain_type", 0)
    is_visible = tile.get("is_visible", True)

    # Mountain
    if is_mountain or plot_type == 3:
        sym, desc = PLOT_ABBREVS[3]
        seen.setdefault(sym, desc)
        return sym

    # Ocean / coastal water
    if is_water or plot_type == 0:
        sym, desc = PLOT_ABBREVS[0]
        seen.setdefault(sym, desc)
        return sym

    # Ice (standalone feature — no terrain prefix makes sense)
    if feature_type in FEATURE_SOLO:
        sym, desc = FEATURE_SOLO[feature_type]
        seen.setdefault(sym, desc)
        return sym

    # Hills (plot type 2)
    if is_hills or plot_type == 2:
        sym, desc = PLOT_ABBREVS[2]
        seen.setdefault(sym, desc)
        return sym

    # Resource (only when visible — not just revealed)
    if is_visible and tile.get("resource_type") is not None:
        rname = tile.get("resource_name") or f"Resource{tile['resource_type']}"
        sym = name_to_abbrev(rname, abbrev_registry)
        seen.setdefault(sym, rname)
        return sym

    # Improvement
    if tile.get("improvement_type") is not None and tile.get("improvement_type") != -1:
        iname = tile.get("improvement_name") or f"Imp{tile['improvement_type']}"
        sym = name_to_abbrev(iname, abbrev_registry)
        seen.setdefault(sym, iname)
        return sym

    # Feature + terrain prefix (forest/jungle/marsh)
    if feature_type in FEATURE_PREFIX:
        prefix = FEATURE_PREFIX[feature_type]
        fname = FEATURE_PREFIX_NAMES[feature_type]
        terrain_abbrev, terrain_name = TERRAIN_ABBREVS.get(terrain_type, ("GRS", "Grassland"))
        sym = prefix + terrain_abbrev[:2]
        seen.setdefault(sym, f"{fname} {terrain_name}")
        return sym

    # Base terrain
    if terrain_type in TERRAIN_ABBREVS:
        sym, desc = TERRAIN_ABBREVS[terrain_type]
        seen.setdefault(sym, desc)
        return sym

    return "   "


def render_map(
    tiles: List[Dict],
    units: List[Dict] = None,
    cities: List[Dict] = None,
    center: Tuple[int, int] = None,
    radius: int = 10,
    layers: List[str] = None,
) -> Tuple[str, Dict[str, str]]:
    """Render triple-char hex offset ASCII map.

    Args:
        tiles: Tile dicts from get_visible_tiles
        units: Unit dicts (optional)
        cities: City dicts (optional)
        center: (x, y) storage coordinates for viewport center
        radius: Tiles from center to edge
        layers: Which layers to render (default: all)

    Returns:
        (grid_str, seen) — grid string and symbol→description dict for legend
    """
    if layers is None:
        layers = ["terrain", "resources", "improvements", "units", "cities"]
    if units is None:
        units = []
    if cities is None:
        cities = []

    # Build display grid indexed by (display_x, y)
    display_grid: dict[tuple[int, int], str] = {}
    abbrev_registry: dict[str, str] = {}  # abbrev → name, for collision resolution
    seen: dict[str, str] = {}             # symbol → description, for legend

    # Determine viewport bounds in storage coords
    if center is None:
        xs = [t["x"] for t in tiles]
        ys = [t["y"] for t in tiles]
        if not xs:
            return ("No tiles to display", {})
        x_min, x_max = min(xs), max(xs)
        y_min, y_max = min(ys), max(ys)
    else:
        x_min = center[0] - radius
        x_max = center[0] + radius
        y_min = center[1] - radius
        y_max = center[1] + radius

    # Layer 1: Terrain (base)
    if "terrain" in layers:
        for tile in tiles:
            x, y = tile["x"], tile["y"]
            if x_min <= x <= x_max and y_min <= y <= y_max:
                dx = _to_display_x(x, y)
                display_grid[(dx, y)] = _tile_cell(tile, abbrev_registry, seen)

    # Layer 2: Improvements (overlays terrain)
    if "improvements" in layers:
        for tile in tiles:
            x, y = tile["x"], tile["y"]
            if x_min <= x <= x_max and y_min <= y <= y_max:
                if tile.get("improvement_type") is not None and tile.get("improvement_type") != -1:
                    iname = tile.get("improvement_name") or f"Imp{tile['improvement_type']}"
                    sym = name_to_abbrev(iname, abbrev_registry)
                    seen.setdefault(sym, iname)
                    dx = _to_display_x(x, y)
                    display_grid[(dx, y)] = sym

                route = tile.get("route_type")
                if route is not None and route != -1:
                    sym = "===" if route == 1 else "-R-"
                    seen.setdefault(sym, "Railroad" if route == 1 else "Road")
                    dx = _to_display_x(x, y)
                    display_grid[(dx, y)] = sym

    # Layer 3: Resources (overlays improvements)
    if "resources" in layers:
        for tile in tiles:
            x, y = tile["x"], tile["y"]
            if x_min <= x <= x_max and y_min <= y <= y_max:
                if tile.get("is_visible", True) and tile.get("resource_type") is not None:
                    rname = tile.get("resource_name") or f"Resource{tile['resource_type']}"
                    sym = name_to_abbrev(rname, abbrev_registry)
                    seen.setdefault(sym, rname)
                    dx = _to_display_x(x, y)
                    display_grid[(dx, y)] = sym

    # Layer 4: Cities (high priority)
    if "cities" in layers:
        for city in cities:
            x, y = city["x"], city["y"]
            if x_min <= x <= x_max and y_min <= y <= y_max:
                if city.get("is_capital") and city.get("is_ours"):
                    sym = CITY_SYMBOLS["capital"]
                elif city.get("is_ours"):
                    sym = CITY_SYMBOLS["ours"]
                else:
                    sym = CITY_SYMBOLS["other"]
                seen.setdefault(sym, CITY_SYMBOL_NAMES[sym])
                dx = _to_display_x(x, y)
                display_grid[(dx, y)] = sym

    # Layer 5: Units (highest priority, except fog)
    if "units" in layers:
        for unit in units:
            x, y = unit["x"], unit["y"]
            if x_min <= x <= x_max and y_min <= y <= y_max:
                utype = unit.get("unit_type_name", "").lower()
                if "settler" in utype or "colonist" in utype:
                    role = "settler"
                elif "worker" in utype or "builder" in utype:
                    role = "worker"
                elif not unit.get("is_combat_unit", True):
                    role = "civilian"
                else:
                    role = "military"
                sym = UNIT_SYMBOLS[role]
                seen.setdefault(sym, UNIT_SYMBOL_NAMES[sym])
                dx = _to_display_x(x, y)
                display_grid[(dx, y)] = sym

    # Compute display-space column bounds from converted coords
    if display_grid:
        all_dx = [k[0] for k in display_grid]
        dx_min, dx_max = min(all_dx), max(all_dx)
    else:
        dx_min = _to_display_x(x_min, y_max)
        dx_max = _to_display_x(x_max, y_min)

    # Render rows
    lines = []
    for y in range(y_min, y_max + 1):
        indent = "  " if (y % 2 != 0) else ""
        cells = [display_grid.get((dx, y), "   ") for dx in range(dx_min, dx_max + 1)]
        lines.append(indent + "  ".join(cells))

    return "\n".join(lines), seen


def render_map_with_context(
    tiles: List[Dict],
    units: List[Dict] = None,
    cities: List[Dict] = None,
    center: Tuple[int, int] = None,
    radius: int = 10,
    layers: List[str] = None,
    show_legend: bool = True,
    turn: int = None,
    center_name: str = None,
) -> str:
    """Render map with optional header and contextual legend.

    Public API — signature unchanged from prior version.

    Args:
        tiles: Tile dicts from get_visible_tiles
        units: Unit dicts (optional)
        cities: City dicts (optional)
        center: (x, y) storage coordinates for viewport center
        radius: Tiles from center to edge
        layers: Which layers to render
        show_legend: Prepend legend block
        turn: Current turn number (for header)
        center_name: Name of center location (for header)

    Returns:
        Formatted map string
    """
    grid_str, seen = render_map(tiles, units, cities, center, radius, layers)

    result = []

    # Header
    title_parts = []
    if turn is not None:
        title_parts.append(f"Turn {turn}")
    if center_name:
        title_parts.append(f"Center: {center_name}")
    elif center:
        title_parts.append(f"Center: ({center[0]}, {center[1]})")
    if title_parts:
        result.append(" - ".join(title_parts))
        result.append("")

    # Legend
    if show_legend:
        legend = generate_legend_text(seen)
        if legend:
            result.append(legend)
            result.append("")

    # Map
    result.append(grid_str)
    result.append("")

    # Unit summary
    if units:
        result.append("Units in view:")
        for unit in units:
            moves = unit.get("moves_remaining", 0)
            max_moves = unit.get("max_moves", 0)
            result.append(
                f"  - {unit.get('unit_type_name', 'Unknown')} "
                f"(id={unit['id']}) at ({unit['x']}, {unit['y']}) "
                f"- {moves}/{max_moves} moves"
            )
        result.append("")

    return "\n".join(result)
