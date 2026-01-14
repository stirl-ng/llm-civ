# Claude Plays Pokemon: A Visual Guide

```
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│                                                                                             │
│                          CLAUDE PLAYS POKEMON, A VISUAL GUIDE                               │
│                                                                                             │
└─────────────────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│  System prompt is mostly just tips + tricks about tools + a few short reminders about      │
│  things Claude is bad at (i.e. don't trust your vision, use your knowledge base more       │
│  often than you think)                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## About the Knowledge Base

The knowledge base gives Claude access to **long term memory**. It's basically just a Python dictionary, and it is rendered like this:

```xml
<section id="pokemon">
I like pikachu because its cute and I like
how it electrocutes people
</section>
<section id="brock">
Brock stinks and I kicked his ass back
on step 3432
</section>
...
```

---

## The Tools

```
┌──────────────────────────┬──────────────────────────┬──────────────────────────┐
│   update_knowledge_base  │      use_emulator        │        navigator         │
├──────────────────────────┼──────────────────────────┼──────────────────────────┤
│                          │                          │                          │
│ WHAT: Add to, edit, or   │ WHAT: Executes a series  │ WHAT: Finds the path to  │
│ delete content in        │ of button presses +      │ selected coordinates on  │
│ knowledge base           │ optional pauses for      │ screen, and executes     │
│                          │ time to pass             │ button presses to get    │
│ HOW: Claude specifies    │                          │ there. Calls use_emulator│
│ an operation + content   │ HOW: Claude writes an    │ for execution.           │
│                          │ array that looks like    │                          │
│                          │                          │ HOW: Claude specifies    │
│                          │ ['a', 'b', 'start',      │ coordinates in its       │
│                          │  'select']               │ current view, i.e.       │
│                          │                          │ (6, 21)                  │
│           │              │           │              │           │              │
│           ▼              │           ▼              │           ▼              │
│    ┌──────────────┐      │    ┌──────────────┐      │    ┌──────────────┐      │
│    │ Tool Result  │      │    │ Tool Result  │      │    │ Tool Result  │      │
│    └──────────────┘      │    └──────────────┘      │    └──────────────┘      │
│           │              │           │              │           │              │
│           ▼              │           ▼              │     ┌─────┴─────┐        │
│   Acknowledgement        │    Screenshot            │     │           │        │
│                          │                          │     ▼           ▼        │
│                          │                          │  IF FAILED   IF SUCCESS  │
│                          │                          │     │           │        │
│                          │                          │     ▼           ▼        │
│                          │                          │  Return      Success     │
│                          │                          │  helpful     Message +   │
│                          │                          │  error       Result from │
│                          │                          │  message     use_emulator│
└──────────────────────────┴──────────────────────────┴──────────────────────────┘
```

### Screenshot Overlay System

```
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│    ┌─────────────────┐     ┌─────────────────────────────────────┐  │
│    │   Screenshot    │     │  Screenshot + Overlay               │  │
│    │   [Game View]   │ --> │  [Game View with Navigation Grid]   │  │
│    └─────────────────┘     └─────────────────────────────────────┘  │
│                                                                     │
│    This overlay comes from reading the tiles on the screen          │
│    and checking if they are walkable                                │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### State from RAM

```
┌─────────────────────────────────────────────────────────────────────┐
│  This info is all parsed directly from the RAM of the game.         │
│  Claude Code is very good at this task                              │
│                                                                     │
│  Examples of RAM data:                                              │
│  ┌─────────────────────────────────┐                                │
│  │ PLAYER POSITION: (12, 45)       │                                │
│  │ CURRENT MAP: VIRIDIAN_CITY      │                                │
│  │ PARTY POKEMON: 3                │                                │
│  │ BADGES: 2                       │                                │
│  │ MONEY: $4500                    │                                │
│  │ ...                             │                                │
│  └─────────────────────────────────┘                                │
│                                                                     │
│  + Helpful reminders                                                │
└─────────────────────────────────────────────────────────────────────┘
```

---

## The Prompt

```
┌─────────────────────────────────────────┐
│            THE PROMPT                   │
│  ┌───────────────────────────────────┐  │
│  │       Tool Definitions            │  │
│  └───────────────────────────────────┘  │
│                  │                      │
│                  ▼                      │
│  ┌───────────────────────────────────┐  │
│  │        System Prompt              │  │
│  └───────────────────────────────────┘  │
│                  │                      │
│                  ▼                      │
│  ┌───────────────────────────────────┐  │
│  │       Knowledge Base              │  │
│  │  ┌─────────────────────────────┐  │  │
│  │  │ Blurb about how             │  │  │
│  │  │ summaries work              │  │  │
│  │  └─────────────────────────────┘  │  │
│  └───────────────────────────────────┘  │
│                  │                      │
│                  ▼                      │
│  ┌───────────────────────────────────┐  │
│  │     Conversation History          │  │
│  │  ┌─────────────┐                  │  │
│  │  │  Tool Use   │                  │  │
│  │  └─────────────┘                  │  │
│  │         │                         │  │
│  │         ▼                         │  │
│  │  ┌─────────────┐                  │  │
│  │  │ Tool Result │                  │  │
│  │  └─────────────┘                  │  │
│  │         │                         │  │
│  │         ▼                         │  │
│  │  ┌─────────────┐                  │  │
│  │  │  Tool Use   │                  │  │
│  │  └─────────────┘                  │  │
│  │         │                         │  │
│  │         ▼                         │  │
│  │  ┌─────────────┐                  │  │
│  │  │ Tool Result │                  │  │
│  │  └─────────────┘                  │  │
│  └───────────────────────────────────┘  │
└─────────────────────────────────────────┘
```

