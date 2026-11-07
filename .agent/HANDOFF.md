# Handoff - 2026-11-06 - task S3.4

## Done
- Extended `site/index.html` with the Institutions leaderboard, type filter
  chips, all-time/latest-five-year tagged-work counts, accessible sparklines,
  and a dependency-free coordinate-aware clustered map.
- Added leaderboard and map-marker links that write the existing Experts
  institution hash filter, preserving S3.3 filters, virtual rows, and the lazy
  researcher drawer.
- Added `scripts/check_s3_4.py`, `tests/test_s3_4.py`, and
  `docs/S3_4_VERIFICATION.md`; updated the S3.4 TODO, durable memory,
  decision, and lesson records.

## State of the repo
- `py -3.14 scripts/check_s3_4.py` passes (3 fixture institutions qualify).
- `py -3.14 scripts/check_s3_3.py` and `py -3.14 scripts/check_s3_2.py` pass.
- `C:\rtools45\usr\bin\make.exe PYTHON="py -3.14" test` passes (47 tests).
- Ruff check/format, compileall, and `git diff --check` pass.
- WSL Node 20.20.2/Chromium smoke passed: Institutions tab, UC type chip,
  map marker, Experts link, and Alice's S3.3 drawer. The only console entries
  were expected missing `favicon.ico` requests.

## Next task (suggested)
S3.5: add the About/Methods content and generated freshness metadata. Start by
reading the S3.5 contract in `spec.md`, inspect `docs/METHODS.md` and the S3.1
build metadata, then preserve the S3.3/S3.4 tab and hash behavior. Stop before
S3.6.

## Gotchas the next agent must know
- The site is dependency-free and must be served over HTTP for JSON fetches.
- The Institutions view counts only `plastic_related === true`; this keeps the
  old broad S1.2 `search=plastic` heuristic out of the public leaderboard.
- Institutions without coordinates stay in the leaderboard and are reported
  below the map; only valid California coordinates receive map markers.
- Playwright runs in WSL; use an explicit named session and
  `--browser=chromium`. Missing `favicon.ico` produces harmless console 404s.
- Do not promote the inactive `plastic-v2-candidate` query.

## Needs owner input
- None for S3.5; existing owner questions remain in `.agent/QUESTIONS.md`.

## Files that are large or unsafe to read whole
- `data/processed/*.parquet` -> inspect with DuckDB or targeted PyArrow schema.
- `site/data/authors/*.json` -> inspect one author document at a time.

## Successor prompt
Continue exactly S3.5 from `.agent/HANDOFF.md`; read the S3.5 contract and
`docs/METHODS.md`, implement About/Methods and generated freshness metadata,
preserve S3.3/S3.4 behavior, run the acceptance and full suite, update B4
records, commit and push only S3.5, then stop before S3.6.
