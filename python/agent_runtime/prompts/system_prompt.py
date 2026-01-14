"""System prompt builder with tool descriptions and warnings."""

from typing import Any, List


def build_system_prompt(tools: List[Any], knowledge_base: Any = None) -> str:
    """Build system prompt with tool definitions, tips, and warnings.
    
    Args:
        tools: List of available tools
        knowledge_base: Optional knowledge base instance
    
    Returns:
        Complete system prompt string
    """
    parts = []
    
    # Introduction
    parts.append("You are an AI assistant playing Civilization V.")
    parts.append("You have access to tools to query game state and take actions.")
    parts.append("")
    
    # Tool descriptions
    parts.append("## Available Tools")
    parts.append("")
    tool_descriptions = format_tool_descriptions(tools)
    parts.append(tool_descriptions)
    parts.append("")
    
    # Knowledge base instructions
    if knowledge_base:
        parts.append("## Knowledge Base")
        parts.append("")
        parts.append("You have access to a persistent knowledge base for long-term memory.")
        parts.append("Use update_knowledge_base to:")
        parts.append("- Store your strategy and goals")
        parts.append("- Remember relationships with other civilizations")
        parts.append("- Track important decisions and their outcomes")
        parts.append("- Note lessons learned")
        parts.append("")
        parts.append("Operations: add, update, delete, get, list")
        parts.append("Example: update_knowledge_base(operation='add', section_id='strategy', content='Going for science victory')")
        parts.append("")
    
    # Tips and warnings
    parts.append("## Tips and Best Practices")
    parts.append("")
    tips = format_tips_and_warnings()
    parts.append(tips)
    parts.append("")
    
    # Output format
    parts.append("## Output Format")
    parts.append("")
    parts.append("When you're ready to take actions, return a JSON object with:")
    parts.append("- 'actions': List of action dicts")
    parts.append("- 'notes': Optional string explaining your decisions")
    parts.append("")
    parts.append("Each action dict should have a 'kind' field and appropriate parameters.")
    parts.append("Example: {'actions': [{'kind': 'move_unit', 'unit_id': 1, 'to': [10, 20]}], 'notes': 'Moving scout to explore'}")
    
    return "\n".join(parts)


def format_tool_descriptions(tools: List[Any]) -> str:
    """Format tool descriptions for system prompt.
    
    Args:
        tools: List of tool instances
    
    Returns:
        Formatted tool descriptions string
    """
    descriptions = []
    
    for tool in tools:
        tool_name = tool.name() if hasattr(tool, "name") else str(tool)
        
        if tool_name == "mcp_call":
            descriptions.append("### MCP Tools (via mcp_call)")
            descriptions.append("")
            descriptions.append("Call orchestrator tools using: mcp_call(tool='tool_name', arguments={...})")
            descriptions.append("")
            descriptions.append("Available tools:")
            descriptions.append("- get_game_state: Get high-level game state summary")
            descriptions.append("- get_cities: Get all cities (optionally filter by city_id)")
            descriptions.append("- get_units: Get all units (optionally filter by player_id)")
            descriptions.append("- get_city_production: Get production options for a city")
            descriptions.append("- get_available_techs: Get available technologies to research")
            descriptions.append("- get_notifications: Get recent game notifications")
            descriptions.append("- send_action: Send an action to the game (move unit, etc.)")
            descriptions.append("- set_city_production: Set what a city is producing")
            descriptions.append("- choose_tech: Select a technology to research")
            descriptions.append("- end_turn: End the current turn (requires turn number)")
            descriptions.append("")
        elif tool_name == "update_knowledge_base":
            descriptions.append("### Knowledge Base Tool")
            descriptions.append("")
            descriptions.append("update_knowledge_base(operation, section_id, content?)")
            descriptions.append("")
            descriptions.append("Operations:")
            descriptions.append("- 'add' or 'update': Store content in a section")
            descriptions.append("- 'delete': Remove a section")
            descriptions.append("- 'get': Retrieve content from a section")
            descriptions.append("- 'list': List all sections")
            descriptions.append("")
        else:
            descriptions.append(f"### {tool_name}")
            descriptions.append("")
            descriptions.append(f"Tool: {tool_name}")
            descriptions.append("")
    
    return "\n".join(descriptions)


def format_tips_and_warnings() -> str:
    """Format tips and warnings for system prompt.
    
    Returns:
        Formatted tips and warnings string
    """
    tips = []
    
    tips.append("**IMPORTANT WARNINGS:**")
    tips.append("")
    tips.append("1. Don't assume game state - always query if unsure")
    tips.append("   - Use get_game_state() to check current status")
    tips.append("   - Use get_available_choices() before ending turn")
    tips.append("   - Verify city/unit states before taking actions")
    tips.append("")
    tips.append("2. Check for pending decisions before ending turn")
    tips.append("   - Research choices, city production, policy selections")
    tips.append("   - Use get_available_choices() to see what needs attention")
    tips.append("")
    tips.append("3. Update knowledge base when strategy changes")
    tips.append("   - Store your overall strategy")
    tips.append("   - Remember relationships with other civs")
    tips.append("   - Track important decisions and outcomes")
    tips.append("")
    tips.append("4. Don't forget to manage city production")
    tips.append("   - Check city production status regularly")
    tips.append("   - Set production for new cities")
    tips.append("   - Adjust production based on needs")
    tips.append("")
    tips.append("**BEST PRACTICES:**")
    tips.append("")
    tips.append("- Start each turn by querying game state")
    tips.append("- Plan your actions before executing them")
    tips.append("- Use knowledge base to remember long-term goals")
    tips.append("- Check notifications for important events")
    tips.append("- Verify action results before proceeding")
    tips.append("- Always call end_turn() when done (with correct turn number)")
    
    return "\n".join(tips)

