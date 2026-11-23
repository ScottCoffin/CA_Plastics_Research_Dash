# Global denominator series (BQ-2.1)

Built by `py -3.14 scripts/build_denominator_series.py` from stored files only. No network calls.
Output: `data/processed/analytics/denominator_series.json` (gitignored; not published).
BQ-2.4 publishes `site/data/denominators.json` later. This task does not change `site/data/`
or the Evidence Map panel.

Series are declared in `config/denominator_series.yml`. The code is `src/atlas/analytics/denominators.py`.
Counts below are from the build of 2026-11-23 (UTC). The last complete year is 2025.

## Counting units

There are two units. A ratio is allowed only inside one unit.

- **OpenAlex records.** Each OpenAlex work ID is one record, counted in its publication year.
  Records of the types erratum, peer-review, retraction and paratext are removed. Duplicate records are
  counted, not merged. Retracted-flagged articles stay in. This is the unit of series A, B and C.
- **Curated works.** One row per work in the published site index, after owner labels and
  curation removals. This is the unit of series D and B2.

## Series

| ID | What it counts | Scope | Status | 2025 count |
|---|---|---|---|---|
| A | Every OpenAlex record the plastics query v3.1 matches | global | available | 23,450 |
| B | Pollution-core tier, same count basis as A | global | pending_fetch (BQ-2.2) | not computed |
| B2 | Lifecycle-and-society hits with plastics_centrality primary or substantial | global | waits_for BQ-S3 | not computed |
| C | California-connected records that the OpenAlex query matched | California | available | 252 |
| D | Published works with plastic_related true | California | available, beside only | 228 |

Counts include the retracted records that are in each series. The 2026 values are partial (see below).

### A: global query count

- **Is:** the number of OpenAlex records that match the active plastics query, minus the four excluded
  types. It is fetched by `scripts/fetch_trend_global.py` with one `group_by` request.
- **Is not:** a list of plastics papers. The query is a title and abstract search. It also matches
  some records that are not about plastics. C carries the same false matches, because it is a subset
  of the same query.
- **Retractions:** A cannot leave them out. The `group_by` request has no retraction split, so the
  `retracted` field is null for every year.
- **Years:** the file has 175 years, 1853 to 2027. It has 25,576 records for 2026 (partial) and
  7 future-dated records for 2027 (partial).

### B and B2: not yet computed

- **B** (pollution-core, global) needs a new OpenAlex fetch. BQ-2.2 adds it. Once fetched it uses
  the same unit as A, so B/A can be a like-for-like share.
- **B2** (lifecycle-and-society with plastics_centrality primary or substantial) is built from labels.
  Its precision is estimated on its own (A3 P4). It waits for BQ-S3. It is shown beside A and never
  divided until BQ-2.3 decides how to treat that precision.

### C: California-connected records the query matched

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

### D: published plastic-related works

- **Is:** the published works in `site/data/index.json` with `plastic_related` true, counted by year.
  Owner labels and curation removals apply. The count was 1,602 across all years.
- **Is not:** a query count. Its unit is curated works, so it is never divided by A or C. It is
  shown beside them.
- **Retractions:** the index has no retraction field. The builder joins `is_retracted` from the
  normalized works table by work ID. One published work is retracted.

## Provenance of C (the [VERIFY] field)

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

## Ratios

| Ratio | Allowed | Why |
|---|---|---|
| C / A | Yes | Same OpenAlex-records unit. C is the California share of the query count. |
| B / A | Later | Same unit. Allowed once BQ-2.2 fetches B. |
| anything with D | No | Curated works. Shown beside only. |
| anything with B2 | No | Labelled precision. Shown beside only until BQ-2.3 decides. |

The builder checks these rules when the config loads and again when series are built. A pair with
different `counting_unit` text raises an error. So does a one-sided pair, or a beside-only series in
a pair. The output lists the allowed pairs in `ratio_pairs`. In this build it lists only `["A", "C"]`.

## Current Evidence Map share (not changed here)

The panel's California share divides the published index totals for each year by A. The index
has 268 works for 2025. Of those, 40 are labelled not plastic-related. C counts 283 California records
for 2025 (252 on query routes plus 31 from DOI routes, duplicates included). The gap of 15 is
duplicates and curation removals. So the current share is not like-for-like with A. It counts curated
works, not OpenAlex records. It also counts works labelled not plastic-related. BQ-2.2 and BQ-2.3
should decide whether to switch the panel to C.

## Partial years

`last_complete_year` is the as-of year minus one. Every year from the as-of year onward is flagged
`partial_year` in every series. The as-of date defaults to today (UTC), so the flags move forward
when the builder reruns.

## Output file

- `as_of`, `last_complete_year`, `query_version`.
- `series`: one object per computed series with `counting_unit`, `scope`, `source`,
  `comparable_with`, `beside_only`, `retractions`, `undated`, and `years`. C also has `route_records`,
  the record count per route family over all records.
- `years`: one row per year from the earliest to the latest year in any series. Rows hold `count`,
  `retracted` and `partial_year`. C also has `other_route`.
- `not_computed`: B and B2 with their status and the task they wait for.
- `ratio_pairs`: the allowed pairs among computed series.
- `inputs`: the path and SHA-256 of each input file. `--check` uses these to detect a stale output.

## Commands

    py -3.14 scripts/build_denominator_series.py           # write the JSON
    py -3.14 scripts/build_denominator_series.py --check   # fail when stale; SKIP when inputs are absent
    py -3.14 -m pytest -q tests/test_denominator_series.py

`--check` also reports stale when the date changes, because the partial-year flags depend on the
as-of date.
