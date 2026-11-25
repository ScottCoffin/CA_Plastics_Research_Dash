# Global denominator series (BQ-2.1, BQ-2.2)

Built by `py -3.14 scripts/build_denominator_series.py` from stored files. The builder makes no
network calls. The only fetcher for these series is `scripts/fetch_denominator_series.py` (BQ-2.2).
Output: `data/processed/analytics/denominator_series.json` (gitignored; not published).
BQ-2.4 publishes `site/data/global/denominators.json` later. This work does not change `site/data/`
or the Evidence Map panel.

Series are declared in `config/denominator_series.yml`. The code is `src/atlas/analytics/denominators.py`.
Counts below come from the live fetches of 2026-11-23 UTC (A-all and A-article_review at 05:41 UTC; B on
the v0 set later that day) and the build of the same day.
The last complete year is 2025.

## Counting units

There are two units. A ratio is allowed only inside one unit.

- **OpenAlex records.** Each OpenAlex work ID is one record, counted in its publication year.
  Records of the types erratum, peer-review, retraction and paratext are removed. Duplicate records are
  counted, not merged. Retracted-flagged articles stay in. This is the unit of series A, B and C.
  The article+review sensitivity series use the same unit, restricted to OpenAlex types article and review.
- **Curated works.** One row per work in the published site index, after owner labels and
  curation removals. This is the unit of series D and B2.

## Series

| ID | What it counts | Scope | Status | 2025 count |
|---|---|---|---|---|
| A | Every OpenAlex record the plastics query v3.1 matches, all types | global | available (cache `A-all`) | 23,758 |
| A-article_review | Same, OpenAlex types article or review only (sensitivity) | global | available (cache `A-article_review`) | 17,949 |
| B | Pollution-core v0 (A3 section 5.3, 29 core terms): same exclusions and type filters as A | global | available (cache `B-all`) | 16,263 |
| B-article_review | Same as B, types article or review only (sensitivity) | global | available (cache `B-article_review`) | 12,176 |
| B2 | Lifecycle-and-society hits with plastics_centrality primary or substantial | global | waits_for BQ-S3 | not computed |
| C | California-connected records that the OpenAlex query matched | California | available | 252 |
| D | Published works with plastic_related true | California | available, beside only | 228 |

Counts include the retracted records that are in each series. The 2026 values are partial.

2025 shares: B/A is 68.5% (16,263 / 23,758). The article+review pair gives 67.8% (12,176 / 17,949).
The v0 set replaced an earlier B that used all 38 `queries.yml` core terms (2025: 18,280, 76.9% of A).
That set included lifecycle terms (recycling, single-use, biodegradable, circular economy), so it is not used.
C/A is 1.06%. The builder reports these from the same fetch run, so the B/A pair is one snapshot.

## Fetch and cache (BQ-2.2)

    py -3.14 scripts/fetch_denominator_series.py --dry-run       # print the four URLs; no call
    py -3.14 scripts/fetch_denominator_series.py                 # cached unless stale or changed
    py -3.14 scripts/fetch_denominator_series.py --force         # refetch regardless of cache
    py -3.14 scripts/fetch_denominator_series.py --allow-stale   # exit 0 on a refused refresh

### The four requests

Each series is one `group_by=publication_year` request on the works endpoint. The filter clauses are:

| Series | Filter clauses |
|---|---|
| A-all | the v3.1 query (`title_and_abstract.search`, with its exclusions) and `exclude_types`. Same clauses as `scripts/fetch_trend_global.py`, which a test checks. |
| A-article_review | A-all plus `type:article\|review` |
| B-all | the pollution-core v0 terms from `config/pollution_core_v0.yml` (A3 section 5.3; 29 terms in `queries.yml` spelling), rendered like the query, with the query's exclusions and `exclude_types`. No qualified or lifecycle terms. B is inside A. |
| B-article_review | B-all plus `type:article\|review` |

