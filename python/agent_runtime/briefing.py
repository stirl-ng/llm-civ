"""Turn briefing generator for structured state presentation."""

from typing import Any, Dict, List, Optional


def generate_turn_briefing(
    mcp_tool: Any,
    knowledge_base: Any,
    turn_number: int
) -> str:
    """Generate structured turn briefing.
    
    Args:
        mcp_tool: MCP tool instance for querying orchestrator
        knowledge_base: Knowledge base instance for reminders
        turn_number: Current turn number
    
    Returns:
        Formatted turn briefing string
    """
    parts = []
    
    # Header
    parts.append("=" * 60)
    parts.append(f"TURN {turn_number} BRIEFING")
    parts.append("=" * 60)
    parts.append("")
    
    # Get game state
    state_result = mcp_tool.run({
        "tool": "get_game_state",
        "arguments": {}
    })
    
    if state_result.get("status") == "success":
        state = state_result.get("result", {})
        if isinstance(state, dict) and state.get("type") == "state_refresh":
            state = state.get("state", {})
        
        # Format state summary
        state_summary = format_state_summary(state)
        parts.append("STATUS:")
        parts.append(state_summary)
        parts.append("")
    
    # Get recent notifications
    notifications_result = mcp_tool.run({
        "tool": "get_notifications",
        "arguments": {}
    })
    
    if notifications_result.get("status") == "success":
        notifications = notifications_result.get("result", {})
        if isinstance(notifications, dict):
            recent_events = format_recent_events(notifications)
            if recent_events:
                parts.append("RECENT EVENTS:")
                parts.append(recent_events)
                parts.append("")
    
    # Get pending decisions
    choices_result = mcp_tool.run({
        "tool": "get_available_choices",
        "arguments": {}
    })
    
    if choices_result.get("status") == "success":
        choices = choices_result.get("result", {})
        if isinstance(choices, dict):
            pending = format_pending_decisions(choices)
            if pending:
                parts.append("PENDING DECISIONS:")
                parts.append(pending)
                parts.append("")
    
    # Knowledge base reminders
    if knowledge_base:
        kb_reminders = format_kb_reminders(knowledge_base)
        if kb_reminders:
            parts.append("KNOWLEDGE BASE REMINDERS:")
            parts.append(kb_reminders)
            parts.append("")
    
    parts.append("=" * 60)
    
    return "\n".join(parts)


def format_state_summary(state: Dict[str, Any]) -> str:
    """Format game state summary like RAM data.
    
    Args:
        state: Game state dictionary
    
    Returns:
        Formatted state summary string
    """
    lines = []
    
    # Basic info
    turn = state.get("turn", "?")
    active_player = state.get("activePlayer", "?")
    
    lines.append(f"TURN: {turn}")
    lines.append(f"ACTIVE PLAYER: {active_player}")
    
    # Civilization info (if available)
    if "civilization" in state:
        lines.append(f"CIVILIZATION: {state['civilization']}")
    if "leader" in state:
        lines.append(f"LEADER: {state['leader']}")
    
    # Resource info
    if "gold" in state:
        lines.append(f"GOLD: {state['gold']}")
    if "happiness" in state:
        lines.append(f"HAPPINESS: {state['happiness']}")
    if "culture" in state:
        lines.append(f"CULTURE: {state['culture']}")
    if "faith" in state:
        lines.append(f"FAITH: {state['faith']}")
    
    # Research info
    if "current_research" in state:
        research = state["current_research"]
        if isinstance(research, dict):
            name = research.get("name", "?")
            turns = research.get("turns", "?")
            lines.append(f"RESEARCH: {name} ({turns} turns)")
    elif "researching" in state:
        lines.append(f"RESEARCH: {state['researching']}")
    
    # City/unit counts
    if "cities" in state:
        city_count = len(state["cities"]) if isinstance(state["cities"], list) else state.get("city_count", "?")
        lines.append(f"CITIES: {city_count}")
    if "units" in state:
        unit_count = len(state["units"]) if isinstance(state["units"], list) else state.get("unit_count", "?")
        lines.append(f"UNITS: {unit_count}")
    
    return "\n".join(f"  - {line}" for line in lines)


def format_recent_events(notifications: Dict[str, Any]) -> str:
    """Format recent notifications/events.
    
    Args:
        notifications: Notifications dictionary
    
    Returns:
        Formatted recent events string
    """
    lines = []
    
    # Extract notifications list
    notif_list = notifications.get("notifications", [])
    if isinstance(notif_list, list):
        # Get last 2-3 notifications
        recent = notif_list[-3:] if len(notif_list) > 3 else notif_list
        
        for notif in recent:
            if isinstance(notif, dict):
                msg = notif.get("message", notif.get("text", str(notif)))
                turn = notif.get("turn", "")
                if turn:
                    lines.append(f"  - Turn {turn}: {msg}")
                else:
                    lines.append(f"  - {msg}")
    
    if not lines:
        return ""
    
    return "\n".join(lines)


def format_pending_decisions(choices: Dict[str, Any]) -> str:
    """Format pending decisions that need attention.
    
    Args:
        choices: Available choices dictionary
    
    Returns:
        Formatted pending decisions string
    """
    lines = []
    
    # Check for tech choice
    if choices.get("needs_tech_choice"):
        lines.append("  - Choose next technology to research")
    
    # Check for policy choice
    if choices.get("needs_policy_choice"):
        lines.append("  - Choose social policy")
    
    # Check for city production
    cities_needing_production = choices.get("cities_needing_production", [])
    if cities_needing_production:
        for city in cities_needing_production:
            if isinstance(city, dict):
                city_name = city.get("name", f"City {city.get('id', '?')}")
                lines.append(f"  - Set production for {city_name}")
            else:
                lines.append(f"  - Set production for city {city}")
    
    # Check for other choices
    other_choices = choices.get("other_choices", [])
    if other_choices:
        for choice in other_choices:
            if isinstance(choice, dict):
                desc = choice.get("description", str(choice))
                lines.append(f"  - {desc}")
            else:
                lines.append(f"  - {choice}")
    
    if not lines:
        return ""
    
    return "\n".join(lines)


def format_kb_reminders(knowledge_base: Any) -> str:
    """Format knowledge base reminders.
    
    Args:
        knowledge_base: Knowledge base instance
    
    Returns:
        Formatted KB reminders string
    """
    lines = []
    
    # Get all sections
    all_sections = knowledge_base.list_all()
    
    # Show strategy if available
    if "strategy" in all_sections:
        strategy = all_sections["strategy"]
        # Truncate if too long
        if len(strategy) > 100:
            strategy = strategy[:100] + "..."
        lines.append(f"  - Strategy: {strategy}")
    
    # Show relationships (civ names as keys)
    for section_id, content in all_sections.items():
        if section_id != "strategy" and len(content) < 150:
            # Truncate if too long
            display_content = content[:100] + "..." if len(content) > 100 else content
            lines.append(f"  - {section_id}: {display_content}")
    
    if not lines:
        return ""
    
    return "\n".join(lines)

