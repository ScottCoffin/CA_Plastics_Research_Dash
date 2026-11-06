# Handoff - 2026-11-06 - task S2.3

## Done
- Implemented deterministic S2.3 labeling in `src/atlas/nlp/labels.py`.
- Added `scripts/label_works.py` and `scripts/check_s2_3.py`.
- Added the <=200-work fixture `tests/fixtures/s2_3_openalex_works.json` and
  focused tests in `tests/test_labels.py`.
- Labels are one sorted row per normalized work, written to a separate
  `work_labels.parquet` output. Rules apply exclusions first, then core,
  qualified-context, and tier-2 terms from `config/queries.yml`.
- Raw OpenAlex topics are joined by `work_id` for display names; missing raw
  works and missing topic entries are retained and counted in the QC report.
- Domain and matrix facets are provisional, local, and deterministic. The
  owner-supplied `plastic-v2-candidate` remains unpromoted; labels use
  `label_source=rule`, nullable `confidence`, and
  `plastic-v2-candidate-rule-v1`.
- Documented the independent implementation and MIT Trendspotter inspection
  in `docs/REUSE.md` and `docs/api_notes/labels.md`.
- Updated B4 records in order: `.agent/TODO.md`, `.agent/MEMORY.md`,
  `.agent/DECISIONS.md`, `.agent/LESSONS.md`, `.agent/QUESTIONS.md`,
  `docs/api_notes/labels.md`, and `docs/REUSE.md`.

## State of the repo
- Focused acceptance: `py -3.14 scripts/check_s2_3.py` passes.
- Full suite: `C:\rtools45\usr\bin\make.exe PYTHON="py -3.14" test` passes
  (40 tests).
- Ruff check/format, `make build`, and `git diff --check` pass.
- No S2.4 workflow, schedule, commit guard, or rate-limit work was started.
- Candidate promotion and later validation remain owner decisions; no owner
  action is required to use this local provisional layer.

## Next task (suggested)
- S2.4: add the daily works workflow with guarded output commits and resumable
  rate-limit handling. First inspect the workflow conventions, then implement
  only S2.4, run its simulated 429 acceptance, and provide the next successor
  prompt.

## Gotchas the next agent must know
- Do not infer CA sampling from author affiliations; S2.3 leaves
  `ca_sampled=unclear` for the later classifier stage.
- Normalized works retain topic IDs only; raw OpenAlex JSON is needed for topic
  display names. Never drop a work because its raw/topic join is missing.
- The configured query and taxonomy are owner-supplied candidate inputs, not a
  validated classifier. Do not promote `plastic-v2-candidate` automatically.
- Trendspotter is MIT-licensed, but no external code was copied; preserve the
  independent local implementation unless a later task explicitly changes it.

## Needs owner input
- None for S2.3. Promotion/validation remains an owner-gated later decision.

## Files that are large or unsafe to read whole
- `data/processed/institutions.parquet` -> inspect selected columns with
  PyArrow/DuckDB; preserve the owner-reviewed registry.
- `data/raw/openalex_works/` -> inspect bounded snapshot metadata only.
- `data/interim/works_raw.parquet` -> inspect schema and bounded rows with
  PyArrow/DuckDB; do not load the full corpus into context.

## Prompt for the next fresh agent

Continue exactly S2.4 from `.agent/HANDOFF.md`; preserve existing dirty files,
do not revisit or modify completed S2.3, and provide a copy-paste successor
prompt in your final handoff. Use the lowest-cost available worker model and
do not use any Sol models.
