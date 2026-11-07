# Project Structure

## Directory Layout

- `src/atlas/` is the installable Python package.
  - `ingest/` contains institution-registry, OpenAlex works-ingestion, and
    works-normalization code; `grants/` and `monitoring/` currently contain
    package namespaces only.
  - `geo/` contains California boundary and gazetteer utilities.
  - `query.py` renders the configured OpenAlex plastics query and validates
    count-cache identity.
  - `util/` contains the API usage and cost logger.
  - `fulltext/` and `nlp/` currently contain package namespaces only.
- `scripts/` contains builders, ingestion/normalization CLIs, acceptance
  checks, and bounded external-service smoke tests.
- `config/` contains source, query, taxonomy, gazetteer, author, and
  institution configuration and override tables.
- `data/raw/`, `data/interim/`, `data/processed/`, and `data/logs/` separate
  downloaded inputs, intermediate pipeline state, processed reference and
  geography artifacts, and API usage logs. Raw, interim, and log contents are
  ignored by Git except for their `.gitkeep` files.
- `curation/` contains gold, review-queue, and work-override CSV inputs.
- `docs/` contains methods, source/reuse/secret notes, QC reports, and dated
  API verification notes under `docs/api_notes/`.
- `tests/` contains pytest tests and bounded JSON/text fixtures.
- `site/` contains the S3 static atlas shell, Experts and Institutions views,
  and deterministic static data payloads under `site/data/`.
- `.github/workflows/` contains CI, Pages build/deploy, keepalive, and
  watchdog workflows.
- `AGENTS.md` contains the repository-level continuous-checkpoint contract.
- `.agent/` contains the canonical task protocol, roadmap, current handoff,
  questions, decisions, lessons, and checkpoint records.

## Modules and Responsibilities

- The configuration files are the inputs for source selection, the plastics
  query, taxonomy seeds, and owner-reviewed overrides.
- The reference-data workflow builds a California institution registry from
  OpenAlex and ROR data, plus California geography and a GeoNames-derived
  gazetteer.
- The works workflow retrieves OpenAlex records incrementally and resumably,
  keeps raw snapshots outside Git, and writes an intermediate raw-work
  Parquet table.
- The normalization workflow converts OpenAlex works into separate works,
  authorships, authors, and institutions tables with QC metrics and
  California flags. Its generated institution output is separate from the
  reviewed registry input.
- The static site consumes the S3.1 compact data contract and implements the
  app shell, Experts filters/detail drawer, and Institutions leaderboard/map.
  Remaining S3 tasks add methods/freshness and deployment performance evidence.

## Main Interfaces and Integration Boundaries

- `config/queries.yml` is the versioned input to `src/atlas/query.py` and the
  OpenAlex works ingester. The current query is explicitly marked an
  owner-supplied candidate.
- The main generated-data boundaries are `data/processed/institutions.parquet`,
  `data/interim/works_raw.parquet`, normalization output tables, geography
  Parquet/GeoJSON assets, the SQLite gazetteer, and
  `data/logs/api_usage.jsonl`.
- External boundaries are the OpenAlex API, ROR API/data dump, GeoNames
  extract, Natural Earth, and CDFW geography archives. The local OpenAlex
  credential is read through the `OPENALEX_API_KEY` environment variable when
  needed; no credential value is documented here.
- `Makefile`, the scripts in `scripts/`, and GitHub Actions provide the
  command-line and automation interfaces. The package is tested through the
  `src` import path configured in `pyproject.toml`.

## Tests and Supporting Assets

Pytest tests cover package behavior, query construction and cache validation,
API cost logging, institution classification, geography, gazetteer lookup,
OpenAlex ingestion, normalization, static exports, and S3 UI contracts.
Stage-specific checks are exposed through `scripts/check_s3_4.py`; smoke tests
cover external APIs, source archives, and browser behavior where required.
