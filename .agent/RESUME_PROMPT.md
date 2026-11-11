Resume the CA Plastics Research Atlas as lead orchestrator (CLAUDE.md role) from the latest
commit on main (S3-INST checkpoint, 2026-11-11; full gate, clean worktree, CI and deploy green).

Session entry only (CLAUDE.md "Session entry"): `git status --short && git log --oneline -15`,
read `.agent/MEMORY.md` in full, read `.agent/HANDOFF.md` (its owner-request tracker rows 1-31
are the live record of this owner's requests), list open TODO lines, and
`git diff HEAD -- .agent/QUESTIONS.md`. Also run `py -3.14 scripts/check_framework_triggers.py`.

First, remind the owner: renew the CORE API key today (2026-11-12) and put the new value in `.env`.
Then ask whether they finished any review in `scripts/review_work_relevance_app.py` (Smart queue)
and confirm the two pending state-agency overrides in `config/institution_overrides.csv`.

Then continue with "Next eligible" in HANDOFF.md, starting with AT-3 (SQL analytics), using workers
per CLAUDE.md (Haiku for bounded tasks; Sonnet for large single-file UI or cross-cutting data work),
sealing each checkpoint (gate, clean-worktree run, narrow commit, push, CI) and updating the
HANDOFF tracker at every checkpoint. Never commit `curation/work_relevance.csv` edits you did not
make, `data/private/`, `docs/SOURCES.md`, `docs/api_notes/source_watch_s7_6.json`, or the owner's
`data/processed/p{5,25,100}.parquet`. Write patch scripts with the Write tool (shell heredocs
corrupt regex escapes here).
