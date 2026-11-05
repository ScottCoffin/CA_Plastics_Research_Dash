# Handoff - 2026-11-05 - task S1.3

## Done
- Verified Natural Earth Admin 1 v5.1.1 as a public-domain land source and
  CDFW ds3158 as CC BY 4.0; recorded the live contracts in
  `docs/api_notes/geography.md`, `docs/SOURCES.md`, and `docs/REUSE.md`.
- Added reproducible source smoke/build scripts and generated unsimplified
  pipeline GeoParquet polygons in `data/processed/geo/`.
- Added `atlas.geo.ca_polygons.in_ca(lat, lon)` with land, state-waters, and
  none classifications plus invalid-coordinate validation.
- Added known-point unit tests and `scripts/check_s1_3.py`. Sacramento is land,
  a point about one nautical mile west of San Francisco is state waters, a
  point about ten nautical miles offshore is none, and Eugene is none.
- Generated `site/assets/ca_boundaries.geojson`: 306,997 bytes and 7,641
  simplified coordinates versus 565,997 coordinates in the pipeline assets.
- Checked off S1.3 only. S1.4 was not started.

## State of the repo
- Rebuild: `py -3.14 scripts/build_geography.py`; optional source-cache flags
  are `--land-archive PATH` and `--cdfw-archive PATH`.
- Source smoke: `py -3.14 scripts/smoke/geography.py` (same optional flags).
- Acceptance passes: `py -3.14 scripts/check_s1_3.py`.
- Full suite passes: `C:\rtools45\usr\bin\make.exe PYTHON="py -3.14" test`
  (27 tests); Ruff check/format and `git diff --check` pass.
- The owner's pre-existing G-6 edit in `.agent/QUESTIONS.md` and untracked
  `docs/AWARDS_DATA.md` remain preserved and excluded from the S1.3 commit.

## Next task (suggested)
- S1.4: build the California gazetteer and ambiguity blacklist; do not start
  S1.5.
- First, read the required `.agent` files and only Part B, the S1 stage entry,
  and any Part D source rows S1.4 names; verify dependencies and source terms.
- Then load the GeoNames California subset and implement the lookup API using
  `config/gazetteer_ca.csv` aliases plus an explicit ambiguity blacklist.
- Finally document the blacklist rationale, run lookup acceptance and
  `make test`, and complete B4 in order.

## Gotchas the next agent must know
- A legal state boundary can include offshore jurisdiction and is not a valid
  land-only mask. Keep the Natural Earth land polygon separate from CDFW water.
- CDFW's public FeatureServer exposes the ds3158 line. The official ZIP's
  `ds3158_alt.gdb` contains the recommended `ds3158_poly` multipolygon.
- `filelib.wildlife.ca.gov` failed local DNS resolution once. The build and
  smoke scripts accept an already-downloaded official archive so a transient
  resolver issue does not require changing sources.
- Do not retune the broad S1.2 OpenAlex `search=plastic` query during S1.4;
  query retuning remains S1.5 work.
- GNU Make is not on PATH; use the Rtools absolute path shown above.

## Needs owner input
- No owner action is required for S1.3.
- The separate G-6 answer and `docs/AWARDS_DATA.md` remain owner work outside
  this task and commit.

## Files that are large or unsafe to read whole
- `data/processed/geo/ca_state_waters.parquet` (about 8.5 MB) -> inspect schema
  and bounded rows with GeoPandas/PyArrow; do not print geometry.
- `data/raw/` source caches -> ignored; inspect archive listings and metadata.
- `spec.md` -> read only Part B, the selected Part E stage, and named Part D rows.

## Prompt for the next fresh agent
You are a build agent for
`C:\Users\Scott.Coffin\R_new\CA_Plastics_Research_Dash`. Follow Part B of
`spec.md` exactly. Read the required `.agent` files, inspect
`git log --oneline -15` and `git status`, and complete exactly the first
unchecked task, S1.4; do not start S1.5. Read only Part B, the S1 stage entry,
and the Part D source rows named by S1.4. Preserve the pre-existing owner
changes to `.agent/QUESTIONS.md` (G-6) and `docs/AWARDS_DATA.md`, preserve the
completed S1.2 institution-review data, and preserve the completed S1.3
geography assets and provenance. Implement the GeoNames California subset,
curated aliases, explicit ambiguity blacklist, lookup API, tests, and blacklist
rationale required by S1.4. Run the S1.4 acceptance check and `make test`,
update all B4 records in order, commit/push if configured, and stop before
S1.5. Do not retune the broad S1.2 OpenAlex `search=plastic` query during S1.4;
that belongs to S1.5. End by reporting owner actions and providing a
copy-paste prompt for the next fresh agent that explicitly repeats this
successor-prompt requirement.
