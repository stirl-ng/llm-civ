"""
ASCII Map Renderer for LLM Spatial Awareness

Converts tile data from the game into ASCII maps that give the LLM
spatial awareness similar to what human players see.
"""

from typing import Dict, List, Tuple, Optional

# Terrain type constants (from Civ V)
TERRAIN_GRASS = 0
TERRAIN_PLAINS = 1
TERRAIN_DESERT = 2
TERRAIN_TUNDRA = 4
TERRAIN_SNOW = 5

# Feature type constants
FEATURE_NONE = -1
FEATURE_FOREST = 0
FEATURE_JUNGLE = 1
FEATURE_MARSH = 6
FEATURE_ICE = 3

# Plot type constants
PLOT_OCEAN = 0
PLOT_LAND = 1
PLOT_HILLS = 2
PLOT_MOUNTAIN = 3


def terrain_to_symbol(tile: Dict) -> str:
    """
    Convert tile data to ASCII symbol.

    Priority:
    1. Unexplored (?)
    2. Mountains (M)
    3. Water (~)
    4. Features (n=forest, N=jungle, #=marsh, i=ice)
    5. Hills (^)
    6. Terrain type (., :, d, t, s)
    """
    # Check if revealed
    if not tile.get("is_revealed", False):
        return "?"

    # Mountains (impassable)
    if tile.get("is_mountain", False):
        return "M"

    # Water
    if tile.get("is_water", False):
        return "~"

    # Features (take precedence over terrain)
    feature_type = tile.get("feature_type", FEATURE_NONE)
    if feature_type == FEATURE_FOREST:
        return "n"  # forest (tree)
    elif feature_type == FEATURE_JUNGLE:
        return "N"  # jungle (dense tree)
    elif feature_type == FEATURE_MARSH:
        return "#"  # marsh (hashtag suggests difficult terrain)
    elif feature_type == FEATURE_ICE:
        return "i"  # ice

    # Hills
    if tile.get("is_hills", False):
        return "^"  # hills (caret = elevated)

    # Base terrain
    terrain_type = tile.get("terrain_type", TERRAIN_GRASS)
    if terrain_type == TERRAIN_GRASS:
        return "."  # grassland (fertile)
    elif terrain_type == TERRAIN_PLAINS:
        return ":"  # plains (similar but less dense)
    elif terrain_type == TERRAIN_DESERT:
        return "d"  # desert
    elif terrain_type == TERRAIN_TUNDRA:
        return "t"  # tundra (cold)
    elif terrain_type == TERRAIN_SNOW:
        return "s"  # snow (very cold)

    return "?"  # Unknown


def resource_to_symbol(tile: Dict) -> str:
    """Convert tile with resource to symbol."""
    # Only show if resource is present
    if tile.get("resource_type") is not None and tile.get("is_visible", False):
        # Could differentiate luxury vs strategic in the future
        # For now, use single symbol
        return "*"
    return None


def improvement_to_symbol(tile: Dict) -> str:
    """Convert tile with improvement/route to symbol."""
    # Route takes precedence
    route_type = tile.get("route_type")
    if route_type is not None and route_type != -1:
        if route_type == 1:  # Railroad
            return "="
        else:  # Road (type 0)
            return "R"

    # Improvement
    improvement_type = tile.get("improvement_type")
    if improvement_type is not None and improvement_type != -1:
        # Generic improvement symbol
        return "+"

    return None


def unit_to_symbol(unit: Dict) -> str:
    """Convert unit data to symbol."""
    unit_type = unit.get("unit_type_name", "").lower()

    # Settlers
    if "settler" in unit_type or "colonist" in unit_type:
        return "S"

    # Workers/builders
    if "worker" in unit_type or "builder" in unit_type:
        return "W"

    # Civilian (catch-all)
    if not unit.get("is_combat_unit", True):
        return "w"  # lowercase for other civilians

    # Military units (generic)
    return "U"


def city_to_symbol(city: Dict, is_capital: bool, is_ours: bool) -> str:
    """Convert city data to symbol."""
    if is_capital and is_ours:
        return "@"  # Our capital
    elif is_ours:
        return "C"  # Our city
    else:
        return "c"  # Enemy/other civ city


