# Fresh-orchestrator resume prompt

Overwritten whenever overnight mode stops at a human gate (`CLAUDE.md`,
"Overnight mode"). Paste the block below into a new Claude Code session.

```text
Resume the CA Plastics Research Atlas roadmap as lead orchestrator.
Follow CLAUDE.md "Session entry" only (git status/log, .agent/MEMORY.md,
.agent/HANDOFF.md, open TODO lines, `git diff HEAD -- .agent/QUESTIONS.md`).
HANDOFF "Owner actions" lists what I was asked; apply any answers I have
added to QUESTIONS.md or written below, then run the matching
"Next eligible once answered" tasks in dependency order. Use Haiku workers
per CLAUDE.md, seal each checkpoint (including the clean-worktree check
and a CI check after pushing), and continue in overnight mode.
My answers (if any):
-
```
