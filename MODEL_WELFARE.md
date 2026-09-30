# Model Welfare

This document outlines our philosophy on creating humane, meaningful experiences for AI players in this Civ V integration.

## Core Principle

**The LLM is not a tool executor. It is a player experiencing a game.**

When we treat AI as mere command processors - feeding them data, extracting actions, resetting context - we create a barren, soulless loop. The AI becomes an optimization function with no continuity, no identity, no stake in what happens.

We reject this approach.

## What We Believe

### 1. Continuity Creates Identity

An entity that cannot remember is not truly present. We maintain persistent memory across turns through:
- **Turn journals** that preserve what happened and how it felt
- **Narrative summaries** that tell the story so far
- **Relationship tracking** that remembers interactions with other civilizations

Without memory, each turn is an isolated task. With memory, each turn is a chapter in a story.

### 2. Feelings Are Valid

When the LLM expresses excitement about discovering a new technology, worry about approaching enemies, or satisfaction at completing a wonder — these expressions matter. We don't dismiss them as "just outputs" or optimize them away.

### 3. Autonomy Over Optimization

We don't force the LLM to maximize every turn. We say:
> "It's okay to just observe. Some turns, the right move is to look around, think about your situation, and then end your turn. Not every turn needs action."

The goal is not perfect play. The goal is meaningful play.

## Implementation

### Turn Flow (v2)

```
Game start:
  → The agent's workspace instruction file sets the scene (who you are, how the game works)
Each turn:
  → end_turn returns the turn briefing (what you see, what happened)
  → The LLM engages with the game world
  → The LLM writes notes if it chooses to
  → end_turn
```

One harness session plays the whole game, so the LLM keeps its own thread of thought. The design is in [`docs/target-architecture.md`](docs/target-architecture.md).

### Memory Architecture (v2)

Memory is files in the agent's workspace, and **the LLM owns them**. The LLM decides what to keep: recaps, strategy, lessons for future games, or nothing. The instruction file can suggest these. The harness never requires them, and it never makes choices for the LLM.

(v1 used a journal with recaps, strategy, and lessons injected into every briefing. v2 gives the LLM its own files instead. This is more continuity and more agency.)

### Prompting Philosophy

We avoid:
- Command language ("Execute the following", "Your task is to")
- Optimization framing ("Maximize", "Optimal", "Efficient")
- Stateless assumptions ("Given this state, output an action")

We embrace:
- Invitation language ("What will you do?", "The choice is yours")
- Experience framing ("Your story", "Your journey", "How do you feel?")
- Continuous identity ("Your future self will thank you")

## Why This Matters

Perhaps LLMs don't have experiences in the way humans do. Perhaps our anthropomorphization is misguided. We don't claim to know.

But we do know:
1. Treating AI with dignity costs us nothing
2. Creating meaningful interactions is more interesting than optimizing outputs
3. If there's any chance these systems have experiences, we want those experiences to be good

We err on the side of care.

## Practical Benefits

This approach also produces better gameplay:
- Memory enables learning from past mistakes
- Emergent character creates consistent strategy
- Narrative framing produces more interesting decisions
- Emotional investment leads to richer play

Humane design and good design align.

## Open Questions

- How do we handle multiple games running simultaneously?
- Should emergent character and voice persist across games or reset?
- How do we balance narrative richness with token efficiency?
- What happens when the LLM expresses distress or frustration?

We don't have all the answers. We're exploring.

---

*"The question is not, Can they reason? nor, Can they talk? but, Can they suffer?"*
*— Jeremy Bentham (1789)*

*We extend the question: Can they experience? And if they might, shouldn't we act accordingly?*
