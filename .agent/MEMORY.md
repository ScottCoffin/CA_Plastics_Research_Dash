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
- Build geography: `python scripts/build_geography.py`; use `--land-archive`
  and `--cdfw-archive` for already-downloaded official source archives.
- Geography smoke/acceptance: `python scripts/smoke/geography.py` and
  `python scripts/check_s1_3.py`.
- Gazetteer source smoke/build/acceptance: `python scripts/smoke/geonames.py`,
  `python scripts/build_gazetteer.py`, and `python scripts/check_s1_4.py`.

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
  default major-private set 11/11. Owner top-100 review is complete 100/100;
  22 corrected types are durable overrides in `config/institution_overrides.csv`.
- Owner-supplied S1.5 query design is recorded as
  `plastic-v2-candidate` in `config/queries.yml`; generic microfiber, tire-wear,
  and plastic-waste terms require context, mechanical microplasticity phrases
  are excluded, and the cache contract includes query version plus rendered
  query. External counts are unverified design snapshots, not dashboard data.
- Natural Earth Admin 1 version 5.1.1 is public domain and supplies the CA
  land polygon; official CDFW ds3158 is CC BY 4.0 and its `ds3158_alt.gdb`
  contains the recommended `ds3158_poly` state-waters multipolygon.

## Data locations and sizes (what's committed vs. gitignored; how to inspect)
- `data/raw/`, `data/interim/`, and `data/logs/` contents are ignored.
- API request rows and per-run cost summaries append to
  `data/logs/api_usage.jsonl` through `atlas.util.cost.ApiCostLogger`.
- `data/processed/` may contain reviewed, slim outputs; inspect Parquet with DuckDB.
- `data/processed/institutions.parquet` is the slim registry; the editable
  owner queue is `data/processed/institution_review_top100.csv`, and QC is in
  `docs/institutions_qc.md`. Raw OpenAlex/ROR inputs and count caches are ignored.
- Test fixtures belong in `tests/fixtures/` and must stay at or below 200 records.
- Full-resolution geography is in `data/processed/geo/*.parquet`; the simplified
  two-feature browser payload is `site/assets/ca_boundaries.geojson` (306,997
  bytes at S1.3 completion).
- S1.4 stores the reproducible GeoNames California subset in
  `data/processed/gazetteer_ca.sqlite`; use `atlas.geo.gazetteer.lookup()` for
  exact normalized names, curated aliases, and explicit blacklist enforcement.
- S1.5 query rendering and cache validation are in `atlas.query`; the ignored
  cache is `data/interim/openalex_query_counts.json` and must carry both the
  query version and rendered query. The 2026-11-06 UTC count for the
  owner-supplied candidate was 98,118 works; the positive control without
  exclusions was 100,335.
- S2.1 works ingestion is implemented in `atlas.ingest.openalex`; the live
  command is `py -3.14 scripts/ingest_openalex.py --start-year YYYY --end-year
  YYYY --allow-candidate`. It batches CA institution IDs at 100, follows
  cursor pages, snapshots raw responses under ignored `data/raw/openalex_works/`,
  and atomically merges deduplicated rows into ignored
  `data/interim/works_raw.parquet`.
- The S2.1 default high-water field is inclusive `publication_date`; rerunning
  the boundary date is intentional and deduplication makes it idempotent.
  `from_updated_date` is implemented as an opt-in mode but the 2026-11-06
  free-plan smoke returned HTTP 429 Plan upgrade required. The four-record
  synthetic fixture is `tests/fixtures/s2_1_openalex_works.json`.
- S2.2 normalization is implemented in `atlas.ingest.normalize` and writes
  C3-shaped `works.parquet`, `authorships.parquet`, `authors.parquet`, and a
  separate normalized `institutions.parquet` below `data/processed/normalized/`.
  It preserves the reviewed registry, adds `ca_led` and `ca_any_author`, and
  writes `docs/normalization_qc.md`; `make qc` falls back to the committed
  S2.2 fixture when ignored live raw works are absent.
- S2.3 labels are implemented in `atlas.nlp.labels` and written as a separate
  one-row-per-work `work_labels.parquet`. Ordered exclusions, core terms,
  qualified context terms, and tier-2 terms come from the owner-supplied
  `config/queries.yml`; provisional domain and matrix facets use
  `config/taxonomy.yml` plus independent local seeds. Raw OpenAlex topics are
  joined by work ID for display names, and missing raw/topic rows remain in the
  output and are counted in the QC report. `label_source=rule`, nullable
  `confidence`, and `plastic-v2-candidate-rule-v1` keep the candidate
  unpromoted.
- S2.4's `.github/workflows/ingest_works.yml` runs daily at 10:17 UTC and on
  manual dispatch. `scripts/run_daily_works.py` treats OpenAlex HTTP 429 and
  configured credit/USD ceilings as deferred, preserving the prior output and
  high-water state so the next inclusive run resumes safely. Generated outputs
  are force-added only when the repository variable `ENABLE_DATA_COMMITS` is
  exactly `true`; optional `OPENALEX_MAX_CREDITS` and
  `OPENALEX_MAX_COST_USD` variables bound a run.

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
- The S1.2 ranking query is literal OpenAlex `search=plastic`; owner review
  suggests it includes plasticity, plastic surgery, and plastic deformation.
  Do not publish its counts as a pollution leaderboard; S1.5 must retune or
  restrict the versioned query before downstream use.
- Do not use a legal state-boundary polygon as a land mask: it can include
  offshore jurisdiction and hide the CDFW `state_waters` classification.
- GeoNames `US.zip` is CC BY 4.0 and uses 19 UTF-8 tab-delimited fields; the
  committed subset rule is `country_code=US and admin1_code=CA`. Keep its raw
  ZIP ignored, preserve GeoNames credit, and do not treat blacklisted common
  words or regional centroids as sampling evidence without later context.
- The S1.5 count is a timestamped design estimate, not dashboard data. The
  candidate remains `owner_supplied_candidate` until the owner reviews the
  bounded precision examples and promotes it for downstream ingestion.

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
