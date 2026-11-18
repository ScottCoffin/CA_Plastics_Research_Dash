You are the lead orchestrator for the Plastiverse Live / CA Plastics Research Atlas repo
(clone root, for example C:\Users\Scott.Coffin\R_new\CA_Plastics_Research_Dash). Follow CLAUDE.md.
Owner rule: delegate every bounded task to a Haiku worker and pass `model: haiku` on every Agent call
(Impeccable and reviewer agents included); the lead integrates, gates, commits and edits `.agent/*`.
Owner rule: for OpenAlex, depend on the repo's verified facts (MEMORY "Verified API facts", docs/api_notes/),
not on spec claims (DECISIONS A3-C1).

Resume from the 2026-11-18 (late) handoff: Add-on A3 (`docs/add_on_spec_3.md`, 52 BQ tasks) is integrated.
1. New machine only: copy `.claude/memory/*` to `~/.claude/projects/<project-slug>/memory/`.
2. Run the CLAUDE.md "Session entry" steps only. Remind the owner of the HUMAN_TASKS "Do now" items
   (H34 /explore check, H28 OPC review, H36 A3 answers) and ask for the `/usage` output if they still
   want those fixes.
3. Build the HANDOFF "In flight / next" list in order, one checkpoint per task:
   PLAT-2b first (one parenthesised count query per cell on the throttled path; never split OR lists;
   never paid filters; USD 0.95/day guard), then BQ-0, BQ-S8, BQ-R1, the agent-only BQ tasks listed there,
   VD-SM, PLAT-3, PLAT-4 (= BQ-V.2). For each BQ task read only its TODO line, the A3 section it cites
   (CLAUDE.md reading map) and the A3-C rows it names; tasks tagged `[E]` are lead-implemented with a
   Haiku reviewer; skip `owner:` and "Gated on owner decision" tasks. Quote-check any literature claim
   against the Zotero PDFs listed in `docs/A3_SOURCES.md` (pdf-to-markdown skill into scratch/pdfmd/).
Seal each checkpoint per CLAUDE.md (full gate incl. `scripts/check_a3_scaffold.py`, clean-worktree tests,
.agent updates, narrow commit, push, confirm CI and the deploy).
