# Handoff - 2026-11-05 - task S1.2

## Done
- Added an idempotent/resumable registry builder in
  `scripts/build_institutions.py` and `src/atlas/ingest/institutions.py`.
- Built `data/processed/institutions.parquet` with 4,637 unique California
  institutions and a complete known-ID join to checksum-verified ROR v2.15.
- Added deterministic `atlas_type` rules, override precedence, authenticated
  OpenAlex usage logging, required-campus supplementation, resumable ROR dump
  downloads, and owner-review preservation across reruns.
- Generated `data/processed/institution_review_top100.csv` and
  `docs/institutions_qc.md`; added `scripts/check_s1_2.py` and unit coverage.
- Machine acceptance passes UC 10/10, CSU 23/23, and major private 11/11.

## State of the repo
- Rebuild with `py -3.14 scripts/build_institutions.py`.
- Machine acceptance passes with `py -3.14 scripts/check_s1_2.py`.
- Owner-gated acceptance intentionally reports `OWNER_REVIEW_PENDING: 0/100`
  with `py -3.14 scripts/check_s1_2.py --require-owner-review`.
- `C:\rtools45\usr\bin\make.exe PYTHON="py -3.14" test` passed all 18
  tests; lint, build, and `git diff --check` also passed.
- S1.2 remains unchecked and S1.3 has not been started.
- The pre-existing owner edits to `.agent/QUESTIONS.md` (G-6) and untracked
  `docs/AWARDS_DATA.md` remain preserved outside the S1.2 commit.

## Next task (suggested)
- Finish S1.2; do not start S1.3 until the required owner review is complete.
- Owner: fill all 100 `owner_atlas_type` and `owner_reviewed_at` cells in
  `data/processed/institution_review_top100.csv`; add notes where useful.
- Agent: transfer corrections into `config/institution_overrides.csv`, rebuild,
  and run both acceptance commands plus `make test`.
- Only after owner-gated acceptance passes: check off S1.2, complete B4, commit,
  and stop. S1.3 belongs to a later fresh session.

## Gotchas the next agent must know
- OpenAlex authentication uses `OPENALEX_API_KEY`; the builder also accepts the
  owner's ignored local alias `OPEN_ALEX_API_KEY`. Never print either value.
- The anonymous OpenAlex budget is IP-shared and was exhausted during this
  session; production pulls need the valid key.
- The broad `search=plastic` count is only a review-priority heuristic. S1.5
  will define the versioned corpus query.
- The review CSV preserves owner columns by OpenAlex ID on rerun. Do not replace
  owner judgments with agent judgments or mark 100 rows reviewed automatically.
- The 23 CSU campus records represent 22 universities after the fall-2026 Cal
  Poly/Cal Maritime integration.

## Needs owner input
- Review all 100 rows in `data/processed/institution_review_top100.csv` and use
  an allowed `atlas_type` plus an ISO date in every row.
- Confirm or revise the 11-institution major-private default set recorded as
  S1.2-A in `.agent/QUESTIONS.md`.
- The separate G-6 owner edits in `.agent/QUESTIONS.md` and
  `docs/AWARDS_DATA.md` were not staged or changed by S1.2.

## Files that are large or unsafe to read whole
- `data/raw/openalex_institutions_ca.jsonl` -> ignored; inspect line counts and
  bounded samples only.
- `data/raw/ror/v2.15-2026-10-20-ror-data.zip` -> ignored; inspect checksum and
  selected records only.
- `data/logs/api_usage.jsonl` -> ignored; aggregate by run ID and never dump
  request URLs if diagnosing credentials.
- `spec.md` -> read only Part B, the selected Part E stage, and named Part D
  rows.

## Prompt for the next fresh agent
You are a build agent for
`C:\Users\Scott.Coffin\R_new\CA_Plastics_Research_Dash`. Follow Part B of
`spec.md` exactly. Read the required `.agent` files, inspect
`git log --oneline -15` and `git status`, and complete exactly the first
unchecked task, S1.2; do not start S1.3. Read only Part B, the S1 stage entry,
and the Part D source rows named by S1.2. Preserve the pre-existing owner
changes to `.agent/QUESTIONS.md` and `docs/AWARDS_DATA.md`. Check whether the
owner has filled all 100 rows of
`data/processed/institution_review_top100.csv`; if not, do not impersonate the
owner and report the remaining owner action. If complete, transfer corrections
to `config/institution_overrides.csv`, rebuild, run
`scripts/check_s1_2.py --require-owner-review` and `make test`, update all B4
records in order, commit/push if configured, and stop before S1.3. End by
reporting owner actions and providing a copy-paste prompt for the next fresh
agent that explicitly repeats this successor-prompt requirement.
