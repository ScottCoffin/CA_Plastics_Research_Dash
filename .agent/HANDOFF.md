# Handoff - 2026-11-06 - task S3.3

## Done
- Extended `site/index.html` with hash-shareable Experts filters for tag,
  institution type/institution, year range, CA basis, and OA availability.
- Added bounded virtual rendering (fixed 174px slots with four-row overscan)
  and accessible researcher detail drawer with lazy per-author JSON loading,
  works, affiliation history, links, and report-an-error link.
- Added `scripts/check_s3_3.py`, `tests/test_s3_3.py`, and
  `docs/S3_3_VERIFICATION.md`; browser screenshot is under ignored
  `output/playwright/s3_3-experts.png`.
- Updated `.gitignore` and B4 records for the local screenshot artifact and
  S3.3 decision/lesson.

## State of the repo
- `py -3.14 scripts/check_s3_3.py` passes.
- `py -3.14 scripts/check_s3_2.py` passes.
- `C:\rtools45\usr\bin\make.exe PYTHON="py -3.14" test` passes (45 tests).
- Ruff check/format, compileall, and `git diff --check` pass.
- Playwright smoke through WSL Node 20.20.2/Chromium passed: CA-led filter,
  Alice drawer, work title, correction link, and screenshot.

## Next task (suggested)
S3.4: implement the Institutions leaderboard, sparklines, institution-type
chips, clustered map, and links into the Experts view. Start by reading the
S3.4 contract in `spec.md`, preserve the S3.3 drawer/filter behavior, and stop
before S3.5.

## Gotchas the next agent must know
- The site is dependency-free and must be served over HTTP for JSON fetches.
- Playwright runs in WSL; use an explicit named session and `--browser=chromium`.
- The Experts author summary derives tags and basis from indexed work rows;
  missing `ca_sampled` remains distinct from `ca-affiliated`.
- Do not promote the inactive `plastic-v2-candidate` query.

## Needs owner input
- None for S3.4; existing owner questions remain in `.agent/QUESTIONS.md`.

## Files that are large or unsafe to read whole
- `data/processed/*.parquet` -> inspect with DuckDB or targeted PyArrow schema.
- `site/data/authors/*.json` -> inspect one author document at a time.