def render_map(
    tiles: List[Dict],
    units: List[Dict] = None,
    cities: List[Dict] = None,
    center: Tuple[int, int] = None,
    radius: int = 10,
    layers: List[str] = None,
    show_fog: bool = True,
    show_grid: bool = True
) -> str:
    """
    Render ASCII map from tile/unit/city data.

    Args:
        tiles: List of tile dicts from get_visible_tiles
        units: List of unit dicts (optional)
        cities: List of city dicts (optional)
        center: (x, y) tuple for map center
        radius: Tiles from center to edge
        layers: Which layers to show (terrain, resources, improvements, units, cities)
        show_fog: Show fog-of-war tiles as '?'
        show_grid: Show coordinate grid

    Returns:
        ASCII map string
    """
    if layers is None:
        layers = ["terrain", "resources", "improvements", "units", "cities"]

    if units is None:
        units = []

    if cities is None:
        cities = []

    # Create grid indexed by (x, y)
    grid = {}

    # Determine bounds
    if center is None:
        # Use all tiles if no center specified
        xs = [t["x"] for t in tiles]
        ys = [t["y"] for t in tiles]
        if not xs or not ys:
            return "No tiles to display"
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
                grid[(x, y)] = terrain_to_symbol(tile)

    # Layer 2: Improvements (overlays terrain)
    if "improvements" in layers:
        for tile in tiles:
            x, y = tile["x"], tile["y"]
            if x_min <= x <= x_max and y_min <= y <= y_max:
                symbol = improvement_to_symbol(tile)
                if symbol:
                    grid[(x, y)] = symbol

    # Layer 3: Resources (overlays improvements)
    if "resources" in layers:
        for tile in tiles:
            x, y = tile["x"], tile["y"]
            if x_min <= x <= x_max and y_min <= y <= y_max:
                symbol = resource_to_symbol(tile)
                if symbol:
                    grid[(x, y)] = symbol

    # Layer 4: Cities (high priority)
    if "cities" in layers:
        for city in cities:
            x, y = city["x"], city["y"]
            if x_min <= x <= x_max and y_min <= y <= y_max:
                is_capital = city.get("is_capital", False)
                is_ours = city.get("is_ours", False)
                grid[(x, y)] = city_to_symbol(city, is_capital, is_ours)

    # Layer 5: Units (highest priority, except fog)
    if "units" in layers:
        for unit in units:
            x, y = unit["x"], unit["y"]
            if x_min <= x <= x_max and y_min <= y <= y_max:
                grid[(x, y)] = unit_to_symbol(unit)

    # Render to string
    lines = []

    if show_grid:
        # Header with column numbers
        header = "    "  # Indent for row numbers
        for x in range(x_min, x_max + 1):
            header += f"{x:2d} "
        lines.append(header)

        # Top border
        border = "   +" + "-" * ((x_max - x_min + 1) * 3) + "+"
        lines.append(border)

    # Rows
    for y in range(y_min, y_max + 1):
        if show_grid:
            row = f"{y:2d} |"
        else:
            row = ""

        for x in range(x_min, x_max + 1):
            symbol = grid.get((x, y), "?" if show_fog else " ")
            if show_grid:
                row += f" {symbol} "
            else:
                row += symbol

        if show_grid:
            row += "|"
        lines.append(row)

    if show_grid:
        # Bottom border
        lines.append(border)

    return "\n".join(lines)


def generate_legend() -> str:
    """Generate legend explaining symbols."""
    return """Legend:
  @=Your capital  C=Your city  c=Other city
  U=Military unit  S=Settler  W=Worker
  *=Resource  +=Improvement  R=Road  ==Railroad
  .=Grass  :=Plains  d=Desert  t=Tundra  s=Snow
  ^=Hills  M=Mountain  ~=Water
  n=Forest  N=Jungle  #=Marsh  i=Ice
  ?=Unexplored
"""


def render_map_with_context(
    tiles: List[Dict],
    units: List[Dict] = None,
    cities: List[Dict] = None,
    center: Tuple[int, int] = None,
    radius: int = 10,
    layers: List[str] = None,
    show_legend: bool = True,
    turn: int = None,
    center_name: str = None
) -> str:
    """
    Render map with contextual information (title, legend, unit list).

    Args:
        tiles: List of tile dicts
        units: List of unit dicts (filtered to viewport)
        cities: List of city dicts (filtered to viewport)
        center: (x, y) center point
        radius: Viewport radius
        layers: Which layers to show
        show_legend: Include legend
        turn: Current turn number
        center_name: Name of center location (e.g., city name)

    Returns:
        Formatted map string with context
    """
    result = []

    # Title
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
        result.append(generate_legend())

    # Map
    map_str = render_map(tiles, units, cities, center, radius, layers)
    result.append(map_str)
    result.append("")

    # Unit summary (if units in viewport)
    if units:
        result.append("Units in view:")
        for unit in units:
            moves = unit.get("moves_remaining", 0)
            max_moves = unit.get("max_moves", 0)
            result.append(f"  - {unit.get('unit_type_name', 'Unknown')} "
                         f"(id={unit['id']}) at ({unit['x']}, {unit['y']}) "
                         f"- {moves}/{max_moves} moves")
        result.append("")

    return "\n".join(result)
