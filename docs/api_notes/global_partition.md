# Global partition of the raw store (PLAT-4b slice 1)

**Status: unpublished. Built 2026-11-25 on the one local trial page. A full run waits for the PLAT-4a backfill (owner H43 key).**

## Purpose

PLAT-4a stores the active plastics query for every OpenAlex work as gzip JSONL pages under
the ignored `data/raw/openalex_global/pages/`. This step reads those pages locally, with no
network call, and writes two ignored tables under `data/processed/global/`:

- `works.parquet`: one row per work. Pages are read in `fetched_utc` order and the latest
  page wins for each OpenAlex id.
- `work_regions.parquet`: one row per (work, region). A region is a predicate over the
  authorships: a country code, an ISO subdivision code, or a registry region slug. A work
  that touches several regions gets several rows, so assigning regions is a local join.

Nothing reads these tables for the site, the CA works table or the review exports.

## Command

```bash
py -3.14 scripts/partition_global.py                 # build both tables and print counts
py -3.14 scripts/partition_global.py --check         # validate; SKIP (exit 0) without raw pages
py -3.14 scripts/partition_global.py --raw-dir DIR --out-dir DIR
```

Writes are atomic (temp file, then replace). Rows are sorted by `work_id`, then by region
kind and code, so repeated builds from the same pages give the same bytes.

## Schemas

`works.parquet`: `work_id`, `doi`, `pmid`, `title`, `publication_year` (int32),
`publication_date`, `type`, `language`, `primary_topic_id`, `is_retracted`,
`cited_by_count`, `screening_status`, `query_version`, `query_hash`.

- `work_id` is the short OpenAlex id (`W...`). `primary_topic_id` is short too (`T...`).
- `pmid` comes from `ids.pmid`, compacted to digits: `https://pubmed.ncbi.nlm.nih.gov/123`
  becomes `123`. It is null when the record has no PubMed id.
- `screening_status` is always `unscreened_query_hit`.

`work_regions.parquet`: `work_id`, `region_kind` (`country`, `subdivision`,
`registry_region`), `region_code`, `basis`.

| region_kind | region_code | basis values |
|---|---|---|
| country | ISO alpha-2 from `authorships[].institutions[].country_code` (`institution_country`) or `authorships[].countries` (`author_country`) | `institution_country`, `author_country` |
| subdivision | ISO `CC-SUB` from `institutions[].geo.country_subdivision_code`, with the institution's country prefixed when the code has no dash | `institution_country` |
| registry_region | registry slug from `regions/_registry.yml` | `registry_institution` (an authorship institution id is in the region's institution registry), `registry_predicate` (institution geo region or subdivision, with the predicate's country codes), `raw_affiliation` (raw affiliation text) |

When two bases apply to the same (work, region), the stronger one is kept:
institution over author for countries, and for regions registry institution, then registry
predicate, then raw affiliation.

## Region predicates

Predicates are read from the registry through `atlas.regions.scope` (`country_codes`,
`institution_region_names`, `ror_subdivision_codes`, `raw_affiliation_terms`). The code
holds no region names.

- Institution match: the institution's country is in the predicate's country codes (an
  empty country also passes, as in `normalize.py`), and its `geo.region` or
  `geo.country_subdivision_code` is in the predicate's lists.
- Raw-affiliation match, default region: `normalize.matches_california_affiliation`. It is
  the engine's strict rule, and it excludes `Baja California` and the Pennsylvania and
  Missouri places. This is used because no scope helper can express the rule.
- Raw-affiliation match, other registry regions: a case-insensitive, word-bounded match on
  the registry's `raw_affiliation_terms`. No other region is registered yet.

## Institution registry join (PLAT-4b slice 2)

The default region's predicate sets `institution_registry: data/processed/institutions.parquet`
(the reviewed California institution registry, 4,677 OpenAlex ids). `scope.region_institution_ids`
reads it and keeps the rows that pass the same rule as `normalize`'s `ca_flag`
(`scope.registry_row_matcher`, shared by both). The partition loads the ids once per run.
A work matches the region with basis `registry_institution` when any `authorships[].institutions[].id`
is in that set. The raw-affiliation rule still applies on its own. A missing registry file gives
an empty set and a warning, so only raw-affiliation matches remain.

The field is validated: repo-relative, no `..`, no drive, `.parquet` suffix.

## Gaps (for orchestrator review)

1. **No institution geo in work records (closed for the default region by slice 2).** OpenAlex
   work records carry `institutions[]` with `country_code`, `ror` and `lineage`, but not `geo`.
   The trial page confirms this (483 institutions, 0 with `geo`). The registry join matches the
   institution id instead, so the default region no longer depends on `geo`. Subdivision rows
   still appear only if a record carries `geo`.
2. **No ROR subdivision in records.** The ROR field is a URL. The GeoNames subdivision code is
   not in the record, so `ror_subdivision_codes` matches only through the `geo` path above.
3. **Strict raw-affiliation rule is not a scope helper.** Only the default region has the
   Baja and Pennsylvania exclusions. Other regions get term matching until they have their
   own rule.

## BQ-V.2 acceptance (A3-C2)

| Item | Status |
|---|---|
| Cost estimate before the first run | Done in PLAT-4a (`--estimate`, 2026-11-25: 136,080 works, USD 1.438 maximum). See `docs/api_notes/global_raw_fetch.md`. |
| Works labelled "unscreened query hits" | Done here: `screening_status = unscreened_query_hit` on every row; `--check` fails on any other value. |
| `ids.pmid` kept | Done here: `pmid` column, compacted. The trial page has 31 of 100 works with a PMID. |
| Budget guard USD 0.95/day | PLAT-4a fetch (`DAILY_STOP_USD`, shared usage log). Nothing in this step calls the network. |
| No paid filters | PLAT-4a fetch: the query has no institution, California, author or paid filter. This step reads only local files. |

## Trial run (2026-11-25, one local page)

`py -3.14 scripts/partition_global.py` on `data/raw/openalex_global/pages/2025_00001.jsonl.gz`
(100 works):

- works: 100; works with pmid: 31; records without an OpenAlex id: 0
- top countries (works): IN 16, US 13, CN 9, IT 8, GB 7, ID 6, MY 6, ES 5, PK 5, JP 4
- works matching the default registry region: 1 (basis `registry_institution`; the count was
  also 1 before the registry join)
- `work_regions.parquet`: 127 rows

`--check` passes on these outputs. A full run waits for the PLAT-4a backfill. Paging is
blocked until the OpenAlex key (owner H43) is loaded, so only one page exists today.

## Not published

The tables keep raw affiliation strings out (only the derived region rows are written), but
titles and DOIs are in `works.parquet`. Nothing publishes from `data/processed/global/`.
Any later publishing step must apply the redaction used in `atlas.ingest.openalex`.
