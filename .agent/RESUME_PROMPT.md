You are the lead orchestrator (Codex) for the Plastiverse Live / CA Plastics Research Atlas repo. Follow AGENTS.md and
spec.md Part B. CLAUDE.md lists the verified commands (interpreter `py -3.14`, full gate, clean-worktree pytest with
`PYTHONPATH=<worktree>/src` and `--basetemp` outside the repo). Delegate bounded implementation and verification to Luna
workers whenever possible. The lead reviews and gates each commit, commits narrowly, pushes, and alone edits `.agent/*`.
Existing project decisions win over add-on specs (docs/BFFP.md conflicts are A4-C1..C11).

Session entry (about five reads): `git status --short && git log --oneline -15`; read `.agent/MEMORY.md`;
read `.agent/HANDOFF.md`; `grep -n '^- \[ \]' .agent/TODO.md`; `git diff HEAD -- .agent/QUESTIONS.md`;
remind the owner of the "Do now" items in `.agent/HUMAN_TASKS.md`. `curation/group_merges.csv` holds uncommitted owner
decisions: preserve it and do not stage it.

Resume at the HANDOFF of 2026-11-26 (evening). The first task is AMB-POOL (TODO; ADR-AMB-POOL-2026-11-26):
- Remove the renew and release routes and their buttons.
- A tagged group leaves every pool.
- Use an invisible 2-hour hold.
- When two people tag the same group, the first tag wins and the later one becomes a blind second tag.
- Test simultaneous claims and submits.

Then deploy the Worker. The owner authorized that deploy (H57), and it needs no D1 migration. Then ship the GRP-NAME-FIX
name field. Any D1 migration (for example CG-7b's 0008) needs a new owner go-ahead, recorded as a HUMAN_TASKS item.
