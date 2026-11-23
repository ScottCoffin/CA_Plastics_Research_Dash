# OpenAlex operator limit (boolean title and abstract searches)

Checked 2026-11-18 offline. No live calls were made for this note. Owner rule A3-C1 applies:
repo-verified facts override the Add-on A3 spec, including its section 5.9 (see
[docs/add_on_spec_3.md](../add_on_spec_3.md)).

## The rule

- A `title_and_abstract.search` filter with more than 5 boolean operators (OR, AND, NOT)
  costs 10 credits per call.
- Such requests are limited to 5 requests per second. Over the limit, OpenAlex returns
  HTTP 429 with a message containing "wait 1s".
- They are throttled, not refused. A retry after a short wait succeeds.
- Source: MEMORY, "Verified API facts", entry "OpenAlex (2026-11-11)"; owner rule A3-C1.
- Spec section 5.9 says the existing fetcher does not handle 429. That is out of date. The
  shared client retries burst 429s (fixed after the 2026-11-10 burst). Every caller below
  goes through the shared client except where the table says otherwise.

Every shipped query is far above the limit. Counts from 2026-11-18, made by rendering each
query and counting explicit OR, AND and NOT tokens:

- `config/queries.yml` (the active query, plastic-v3.1): 169 with type exclusions, 155 without.
- `config/queries_v2.yml`: 43 with exclusions, 38 without.
- `config/queries_v3.yml`: 142 with exclusions, 128 without.
- `config/query_v2.txt` (the AT-1 audit input): 43.
- Repeat-sample filter (`added_only_filter` in `scripts/run_at1_repeat_sample.py`): 149.
- Leak-candidate place filter (`place_filter` in `scripts/fetch_leak_candidates.py`): 11.

## How the client handles it

In [src/atlas/ingest/openalex.py](../../src/atlas/ingest/openalex.py):

- `MIN_REQUEST_INTERVAL_SECONDS = 0.25` and `_throttle()`: each attempt waits so that requests
  from one process are at least 0.25 s apart, which is at most 4 per second.
- `_is_burst_limit(message)`: true when the lowercased message contains "per second" or
  "wait 1s".
- `_request_json(url, *, logger, attempts=4, timeout=60)`: on a burst 429 with attempts left,
  it waits and sends the same URL again. The wait is the `Retry-After` header when present
  (clamped to 1 to 30 s); otherwise it is 1 s, then 2 s, then 4 s (`_retry_delay`).
- On the last attempt, a burst 429 raises `OpenAlexRateLimitError`. The daily ingest in
  [src/atlas/ingest/daily.py](../../src/atlas/ingest/daily.py) reports that as a deferred run
  with reason `rate_limited`.
- A burst 429 never switches to the fallback key. Only a 429 without the burst wording does.
- Tests: [tests/test_openalex_operator_limit.py](../../tests/test_openalex_operator_limit.py)
  (this rule, offline) and `test_burst_rate_limit_429_is_retried_not_deferred` in
  [tests/test_openalex_budget.py](../../tests/test_openalex_budget.py).

## Callers that send a search over the limit

"Yes" means the call sends a `title_and_abstract.search` filter with more than 5 operators.
Credits use the 10-per-search rule above. A figure is cited only where the script states it.

| Caller | Sends over-limit search? | Through `_request_json` (throttle and retry)? | Requests per run | Credits per run | Schedule |
|---|---|---|---|---|---|
| [scripts/run_daily_works.py](../../scripts/run_daily_works.py) (`atlas.ingest.daily`, `ingest_live` in openalex.py) | Yes, for institution, author and raw-affiliation units (`openalex_filter(config)`). Always-include scope units do not send it. | Yes (4 attempts) | One per cursor page per unit; not fixed in code | 10 per page; stopped by the daily budget guard in `config/budget.yml` | Daily, [ingest_works.yml](../../.github/workflows/ingest_works.yml) cron `17 10 * * *` |
| [scripts/fetch_author_metrics.py](../../scripts/fetch_author_metrics.py) (plastics pass) | Yes (`plastic_works_url`). The `/authors` list calls do not search. | Yes (4 attempts) | Cursor pages per author batch; incremental | 10 per page; 1 per `/authors` call (script docstring) | Daily step after a successful refresh (ingest_works.yml) |
| [scripts/build_global_counts.py](../../scripts/build_global_counts.py) | Yes (`group_by=authorships.countries` under `openalex_filter`) | Yes (`BudgetedRun.get`, 3 attempts) | 3 (script docstring) | 10 each (script comment); run cap 60 (`RUN_CREDIT_CAP`) | Daily, after a successful refresh (ingest_works.yml); output cached 7 days, so a real refresh is about weekly |
| [scripts/fetch_global_explore_sample.py](../../scripts/fetch_global_explore_sample.py) | Yes (`g.openalex_filter`) | Yes, through `build_global_counts.BudgetedRun` (3 attempts) | 35 per full refresh (docstring); a same-day rerun sends only missing requests | About 350 per full refresh (docstring) | Daily, after a successful refresh (ingest_works.yml); skipped while under 7 days old |
| [scripts/fetch_evidence_cells.py](../../scripts/fetch_evidence_cells.py) | Yes (`render_query` plus row and column terms) | Yes (`count()`, 3 attempts) | 30 (5 rows x 6 columns, one `per-page=1` count each) | 10 each, about 300 (script comment) | Daily, after a successful refresh (ingest_works.yml); cached 20 hours |
| [scripts/fetch_trend_global.py](../../scripts/fetch_trend_global.py) | Yes (`openalex_filter`) | Yes (3 attempts) | 1 `group_by` (docstring) | 10 (search rule; script states no figure) | Manual; in no workflow; cached 30 days |
| [scripts/fetch_leak_candidates.py](../../scripts/fetch_leak_candidates.py) | Yes, two `title_and_abstract.search` clauses: the active query (169) and the place filter (11) | Yes (4 attempts) | One probe (`per-page=1`), then cursor pages of 100; stops without pages if the count exceeds `--max-works` | 10 per request; the script assumes 10 when no credit is recorded | Manual |
| [scripts/run_at1_repeat_sample.py](../../scripts/run_at1_repeat_sample.py) | Yes (`added_only_filter`, 149 operators) | Yes (4 attempts) | One per institution stratum (docstring) | 10 per request (search rule; script states no figure) | Manual |
| [scripts/audit_europepmc_recall.py](../../scripts/audit_europepmc_recall.py) via [src/atlas/ingest/europepmc_audit.py](../../src/atlas/ingest/europepmc_audit.py) | Yes. `fetch_openalex_by_doi` defaults to `with_query=True`, and this caller does not override it. | Yes (`fetch_openalex_urls` calls `oa._request_json`, 4 attempts) | One per batch of up to 50 DOIs | 10 per batch | Manual |
| [scripts/audit_escholarship_openalex.py](../../scripts/audit_escholarship_openalex.py) | Yes (`page_url` uses `openalex_filter`) | Yes (via `fetch_openalex_urls`) | One per page, capped by `--max-credits` (default 1500) | 10 per page | Manual |
| [scripts/ingest_orcid_dois.py](../../scripts/ingest_orcid_dois.py) | No. It passes `with_query=False`, a plain filter. | Yes | One per DOI batch | 1 per list call (europepmc_audit.py docstring) | Manual |
| [scripts/run_at1_audit.py](../../scripts/run_at1_audit.py) | Yes (`config/query_v2.txt`, 43 operators) | **Yes, since OA-2 (2026-11-22).** Searches go through `atlas.ingest.openalex._request_json` (throttle, burst-429 retry, 4 attempts, each attempt charged). The fallback key is removed for the run because the preflight checks only the primary account. Only the `/rate-limit` status call keeps its own `urlopen`. | Up to 80 (`MAX_REQUESTS`) | 10 per call (search rule); credit cap 1000 (`MAX_CREDITS`) | Manual, `--live` only |

