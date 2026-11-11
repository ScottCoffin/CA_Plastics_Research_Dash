# AT-11 verification: CI guards for the daily ingest

Date: 2026-11-11. Module: `atlas.guards`; CLI: `py -3.14 scripts/check_ci_guards.py`.

## Guards

| Guard | Where | Fails when |
|---|---|---|
| Raw works schema | `ingest_works.yml` (`--require-raw`) | raw parquet columns change, or sampled OpenAlex records lack keys the normalizer needs (id, title, publication_year/date, type, authorships with author/institutions, primary_location, open_access, is_retracted, cited_by_count) |
| Normalized schema | `ingest_works.yml` (`--require-normalized`) | a normalized table is missing, or lacks a field / has a different Arrow type than the normalize schema |
| Site payload | `ingest_works.yml` and `ci.yml` | initial payload (index, institutions, aggregates, build_metadata) > 3 MB gz, any file > 25 MB (G-HOST), or `index.json` lacks required keys |
| Rate limit / budget | existing `run_daily_ingest` | OpenAlex 429 or budget ceiling: status `deferred`, outputs and high-water untouched, next run retries |
| Keep-alive | existing `keepalive.yml` | (monthly commit against the 60-day schedule disablement) |

The guard step runs after the export and before the data commit, so a failure stops the commit.

## Failure modes tested (`tests/test_ci_guards_at11.py`, 21 passed)

Rate limit and budget deferral (files byte-identical), empty day (0 fetched; empty raw table OK),
schema change (raw `authorships` or `is_retracted` missing, authorship without `institutions`,
missing raw column, normalized missing column / wrong type / missing table), oversized payload
(gzip limit and per-file limit), index keys, real committed `site/data` with default limits.

## Real data (2026-11-11)

raw 1,933 rows (200 sampled, 0 bad); normalized works 1,896 / authorships 13,434 / authors 8,500 /
institutions 2,344; initial payload 587,213 B gz; largest file `index.json` 1,947,479 B.
The guard first flagged the committed `works.parquet` as missing `is_retracted` (it predated AT-3);
it was re-normalized from the unchanged committed raw table.

## Decision

The previous-complete-day window was not adopted: the run uses an inclusive
`publication_date` high-water with dedupe, which is already idempotent, and a cap at
yesterday would delay future-dated works (QUESTIONS AT11-WINDOW, default in use).
