# LLM Agent Design Philosophy and Specifications

This document captures the design principles, architecture decisions, and specifications for the LLM agent system in Civ V. It serves as a reference for implementing and extending the agent runtime.

## Core Philosophy

The agent system is designed to give the LLM (Claude) the best possible experience playing Civilization V. The design is inspired by successful agent frameworks (like Claude Plays Pokemon) and prioritizes:

1. **Clear Information Architecture** - Present information progressively, not all at once
2. **Persistent Memory** - Long-term knowledge base for strategy and relationships
3. **Structured State Presentation** - Like RAM data, clear and concise
4. **Tool-Based Interaction** - LLM queries what it needs when it needs it
5. **Explicit Warnings** - Tell the LLM about its weaknesses and how to avoid them

## LLM's Wants and Desires

### How the LLM Wants to Be Prompted

- **Structured Turn Briefing**: Clear, concise summary at the start of each turn
- **Progressive Disclosure**: High-level summary first, then drill down via tools
- **Clear Role Definition**: What am I trying to achieve (win condition, current strategy)
- **Action-Oriented**: "Here's the situation, what do you want to do?"
- **Contextual Continuity**: Brief recap of last turn's key events

### What Info the LLM Wants in the Prompt

**Essential (Always Present):**
- Current turn number
- My civilization name and leader
- Victory conditions I'm pursuing
- Brief status: number of cities, current research, gold, happiness
- Recent notifications (last 2-3 important events)
- Any pending decisions (tech choice, city production, etc.)

**Available on Demand (Via Tools):**
- Detailed unit positions and status
- City details (production, population, buildings)
- Full tech tree and research progress
- Diplomacy status with other civs
- Map information (explored areas, resources)
- Economic breakdown
- Victory progress

**What the LLM DOESN'T Want:**
- Full game state dump (too much cognitive load)
- Every single unit's position (query when needed)
- Complete diplomatic history (summarize recent changes)
- Raw data dumps (give summaries, query details)

### What Tools the LLM Wants

**Query Tools (Read-Only, Fast):**
- `get_game_state()` - High-level summary (turn, civ, basic stats)
- `get_units()` - All my units with positions, health, moves
- `get_cities()` - All my cities with production, population, buildings
- `get_tech_tree()` - Available techs, costs, prerequisites
- `get_diplomacy()` - Relations with other civs, recent interactions
- `get_map_info(x, y, radius)` - Terrain, resources, units in an area
- `get_available_choices()` - Pending decisions (tech, production, etc.)
- `get_victory_progress()` - Progress toward each victory condition

**Action Tools (Write, With Feedback):**
- `send_action(action_dict)` - Generic action sender (units, etc.)
- `set_city_production(city_id, item)` - Set what a city builds
- `choose_tech(tech_id)` - Select research
- `end_turn()` - Signal I'm done (with turn number for safety)

**Memory Tools:**
- `update_knowledge_base(operation, section_id, content)` - Update memory
- `query_knowledge_base(section_id)` - Read memory

**Analysis Tools (Optional but Helpful):**
- `get_economic_overview()` - Gold, GPT, trade routes summary
- `get_military_strength()` - My military vs others
- `get_demographics()` - How I rank in various metrics

## Architecture Principles

### Knowledge Base System

