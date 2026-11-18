You are the lead orchestrator for the Plastiverse Live / CA Plastics Research Atlas repo
(clone root, for example C:\Users\Scott.Coffin\R_new\CA_Plastics_Research_Dash). Follow CLAUDE.md:
delegate bounded work to Haiku workers; the lead integrates, gates, and commits.

Resume from the 2026-11-17 (late) handoff: the global landing design is approved.
1. If this is a new machine, restore Claude memory first: copy `.claude/memory/*` to
   `~/.claude/projects/<project-slug>/memory/` (CLAUDE.md "Cross-machine handoff").
2. Run the CLAUDE.md "Session entry" steps only: git status/log, read .agent/MEMORY.md and
   .agent/HANDOFF.md, list open TODO tasks, check the QUESTIONS diff, remind the owner of the
   HUMAN_TASKS "Do now" items (H31 key rotation, H30 evidence cells, H29 Buttondown).
3. Read docs/PLAT_2_LANDING_SPEC.md (the build spec) and open the approved prototype
   .impeccable/sketches/spectral_story.html over HTTP (see .impeccable/sketches/src/README.md).
4. Work the HANDOFF "In flight / next" list in order: MAIL-1 fix (and its failing CI test),
   PLAT-1 move to /california, PLAT-2a global data, then PLAT-2 build to the spec with the
   Impeccable skill (direction contract .impeccable/surfaces/framework-src-index-md.md), ending
   with the finish reviewer and documenter.
Seal each checkpoint per CLAUDE.md (full gate, .agent updates, narrow commit, push, confirm CI).
