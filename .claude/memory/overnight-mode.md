---
name: overnight-mode
description: "When the owner says \"I am going to sleep\", run the repo's overnight mode (CLAUDE.md) and hand off with a fresh-orchestrator prompt"
metadata:
  node_type: memory
  type: feedback
  originSessionId: 4588fb1b-94a5-45a3-ad59-858dde15d3f6
  modified: 2026-11-10T05:49:30.777Z
---

"I am going to sleep" triggers the overnight mode stored in the repo CLAUDE.md: work continuously through eligible tasks, skip human-gated ones, and seal every checkpoint. At a human gate, overwrite `.agent/HANDOFF.md` (with one-line owner actions) and `.agent/RESUME_PROMPT.md`, then end with both.

**Why:** On 2026-11-09 the owner noted they won't reply within the 60-minute prompt-cache window, so restarting a fresh orchestrator from a short prompt is cheaper than resuming a stale session.

**How to apply:** Follow CLAUDE.md "Overnight mode". Keep the resume prompt to Session-entry reads only. Related: [[pdf-to-markdown-in-atlas-repo]].
