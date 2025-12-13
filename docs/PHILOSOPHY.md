# Everything Is an Interaction

> **In good architecture, concepts rule and implementation follows.**

This document explains the central design principle of YAMS: **every meaningful thing that happens in a game is an interaction**.

This is not a metaphor, a convenience, or an implementation trick. It is a **hard architectural constraint**. Once adopted, it eliminates entire categories of special-case systems while making the engine easier to reason about, teach, and extend.

---

## The Core Concept

At the heart of YAMS is a single idea:

```
Interaction = (Entity A, Entity B, Filter, Action)
```

That is the *entire* behavioral vocabulary of the engine.

If something happens in the game, it can always be described as:

* **Two entities**
* **A condition that becomes true**
* **An action that fires when it does**

There are no other ways for behavior to occur.

---

## Why This Exists

Most engines grow by accumulation:

* collisions
* triggers
* callbacks
* timers
* lifecycle hooks
* input handlers
* win/lose conditions

Each starts simple. Over time, they interact, overlap, and contradict each other. The result is accidental complexity: systems that work individually but are hard to compose or explain.

YAMS takes the opposite approach:

> **Instead of adding systems, collapse them.**

When multiple systems describe the same underlying idea, keep the idea and delete the rest.

---

## Interactions Are the API

In YAMS, the real API is not Python or Lua.

The real API is the interaction model.

Everything else — spatial partitioning, collision math, input plumbing, scheduling — exists only to efficiently *execute* interactions. None of it is visible at the conceptual level.

This inversion matters:

* The **model** decides what can happen
* The **engine** merely enforces it

Implementation follows concept, never the reverse.

---

## What Counts as an Interaction?

All of these are interactions:

| Feature     | Entity A  | Entity B  | Filter                          |
| ----------- | --------- | --------- | ------------------------------- |
| Collision   | `ball`    | `brick`   | `distance: 0`                   |
| Click       | `duck`    | `pointer` | `distance: 0`, `b.active: true` |
| Proximity   | `player`  | `enemy`   | `distance: { lt: 100 }`         |
| Screen edge | `ball`    | `screen`  | `edges: [bottom]`               |
| Spawn       | `entity`  | `level`   | `because: enter`                |
| Update      | `entity`  | `level`   | `because: continuous`           |
| Destroy     | `entity`  | `level`   | `because: exit`                 |
| Timer       | `spawner` | `time`    | `elapsed: { gte: 5.0 }`         |

If a feature cannot be expressed this way, it does not belong in the engine.

---

## This Is a Constraint, Not a Convenience

“Everything is an interaction” is powerful *because it forbids alternatives*.

You are not allowed to:

* add callbacks
* add event hooks
* add special lifecycle methods
* add bespoke subsystems

That constraint keeps the engine coherent.

When a new requirement appears, the question is never *"what system do we add?"* — it is always:

> *Which entities are interacting, and under what conditions?*

---

## System Entities: Nothing Special

System concepts are not special cases. They are entities.

| Entity    | Purpose                       |
| --------- | ----------------------------- |
| `pointer` | Input position and activation |
| `screen`  | World bounds                  |
| `level`   | Lifecycle boundary            |
| `game`    | Global game state             |
| `time`    | Elapsed and absolute time     |

They differ only by `source: system` — not by behavior.

This eliminates entire classes of engine-specific logic while keeping the mental model uniform.

---

## Filters Are Declarative Truths

Filters describe *what must be true*, not *how to check it*.

```yaml
when:
  distance: 0
  angle: { between: [45, 135] }
  b.active: true
```

The engine decides how to evaluate this efficiently.

This separation enables:

* optimization without API changes
* profiling without semantic ambiguity
* reasoning about behavior without reading code

Declarative truth scales. Clever logic does not.

---

## Triggers Are Temporal Semantics

The `because:` field explains *why* an action fires in time:

| Mode         | Meaning                   |
| ------------ | ------------------------- |
| `enter`      | Filter just became true   |
| `exit`       | Filter just became false  |
| `continuous` | Filter is true this frame |

There are no one-off flags or special modes. Temporal behavior is explicit and inspectable.

---

## Timers Are Not Special

Timers are simply interactions with the `time` entity.

```yaml
interactions:
  time:
    when:
      elapsed: { gte: 3.0 }
    action: spawn_enemy
```

No scheduler. No callbacks. No hidden state.

Time is just another participant.

---

## Actions Are Subordinate

Actions do not control flow.

They:

* receive context
* mutate state
* optionally transform entities

They do **not** decide *when* they run — interactions do.

This keeps execution logic simple and replaceable while preserving semantic clarity.

---

## Why This Teaches Good Engineering

This architecture encodes professional taste:

* Fewer concepts, deeply understood
* No clever shortcuts
* No invisible behavior
* No privileged code paths

A reader does not just learn *how to use the engine* — they learn:

* how to collapse systems
* how to name ideas precisely
* how to let constraints do the work

---

## The Payoff

When concepts rule:

* the engine stays small
* features compose naturally
* performance optimizations remain invisible
* the system remains explainable years later

YAMS is not trying to be clever.

It is trying to be **obvious** — and obvious systems are the ones that last.

---

## Final Principle

> If a behavior cannot be explained as an interaction,
> it is not part of the engine.

Everything else is implementation detail.
