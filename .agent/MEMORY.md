# MEMORY (durable facts only; <=200 lines)

## Project in one paragraph
CA Plastics Research Atlas is a static public dashboard and reproducible Python
pipeline for California plastic-related expertise, monitoring data, and funding.
The canonical product and implementation contract is `spec.md` v1.0 (2026-11-05).

## How to run (commands)
- Install: `make setup` or `python -m pip install -e ".[dev]"`.
- Test: `make test` or `python -m pytest`.
- Lint: `make lint` or run Ruff check and format-check directly.
- Build bootstrap validation: `make build` or `python -m compileall -q src`.

## Conventions (naming, IDs, paths, timezones: store UTC; CI cron is UTC)
- Python package uses the `src/atlas/` layout and requires Python >=3.11.
- Processed fields and file names use `snake_case`; stable IDs follow `spec.md` C3.
- Store timestamps in UTC; GitHub Actions schedules are UTC.
- Raw/interim data, API logs, full text, secrets, scratch files, and models are ignored.
- Commit only slim processed/site data after upstream license review.
- Each agent session completes exactly one dependency-satisfied task.

## Key decisions (links to DECISIONS.md IDs)
- No owner-confirmed project decisions yet; Part G defaults remain in use.

## Verified API facts (one line each; details in docs/api_notes/)
- None yet; external API verification begins in S1.1.

## Data locations and sizes (what's committed vs. gitignored; how to inspect)
- `data/raw/`, `data/interim/`, and `data/logs/` contents are ignored.
- `data/processed/` may contain reviewed, slim outputs; inspect Parquet with DuckDB.
- Test fixtures belong in `tests/fixtures/` and must stay at or below 200 records.

## Known pitfalls (top 10; details in LESSONS.md)
- GNU Make is not on PATH, but Rtools provides `C:\rtools45\usr\bin\make.exe`.
- Do not treat Part D research claims as live API contracts without smoke tests.
- Do not copy from reuse candidates before recording and confirming their licenses.

## Current model versions and metrics (one line per model)
- None; classifiers are not implemented.