Callers that send no over-limit search:

| Caller | Sends over-limit search? | Through `_request_json`? | Requests per run | Credits per run | Schedule |
|---|---|---|---|---|---|
| [scripts/fetch_journal_metrics.py](../../scripts/fetch_journal_metrics.py) | No (an `openalex:` ID filter) | Yes | Batches of IDs | 1 per list call (script docstring) | Daily, after a successful refresh; continues on failure (ingest_works.yml) |
| [scripts/fetch_orcid_author_ids.py](../../scripts/fetch_orcid_author_ids.py) | No (ORCID lookups; the file has no search filter) | Yes | One per ORCID lookup | Not stated in the script | Manual |
| [scripts/benchmark_openalex_costs.py](../../scripts/benchmark_openalex_costs.py) | No (`search=plastic`, one term, no operators) | **No** (direct `urlopen`); this is a benchmark, not a fetcher | A few | Zero paid credits; acknowledgement flag required | Manual |
| [scripts/smoke/query_s1_5.py](../../scripts/smoke/query_s1_5.py) | Possibly. It uses `openalex_filter` (line 102) and a direct `urlopen` (line 48). Not traced in full. | **No** (direct `urlopen`) | Smoke run | Not stated | Manual smoke script; not run for this note |

Other paths checked:

- [src/atlas/ingest/institutions.py](../../src/atlas/ingest/institutions.py): its audit mode takes a
  `title_and_abstract.search` query file and sends it through the shared client. No script in
  `scripts/` passes `query_mode="audit"` (grep).
- [src/atlas/release.py](../../src/atlas/release.py) renders the query for a hash and sends no request.
- [scripts/check_s1_5.py](../../scripts/check_s1_5.py) checks the filter string and sends no request.

## Gaps and risks

1. **Fixed by OA-2 (2026-11-22).** `scripts/run_at1_audit.py` had no throttle and no burst
   retry, so the first burst 429 stopped the audit. Its searches now use `_request_json`.
   Open: transport errors (no HTTP response) retried by the shared client are not logged per
   attempt, so the audit counts them only once.
2. **`scripts/smoke/query_s1_5.py` makes a direct request with the active filter.** It is a
   smoke script, was not read in full, and was not run.
3. **The retry depends on message wording.** A burst 429 worded differently is treated as a
   daily-budget 429. With `OPENALEX_API_KEY_ALT` set, that switches the run to the fallback key.
   Watch the logs for new wording.
4. **Counting assumption.** The count uses explicit OR, AND and NOT tokens. The verified fact
   does not say whether implicit AND (whitespace) counts. Spec section 5.9 says it does not.
5. **The throttle is per process.** Parallel jobs are not paced against each other.
6. **Callers with `attempts=3`** (build_global_counts, fetch_evidence_cells, fetch_trend_global,
   the explore sample) defer the run after three burst 429s in a row.

## Replay harness split rule (BQ-S10)

Review search strings may be split into blocks only to retrieve IDs. Deduplicate the blocks by
OpenAlex work ID. Counts always come from one unsplit query, because split counts cannot be
summed (A3-C1). No replay harness exists in the repo yet (a grep for "replay" finds none), so
this is the rule it must follow. [scripts/fetch_evidence_cells.py](../../scripts/fetch_evidence_cells.py)
already follows the count half of the rule: its OR lists are never split across requests.
