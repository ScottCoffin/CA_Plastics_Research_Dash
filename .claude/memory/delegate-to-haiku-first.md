---
name: delegate-to-haiku-first
description: Owner wants maximum cost efficiency — delegate every neatly bounded task to Haiku; lead/Sonnet only when necessary
metadata:
  node_type: memory
  type: feedback
  originSessionId: e3f14e15-6818-4e64-b02a-296e57330e0a
  modified: 2026-11-12T16:55:22.208Z
---

Delegate any task that can be neatly bounded to a Haiku worker (haiku-developer). Use Sonnet or do the work directly only when absolutely necessary (cross-cutting integration, gates, commits, .agent updates).

**Why:** owner said 2026-11-12 "be as cost-efficient as possible" after a session where the lead implemented pipeline, export and UI changes itself.

**How to apply:** before implementing anything over ~1 small edit, write a one-page Haiku brief (CLAUDE.md worker brief format) instead. Lead keeps integration, review, full gate, sealing. Related: [[overnight-mode]].
