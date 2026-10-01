# Prompt Design Notes

Extracted and preserved from earlier design work. Use this when iterating on the system prompt and turn briefing. The specific tools and file references are outdated — the design principles are not.

> **v2 changes** (see [`target-architecture.md`](target-architecture.md)): the system prompt becomes the agent workspace instruction file. The turn briefing becomes the view that `end_turn` returns. Memory becomes files in the agent workspace that the agent reads and writes itself, so the Game Server does not inject recaps, strategy, or lessons. The instruction text can only *influence* the LLM. Nothing is mandatory, and the harness makes no choices for it.

---

## What the LLM Wants in the Turn Briefing

**Always present (low token cost, high value):**
- Current turn number
- Civ name and leader identity
- Brief status: cities, current research, gold, happiness
- Notifications since last turn (events that happened while other civs played)
- Pending decisions (tech choice, production needed, etc.)
- (v1 only: last recaps, current strategy, top lessons. In v2 the agent keeps these in its own workspace files.)

**Available on demand via tools (do NOT dump in briefing):**
- Detailed unit positions and status
- City details (production, population, buildings)
- Full tech tree and research progress
- Diplomacy status
- Map information
- Victory progress breakdown

**What the LLM does NOT want:**
- Full game state dumps — too much cognitive load
- Every unit's position listed out
- Complete diplomatic history
- Raw JSON dumps without framing

---

## Turn Briefing Format Principle

Present state like RAM data — clear, structured, scannable. Not prose. Not a story. A concise header block followed by an invitation to act.

Rough structure:
```
TURN [N]

STATUS:
  Civ / Leader / Cities / Gold / Happiness / Research

RECENT EVENTS:
  (last 2-3 notable events with turn numbers)

PENDING:
  (decisions that need to be made this turn)

REMINDERS:
  (1-2 relevant lessons or strategic notes)

---
What will you do?
```

---

## Design Maxims

These should inform both system prompt content and briefing structure:

1. **Progressive Disclosure** — Start broad, drill down via tools when needed
2. **Explicit over implicit** — Explain game mechanics and conventions; don't assume the LLM knows them. Give information, not orders.
3. **Feedback loops** — Every action should have clear, immediate feedback
4. **State caching** — Don't re-query unchanged data within a turn
5. **Error clarity** — Clear error messages, not cryptic failures
6. **Turn boundaries** — Make it unambiguous when a turn starts and ends
7. **Memory persistence** — Lessons and strategy survive across turns and games
8. **Tool simplicity** — One tool, one purpose

---

## What the LLM Should NOT Do (Warn Explicitly in System Prompt)

- Assume game state — query if unsure
- End turn without checking for pending decisions (tech, production)
- Ignore notifications and events
- Move units without a specific destination and reason
- Re-query the same state repeatedly within a turn
- Forget important events — write them down in its notes

---

## Memory and Context (v2)

- **Memory**: files in the agent workspace that the agent owns (notes, strategy, lessons, whatever it chooses). The instruction file can suggest what to keep. Nothing is required.
- **Context**: one long harness session per game. The harness does its own compaction. The agent's files are what survive compaction.
- v1 had a journal with recaps, strategy, and lessons injected into every briefing, plus a planned forced lesson review. v2 removes both (see D9 and D11 in `target-architecture.md`).

---

## Notes on Differences from Claude Plays Pokemon

- **No visual screenshots** — use structured state from DLL instead
- **Turn-based** — loop per turn, not per frame/action
- **Clear turn boundaries** — explicit start/end vs. continuous action stream
- **Different state** — cities/units/diplomacy vs. party/badges/map
- **Longer horizon** — 500 turns vs. one playthrough; compression matters more
