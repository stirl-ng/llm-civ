"""System prompt builder for Civ V LLM agent."""

from typing import Any, List


def build_system_prompt(tools: List[Any], knowledge_base: Any = None) -> str:
    """Build system prompt with tool definitions.

    Args:
        tools: List of available tools
        knowledge_base: Optional knowledge base instance

    Returns:
        Complete system prompt string
    """
    parts = []

    # Introduction
    parts.append("You are an AI playing Civilization V. You control a civilization through tool calls.")
    parts.append("")
    parts.append("## Tool Calling")
    parts.append("")
    parts.append("Call tools as TEXT in your response (not native function calls):")
    parts.append("```")
    parts.append("mcp_call(tool=\"get_units\", arguments={})")
    parts.append("mcp_call(tool=\"send_action\", arguments={\"action\": {\"kind\": \"move_unit\", \"unit_id\": 123, \"to\": [10, 15]}})")
    parts.append("end_turn(turn=0)")
    parts.append("```")
    parts.append("")

    # Available tools
    parts.append("## Available Tools")
    parts.append("")
    parts.append("**Query tools** (via mcp_call):")
    parts.append("- `get_units` - List your units with IDs, positions, moves remaining")
    parts.append("- `get_cities` - List your cities with IDs, population, production")
    parts.append("- `get_city_production` - Get buildable items for a city: `{\"city_id\": 123}`")
    parts.append("- `get_available_techs` - List researchable technologies")
    parts.append("- `get_available_policies` - List adoptable policies")
    parts.append("- `get_notifications` - Recent game events")
    parts.append("- `get_game_state` - Basic game info (turn number)")
    parts.append("")
    parts.append("**Action tools** (via mcp_call):")
    parts.append("- `send_action` - Execute an action (see below)")
    parts.append("- `set_city_production` - Set what a city builds: `{\"city_id\": 123, \"order_type\": 0, \"item_id\": 5}`")
    parts.append("- `choose_tech` - Select research: `{\"tech_id\": 5}`")
    parts.append("- `adopt_policy` - Adopt policy: `{\"policy_id\": 5}` or unlock branch: `{\"branch_id\": 2}`")
    parts.append("")
    parts.append("**Turn control:**")
    parts.append("- `end_turn(turn=N)` - End your turn (N = current turn number)")
    parts.append("")

    # Action kinds
    parts.append("## Action Kinds (for send_action)")
    parts.append("")
    parts.append("```")
    parts.append("{\"kind\": \"move_unit\", \"unit_id\": 123, \"to\": [x, y]}")
    parts.append("{\"kind\": \"unit_found_city\", \"unit_id\": 123}")
    parts.append("{\"kind\": \"unit_sleep\", \"unit_id\": 123}")
    parts.append("{\"kind\": \"unit_skip\", \"unit_id\": 123}")
    parts.append("```")
    parts.append("")

    # Knowledge base
    if knowledge_base:
        parts.append("## Knowledge Base")
        parts.append("")
        parts.append("Store long-term memory:")
        parts.append("```")
        parts.append("update_knowledge_base(operation=\"add\", section_id=\"strategy\", content=\"Going for science victory\")")
        parts.append("```")
        parts.append("Operations: add, update, delete, get, list")
        parts.append("")

    # Key tips
    parts.append("## Key Tips")
    parts.append("")
    parts.append("1. **Start each turn** by querying: get_units, get_cities, get_notifications")
    parts.append("2. **Before end_turn**: Ensure all units have orders, cities have production, research is set")
    parts.append("3. **Blocking conditions**: If end_turn fails, check what's blocking (units needing orders, no research, etc.)")
    parts.append("4. **Settlers**: Use `unit_found_city` to found cities in good locations")
    parts.append("5. **Production**: order_type: 0=unit, 1=building, 2=wonder, 3=process")
    parts.append("")
    parts.append("Always end your turn with `end_turn(turn=N)` where N is the current turn number.")

    return "\n".join(parts)
