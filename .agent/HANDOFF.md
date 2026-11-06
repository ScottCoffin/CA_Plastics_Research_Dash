# Handoff - 2026-11-05 - task S1.4

## Done
- Verified the official GeoNames U.S. extract and CC BY 4.0 terms with
  `scripts/smoke/geonames.py`; recorded the observed contract in
  `docs/api_notes/geonames.md`, `docs/SOURCES.md`, and `docs/REUSE.md`.
- Added reproducible `scripts/build_gazetteer.py`, which downloads ignored
  `data/raw/geonames_us.zip` and writes the committed
  `data/processed/gazetteer_ca.sqlite` subset. The 2026-11-05 build contains
  127,963 features and 187,760 normalized name variants.
- Added `atlas.geo.gazetteer.lookup()` and `is_blacklisted()`, curated water
  and regional aliases in `config/gazetteer_ca.csv`, and the explicit common
  word exclusion list in `config/gazetteer_blacklist.csv`.
- Added the blacklist rationale, fixture-based unit tests, and
  `scripts/check_s1_4.py`. S1.4 is checked off; S1.5 was not started.

## State of the repo
- Rebuild: `py -3.14 scripts/build_gazetteer.py`.
- Smoke source/license: `py -3.14 scripts/smoke/geonames.py`.
- Acceptance: `py -3.14 scripts/check_s1_4.py`.
- Full suite: `C:\rtools45\usr\bin\make.exe PYTHON="py -3.14" test`
  passes (29 tests). Ruff check/format, compileall, and `git diff --check`
  also pass.
- `lookup()` returns only exact normalized GeoNames/curated matches. The
  blacklist applies first; alias/region centroids are candidates for later
  context-aware classification, not sampling evidence.

## Next task (suggested)
- S1.5: finish the versioned plastics-query configuration and count estimate.
  First read the required agent files and only the S1 task/source rows; then
  inspect the owner-supplied `plastic-v2-candidate` preparation; finally run
  only the required S1.5 smoke/count/precision work and its acceptance checks.

## Gotchas the next agent must know
- GeoNames `US.zip` is an upstream daily snapshot. Raw inputs remain ignored;
  preserve its CC BY 4.0 attribution if publishing derivative lookup data.
- The source may contain alternate spellings that normalize to the same key;
  the builder deduplicates each `(geonames_id, normalized_name)` deterministically.
- Never use a blacklist exclusion or a regional alias centroid as a silent
  final geocode. Later stages must require context or a reviewed override.
- Do not alter the S1.2 review data, S1.3 geography assets, or owner-supplied
  S1.5 preparation while doing unrelated work.

## Needs owner input
- No new owner action is required for S1.4.
- G-6 and `docs/AWARDS_DATA.md` remain owner/concurrent work outside this task.

## Files that are large or unsafe to read whole
- `data/processed/gazetteer_ca.sqlite` (about 30 MB) -> inspect with SQLite:
  `py -3.14 -c "import sqlite3; c=sqlite3.connect('data/processed/gazetteer_ca.sqlite'); print(c.execute('select count(*) from feature').fetchone())"`.
- `data/raw/geonames_us.zip` is ignored -> rebuild through
  `scripts/build_gazetteer.py`, not by printing its records.
- `spec.md` -> read only Part B, the selected Part E stage, and named Part D
  source rows.

## Prompt for the next fresh agent
You are a build agent for
`C:\Users\Scott.Coffin\R_new\CA_Plastics_Research_Dash`. Follow Part B of
`spec.md` exactly. Read the required `.agent` files, inspect
`git log --oneline -15` and `git status`, and complete exactly the first
unchecked task, S1.5; do not start S2.1. Read only Part B, the S1 stage entry,
and the Part D source rows named by S1.5. Preserve all pre-existing
owner/concurrent changes, including `.agent/QUESTIONS.md` (G-6),
`docs/AWARDS_DATA.md`, the completed S1.2 institution-review data, the S1.3
geography assets, and the completed S1.4 gazetteer. Treat the owner-supplied
`plastic-v2-candidate` material in `config/queries.yml`, `config/taxonomy.yml`,
and `docs/query_design_v2.md` as S1.5 input: verify and complete only the S1.5
requirements, with no unrelated query redesign. Run the S1.5 acceptance check
and `make test`, update all B4 records in order, commit and push only S1.5
changes if configured, and stop before S2.1. End by reporting owner actions
and providing a copy-paste prompt for the next fresh agent that explicitly
repeats this successor-prompt requirement.