---

## The Core Loop

```
    ┌──────────────────┐
    │  Compose Prompt  │
    └────────┬─────────┘
             │
             ▼
    ┌──────────────────┐
    │   Call Model     │
    └────────┬─────────┘
             │
             ▼
    ┌──────────────────┐
    │  Resolve Tools   │
    └────────┬─────────┘
             │
             ▼
    ┌──────────────────┐
    │    Check for     │
    │  Summarization   │
    └────────┬─────────┘
             │
             ▼
    ┌──────────────────┐
    │   Save State     │
    └────────┬─────────┘
             │
             └──────────────┐
                            │
                            ▼
                    (loop back to
                     Compose Prompt)
```

---

## Summarization / Managing Long Context

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                                                                 │
│  Rollouts are way too long for the 200k context window, so we need some way     │
│  to manage context. I've found progressive summarization to work well.          │
│                                                                                 │
│  ┌───────────────────────────────────────────────────────────────────────────┐  │
│  │                                                                           │  │
│  │  1. Once conversation history > max_turns                                 │  │
│  │     we trigger a summarization event                                      │  │
│  │                         │                                                 │  │
│  │                         ▼                                                 │  │
│  │  2. This has Claude write a summary of their recent progress /            │  │
│  │     what happened in the last max_turns.                                  │  │
│  │                         │                                                 │  │
│  │                         ▼                                                 │  │
│  │  3. Then we clear the full conversation history and insert the            │  │
│  │     summary as the first assistant message, and Claude resumes            │  │
│  │     its journey                                                           │  │
│  │                         │                                                 │  │
│  │                         ▼                                                 │  │
│  │  4. Finally, another LLM is called to inspect the first LLM's             │  │
│  │     knowledge base and to provide feedback — this helps ensure            │  │
│  │     the agent does more frequent maintenance of its knowledge base.       │  │
│  │                                                                           │  │
│  └───────────────────────────────────────────────────────────────────────────┘  │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## System Architecture Overview

```
                    ┌─────────────────────────────────────────┐
                    │           KNOWLEDGE BASE                │
                    │    (Persistent Long-Term Memory)        │
                    └──────────────────┬──────────────────────┘
                                       │
                                       │ read/write
                                       │
    ┌──────────────────────────────────┼──────────────────────────────────┐
    │                                  │                                  │
    │                                  ▼                                  │
    │  ┌─────────────┐    ┌─────────────────────────┐    ┌────────────┐  │
    │  │   System    │───▶│                         │◀───│ Tool       │  │
    │  │   Prompt    │    │         CLAUDE          │    │ Results    │  │
    │  └─────────────┘    │                         │    └────────────┘  │
    │                     │    (Decision Making)    │          ▲        │
    │  ┌─────────────┐    │                         │          │        │
    │  │Conversation │───▶│                         │──────────┘        │
    │  │  History    │    └─────────────────────────┘   Tool Calls      │
    │  └─────────────┘              │                                   │
    │        ▲                      │                                   │
    │        │                      ▼                                   │
    │        │         ┌───────────────────────────┐                    │
    │        │         │         TOOLS             │                    │
    │        │         ├───────────┬───────────────┤                    │
    │        │         │           │               │                    │
    │        │         ▼           ▼               ▼                    │
    │        │  ┌───────────┐ ┌─────────┐ ┌────────────┐               │
    │        │  │update_    │ │use_     │ │ navigator  │               │
    │        │  │knowledge_ │ │emulator │ │            │               │
    │        │  │base       │ │         │ │            │               │
    │        │  └───────────┘ └────┬────┘ └─────┬──────┘               │
    │        │                     │            │                       │
    │        │                     ▼            │                       │
    │        │              ┌───────────┐       │                       │
    │        │              │  GAME     │◀──────┘                       │
    │        │              │ EMULATOR  │                               │
    │        │              │  (RAM)    │                               │
    │        │              └───────────┘                               │
    │        │                                                          │
    │        └──────────────────────────────────────────────────────────│
    │                     (Summarization Loop)                          │
    │                                                                   │
    └───────────────────────────────────────────────────────────────────┘
```
