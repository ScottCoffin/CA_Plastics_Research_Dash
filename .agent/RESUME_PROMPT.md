# Fresh-orchestrator resume prompt

Overwritten whenever overnight mode stops at a human gate (`CLAUDE.md`,
"Overnight mode"). Paste the block below into a new Claude Code session.

```text
Resume the CA Plastics Research Atlas roadmap as lead orchestrator.
Follow CLAUDE.md "Session entry" only (git status/log, .agent/MEMORY.md,
.agent/HANDOFF.md, open TODO lines, `git diff HEAD -- .agent/QUESTIONS.md`).
Resume from checkpoint e414e62 (AT-1 v3 candidate ready). HANDOFF "Owner
actions" lists what I was asked; apply my answers below, then run the matching
"Next eligible" tasks in dependency order. First task if I say "v3 labels done":
compute precision of docs/QUERY_AUDIT_REVIEW_V3.csv and prepare the AT1-V3 /
S1.5-A promotion. Use Haiku workers per CLAUDE.md, seal each checkpoint
(including the clean-worktree check and a CI check after pushing), and
continue in overnight mode.
My answers (if any):
-
```
