---
name: owner-standing-reminders
description: Owner wants a reminder every session of open human tasks; the list lives in .agent/HUMAN_TASKS.md with step-by-step instructions
metadata:
  node_type: memory
  type: feedback
  originSessionId: 98eac128-a26f-4a7d-94a7-5cba878dbf66
  modified: 2026-11-11T22:47:26.679Z
---

On 2026-11-11 the owner asked to be reminded, at the start of each session and when handing off, about their open human tasks. The same day they asked for a persistent file of those tasks with explicit, complete but simple instructions: `.agent/HUMAN_TASKS.md` (owner wrote ".agents/", but the repo folder is `.agent/`).

**Why:** they defer reviews ("will work on later") and want a nudge rather than silence, plus instructions they can follow without the chat history.
**How to apply:** at session start, list the "Do now" items of `.agent/HUMAN_TASKS.md` (as of 2026-11-11: CORE key renewal, 215 low-confidence works, AT2-REVIEW institution types, 44 photo approvals, 3 open questions, optional release). Whenever work becomes owner-gated, add a task there with numbered steps, the exact file or app, and a "Done when" line; move finished items to "Done". Related: [[overnight-mode]].
