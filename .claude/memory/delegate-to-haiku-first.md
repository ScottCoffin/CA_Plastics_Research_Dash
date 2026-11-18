---
name: delegate-to-haiku-first
description: Owner wants maximum cost efficiency: every spawned agent runs on Haiku (pass model haiku), including Impeccable reviewer/documenter agents
metadata:
  node_type: memory
  type: feedback
  originSessionId: e3f14e15-6818-4e64-b02a-296e57330e0a
  modified: 2026-11-18T18:00:00.000Z
---

Delegate any task that can be neatly bounded to a Haiku worker (haiku-developer). Use Sonnet or do the work directly only when absolutely necessary (cross-cutting integration, gates, commits, .agent updates).

Every agent the lead spawns gets `model: "haiku"` in the Agent call, including skill-shipped agents (impeccable-finish-reviewer, impeccable-documenter, Explore, general-purpose), unless the owner names another model for that agent.

**Why:** owner said 2026-11-12 "be as cost-efficient as possible"; on 2026-11-18 the owner said "ensure spawned agents are Haiku!" after the GA-1 run spawned the Impeccable finish reviewer and documenter on the default (inherited) model.

**How to apply:** before implementing anything over ~1 small edit, write a one-page Haiku brief (CLAUDE.md worker brief format) instead. Set model haiku on every Agent call; a skill saying "spawn the shipped agent" does not change the model rule. Lead keeps integration, review, full gate, sealing. Related: [[overnight-mode]].
