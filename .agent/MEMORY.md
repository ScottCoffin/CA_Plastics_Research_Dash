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
- OpenAlex smoke: `python scripts/smoke/openalex.py` after editable install.
- ROR smoke: `python scripts/smoke/ror.py` after editable install.
- Build/update institutions: `python scripts/build_institutions.py`; it reads
  `OPENALEX_API_KEY` (or local alias `OPEN_ALEX_API_KEY`) from ignored `.env`.
- S1.2 machine acceptance: `python scripts/check_s1_2.py`; add
  `--require-owner-review` only after all 100 review rows are signed off.

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
- ADR-002: keep the repository public, use GitHub Actions Pages, enable guarded
  repository writes, and use MIT for code plus CC BY for eligible derived data.

## Verified API facts (one line each; details in docs/api_notes/)
- GitHub Actions schedules use the default branch, default to UTC, and may be
  delayed; the 60-day inactivity disablement is documented for public repos.
- Pages was enabled after the owner made the repository public. Manual run
  `42092058401` succeeded and the live placeholder returned HTTP 200.
- The 2026-11-05 registry has 4,637 unique OpenAlex institutions, including
  explicit UC/CSU/private-university supplements; all 4,637 ROR IDs matched
  ROR dump v2.15 (`10.5281/zenodo.23500708`).
- S1.2 machine acceptance covers UC 10/10, CSU 23/23 campus records (22
  universities after the 2026 Cal Poly/Cal Maritime integration), and the
  default major-private set 11/11. Owner top-100 review remains 0/100.

## Data locations and sizes (what's committed vs. gitignored; how to inspect)
- `data/raw/`, `data/interim/`, and `data/logs/` contents are ignored.
- API request rows and per-run cost summaries append to
  `data/logs/api_usage.jsonl` through `atlas.util.cost.ApiCostLogger`.
- `data/processed/` may contain reviewed, slim outputs; inspect Parquet with DuckDB.
- `data/processed/institutions.parquet` is the slim registry; the editable
  owner queue is `data/processed/institution_review_top100.csv`, and QC is in
  `docs/institutions_qc.md`. Raw OpenAlex/ROR inputs and count caches are ignored.
- Test fixtures belong in `tests/fixtures/` and must stay at or below 200 records.

## Known pitfalls (top 10; details in LESSONS.md)
- GNU Make is not on PATH, but Rtools provides `C:\rtools45\usr\bin\make.exe`.
- Do not treat Part D research claims as live API contracts without smoke tests.
- Do not copy from reuse candidates before recording and confirming their licenses.
- Pages must be configured with `build_type=workflow` before the deploy workflow
  can pass `configure-pages`; the live URL uses the account custom domain.
- OpenAlex California institutions use exact filter `geo.region:California`;
  new works code should use `institutions.id`, at most 100 OR values per batch.
- OpenAlex list/filter calls observed 2026-11-05 cost 1 credit/USD 0.0001;
  use cursor paging for large works pulls and read live cost metadata/headers.
- ROR v2 currently returns schema 2.1; California locations use country `US`
  plus subdivision code `CA`, and list/search pages contain 20 records.
- Do not rely on a region-filtered institution pull alone for required-system
  coverage; check explicit expected lists and supplement by name when absent.

## Automation
- `.github/workflows/ci.yml` runs lint, tests, and the build on pushes, pull
  requests, and manual dispatches.
- `build_deploy.yml` publishes `site/` on pushes, manual dispatches, and daily at
  10:15 UTC; `watchdog.yml` checks at 11:47 UTC and redispatches after 25 hours.
- `keepalive.yml` runs monthly at 09:42 UTC. It commits only when the repository
  variable `ENABLE_DATA_COMMITS` is exactly `true`; the owner enabled it.
- User-managed Actions configuration names are listed, without values, in
  `docs/SECRETS.md`.
- Live Pages URL: `https://scottcoff.in/CA_Plastics_Research_Dash/`.

## Current model versions and metrics (one line per model)
- None; classifiers are not implemented.
