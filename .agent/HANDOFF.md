# Handoff - 2026-11-05 - task S1.2

## Done
- Accepted the completed 100/100 owner review in
  `data/processed/institution_review_top100.csv`.
- Transferred 22 owner type corrections to
  `config/institution_overrides.csv`, rebuilt all S1.2 outputs, and confirmed
  that every review row's proposed type now matches the owner type.
- Rebuilt `data/processed/institutions.parquet` with 4,637 institutions and
  4,637/4,637 ROR joins; refreshed `docs/institutions_qc.md`.
- Documented the owner's inference that broad OpenAlex `search=plastic` counts
  include non-pollution senses and must not feed a public leaderboard pending
  S1.5 query/topic retuning. The executable query is in
  `src/atlas/ingest/institutions.py` (`plastic_work_counts`, lines 467-528).
- Checked off S1.2 only. S1.3 was not started.

## State of the repo
- Rebuild: `py -3.14 scripts/build_institutions.py`.
- Acceptance passes: `py -3.14 scripts/check_s1_2.py --require-owner-review`.
- Full suite passes: `C:\rtools45\usr\bin\make.exe PYTHON="py -3.14" test`
  (18 tests); lint and `git diff --check` also pass.
- The owner's pre-existing G-6 change in `.agent/QUESTIONS.md` and untracked
  `docs/AWARDS_DATA.md` are preserved and excluded from the S1.2 commit.

## Next task (suggested)
- S1.3: build California land and 3-nm state-waters geography assets; do not
  start S1.4.
- First, read the required `.agent` files and only Part B, the S1 stage entry,
  and Part D source rows named by S1.3; verify dependencies and source license.
- Then implement the polygon loader and `in_ca` contract with known-point tests.
- Finally verify the simplified browser asset is under 1 MB, run S1.3
  acceptance plus `make test`, and complete B4 in order.

## Gotchas the next agent must know
- The institution review ranking is literal OpenAlex `search=plastic`, not a
  pollution corpus query. Hospitals, biomedical institutes, physics units, and
  technology companies indicate likely plasticity, plastic-surgery, and
  deformation matches. This is an owner inference from institution types; the
  underlying works were not reviewed.
- Query retuning belongs to S1.5 or a separately authorized external agent.
  Do not silently use the broad S1.2 counts in a dashboard leaderboard.
- A generated review CSV contains durable owner state. Preserve owner columns
  by OpenAlex ID on every rebuild.
- GNU Make is not on PATH; use the Rtools absolute path shown above.

## Needs owner input
- No owner action remains for S1.2.
- Before a downstream leaderboard uses institution counts, have the external
  query agent retune or topic-restrict `plastic_work_counts` and validate it
  against sampled works. Track that work under S1.5, not S1.3.
- The separate G-6 answer and `docs/AWARDS_DATA.md` remain owner work outside
  this S1.2 commit.

## Files that are large or unsafe to read whole
- `data/raw/openalex_institutions_ca.jsonl` -> ignored; inspect bounded samples.
- `data/raw/ror/v2.15-2026-10-20-ror-data.zip` -> ignored; inspect checksum and
  selected records only.
- `data/logs/api_usage.jsonl` -> ignored; aggregate by run ID and never print
  request URLs while diagnosing credentials.
- `spec.md` -> read only Part B, the selected Part E stage, and named Part D rows.

## Prompt for the next fresh agent
You are a build agent for
`C:\Users\Scott.Coffin\R_new\CA_Plastics_Research_Dash`. Follow Part B of
`spec.md` exactly. Read the required `.agent` files, inspect
`git log --oneline -15` and `git status`, and complete exactly the first
unchecked task, S1.3; do not start S1.4. Read only Part B, the S1 stage entry,
and the Part D source rows named by S1.3. Preserve the pre-existing owner
changes to `.agent/QUESTIONS.md` (G-6) and `docs/AWARDS_DATA.md`, and preserve
the completed S1.2 institution-review data. Verify the geography sources and
licenses required by S1.3, implement California land and CDFW 3-nm-water
polygons plus the `in_ca` known-point tests, confirm the browser asset is under
1 MB, run the S1.3 acceptance check and `make test`, update all B4 records in
order, commit/push if configured, and stop before S1.4. Do not retune the broad
S1.2 OpenAlex `search=plastic` query during S1.3; that belongs to S1.5 or a
separately authorized external agent. End by reporting owner actions and
providing a copy-paste prompt for the next fresh agent that explicitly repeats
this successor-prompt requirement.
