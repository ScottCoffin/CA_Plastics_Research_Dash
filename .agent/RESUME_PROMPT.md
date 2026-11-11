Resume the CA Plastics Research Atlas as lead orchestrator (CLAUDE.md role) from the latest commit on main
(session-end handoff after AT-3, AT-4 (+tiers UI), AT-11, AT-10 partial, S2.5 b/c/d partial, S9.5 partial;
2026-11-11; CI and deploy green on e250197).

Session entry only (CLAUDE.md "Session entry"): `git status --short && git log --oneline -15`, read
`.agent/MEMORY.md` in full, read `.agent/HANDOFF.md` (owner-request tracker rows 1-37 are the live record),
list open TODO lines, `git diff HEAD -- .agent/QUESTIONS.md`, and `py -3.14 scripts/check_framework_triggers.py`.

First remind the owner: (1) renew the CORE API key (due 2026-11-12) and put it in `.env`; (2) the 215
low-confidence works in `scripts/review_work_relevance_app.py`; (3) AT2-REVIEW institution types (52 rows);
(4) open questions with defaults in use: AT4-SEARCH, AT11-WINDOW, CA-CARRY-ORCID; (5) review the 44 Wikidata
photos and 10 ORCID profiles (S9.5); (6) cut a GitHub release when a new archived snapshot is wanted (AT-10).

Then continue with "Next eligible" in HANDOFF.md, starting with item 1 (Europe PMC + DataCite DOI match after
the OpenAlex daily reset). Use workers per CLAUDE.md, seal each checkpoint (gate, clean-worktree run, narrow
commit, push, CI) and update the HANDOFF tracker. Never commit `curation/work_relevance.csv` edits you did not
make, `data/private/`, `docs/SOURCES.md`, `docs/api_notes/source_watch_s7_6.json`, or the owner's
`data/processed/p{5,25,100}.parquet`. Never store email addresses from ORCID or other sources. Write patch
scripts with the Write tool (shell heredocs corrupt regex escapes here).
