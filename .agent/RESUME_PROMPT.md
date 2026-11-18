You are the lead orchestrator for the Plastiverse Live / CA Plastics Research Atlas repo
(clone root, for example C:\Users\Scott.Coffin\R_new\CA_Plastics_Research_Dash). Follow CLAUDE.md.
Owner rule: delegate every bounded task to a Haiku worker and pass `model: haiku` on every Agent call
(Impeccable agents included); the lead integrates, gates, commits and edits `.agent/*`.

Resume from the 2026-11-18 end-of-session handoff (GA-1..GA-3, PLAT-2d and LOGO-1 are done and live).
1. New machine only: copy `.claude/memory/*` to `~/.claude/projects/<project-slug>/memory/`.
2. Run the CLAUDE.md "Session entry" steps only: git status/log, read .agent/MEMORY.md and .agent/HANDOFF.md,
   list open TODO tasks, check the QUESTIONS diff, remind the owner of the HUMAN_TASKS "Do now" items
   (H34 /explore check, H28 OPC review) and ask for the `/usage` output if they still want those fixes.
3. Work the HANDOFF "In flight / next" list in order, starting with PLAT-2b (live global evidence-map counts;
   cells approved in QUESTIONS PLAT2-EVIDENCE-CELLS; never use paid OpenAlex filters; stay under the
   USD 1/day budget guard).
Seal each checkpoint per CLAUDE.md (full gate, clean-worktree tests, .agent updates, narrow commit, push,
confirm CI and the deploy).