There is no language filter in any series. A test checks every URL. Each URL is well under the
8,000-character limit (about 1,600 characters for B and 3,500 for A).

### Cache

- File: `data/interim/denominator_series_cache.json` (gitignored). Schema `denominator_series_cache.v1`.
- Key: `series id|query version|filter digest`. The digest is the first 16 hex characters of the
  SHA-256 of the joined filter clauses, so any change to a term, a type or a sensitivity clause makes
  a new key. A query version change therefore invalidates every entry.
- Entry fields: `series_id`, `query_version`, `filter_digest`, `filter` (audit copy, no key),
  `fetched_at`, `source`, `by_year`, `stale`, `stale_reason`, and `refused_at` when a refresh was refused.
- Freshness: an entry is fresh for 30 days after `fetched_at`, unless it is flagged stale. Freshness is
  checked per series, so one aged series is refetched alone.
- Older entries for other keys are kept. They are never used for another key.

### Shared request path

Each request goes through the same pieces as `fetch_evidence_cells.py` and `fetch_trend_global.py`:

- `atlas.ingest.openalex._request_json` with at most 3 HTTP attempts (`MAX_HTTP_ATTEMPTS`), so
  its 429 back-off and key fallback apply.
- The budget guard from `config/budget.yml`, with today's logged usage from `data/logs/api_usage.jsonl`.
  The guard is checked before each request and again after each response.
- A run credit cap of 100 credits (`RUN_CREDIT_CAP`). Before each request the run must have room for
  that request's worst case (3 attempts at 10 credits each).
- `ApiCostLogger`, run id `denominator-series-<timestamp>`.

The OpenAlex key is loaded by the shared loader from `.env`, as in the other fetchers. The script
does not print it.

### Costs

A full refresh is four requests at about 10 credits each: about 40 credits, roughly USD 0.004.
A 30-day refresh cycle is therefore about 40 credits a month. The run cap is 100 credits. The daily
guard in `config/budget.yml` still applies on top of that.

Credits spent on 2026-11-23: 40 for the first four-series fetch (B on the earlier 38-term set), then
20 for the B refetch on the v0 set (two requests). The old B entries stay in the cache under their old
keys. The builder ignores them. A changed term set changes the B key, so it refetches B alone.

### Refusals, stale values and exit codes