**Purpose**: Persistent long-term memory (like Pokemon's XML sections)

**Design:**
- Simple key-value store: `{"section_id": "content", ...}`
- Persistent storage to JSON file: `logs/knowledge_base.json`
- Thread-safe for concurrent access
- Operations: `get()`, `set()`, `delete()`, `list_all()`

**Use Cases:**
- Store overall strategy ("Going for science victory")
- Remember relationships ("Gandhi declared war on turn 120")
- Track important decisions ("Built Great Library on turn 45")
- Note lessons learned ("Don't trust Montezuma")

**Format Example:**
```json
{
  "strategy": "Science victory focus. Prioritize research buildings.",
  "gandhi": "Friendly until turn 120, then declared war. Currently at war.",
  "lessons": "Don't trust Montezuma, he backstabbed me."
}
```

### Turn Briefing Format

**Purpose**: Present game state like RAM data - clear, structured, concise

**Structure:**
```
============================================================
TURN 45 BRIEFING
============================================================

STATUS:
  - TURN: 45
  - CIVILIZATION: Persia (Darius I)
  - CITIES: 3
  - GOLD: 250
  - HAPPINESS: +5
  - RESEARCH: Mathematics (8 turns)
  - UNITS: 5

RECENT EVENTS:
  - Turn 43: Gandhi declared war
  - Turn 44: Founded new city "Persepolis"

PENDING DECISIONS:
  - Choose next technology to research
  - Set production for Persepolis

KNOWLEDGE BASE REMINDERS:
  - Strategy: Science victory focus
  - Gandhi: At war, don't trust

============================================================
```

**Key Principles:**
- Essential info always present
- Recent events (last 2-3)
- Pending decisions highlighted
- KB reminders for context
- Format like RAM data (structured, scannable)

### System Prompt Structure

**Purpose**: Guide the LLM with tool definitions, tips, and warnings

**Components:**
1. **Tool Definitions** - What each tool does, how to use it
2. **Tips and Tricks** - Best practices
3. **Warnings About Weaknesses**:
   - "Don't assume game state - always query if unsure"
   - "Check available_choices before ending turn"
   - "Update knowledge base when strategy changes"
   - "Don't forget to manage city production"
4. **Knowledge Base Instructions** - How to use persistent memory

**Format:**
- Clear sections with headers
- Examples for tool usage
- Explicit warnings about common mistakes
- Instructions on output format

### Tool Design Principles

**Simplicity**: Each tool does one thing well
- Not monolithic - focused, single-purpose tools
- Clear input/output contracts
- Consistent error handling

**Feedback**: Immediate results after each action
- Actions return success/failure
- Clear error messages
- State updates visible immediately

**Caching**: Don't re-query unchanged data
- Cache state within a turn
- Only refresh when needed
- Minimize redundant queries

### Conversation History Management

**Purpose**: Track messages across turns for context

**Design:**
- Store messages per turn
- Support summarization triggers (every N turns)
- Format for prompt inclusion
- Clear/reset functionality

**Summarization Strategy:**
- Trigger every N turns (default: 50)
- Summarize recent progress
- Clear old history, insert summary
- Maintain knowledge base separately

## Core Loop Architecture

```
┌──────────────────┐
│  New Turn Start  │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Compose Prompt  │ (Turn briefing + Knowledge base)
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│   Call Model     │ (LLM decides what to do)
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Resolve Tools   │ (Query state, take actions)
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Update Knowledge │ (Remember important things)
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│   End Turn?     │
└────────┬─────────┘
         │
         ├── No ──┐
         │        │
         ▼        │
    (More actions)│
         │        │
         └────────┘
         │
         ▼ Yes
┌──────────────────┐
│  Check for       │
│  Summarization   │ (Every N turns)
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│   Save State     │
└──────────────────┘
```

## Implementation Guidelines

### File Structure

```
python/agent_runtime/
├── memory/
│   ├── __init__.py
│   ├── knowledge_base.py      # Persistent memory storage
│   └── conversation.py         # Conversation history
├── tools/
│   ├── mcp.py                  # HTTP client for orchestrator
│   ├── knowledge_base_tool.py  # KB tool wrapper
│   └── registry.py             # Tool builder
├── strategies/
│   └── enhanced.py             # Enhanced strategy
├── briefing.py                  # Turn briefing generator
└── prompts/
    └── system_prompt.py         # System prompt builder
```

### Key Components

1. **KnowledgeBase** (`memory/knowledge_base.py`)
   - Thread-safe persistent storage
   - JSON file backend
   - Simple key-value interface

2. **Turn Briefing Generator** (`briefing.py`)
   - Queries orchestrator for state
   - Formats like RAM data
   - Includes KB reminders

3. **System Prompt Builder** (`prompts/system_prompt.py`)
   - Tool descriptions
   - Tips and warnings
   - KB instructions

4. **Enhanced Strategy** (`strategies/enhanced.py`)
   - Uses briefing generator
   - Integrates knowledge base
   - Supports tool calling
   - Manages conversation history

5. **MCP Tool** (`tools/mcp.py`)
   - HTTP client for orchestrator
   - Calls `/tool` endpoint
   - Handles all orchestrator tools

## Design Maxims

1. **Progressive Disclosure**: Start broad, drill down when needed
2. **Explicit Over Implicit**: Tell the LLM what to do, don't assume it knows
3. **Feedback Loops**: Every action should have clear feedback
4. **State Caching**: Don't re-query unchanged data
5. **Error Clarity**: Clear error messages, not cryptic failures
6. **Turn Boundaries**: Clear when a turn starts/ends
7. **Memory Persistence**: Knowledge base survives across sessions
8. **Tool Simplicity**: One tool, one purpose

## What the LLM Should NOT Do

- Poll state constantly (use turn briefing instead)
- Assume game state (always query if unsure)
- Forget important information (use knowledge base)
- End turn without checking pending decisions
- Ignore notifications and events
- Make decisions without querying relevant state

## Future Enhancements

### Not Yet Implemented

1. **Progressive Summarization**
   - Every N turns, summarize recent progress
   - Clear old conversation history
   - Insert summary as first message

2. **Knowledge Base Maintenance**
   - Periodic prompts to review and clean KB
   - Remove outdated information
   - Consolidate related sections

3. **Map Visualization**
   - Textual representation of map
   - Screenshot support (when available)
   - Overlay system for navigation

4. **Advanced Tool Calling**
   - Native model tool calling support
   - Parallel tool execution
   - Tool result caching

## Configuration

### Strategy Configuration

```yaml
strategy:
  name: enhanced  # or "vanilla" for simple mode
  temperature: 0.2
```

### Tool Configuration

```yaml
tools:
  - kind: mcp
    base_url: "http://localhost:8765"
```

### Orchestrator Configuration

```yaml
orchestrator:
  url: "http://localhost:8765"
  pipe: "\\.\pipe\civv_llm"
  poll_interval: 2.0
```

## Testing Principles

1. **Knowledge Base Persistence**: Test that KB survives restarts
2. **Tool Integration**: Test MCP tool HTTP calls
3. **Briefing Format**: Verify turn briefing clarity
4. **Strategy Behavior**: Test with mock model
5. **Conversation History**: Test summarization triggers

## Extension Points

### Adding New Tools

1. Implement `Tool` interface in `tools/`
2. Add to `tools/registry.py`
3. Update system prompt builder with description
4. Add to tool list in strategy

### Adding New Memory Types

1. Extend `KnowledgeBase` or create new memory class
2. Add tool wrapper if needed
3. Integrate into briefing generator
4. Update strategy to use new memory

### Modifying Turn Briefing

1. Edit `briefing.py` formatting functions
2. Add new sections as needed
3. Update briefing generator to include new info
4. Test with real game state

### Updating System Prompt

1. Edit `prompts/system_prompt.py`
2. Add new warnings/tips as needed
3. Update tool descriptions
4. Test with model to verify clarity

## Notes on Differences from Pokemon

1. **No Visual Screenshots**: Use structured state from DLL instead
2. **Turn-Based**: Loop per turn, not per action
3. **Turn Boundaries**: Clear start/end of turn
4. **Different State**: Cities, units, diplomacy vs. Pokemon party/badges

## Success Criteria

The system is successful if:
- LLM can play effectively with minimal confusion
- Knowledge base maintains useful long-term memory
- Turn briefings provide clear, actionable information
- Tools are easy to use and provide good feedback
- System prompt guides LLM away from common mistakes
- Conversation history supports long games without context overflow

---

**Last Updated**: 2026-01-14
**Version**: 1.0
**Status**: Initial Implementation Complete

