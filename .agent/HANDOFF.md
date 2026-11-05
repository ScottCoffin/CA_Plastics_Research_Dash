# Handoff — 2026-11-05 — task S1.1

## Done
- Added bounded live OpenAlex and ROR checks in `scripts/smoke/openalex.py`
  and `scripts/smoke/ror.py`.
- Added the secret-redacting request/run cost logger in
  `src/atlas/util/cost.py` and focused tests in `tests/test_cost.py`.
- Documented exact filters, batch and URL limits, observed costs, pagination,
  response shapes, rate behavior, and licenses in `docs/api_notes/openalex.md`
  and `docs/api_notes/ror.md`.
- Recorded the verified retrieval contract in agent memory and ADR-003.

## State of the repo
- Run local checks with `C:\rtools45\usr\bin\make.exe PYTHON="py -3.14" test`.
- After editable install, run live checks with
  `python scripts/smoke/openalex.py` and `python scripts/smoke/ror.py`.
- S1.1 acceptance passed live on 2026-11-05; `make test` passed all 4 tests,
  Ruff passed, and `git diff --check` passed.
- The owner changes to `.agent/QUESTIONS.md` and `docs/AWARDS_DATA.md` predated
  S1.1 and were preserved outside this task's staged changes.

## Next task (suggested)
- S1.2: build the California institution registry, join ROR, derive
  `atlas_type`, and generate the institution QC/review artifacts.
- First read Part B, the S1 stage entry, and only the Part D source rows named
  by S1.2; then inspect the S1.1 API notes and reusable smoke/logger code.
- Implement the registry pull and ROR join using the verified filters, 100-ID
  batches, pagination, and usage accounting contracts.
- Generate the Parquet/QC outputs and the owner-review CSV, then run the S1.2
  acceptance check and `make test` without starting S1.3.

## Gotchas the next agent must know
- OpenAlex requires exact `geo.region:California`; the canonical works filter
  is `institutions.id`, with no more than 100 OR values per request.
- Basic OpenAlex paging stops at 10,000 results. Cursor continuation after its
  first page requires `OPENALEX_API_KEY`.
- ROR California records use `country_code=US` and subdivision code `CA`, not
  `US-CA`; list/search pages contain 20 records and cap at 10,000 results.
- ROR warns that exhaustive API paging can omit or duplicate records as the
  registry changes; use known-ID enrichment or the versioned dump as ADR-003
  directs.
- GNU Make is not on PATH; use the absolute Rtools executable shown above.

## Needs owner input
- S1.2 requires owner review of the generated top-100 plastic-work institution
  CSV after the agent produces it. No owner action remains for S1.1.
- G-6 remains open for the later S8.8 task; the owner's uncommitted
  `docs/AWARDS_DATA.md` note was not changed or staged.

## Files that are large or unsafe to read whole
- `spec.md` (~80 KB) → read only Part B, the selected Part E stage entry, and
  the named Part D source rows.
- Future `data/raw/`, `data/interim/`, and API logs → inspect schemas, counts,
  and bounded samples; do not load or commit them whole.

## Prompt for the next fresh agent
You are a build agent for `C:\Users\Scott.Coffin\R_new\CA_Plastics_Research_Dash`.
Follow Part B of `spec.md` exactly. Read the required `.agent` files, inspect
`git log --oneline -15` and `git status`, and complete exactly the first
unchecked task, S1.2. Read only Part B, the S1 stage entry, and the Part D
source rows named by S1.2. Preserve the pre-existing owner changes to
`.agent/QUESTIONS.md` and `docs/AWARDS_DATA.md`. Use the verified S1.1 API
notes and cost logger, run the S1.2 acceptance check and `make test`, update all
B4 records in order, commit/push if configured, and stop without starting
S1.3. End by reporting owner actions and providing a copy-paste prompt for the
next fresh agent that explicitly repeats this successor-prompt requirement.
