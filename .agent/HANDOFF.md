# Handoff - 2026-11-06 - task S3.5

## Done
- Added the About/Methods view, G-12 disclaimer, data-correction route, and
  metadata-backed freshness and counts. Full methods are in `docs/METHODS.md`;
  rendered acceptance evidence is in `docs/S3_5_VERIFICATION.md`.
- Fixture timestamp and counts come from `build_metadata.json`; fixture and
  unavailable cases are labeled explicitly. Do not interpret the fixture as a
  current data refresh.
- The S3.5 acceptance, S3.2-S3.4 regression checks, 49-test suite, Ruff, and
  `git diff --check` passed. Independent Chromium verified About, the
  Institutions-to-Experts filtered drawer path, and 390x844 layout. The only
  browser errors were harmless `/favicon.ico` 404s.

## State of the repo
- S3.5 is verified. The main agent owns the narrow S3.5 commit and push; confirm
  its final commit and clean/synchronized status before continuing.
- Recheck with `py -3.14 scripts/check_s3_5.py` and
  `C:\rtools45\usr\bin\make.exe PYTHON="py -3.14" test` if the implementation
  changes after this verification.

## Next task (suggested)
S3.6: verify the Pages deployment and record the performance ladder metrics.
First read the S3.6 contract in `spec.md`, then inspect the deployed result and
measure the current static site against C5. Consider DuckDB-Wasm only if the
recorded performance decision supports it.

## Gotchas the next agent must know
- The `fixture` value is a deliberate sentinel, not a timestamp; live refresh
  time and counts come from export build metadata.
- Browser smoke used the committed fixture. Live ISO and missing metadata cases
  were covered by the Node renderer harness rather than browser fetch
  interception.
- Playwright produced two expected favicon 404s; data loaded and no other
  browser warnings were reported.
- S3.6 remains unchecked in `.agent/TODO.md`; do not begin it before S3.5's
  narrow Git handoff is complete.

## Needs owner input
- None for S3.6 is recorded in this handoff; check `.agent/QUESTIONS.md` for
  existing owner-gated roadmap tasks.

## Files that are large or unsafe to read whole
- `data/processed/*.parquet` -> inspect with DuckDB or targeted PyArrow schema.
- `site/data/authors/*.json` -> inspect one author document at a time.
