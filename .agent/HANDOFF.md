# Handoff - 2026-11-06 - task S3.1

## Done
- Added `.github/workflows/ingest_works.yml` with a daily UTC schedule,
  manual bounded dispatch, serialized data commits, and the exact
  `ENABLE_DATA_COMMITS == 'true'` write guard.
- Added typed `OpenAlexRateLimitError` and `OpenAlexBudgetError`. Expected
  429/budget stops preserve existing output and high-water state; the next
  inclusive publication-date run resumes safely.
- Added `atlas.ingest.daily.run_daily_ingest`, `scripts/run_daily_works.py`,
  optional `OPENALEX_MAX_CREDITS`/`OPENALEX_MAX_COST_USD` ceilings, and
  `scripts/check_s2_4.py`.
- Documented the workflow in `docs/api_notes/openalex.md`, `docs/SECRETS.md`,
  and the B4 records.

## Verification
- `py -3.14 scripts/check_s2_4.py` passes, including simulated 429/budget
  deferral, unchanged high-water state, and successful subsequent resume.
- `py -3.14 -m pytest -q` passes (40 tests).
- Ruff check/format, compileall, and `git diff --check` pass.
- Hosted bounded smoke `42321442943` completed successfully on GitHub Actions
  with `max_credits=0` and the expected `budget_exceeded` defer; no API key
  value was read or committed.
- `py -3.14 scripts/check_s3_1.py` passes; `py -3.14 -m pytest -q` passes with
  41 tests; Ruff, compileall, and `git diff --check` pass. The committed
  fixture site payload is 3,678 bytes gzip.

## Next task
S3.2: build the accessible mobile app shell and stub tabs from the S3.1 data
contract. Preserve the current workflow and do not start S3.3 in the same
session.

## Prompt for the next fresh agent

Continue exactly S3.2 from `.agent/HANDOFF.md`; preserve unrelated files, read
the S3.2 contract in `spec.md` and the S3.1 data contract in
`docs/SITE_DATA.md`, implement only the accessible app shell and stub tabs, run
its acceptance plus the full suite, update B4 records, commit and push only
S3.2, and stop before S3.3. If directing a bounded worker, use a
Luna worker only.
