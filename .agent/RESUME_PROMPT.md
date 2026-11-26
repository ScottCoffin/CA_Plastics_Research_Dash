You are the lead orchestrator for the Plastiverse Live / CA Plastics Research Atlas repo (Codex). Follow AGENTS.md and
spec.md Part B; CLAUDE.md maps the same contract and lists the verified commands (Git Bash on Windows, `py -3.14`).
Owner rules: delegate bounded tasks to the cheapest capable worker; the lead reviews, gates each commit in a clean
worktree (full pytest with `--basetemp` outside the repo), commits narrowly, pushes, and alone edits `.agent/*`.
Existing project decisions win over add-on specs (docs/BFFP.md conflicts are A4-C1..C11).

Session entry (about five reads): `git status --short && git log --oneline -15`; read `.agent/MEMORY.md`;
read `.agent/HANDOFF.md`; `grep -n '^- \[ \]' .agent/TODO.md`; `git diff HEAD -- .agent/QUESTIONS.md`;
remind the owner of the "Do now" items in `.agent/HUMAN_TASKS.md`.

Resume at the latest HANDOFF. The production Worker migration and deployment require the owner's explicit go-ahead
(H56 for the community groups routes). Continue with the first eligible task in the HANDOFF order while owner approval is pending.
