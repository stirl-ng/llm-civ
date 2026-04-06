"""Legend and abbreviation system for the hex ASCII map renderer.

Owns all symbol→meaning mappings. Hardcoded tables cover the fixed Civ V enums
(terrain, feature, plot type). Dynamic resources/improvements use name_to_abbrev()
with names supplied by the DLL at runtime.

TODO: Load abbreviation overrides from a config/XML file so common resources
      get canonical 3-char codes (WHT=Wheat, IRN=Iron, HRS=Horses, etc.) rather
      than auto-generated ones.
"""

# ── Hardcoded enum tables ──────────────────────────────────────────────────────
# (abbrev, description) tuples

# terrain_type int → (3-char abbrev, display name)
TERRAIN_ABBREVS: dict[int, tuple[str, str]] = {
    0: ("GRS", "Grassland"),
    1: ("PLN", "Plains"),
    2: ("DST", "Desert"),
    4: ("TND", "Tundra"),
    5: ("SNW", "Snow"),
}

# feature_type int → single char prefix, combined with terrain[:2]
# e.g. forest(0) on grassland → "n" + "GR" = "nGR"
FEATURE_PREFIX: dict[int, str] = {
    0: "n",   # Forest
    1: "N",   # Jungle
    6: "#",   # Marsh
}
FEATURE_PREFIX_NAMES: dict[int, str] = {
    0: "Forest",
    1: "Jungle",
    6: "Marsh",
}

# feature_type int → standalone (3-char abbrev, display name) — no terrain prefix
FEATURE_SOLO: dict[int, tuple[str, str]] = {
    3: ("ICE", "Ice"),
}

# plot_type int → (3-char abbrev, display name)  — overrides terrain
PLOT_ABBREVS: dict[int, tuple[str, str]] = {
    0: ("~~~", "Ocean"),
    2: ("^^^", "Hills"),
    3: ("/M\\", "Mountain"),
}

# Unit role → 3-char symbol
UNIT_SYMBOLS: dict[str, str] = {
    "settler":  "[S]",
    "worker":   "[W]",
    "military": "[U]",
    "civilian": "[w]",
}
UNIT_SYMBOL_NAMES: dict[str, str] = {
    "[S]": "Settler",
    "[W]": "Worker",
    "[U]": "Military unit",
    "[w]": "Civilian unit",
}

# City role → 3-char symbol
CITY_SYMBOLS: dict[str, str] = {
    "capital": "[@]",
    "ours":    "[C]",
    "other":   "[c]",
}
CITY_SYMBOL_NAMES: dict[str, str] = {
    "[@]": "Our capital",
    "[C]": "Our city",
    "[c]": "Enemy/CS city",
}

FOG = "???"


# ── Dynamic abbreviation generator ────────────────────────────────────────────

def name_to_abbrev(name: str, registry: dict[str, str]) -> str:
    """Generate a unique 3-char uppercase abbreviation from a display name.

    Uses a session-scoped registry to detect and resolve collisions.

    Strategy:
      1. First 3 chars of first word (e.g. "Iron" → "IRO")
      2. Acronym of first 3 words (e.g. "Iron Ore" → "IO_")
      3. 2-char prefix + digit suffix (e.g. "IR2", "IR3"...)

    Args:
        name: Human-readable name from DLL (e.g. "Iron", "Farm", "Wheat")
        registry: Mutable dict mapping abbrev → canonical name for this render

    Returns:
        3-char uppercase abbreviation, registered in registry
    """
    if not name:
        return "???"

    words = name.upper().split()
    candidates = [
        words[0][:3].ljust(3, "_"),
        "".join(w[0] for w in words[:3]).ljust(3, "_"),
    ]

    for cand in candidates:
        if cand not in registry or registry[cand] == name:
            registry[cand] = name
            return cand

    # Collision: append digit
    base = candidates[0][:2]
    for n in range(2, 10):
        cand = base + str(n)
        if cand not in registry or registry[cand] == name:
            registry[cand] = name
            return cand

    return "???"


# ── Legend text generator ──────────────────────────────────────────────────────

def generate_legend_text(seen: dict[str, str]) -> str:
    """Generate a compact legend showing only symbols that appeared in this render.

    Args:
        seen: dict mapping symbol → description, populated during render

    Returns:
        Multi-line legend string
    """
    if not seen:
        return ""
    lines = ["Legend:"]
    for symbol, desc in sorted(seen.items()):
        lines.append(f"  {symbol} = {desc}")
    return "\n".join(lines)
