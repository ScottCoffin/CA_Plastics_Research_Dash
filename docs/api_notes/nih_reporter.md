# NIH RePORTER API notes (S8.2)

Source: `POST https://api.reporter.nih.gov/v2/projects/search`. Keyless and free.
Send `User-Agent: ca-plastics-atlas/0.1 (research dashboard)`. The ingester
contacts no other host.

## Verified facts (live, 2026-11-09 and 2026-11-10)

- `criteria.advanced_text_search` takes `operator`, `search_field`, and
  `search_text`. Use `operator: "advanced"`, which understands quoted phrases and
  `OR`. `search_field` must be `projecttitle,abstracttext,terms`. The
  comma-separated list is accepted. The value `abstract` is rejected with HTTP
  400, and `abstracttext` is the correct name.
- `criteria.org_states` takes two-letter codes. An unknown code such as
  `"California"` returns HTTP 200 with `meta.total: 0` and no error.
- `criteria.fiscal_years` is a list of integers.
- Response: `meta` (`search_id`, `total`, `offset`, `limit`, `sort_field`,
  `sort_order`, `sorted_by_relevance`, `properties`) and `results`.
- `sort_field: "appl_id"` is accepted (echoed in `meta`).
- Maximum `limit`: 500 accepted (`meta.limit` echoed 500).
- Offset ceiling: `offset` 15000 returns HTTP 400 with `{"message": "Requested limit
  exceeded. Maximum offset is 14,999."}`. Stay at or below offset 14999. A
  query with `total` above 15000 cannot be read in full, so the ingester defers
  that unit instead of truncating it.
- Quoted phrases are matched as written, not stemmed. The 16 singular core terms
  gave 17 hits for FY2024, while adding the plural forms (lead query) gave 29.
  The term set therefore includes plural variants.
- Result keys used: `appl_id`, `project_num`, `core_project_num`, `project_title`,
  `abstract_text`, `principal_investigators` (list with `full_name`, `first_name`,
  `last_name`), `organization` (`org_name`, `org_state`, `org_city`),
  `project_start_date` and `project_end_date` (`2024-03-11T00:00:00`, so the
  calendar date is taken from the first 10 characters), `award_amount` (integer,
  USD assumed), `fiscal_year`, `agency_ic_admin` (`code`, `abbreviation`, `name`),
  and `project_detail_url`.

## Not verified

- Whether `award_amount` is total award value or the current-year amount. The
  amount caveat in `docs/GRANTS_SCHEMA.md` applies. Treat it as unverified.
- The text length limit of `advanced_text_search`. The ingester keeps each group
  to 1000 characters, which is a conservative bound, and the current term set
  fits in one group.
- Whether a page at offset 14500 with limit 500 succeeds. This is not reached in
  practice, because the largest unit so far is far below 15000 records.

## Costs

Free and keyless. Requests used by S8.2 so far: 6 smoke requests, 2 offset and
limit checks, and 4 live requests from the incremental run.

## Term set and sweeps

Phrases come from `core_terms` in `config/queries.yml`. Each term also gets a
plural form if it does not already end in `s`. The phrases are OR-joined and
quoted: microplastic(s), nanoplastic(s), micro-plastic(s), nano-plastic(s),
micro-sized plastic(s), microsized plastics, plastic pollution(s), plastic
debris(es), plastic litter(s), marine debris(es), marine litter(s), plastic
particle(s), plastic fragment(s), plastic ingestion(s), resin pellet(s), and
plastic pellet(s). The qualified terms (microfiber, tire wear, plastic waste)
need context and are left to the local `plastic_related` rule in
`normalize_grant`.

Each fiscal year runs two sweeps. Sweep `ca` adds `org_states: ["CA"]`. Sweep
`terms` is the term set alone and catches out-of-state recipients. Both sweeps
are kept. The sweep and fiscal year that reported each grant are stored in the
state file (`provenance`), not in the C3 row.

## Incremental and backfill

- Backfill covers the last 15 fiscal years, newest first. Fiscal years start on
  1 October. Completed `fy:sweep` units are skipped on a rerun.
- Incremental refetches the current and previous fiscal year, both sweeps. The
  current year is 2027 on 2026-11-10.
- A unit is applied only after all its pages are fetched. Applying a unit drops
  its previous provenance and adds the new one. A grant is kept while at least
  one unit still reports it.
- Request cap (`--max-requests`, default 25) includes retries. Reaching the cap
  yields status `partial`, and the completed units are applied.
- HTTP errors (after 3 retries on 429 and 5xx) and offset-ceiling failures yield
  status `deferred`. Nothing is written, so prior output and state are kept.

## Live run (2026-11-10)

`py -3.14 scripts/ingest_nih_reporter.py --incremental --max-requests 10`:
status `ok`, 4 requests, 4 units, 0 invalid records skipped, 61 rows written to
`data/interim/grants/nih_reporter.parquet`. Only counts are recorded here.
Per-unit provenance counts: FY2026 `terms` 61 grants, FY2026 `ca` 6 grants (all
six also appear in `terms`), FY2027 both sweeps 0 grants. The 0 for FY2027 was
not investigated further; it may reflect how recently the fiscal year began.

No full backfill has been run.
