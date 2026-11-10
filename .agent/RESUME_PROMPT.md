# Fresh-orchestrator resume prompt

Overwritten whenever overnight mode stops at a human gate (`CLAUDE.md`,
"Overnight mode"). Paste the block below into a new Claude Code session.

```text
Resume the CA Plastics Research Atlas roadmap as lead orchestrator.
Follow CLAUDE.md "Session entry" exactly (git status/log, .agent/MEMORY.md,
.agent/HANDOFF.md, open TODO lines, QUESTIONS diff); do not read other
files until a task needs them. Apply my answers in HANDOFF "Owner actions"
if I have added any, then continue in overnight mode ("I am going to sleep")
with the first eligible task named in HANDOFF. Use Haiku workers per
CLAUDE.md for bounded sub-tasks.
```
