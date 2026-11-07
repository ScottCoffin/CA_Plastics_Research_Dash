# Handoff - 2026-11-06 - task S3.2

## Done
- Replaced the Pages placeholder with a dependency-free single-file app shell
  in `site/index.html`.
- The shell loads the S3.1 `index.json`, `institutions.json`,
  `aggregates.json`, and `build_metadata.json` payloads; renders Experts and
  Institutions; and provides explicit Monitoring and Funding stubs plus About.
- Experts filters are persisted in the URL hash, native tabs support keyboard
  arrow/Home/End navigation, and the filtered author index exports CSV.
- Added `scripts/check_s3_2.py` and `tests/test_site_shell.py`; documented the
  design in ADR-012 and the independent implementation in `docs/REUSE.md`.

## Verification
- `py -3.14 scripts/check_s3_2.py` passes: five accessible tabs, hash/CSV
  hooks, responsive marker, and non-empty S3.1 fixture payloads.
- `py -3.14 -m pytest -q` passes with 43 tests.
- Ruff check/format, compileall, and `git diff --check` pass.
- A local static HTTP server returned the shell and `/data/index.json` with the
  expected fixture schema and author records. The bundled Playwright wrapper
  could not run in this environment because its current package requires Node
  20 while the available Node is 18; no browser result is claimed.

## Next task
S3.3: implement the Experts filters, virtualized list, researcher detail
drawer, works list, and report-an-error link. Preserve this shell and do not
start S3.4 in the same session.

## Prompt for the next fresh agent

Continue exactly S3.3 from `.agent/HANDOFF.md`; preserve unrelated files, read
the S3.3 contract in `spec.md` and the S3.1 data contract in
`docs/SITE_DATA.md`, build on the existing accessible shell without starting
S3.4, run the S3.3 acceptance plus the full suite, update B4 records, commit
and push only S3.3, and stop before S3.4. If directing a bounded worker, use a
Luna worker only.
