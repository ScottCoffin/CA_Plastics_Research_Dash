# Project Core Technologies

## Languages and Runtimes

- Python is the implementation language; `pyproject.toml` requires Python
  3.11 or newer, and CI is configured for Python 3.11.
- The package is built with setuptools from the `src/` layout.

## Frameworks and Libraries

- Core data and geospatial dependencies are PyArrow, GeoPandas, Pyogrio, YAML,
  and Shapely.
- Development dependencies are pytest, Ruff, and pre-commit.
- Data formats used by the repository include Parquet, GeoJSON, SQLite,
  JSON/JSONL, YAML, and CSV.

## Build, Test, and Development Tools

- The `Makefile` exposes `setup`, `test`, `lint`, `build`, and `qc` targets.
- Pytest is configured with `src` on `pythonpath` and discovers tests under
  `tests/`.
- Ruff checks and formats Python code; `compileall` is the build sanity check.
- `scripts/` supplies reproducible builders, ingestion and normalization
  commands, acceptance checks, and bounded smoke tests.
- GitHub Actions runs CI and publishes the current static `site/` artifact to
  GitHub Pages through separate build and deploy jobs.

## External Services and Infrastructure

- OpenAlex supplies institution and works metadata; ROR supplies organization
  metadata and a versioned data dump; GeoNames, Natural Earth, and CDFW
  provide geographic reference inputs.
- OpenAlex authentication, when required, uses the environment variable
  `OPENALEX_API_KEY`. Secret values are not part of this documentation.
- GitHub Actions and GitHub Pages provide the repository automation and static
  hosting boundary.

## Important Technical Constraints

- The OpenAlex query is rendered from `config/queries.yml`, scoped to
  `title_and_abstract.search`, and is explicitly an owner-supplied candidate.
  Any term, Boolean, exclusion, or field-scope change requires a new query
  version; count caches are valid only when both version and rendered query
  match.
- OpenAlex institution filters are limited to 100 IDs per request. Large
  works retrieval uses cursor pagination, and the incremental ingester writes
  merged output and its high-water mark only after successful processing.
- Raw downloads, intermediate state, and API logs are kept in Git-ignored
  `data/` locations; processed reference artifacts and review inputs are
  separate from those working areas.
- The reviewed institution registry is preserved as a distinct normalizer
  input so works normalization cannot overwrite it.
- The public site is currently a bootstrap placeholder; later roadmap stages
  own the interactive atlas and broader data products.
