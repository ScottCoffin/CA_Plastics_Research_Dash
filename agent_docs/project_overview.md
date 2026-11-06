# Project Overview

## Purpose

The repository is building a public, auto-updating atlas of California
plastic-related researchers, monitoring data, and research funding. The
README identifies the repository as being in bootstrap development, with
`spec.md` as the product and implementation specification.

## Scope

The implemented foundation covers configuration-driven reference-data
acquisition, California institution and ROR joining, geography and gazetteer
assets, a versioned OpenAlex plastics-query renderer, incremental OpenAlex
works ingestion, normalization into C3 tables, API usage accounting, and a
static deployment placeholder. The roadmap also defines future work for
classification, full text, monitoring, grants, linking, and the interactive
front end; those areas are not represented as completed functionality by this
bootstrap documentation.

## Architecture

The project is a Python package plus command-line pipeline. YAML/CSV files in
`config/` define sources, the candidate query, taxonomy seeds, and overrides.
Builder and smoke/check scripts call the package modules and external APIs,
write reference artifacts under `data/processed/`, and write raw or
intermediate pipeline state under the corresponding `data/` directories.
OpenAlex works are first stored as a resumable raw-work table and are then
normalized into separate works, authorships, authors, and institutions
outputs. The `site/` directory is currently a static placeholder consumed by
the Pages workflow.

## Main Workflows

- `make setup`, `make test`, `make lint`, and `make build` install development
  dependencies, run pytest, run Ruff checks, and compile the package.
- The reference-data scripts build institutions, California geography, and a
  gazetteer; corresponding `check_s1_*` scripts and API smoke tests document
  bounded verification.
- `scripts/ingest_openalex.py` runs the incremental/resumable works ingester;
  `scripts/normalize_openalex.py` produces normalized outputs and QC.
- GitHub Actions provides CI, scheduled/manual Pages build and deployment,
  keepalive, and a watchdog workflow.

## Major Decisions

- `spec.md` is the product and implementation specification, while
  `.agent/TODO.md` is the staged roadmap and acceptance checklist.
- The configured `plastic-v2-candidate` query is owner-supplied and remains
  marked `owner_supplied_candidate`; it is not documented as the active
  production corpus.
- Query count caches must retain both the query version and rendered query,
  and mismatches are rejected.
- OpenAlex works retrieval is bounded to at most 100 institution IDs per
  request and uses cursor pagination for large retrievals. The normalizer
  preserves the reviewed institution registry as a separate input.
