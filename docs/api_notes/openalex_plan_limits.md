# OpenAlex plan limits for the works ingest

Status: 2026-11-17 (ING-SAFETY). Companion to [openalex_costs.md](openalex_costs.md),
which covers credits and the daily budget guard. Filter behaviour is taken from the
2026-11-06 probe in [openalex.md](openalex.md), the 2026-11-16/17 CI failures reported
by the owner, and the owner's plan notes. The filter lists below are not re-verified
against OpenAlex's live documentation.

## Filters the ingest relies on

| Filter | Where the ingest uses it | Plan status |
| --- | --- | --- |
| `from_publication_date`, `to_publication_date` | Incremental and backfill windows (`build_works_url`) | Free. HTTP 200 in the 2026-11-06 probe. |
| `title_and_abstract.search` | Always-include scope filters in `config/queries.yml` | Free, per the owner's plan notes. |
| `institutions.id` | Institution units (batches of at most 100 IDs) | Free, per the owner's plan notes. HTTP 200 in the 2026-11-06 probe. |
| `authorships.author.id` | Author-anchored units (at most 25 IDs) | Free, per the owner's plan notes. |
| `raw_affiliation_strings.search` | Raw-affiliation scope unit (`California`) | Not on the owner's list. Plan status not confirmed. The owner attributes the 2026-11-16/17 failures to `from_updated_date`, not to this filter. |

## Paid filters

| Filter | Status | Evidence |
| --- | --- | --- |
| `from_updated_date` | Paid "daily sync" filter (Member+ or Partner plan). | HTTP 403 "Plan upgrade required" in the scheduled ingest on 2026-11-16 and 2026-11-17. The 2026-11-06 local probe got HTTP 429 with "daily sync requires the Member+ or Partner plan". |
| `from_created_date` | Listed as paid with `from_updated_date` in the owner's plan notes. | Not used by this repository; not observed. |

`from_updated_date` is still reachable through the runner's `--updated-since` option,
but only as an explicit opt-in. The scheduled workflow never passes it.

## Incident: 2026-11-16 and 2026-11-17

The scheduled daily works ingest failed on both days. OpenAlex rejected the
`from_updated_date` request with HTTP 403 "Plan upgrade required", and the run exited
non-zero. The high-water mark did not move, so no data was lost, but nothing was
refreshed.

Changes made on 2026-11-17:

- **Incremental filter.** Incremental runs filter on publication date only:
  `from_publication_date` = high-water mark minus the lookback. The lookback is
  30 days by default (`INCREMENTAL_LOOKBACK_DAYS`).
- **Adaptive lookback.** After a gap without a successful run, the lookback widens to
  the days since that run plus 7 days, capped at 366. A failed run never advances the
  mark, so the next success re-reads the whole gap.
- **Weekly deep sweep.** On Sundays (UTC) the workflow passes `--deep-sweep`, which sets
  the base lookback to 180 days.
- **Plan classification.** HTTP 403 "Plan upgrade required" raises `OpenAlexPlanError`
  (a `RuntimeError`), and the message names the paid filter. The run fails; it does
  not defer.
- **Failure alert.** A failed refresh on a scheduled or manual run opens, or comments
  on, the issue "Daily ingest failing" (label `ingest-alert`). The next successful
  refresh comments "Recovered on <date>" and closes it. The alert body carries the
  redacted `OpenAlex HTTP ...` line written by `run_daily_works.py --failure-note`.

## Limits of this safety net

- **Plan refusal as HTTP 429.** The 2026-11-06 probe returned the plan message with
  HTTP 429. The runner treats 429 as a rate limit, so that refusal defers the run and
  does not alert. Only the 403 form is classified as a plan error.
- **Failures after a successful refresh.** A failure in normalization, labelling or
  export fails the job, but the alert steps only watch the refresh. They neither open
  an issue nor close an open one.
- **Deep-sweep cost.** The sweep still makes one publication-date window per unit, but
  the window is six times wider, so it pages through more works and uses more credits
  than a normal run. The daily budget guard in `config/budget.yml` bounds it. A budget
  stop defers the run and leaves the mark unchanged, so the next run retries.
- **Keys.** The failure note and the alert body never contain a key. Values from
  `OPENALEX_API_KEY` and `OPENALEX_API_KEY_ALT`, and `api_key=` or bearer patterns, are
  replaced before the note is written.
