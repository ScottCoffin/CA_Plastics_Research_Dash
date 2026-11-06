# Handoff - 2026-11-06 - task S2.3 (budget checkpoint)

## Done
- No S2.3 production code, tests, fixtures, outputs, roadmap completion, or
  commit was made. The session stopped before implementation because the
  workflow budget was nearly exhausted.
- Confirmed the S2.3 boundary: a separate deterministic `work_labels` Parquet
  must join normalized works to raw OpenAlex records by `work_id`, preserving
  the S2.2 normalized schema and the owner-reviewed institution registry.
- Confirmed the repository-owned inputs: `config/queries.yml` supplies ordered
  core, qualified, tier-2, and exclusion rules, and `config/taxonomy.yml`
  supplies ordered multi-label domain seeds. The candidate remains
  `owner_supplied_candidate` and unpromoted.

## State of the repo
- S2.2 remains the last completed task (`8fdb15a`, `S2.2: finalize session
  log`). Its earlier acceptance was `py -3.14 scripts/check_s2_2.py`; no S2.3
  acceptance or full-suite rerun was performed in this budget-limited session.
- Pre-existing protected changes remain untouched: `.agent/QUESTIONS.md`,
  `data/processed/institution_review_top100.csv`,
  `data/processed/institutions.parquet`, `docs/institutions_qc.md`, untracked
  `docs/AWARDS_DATA.md`, and untracked `agent_docs/`.
- This handoff is the only modification in this checkpoint and is uncommitted.

## Next task (suggested)
- S2.3: implement provisional deterministic rule-based relevance and
  multi-label domain tagging; do not start S2.4.
- First, inspect the exact Part D Trendspotter reuse row and license only far
  enough to decide whether copying is needed; record either licensed reuse or
  independent local implementation in `docs/REUSE.md`.
- Then add `src/atlas/nlp/` labeling code plus a CLI, <=200-record fixture,
  focused tests, and `scripts/check_s2_3.py`. Assert sorted one-row-per-work
  labels, deterministic reruns, rule ordering, provenance, coverage
  reconciliation, and protected-artifact immutability.
- Finally, run focused checks, `C:\rtools45\usr\bin\make.exe PYTHON=\"py -3.14\" test`,
  Ruff, build/compile, and `git diff --check`; perform B4 in order, commit and
  push only S2.3, then provide a successor prompt that repeats this requirement.

## Gotchas the next agent must know
- Normalize retains topic IDs only; raw OpenAlex is required for topic display
  names and primary-topic names. Missing raw/topic rows must be retained and
  counted, never silently dropped.
- Exclusions must override inclusions; qualified terms require their configured
  context; tier-2 chemicals are distinct from core. Use nullable `confidence`,
  not a calibrated score claim.
- The local taxonomy/query configurations are owner-supplied candidate inputs,
  not validated classifiers. Keep `label_source=rule` and do not promote
  `plastic-v2-candidate`.

## Needs owner input
- None to implement the local provisional rules. Promotion/validation of the
  candidate remains an owner decision outside S2.3.

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
gazetteer, awards notes, S2.1 implementation, and S2.2 normalization. Implement
deterministic rule-based `work_labels` from normalized plus raw OpenAlex works;
preserve the candidate as unpromoted, use nullable uncalibrated confidence,
and visibly count missing raw/topic rows. Run the S2.3 acceptance check and
`make test`, update all B4 records in order, commit and push only S2.3 changes
if configured, and stop before S2.4. End by reporting owner actions and
providing a copy-paste prompt for the next fresh agent that explicitly repeats
this successor-prompt requirement.
