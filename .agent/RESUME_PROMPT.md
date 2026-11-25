You are the lead orchestrator for the Plastiverse Live / CA Plastics Research Atlas repo. Follow CLAUDE.md.
Owner rule: delegate every bounded task to a Haiku worker (`model: haiku`); the lead reviews, gates each commit in a
clean worktree, commits, pushes and edits `.agent/*`. For OpenAlex, the repo's verified facts (MEMORY, docs/api_notes/)
override spec claims (A3-C1).

Resume from the 2026-11-25 handoff (last commit 71df3a28).
1. New machine only: follow CLAUDE.md "Cross-machine handoff" (memory copy + toolchain list).
2. Run the CLAUDE.md "Session entry" steps only. Remind the owner of PLAT3-DATA-PATH, H28, H40, H42, H2.
3. The global backfill is complete (`data/raw/openalex_global/`, partition in `data/processed/global/`); daily top-ups: rerun `scripts/fetch_global_raw.py` (resumes) and `scripts/partition_global.py`. California data lives in `site/data/california/` (docs/DATA_LAYOUT.md).
4. Then PLAT-4 Tier B outputs and the BQ-V.2 acceptance check, then BQ-S9b and BQ-V.1 (read
   `docs/PRIVACY_REVIEW.md` first). Skip `owner:` and "Gated on owner decision" tasks.
Seal each checkpoint per CLAUDE.md (full gate in a clean worktree, .agent updates, narrow commit, push, CI via gh).
