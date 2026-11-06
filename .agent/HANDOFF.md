# Handoff - 2026-11-06 - task S2.2

## Done
- Completed S2.2 only; `.agent/TODO.md` checks off S2.2 and S2.3 was not
  started.
- Added `src/atlas/ingest/normalize.py` and
  `scripts/normalize_openalex.py` for C3-shaped works, authorships, authors,
  and separate normalized institution outputs.
- Added resolved-registry `ca_led` and `ca_any_author` flags, unresolved-link
  retention, `docs/normalization_qc.md`, `scripts/check_s2_2.py`, the S2.2
  fixture, and focused tests.
- Added `make qc`; it uses the ignored live raw table when present and the
  committed fixture as a safe development fallback when it is absent.
- Updated B4 records in order through TODO, MEMORY, DECISIONS, LESSONS, the
  reuse registry, this handoff, and the session log. No new owner question or
  external API note was needed.

## State of the repo
- Acceptance: `py -3.14 scripts/check_s2_2.py` passes.
- QC: `C:\rtools45\usr\bin\make.exe PYTHON="py -3.14" qc` passes and writes
  `docs/normalization_qc.md` plus ignored generated tables under
  `data/processed/normalized/`.
- Full tests: `C:\rtools45\usr\bin\make.exe PYTHON="py -3.14" test` passes
  (37 tests).
- Ruff lint/format and `git diff --check` pass.
- Pre-existing owner/concurrent changes remain untouched, including the
  reviewed institution data, `.agent/QUESTIONS.md`, `docs/institutions_qc.md`,
  `docs/AWARDS_DATA.md`, and the untracked `agent_docs/` directory observed
  during this session.

## Next task (suggested)
- S2.3: populate provisional rule-based relevance and domain tags from
  OpenAlex topics and configured facets. First read the required `.agent`
  files and only the S2.3 sections of `spec.md`; then inspect the normalized
  output contract and taxonomy before implementing the next task.

## Gotchas the next agent must know
- Do not overwrite `data/processed/institutions.parquet`; it is the
  owner-reviewed registry. S2.2 normalized institutions are separate.
- Affiliation text is only a QC warning for unresolved California-like rows;
  it does not set either CA flag without a resolved registry institution.
- The candidate S1.5 query remains owner-supplied and unpromoted; live S2.1
  ingestion still needs `--allow-candidate`.
- Do not begin S2.4 or any later task in the next session.

## Needs owner input
- None required for S2.2. The owner may review the unresolved-affiliation QC
  count before relying on the CA flags for downstream public views.

## Files that are large or unsafe to read whole
- `data/processed/institutions.parquet` -> inspect selected columns with
  PyArrow/DuckDB; preserve the owner-reviewed registry.
- `data/raw/openalex_works/` -> inspect bounded snapshot metadata only; raw
  responses are ignored and may become large.
- `data/interim/works_raw.parquet` -> inspect schema and bounded rows with
  PyArrow/DuckDB; do not load the full corpus into context.

## Prompt for the next fresh agent

You are a build agent for
`C:\Users\Scott.Coffin\R_new\CA_Plastics_Research_Dash`. Follow Part B of
`spec.md` exactly. Read the required `.agent` files, inspect
`git log --oneline -15` and `git status`, and complete exactly the first
unchecked task, S2.3; do not start S2.4. Preserve all pre-existing
owner/concurrent changes, including the reviewed institution data, geography,
gazetteer, awards notes, S2.1 implementation, and S2.2 normalization. Run the
S2.3 acceptance check and `make test`, update all B4 records in order, commit
and push only S2.3 changes if configured, and stop before S2.4. End by
reporting owner actions and providing a copy-paste prompt for the next fresh
agent that explicitly repeats this successor-prompt requirement.
