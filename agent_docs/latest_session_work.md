# Latest Session Work

## Detailed Current State

S3.1 was completed from `.agent/HANDOFF.md`. The daily workflow is in
`.github/workflows/ingest_works.yml`; `atlas.ingest.daily` and
`scripts/run_daily_works.py` defer expected OpenAlex 429/budget stops without
advancing state. The workflow normalizes/labels only after a successful pull
and commits generated outputs only under the exact `ENABLE_DATA_COMMITS=true`
guard. S3.1 adds `src/atlas/build/export_site.py`, the
`scripts/build_export_site.py` wrapper, the schema contract in
`docs/SITE_DATA.md`, and committed fixture site payloads under `site/data/`.

## Verification

- `py -3.14 scripts/check_s2_4.py` passes, including simulated 429 and budget
  stops, unchanged high-water state, and a successful subsequent run.
- `py -3.14 -m pytest -q` passes (40 tests).
- Ruff check/format, `py -3.14 -m compileall -q src`, and `git diff --check`
  pass.
- Hosted bounded smoke run `42321442943` completed successfully with
  `max_credits=0`; the expected budget defer skipped normalization, labeling,
  and commits.
- `py -3.14 scripts/check_s3_1.py` passes; the full suite has 41 tests and the
  fixture site payload is 3,678 bytes gzip.

## Next Entry Point

Resume with S3.2: build the accessible mobile app shell and stub tabs from the
S3.1 site-data contract, run its acceptance and full suite, update the B4
records, commit/push only S3.2, and stop before S3.3.