A refused refresh is one of: HTTP 429 from OpenAlex, a plan refusal (HTTP 403 "plan upgrade
required"), the local budget guard, or the run credit cap. A refusal never keeps the old values
silently:

- The run stops at the refusal. No further requests are sent.
- Each series that could not be refreshed keeps its cached values, flagged `stale: true` with a
  `stale_reason` and `refused_at`. The values are not deleted.
- The script exits 1.
- `--allow-stale` exits 0 when every refused series still has cached values. It prints a warning
  that names the stale series. If a refused series has no cached values, the run still exits 1, because
  there is nothing to serve.

Any other failure (for example HTTP 500) also stops the run and exits 1, even with `--allow-stale`.
Series not refreshed in that run are flagged stale in the same way.

The daily job should use `--allow-stale`. The lead decides whether to add it to the daily workflow.
This work does not add it.

### Stale in the builder

The builder reads the same cache. Each cache-backed series carries a `cache` object in
`denominator_series.json`: `query_version`, `filter_digest`, `fetched_at`, `stale` and `stale_reason`.
An entry is also stale when it was fetched 30 or more days before the as-of date, even without the flag.
A missing entry for the active query and filters is an error: the builder never falls back to another entry.
The builder's summary line marks a stale series with `(stale)`.

## Sensitivity series

`A-article_review`, `B-article_review` and any future sensitivity series declare `sensitivity: article_review`
in the config. Their counting unit text names the restriction, so they are never compared with an
all-types series. The ratio guard refuses a pair with different sensitivities, and it also refuses a
pair whose counting unit text differs. OpenAlex document types are imprecise (Céspedes et al. 2025),
so the sensitivity series show how far the type restriction moves the share.

## Ratios

| Ratio | Allowed | Why |
|---|---|---|
| B / A | Yes | Same OpenAlex-records unit, same sensitivity (all types), same fetch run. |
| A-article_review / B-article_review | Yes | Same unit text and sensitivity. |
| C / A | Yes | Same OpenAlex-records unit. C is the California share of the query count. |
| A / B-article_review | No | Different sensitivity and unit text. The guard raises. |
| anything with D | No | Curated works. Shown beside only. |
| anything with B2 | No | Labelled precision. Shown beside only until BQ-2.3 decides. |

The builder checks these rules when the config loads and again when series are built. A pair with
different `counting_unit` text raises an error, and so does a pair with different sensitivity. So does a
one-sided pair, or a beside-only series in a pair. The output lists the allowed pairs in `ratio_pairs`.

## Changes from the BQ-2.1 build

- **B is pollution-core v0, not all core terms.** BQ-2.1 named B as the query's `core_terms`. The first
  BQ-2.2 fetch used all 38 of them, which included lifecycle terms. B now reads
  `config/pollution_core_v0.yml` (A3 section 5.3). A test checks that every v0 term is a `queries.yml`
  core term and that no lifecycle term is in v0.

- **A (all types) now comes from the cache** (`A-all`), not from `site/data/global/trend_global.json`. Both
  use the same filter. The cache entry was fetched in the same run as B, so B/A is one snapshot. The
  2025 count moved from 23,450 (trend file, fetched 2026-11-12) to 23,758 (cache, 2026-11-23 UTC), which is
  +308 (+1.3%). C/A now divides by the newer A.
- The Evidence Map trend panel was moved to `site/data/global/denominators.json` by BQ-2.4 (see the share section above).
- The builder no longer reads `site/data/global/trend_global.json`. Its inputs are the cache, `site/data/california/index.json`,
  `works.parquet` and `works_raw.parquet`.

## Evidence Map share (BQ-2.4 changed it to C/A)

Before BQ-2.4, the panel's California share divided the published index totals for each year by the trend file's A. That mixed curated works (one row per work, including works labelled not plastic-related) with OpenAlex records, so it was not like for like. The panel now shows C/A from `site/data/global/denominators.json`: California-connected OpenAlex records over all OpenAlex records matching the same query, for complete years. Published plastic-related works (D) sit beside the share and are never divided. The panel no longer reads `site/data/global/trend_global.json`; that file is unchanged.

## Series C: California-connected records the query matched

- **Is:** OpenAlex records whose corpus work has `ca_any_author` true, and whose route applied the
  OpenAlex query. Three routes qualify: the query ingest (`openalex-works`), the Europe PMC audit
  (`europepmc-audit`, search AND DOI) and the eScholarship audit (`escholarship-ingest`, location AND
  query). Each duplicate record counts on its own, so the unit matches A.
- **Is not:** all of the regional corpus. The 2025 build leaves out 31 California records from the
  ORCID and ROR DOI routes. Those used a local text rule, not the OpenAlex query. It also leaves out
  60 corpus works that have no California authorship. Those 60 are kept in the corpus but not
  published.
- **Retractions:** the `retracted` field counts retracted records inside `count`. Two raw records are
  retracted. One is a kept work from 2024. The other is a 2025 duplicate record from the Europe PMC
  route, collapsed into a work that is not retracted. Each record counts with its own flag.
- **Possible overcount:** 81 records on the query ingest route carry Moore Institute or Algalita text
  in their raw OpenAlex record. Some of them may have come through the Moore scope unit, which was
  fetched without the query term. Stored fields cannot tell those apart from query matches. So C can
  overstate query-matched output by at most that residual.

### Provenance of C (the [VERIFY] field)

**Answer: the normalized table has no field that says how a row entered. The raw table has a route
field (`source_run_id`) that shows whether the OpenAlex query applied. That gets close, but it is not
an exact query match.**

- `data/processed/normalized/works.parquet` has no entry-route column. Its columns are work
  identifiers, year, type, CA flags, `first_seen` (fetch time) and `duplicate_work_ids`. `ca_led` and
  `ca_any_author` describe California evidence, not how the record came in.
- `authorships.parquet` has `ca_basis` (`registry`, `raw_affiliation`, `author_carry_forward`,
  `escholarship`). It records why an authorship is California, not how the work was fetched.
- `data/interim/works_raw.parquet` has `source_run_id`. The builder reads it and joins by OpenAlex
  ID. It holds 2,100 records: the 2,061 corpus works plus 39 collapsed duplicates. Routes by prefix:

| Route (source_run_id family) | Records | Did the OpenAlex query apply? | How it was written |
|---|---|---|---|
| `openalex-works` | 1,904 | Yes, except the Moore scope unit | query ingest, `src/atlas/ingest/openalex.py` |
| `europepmc-audit` | 10 | Yes (search AND DOI) | `scripts/audit_europepmc_recall.py`; `fetch_openalex_by_doi` default |
| `escholarship-ingest` | 19 | Yes (location AND query) | `scripts/audit_escholarship_openalex.py`, then `scripts/ingest_escholarship_works.py` |
| `orcid-doi-ingest` | 165 | No (DOI only; local text rule) | `scripts/ingest_orcid_dois.py` with `with_query=False` |
| `ror-researcher-doi-ingest` | 2 | No (DOI only; local text rule) | same script, DOI file input |

- The normalizer drops `source_run_id`, so the route is not in `works.parquet`.
- Inside the `openalex-works` route, the ingest runs several unit types. Institution batches,
  author-anchored units and the raw-affiliation "California" unit all AND the query term. The
  always-include Moore scope unit does not. All of them share one run prefix.
- All 167 ORCID and ROR records are California-connected. C leaves them out because the OpenAlex
  query did not select them.

**So "query-matched only" is possible only in part.** The route prefix removes the ORCID and ROR
records exactly. It cannot remove the Moore-scope residual. Exact matching would mean asking OpenAlex
again for every record, which needs the network and is out of scope here.

### Series D: published plastic-related works

- **Is:** the published works in `site/data/california/index.json` with `plastic_related` true, counted by year.
  Owner labels and curation removals apply. The count was 1,602 across all years.
- **Is not:** a query count. Its unit is curated works, so it is never divided by A or C. It is
  shown beside them.
- **Retractions:** the index has no retraction field. The builder joins `is_retracted` from the
  normalized works table by work ID. One published work is retracted.

## Known limits (for review)

- **B is pollution-core v0 (A3 section 5.3), and v0 omits three qualified context terms.** A3 section
  5.3 reads "plus qualified microfiber, tire wear and litter terms". The config lists them under
  `qualified_not_included_v0` instead, so B has no qualified clauses. This follows the lead's instruction
  and is the same B used for the PubMed R2 reference set. The lead should confirm the reading of A3.
- **Excluded from v0.** Eight lifecycle core terms (recycling, recycled plastic, single-use and
  biodegradable plastic, circular economy) and the qualified LCA and bioplastic terms are left out by
  omission. The singular "anthropogenic microparticle" in `queries.yml` is also left out, because A3 lists
  only "anthropogenic microparticles". It still counts in A, which uses the full query, but not in B. Confirm
  whether it should join v0.
- **PubMed R2 uses the same v0 terms.** `config/pubmed/r2_include.txt` was regenerated from
  `config/pollution_core_v0.yml` (29 `[tiab]` phrases). The live PubMed query has not been run.
- **Year range of the A-all response.** The live fetch returned 103 year groups for A-all (the fetch
  reports 136,068 records in all years). The BQ-2.1 note described the trend file as having 175 years,
  1853 to 2027. This build did not check the early years. Before relying on years before 1925, check
  the year range of the cache entry.
- **Partial years.** `last_complete_year` is the as-of year minus one. Every year from the as-of year
  onward is flagged `partial_year` in every series. The as-of date defaults to today (UTC).

## Metrics (BQ-2.3)

The builder adds a `metrics` block to `data/processed/analytics/denominator_series.json`. The code is
`src/atlas/analytics/trend_metrics.py`. The block gives counts, index, shares for the allowed ratio pairs,
and a log-linear CAGR with a 95% interval for each computed series. BQ-2.4 publishes it later. Nothing is
written to `site/data/`.

### Window, base year and exclusions

- **Window.** Complete years only: from 2006 to `last_complete_year` (2025 for the 2026-11-23 build). The
  as-of year and later (2026, 2027) are excluded and listed in `partial_years_excluded`. If the series starts
  after 2006, the window starts at its first year. `window.requested_start` keeps the configured value.
- **Base year.** `window.base_year` is the window start. The index is the value divided by the value in the
  base year. It is blank when the base value is zero.
- **Options.** An optional `metrics` block in `config/denominator_series.yml` can set `window_start` and
  `base_year`. The committed config has no such block, so the defaults apply.
- **Retractions, per series.** C and D exclude retracted-flagged records: count = records minus `retracted`.
  A, A-article_review, B and B-article_review cannot exclude them, because the OpenAlex group_by has no
  retraction split. Their counts include retracted-flagged records.
- **Retractions, in shares.** Both sides of a share keep the declared unit, so retracted-flagged records are
  included on both sides. C/A divides the C count that includes retractions. No share uses a
  retraction-excluded count, so the pair stays like for like.

### Ratios and shares

| Share | Numerator / denominator | Sensitivity |
|---|---|---|
| `B/A` | B / A | all types |
| `C/A` | C / A | all types. C has no article+review twin: no C sensitivity series is configured. |
| `B-article_review/A-article_review` | B-article_review / A-article_review | article and review only |

A share is taken only for a pair that `ratio_pairs` in the output lists. Each numerator is declared in
`SHARE_NUMERATORS` in `trend_metrics.py`. An allowed pair with no declared numerator raises an error. Series D
is beside-only and is never divided. B2 is not computed, so it has no metrics.

### Index and CAGR

- **Log-linear fit.** Ordinary least squares of ln(count) on calendar year over the years used. The slope is
  `b`, and CAGR = exp(b) - 1. A year with a zero count is skipped, because ln 0 is undefined. It is listed in
  `zero_years_skipped`, and `n_years` counts the years used. A share follows the same rule on ln(share), so
  the share CAGR is the growth of the numerator relative to the denominator.
- **95% interval.** exp(b ± t × SE(b)) - 1. SE(b) comes from the residual scatter, and t is the two-sided
  0.975 Student t quantile at df = n - 2. A CAGR needs at least 2 years, and the interval needs at least 3.
  With 2 years the CAGR is given without an interval.
- **t quantile.** Computed from the regularized incomplete beta function, so no scipy dependency is needed.
  `tests/test_trend_metrics.py` checks df 5, 10 and 18 against table values, and df 1 and 2 against closed
  forms.
- **What the interval means.** The interval reflects year-to-year scatter around a log-linear trend. It is
  not sampling error.

### Values from the 2026-11-23 build (window 2006 to 2025)

| Series | CAGR | 95% interval | Count 2006 to 2025 | Index 2025 |
|---|---|---|---|---|
| A (all types; retractions included) | 25.2% a year | 23.0% to 27.4% | 399 to 23,758 | 59.5 |
| A-article_review | 25.3% | 22.8% to 28.0% | 288 to 17,949 | 62.3 |
| B (pollution-core v0) | 34.7% | 32.1% to 37.2% | 78 to 16,263 | 208.5 |
| B-article_review | 34.7% | 31.8% to 37.6% | 57 to 12,176 | 213.6 |
| C (retractions excluded) | 24.1% | 20.6% to 27.7% | 2 to 251 | 125.5 |
| D (beside only; retractions excluded) | 25.9% | 22.2% to 29.7% | 2 to 228 | 114.0 |

| Share | Share 2006 | Share 2025 | Share CAGR | 95% interval |
|---|---|---|---|---|
| `C/A` | 0.50% | 1.06% | -0.9% a year | -4.6% to 3.0% |
| `B/A` | 19.5% | 68.5% | 7.6% a year | 6.6% to 8.5% |
| `B-article_review/A-article_review` | 19.8% | 67.8% | 7.5% a year | 6.5% to 8.4% |

The C/A share interval includes zero, so these data do not show a clear change in the California share of
the query count over 2006 to 2025.

### Limits for review

- **Early years of C and D are small.** Both have 2 records in 2006. Their index and CAGR depend on the window
  start, so a different `window_start` gives a different CAGR.
- **Zero years are skipped.** If a zero is a real zero, skipping it biases the trend upward. The 2006 to 2025
  window has no zero years in any series at this build.
- **The interval is descriptive.** It describes scatter around the fitted trend. It is not an uncertainty
  estimate for the population.
- **Evidence Map panel.** Since BQ-2.4 the panel shows C/A from `denominators.json`. Whether to show B/A there too is an owner decision.

## Published file (BQ-2.4)

`site/data/global/denominators.json` (schema `bq2-v1`) publishes the output above. `scripts/build_denominators_json.py` reads the ignored `data/processed/analytics/denominator_series.json` and writes the committed file; run `scripts/build_denominator_series.py` first. Per series it holds the yearly counts (A, A-article_review, B, B-article_review, C, D; B2 is listed as not computed). It also holds the three allowed ratio pairs (`B/A`, `C/A`, `B-article_review/A-article_review`), the BQ-2.3 `metrics` block, a version block, and a plain-language "what this is and is not" text. The labels are public wording: the internal notes and dependency names are not copied.

The builder refuses any pair that is not in its allowlist. It also refuses a pair whose two sides differ in counting unit, sensitivity or `comparable_with` listing. D and B2 are never a ratio part. `--check` validates the committed file. When the ignored input exists, it also fails when the file differs from a rebuild (stale). When the input is absent (CI has no `data/` tree), the staleness check prints SKIP and the command exits 0.

Pages read the file lazily. The V-4 trend panel on `/california/evidence` draws C/A, with D shown beside it and never divided. The Trend tab on `/explore` shows B/A at world scope as a line under the counts. Both show the file's "what this is and is not" text.

## Output file

- `as_of`, `last_complete_year`, `query_version`.
- `series`: one object per computed series with `counting_unit`, `scope`, `source`, `status`,
  `sensitivity`, `comparable_with`, `beside_only`, `retractions`, `undated`, and `years`. Cache-backed
  series also have `cache` (see above). C also has `route_records`, the record count per route family
  over all records.
- `years`: one row per year from the earliest to the latest year in any series. Rows hold `count`,
  `retracted` and `partial_year`. C also has `other_route`.
- `not_computed`: B2 with its status and the task it waits for.
- `ratio_pairs`: the allowed pairs among computed series.
- `inputs`: the path and SHA-256 of each input file, including the cache. `--check` uses these to detect a stale output.
- `metrics`: the BQ-2.3 block (see "Metrics (BQ-2.3)"): `window`, `partial_years_excluded`, `method`, `series` (counts,
  index and trend per series) and `shares` (per allowed ratio pair).

## Commands

    py -3.14 scripts/fetch_denominator_series.py --dry-run     # URLs and cache state; no call
    py -3.14 scripts/build_denominator_series.py              # write the JSON
    py -3.14 scripts/build_denominator_series.py --check      # fail when stale; SKIP when inputs are absent
    py -3.14 -m pytest -q tests/test_fetch_denominator_series.py tests/test_denominator_series.py tests/test_trend_metrics.py

`--check` also reports stale when the date changes, because the partial-year flags depend on the
as-of date.
