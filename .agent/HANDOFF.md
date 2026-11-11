# Handoff - 2026-11-11 (day) - real Experts data live; curation wired; monitoring map interactive

## State
- S2.1-B done: fixed a backfill that would have pulled only 1950 and replaced the table, and
  per-year windows (~3.8 USD); run 43043699471 fetched 1,506 unique v3.1 works (~0.05 USD),
  committed `site/data` and deployed. Live Experts verified (Cowger, Gray, Coffin, Savoca, ...).
- Curation: AT-1 owner labels now feed `curation/overrides_works.csv`
  (`scripts/build_audit_overrides.py`; new `exclude` override removed 62 owner-rejected works).
  1,081 never-labelled works were screened by three Claude Haiku reviewers into
  `curation/work_relevance.csv` (applied to `plastic_related`; owner overrides win).
  Export: 1,424 works, 1,982 experts. Emails in abstracts are redacted.
- S3.6 done on real data: initial payload 442 KB gzip, render median 0.81 s, filter 5.5 ms
  (was 519 ms: author summaries rebuilt per keystroke).
- Monitoring (owner request): zoom/pan/wheel/keyboard map, re-clustering, clickable markers
  with a details panel, legend toggles, and expandable `<details>` sections. Checked in headless Edge.
- Grant review app: `py -3.14 -m streamlit run scripts/review_grant_relevance_app.py`
  (`assist_plastic_related` column keeps the Haiku call).
- Budget: owner rule, up to the free USD 1/day (stop 0.95). UTC 2026-11-11 spend about 0.80.
- Worktree leftovers (not committed on purpose): `docs/SOURCES.md`,
  `docs/api_notes/source_watch_s7_6.json`, owner's `data/processed/p{5,25,100}.parquet`.

## Owner actions (one line each)
1. GRANT-REL: work through the grant review app (76 low-confidence rows first).
2. WORK-REL: spot-check `curation/work_relevance.csv` low-confidence/false rows; should Haiku-false works leave Experts?
3. ABSTRACT-PUB: keep OpenAlex abstracts in public author files (emails redacted) or drop them?
4. EM18-DATES: confirm "18 June 2026" and "1 October 2026" on the DTSC pages.
5. Author splits: 26 duplicate names on Experts (e.g. Andrew B. Gray x3); approve rows in `curation/author_merges.csv`?

## Next eligible
- AT-2 (institution type carry-forward, now computable offline from the v3.1 authorships),
  then AT-3 -> AT-4 -> EM-5.
- S4.2 representative sample (corpus now exists), which unblocks owner gold labelling and so S5.

## Verification
- Full gate passed locally (886 tests); site checks S3.2-S3.5 and S7.5 pass; clean-worktree
  run and CI after push: see SESSION_LOG.

Older handoff entries: `.agent/archive/HANDOFF_history.md`.
