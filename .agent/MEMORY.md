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
- ADR-001: use official Pages actions, a daily off-peak deploy, a stale-run
  watchdog, and an opt-in monthly keepalive commit.
- No owner-confirmed product decisions yet; Part G defaults remain in use.

## Verified API facts (one line each; details in docs/api_notes/)
- GitHub Actions schedules use the default branch, default to UTC, and may be
  delayed; the 60-day inactivity disablement is documented for public repos.
- The Pages API rejects this private repository under the current plan (HTTP
  422); details are in `docs/api_notes/github_actions_pages.md`.

## Data locations and sizes (what's committed vs. gitignored; how to inspect)
- `data/raw/`, `data/interim/`, and `data/logs/` contents are ignored.
- `data/processed/` may contain reviewed, slim outputs; inspect Parquet with DuckDB.
- Test fixtures belong in `tests/fixtures/` and must stay at or below 200 records.

## Known pitfalls (top 10; details in LESSONS.md)
- GNU Make is not on PATH, but Rtools provides `C:\rtools45\usr\bin\make.exe`.
- Do not treat Part D research claims as live API contracts without smoke tests.
- Do not copy from reuse candidates before recording and confirming their licenses.
- The current GitHub plan cannot host Pages from this private repository; do not
  change visibility while G-7 and the license choice remain open.

## Automation
- `.github/workflows/ci.yml` runs lint, tests, and the build on pushes, pull
  requests, and manual dispatches.
- `build_deploy.yml` publishes `site/` on pushes, manual dispatches, and daily at
  10:15 UTC; `watchdog.yml` checks at 11:47 UTC and redispatches after 25 hours.
- `keepalive.yml` runs monthly at 09:42 UTC. It commits only when the repository
  variable `ENABLE_DATA_COMMITS` is exactly `true`.
- User-managed Actions configuration names are listed, without values, in
  `docs/SECRETS.md`.

## Current model versions and metrics (one line per model)
- None; classifiers are not implemented.
