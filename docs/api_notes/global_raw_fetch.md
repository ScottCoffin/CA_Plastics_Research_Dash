# Global raw OpenAlex fetch (PLAT-4a)

**Status: unpublished. Estimate recorded 2026-11-25. Paging is blocked until an OpenAlex key is loaded (see "Trial run").**

Owner answer A3-Q15 (2026-11-18): start the budget-guarded raw global fetch early, into
ignored `data/raw/`; the regional partition and any publishing come after PLAT-3.

## Purpose

Fetch the active plastics query (`plastic-v3.1`, `config/queries.yml`) for every work
in OpenAlex, with **no California institution, raw-affiliation, author or paid filter**.
The raw store is the input for PLAT-4, which partitions it by region, labels hits as
"unscreened query hits", and keeps `ids.pmid`. Records are stored unmodified (full
OpenAlex work objects, including `ids`). Nothing is published: the store is under the
gitignored `data/raw/`, and no site or CA-works output reads it.

## Command

```bash
py -3.14 scripts/fetch_global_raw.py --dry-run        # print URLs, no network
py -3.14 scripts/fetch_global_raw.py --estimate       # one count request, then stop
py -3.14 scripts/fetch_global_raw.py                  # page (needs estimate.json)
py -3.14 scripts/fetch_global_raw.py --restart        # archive saved state, start over
```

Options: `--start-year` (default 1950), `--end-year` (default current UTC year),
`--max-credits` (per run, default 2000), `--per-page` (default 100).

The request is one filter: the active `title_and_abstract.search` expression (with its
exclusions), the configured `exclude_types`, and `from_publication_date` /
`to_publication_date` for each year. The OR lists are never split. The end date is
capped at yesterday UTC, so only complete days are read (the AT11-WINDOW convention).

## Cost estimate (one `--estimate` call, 2026-11-25)

The count request used `per_page=1` over 1950-01-01 to 2026-11-24.

| Measure | Value |
|---|---|
| Works (`meta.count`) | 136,080 |
| Year slices | 77 |
| Pages at 100 per page | 1,361 minimum, 1,438 maximum (one partial page per slice, plus empty years) |
| Credits per call (measured) | 10 (USD 0.001) |
| Credits, maximum | 14,380 (USD 1.438) |
| Days at the USD 0.95 daily stop | about 1.5 |

Page size is 100, not 200. OpenAlex's maximum is 100, and `atlas.ingest.openalex`
rejects larger pages. The count call's measured cost (10 credits, USD 0.001) is recorded
in `data/logs/api_usage.jsonl`. The estimate is also written to
`data/raw/openalex_global/estimate.json`; paging refuses to start until it exists.

## Budget guard

- The daily stop is USD 0.95 per UTC day. It is passed as a caller cap to
  `resolve_openalex_budget`, so the strictest value wins over `config/budget.yml`
  (abort threshold 0.95) and environment settings. The day's total is read from the
  shared usage log, so CA ingest runs count against the same stop.
- Each request is checked before it is sent, with the planned-request reserve
  (USD 0.001, 10 credits). The run stops cleanly (`status: deferred`, `reason:
  budget_exceeded`) before a request that would pass the stop.
- `--max-credits N` caps each run (default 2,000 credits, about 200 pages). Reaching it
  stops cleanly with `reason: run_credit_cap`.
- An HTTP 429 that is not a burst limit (`atlas.ingest.openalex` rules) exits 0 with
  `reason: rate_limited` and progress saved. Burst 429s are retried inside the request
  helper.

Because the stop is daily, the full pull spreads over about two UTC days at the default
settings, and longer if other OpenAlex runs share the budget.

## Store and resume

Under `data/raw/openalex_global/` (ignored by `.gitignore` via `data/raw/*`):

- `pages/<year>_<NNNNN>.jsonl.gz`: one page per file. Line 1 is a `page_header` (query
  version, query hash, slice year, page index, requested URL without a key, run ID,
  fetch time, OpenAlex `meta`). Each later line is one unmodified OpenAlex work.
- `state.json`: `query_version`, `query_hash` (SHA-256 of the query identity: the
  filter, the type exclusions and the endpoint), `per_page`, and for each slice its
  date window, `cursor` (the next cursor), `done`, `pages`, `works`, and the latest
  `publication_date` seen. It also holds `pages_done`, `works_fetched`, `credits_total`,
  `credits_by_utc_day`, and `last_run`.
- `estimate.json`: the estimate above.

Writes are atomic. A page is written before the cursor that points past it is saved,
so a crash re-fetches at most one page, and that page overwrites the same file name. A
resumed run continues at the saved cursor. Slice date windows are stored in the state,
so a cursor is never reused with a different date filter.

A saved state for a different query version or hash is refused with an error (exit 1)
unless `--restart` is given. `--restart` moves the old `state.json` and `pages/` aside
as `state.restart-<UTC stamp>.json` and `pages.restart-<UTC stamp>/` (nothing is
deleted). A saved state with a different `per_page` is also refused.

## Trial run (2026-11-25)

Planned: one `--max-credits 30` run for the 2025 slice, to show cursor paging on a
multi-page year.

- Page 1 (cursor `*`) succeeded: 100 works, 10 credits, `pages/2025_00001.jsonl.gz`
  written, and `state.json` saved with the next cursor.
- Page 2 (with a cursor) returned HTTP 401, "API key required for cursor paging".
  The key loader (`load_openalex_key`) set no `OPENALEX_API_KEY` in this environment,
  so the run stopped with an error. Its state was consistent (the cursor was not
  advanced past page 1).
- The 401 has no credit header, so the shared usage log line is unknown-credit. Until the
  UTC day ends, `daily_logged_usage` refuses to reset the budget for that day, which
  blocks OpenAlex runs for 2026-11-25. Tomorrow's UTC day is unaffected.

Paging is not proven beyond page 1. Re-run `py -3.14 scripts/fetch_global_raw.py
--start-year 2025 --end-year 2025 --max-credits 30` with a key loaded to finish that
check; that run then resumes at the saved cursor.

## Not published

Nothing in this fetch is published. The site, the CA works table and the review
exports do not read `data/raw/openalex_global/`. Affiliation strings and abstracts in
the raw records can contain email addresses. The raw store is ignored, but any later
step that publishes from it must apply the redaction used in
`atlas.ingest.openalex._RAW_EMAIL_RE` first.
