# Handoff — 2026-11-06 — task S1.5

## Done

- Completed S1.5 only; `.agent/TODO.md` now checks off S1.5 and S2.1 was not started.
- Added `src/atlas/query.py` for YAML-driven rendering, complete OpenAlex filter
  encoding, and versioned count-cache validation.
- Added `scripts/smoke/query_s1_5.py`, `scripts/check_s1_5.py`, focused tests,
  and the four-work recall fixture.
- Ran the authenticated count/audit at 2026-11-06T06:44:00Z: 98,118 candidate
  works, 100,335 without exclusions, six requests, 60 credits, USD 0.0060.
- Recorded the bounded title/abstract audit in `docs/query_audit_s1_5.md`:
  20/22 precision sample matches and 4/4 recall anchors.
- Updated `docs/METHODS.md`, `docs/api_notes/openalex.md`, `docs/REUSE.md`, and
  the B4 memory/decision/lesson records. The candidate remains inactive.

## State of the repo

- Acceptance: `py -3.14 scripts/check_s1_5.py` passes.
- Full tests: `C:\rtools45\usr\bin\make.exe PYTHON="py -3.14" test` passes
  (32 tests). Ruff check/format and `git diff --check` pass.
- Re-run the live estimate with `py -3.14 scripts/smoke/query_s1_5.py`;
  ignored outputs are under `data/interim/` and `data/logs/`.
- The working tree also contains pre-existing owner/concurrent changes in
  `.agent/QUESTIONS.md` (G-6), `docs/AWARDS_DATA.md`, the S1.2 review data and
  QC, S1.3 geography assets, and the S1.4 gazetteer. Do not stage those files.

## Next task (suggested)

- S2.1: build the incremental, resumable OpenAlex works ingester. First read
  the required `.agent` files and only Part B, the S2 stage entry, and named
  Part D rows; then design the fixture/high-water-mark contract and run its
  acceptance checks. Do not begin it in this handoff session.

## Gotchas the next agent must know

- `config/queries.yml` is still `status: owner_supplied_candidate`; do not
  silently promote it to active. The owner must review the precision examples
  and approve promotion before downstream ingestion relies on it.
- Count caches are invalid unless both `query_version` and `rendered_query`
  match. The works identifier filter is `openalex_id`, not bare `id`.
- The broad S1.2 `search=plastic` ranking remains review metadata only.
- G-6 and `docs/AWARDS_DATA.md` are owner/concurrent work; preserve them.

## Needs owner input

- Review `docs/query_audit_s1_5.md` and decide whether to promote
  `plastic-v2-candidate` for downstream use; no promotion was made here.
- Continue the separate G-6 State Water Board awards decision documented in
  `docs/AWARDS_DATA.md`.

## Files that are large or unsafe to read whole

- `data/processed/institutions.parquet` → inspect selected columns with
  PyArrow/DuckDB; preserve the owner-reviewed registry.
- `data/processed/gazetteer_ca.sqlite` → inspect with SQLite count queries;
  do not print the database.
- `data/interim/openalex_query_counts.json` and
  `data/interim/s1_5_audit.json` → ignored generated evidence; inspect with
  bounded JSON summaries.
- `spec.md` → read only Part B, the selected stage entry, and named Part D rows.

## Prompt for the next fresh agent

You are a build agent for
`C:\Users\Scott.Coffin\R_new\CA_Plastics_Research_Dash`. Follow Part B of
`spec.md` exactly. Read the required `.agent` files, inspect
`git log --oneline -15` and `git status`, and complete exactly the first
unchecked task, S2.1; do not start S2.2. Read only Part B, the S2 stage entry,
and the Part D source rows named by S2.1. Preserve all pre-existing
owner/concurrent changes, including `.agent/QUESTIONS.md` (G-6),
`docs/AWARDS_DATA.md`, the completed S1.2 institution-review data, the S1.3
geography assets, the completed S1.4 gazetteer, and the S1.5 candidate query
work. Run the S2.1 acceptance check and `make test`, update all B4 records in
order, commit and push only S2.1 changes if configured, and stop before S2.2.
End by reporting owner actions and providing a copy-paste prompt for the next
fresh agent that explicitly repeats this successor-prompt requirement.
