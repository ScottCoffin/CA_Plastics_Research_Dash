# BQ-S9: PubMed coverage check, stage 1 (California)

Run: 2026-11-23 05:01 UTC (NCBI E-utilities, no API key, 3 requests per second). Payload:
`site/data/california/pubmed_coverage.json` (schema `bqs-pm-v1`), built by `scripts/build_pubmed_coverage_json.py`.

## What was measured

PubMed is an independent check. Two PubMed reference sets were restricted to records with a California
affiliation (`California[ad]`, which is approximate). For each set we counted how many of its PubMed records
are in the published Atlas corpus. This is **coverage of a reference set**, not recall: the reference set is
not a sample of a defined population, so no confidence interval is given (A3-D24).

| Set | Query | PubMed records | In the published Atlas | Coverage |
|---|---|---:|---:|---:|
| R1 | `"Microplastics"[MeSH Terms] AND California[ad]` | 178 | 163 | 91.6% |
| R2 | the 29 pollution-core v0 terms (A3 §5.3, `config/pollution_core_v0.yml`) as `[tiab]` phrases, `AND California[ad]` | 352 | 313 | 88.9% |

- Join: by PMID first (OpenAlex `ids.pmid`, now stored as `pmid` on normalized works), then by DOI. 871 of
  1,939 published works (45%) carry a PMID.
- R2 was first run with all 38 `core_terms` of `config/queries.yml` (387 records, 88.6%). That list includes the
  lifecycle terms A3 §5.3 excludes (recycling, single-use, biodegradable, ...), so R2 was rerun on 2026-11-23 with
  the 29-term pollution core (BQ-2.2 shares the list).
- Misses: 43 distinct PMIDs across R1 and R2. All 43 form the fixed-seed triage sample
  (`curation/pubmed_miss_triage_v1.csv`, seed 20261122; the 50 cap did not bind).
- MeSH indexing lags, so recent years look worse; see `coverage_by_year` in the payload.

## Miss triage (owner)

A miss is not automatically an Atlas error. The owner classifies each sampled miss in
`scripts/review_pubmed_misses_app.py` (HUMAN_TASKS H42) using `config/failure_taxonomy.yml`. BQ-S9 added two
`not_an_error` classes (affiliation not really California; plastics not central) and finalised the two PubMed
classes. Once labelled, the payload reports the false-negative share with a Wilson interval.

## How to rerun

```
py -3.14 scripts/qc_pubmed_coverage.py --reference-set r1 --affiliation California --start 1950/01/01 --live --no-cache
py -3.14 scripts/qc_pubmed_coverage.py --reference-set r2 --affiliation California --start 1950/01/01 --live --no-cache
py -3.14 scripts/build_pubmed_coverage_json.py
```

PubMed counts change daily; each run's manifest (in ignored `data/interim/pubmed/`) carries its timestamp, query
translation and per-partition counts. Stage 2 (global works) is in the next section.

## Stage 2 (global)

Run: 2026-11-26 01:09 UTC (R1) and 01:13 UTC (R2), NCBI E-utilities, no API key, 3 requests per second,
271 cached responses (one per successful request). Payload: `site/data/global/pubmed_coverage.json`
(schema `bqs-pm-v1`, `"scope": "global"`, `"stage": 2`), built by `scripts/build_pubmed_coverage_json.py --scope global`.
The global block is a separate file because the California payload is a California-only file; the stage 1
numbers and triage sheet are unchanged.

Method: the same two reference sets as stage 1, with the affiliation clause removed, so each covers all of
PubMed (1950/01/01 to the run date). The Atlas side is the ignored global works table
`data/processed/global/works.parquet` (136,074 works; sha256 `a9f927980a51d3eb43501b6d30fe99e27cb0912dc71fe80dec88861be3b31b0b`).
Join: PMID first, then DOI for PubMed records whose ESummary carries a DOI. Only 37,925 global works (27.9%)
carry a PMID, so most of the join runs through PMIDs. No manifest file exists for the global works table, so the
hash is of the parquet file itself.

| Set | Query (no affiliation) | PubMed records | Joined to global works | By PMID | By DOI | Coverage | Misses |
|---|---|---:|---:|---:|---:|---:|---:|
| R1 | `"Microplastics"[MeSH Terms]` | 16,076 | 15,932 | 15,920 | 12 | 99.1% | 144 |
| R2 | the 29 pollution-core v0 terms as `[tiab]` phrases | 20,285 | 19,733 | 19,720 | 13 | 97.3% | 552 |

- Coverage by year (payload `coverage_by_year`): R1 is 98.2% to 99.5% for 2020 to 2026 and 93.4% for 2019 (121
  records). R2 is 96.7% to 97.8% for 2019 to 2026. Years before about 2010 hold small counts, so single-record
  steps move the share a lot.
- The 2027 bucket (R1 27 records, R2 35 records) holds PubMed records dated after the run year (ahead-of-print
  dates). They are kept, labelled as they are.
- R1 needed 6 date partitions and R2 needed 33 across 29 OR chunks at the 9,500-record threshold. The 10,000
  cap never bound a single day.

Caveats:
- The Atlas side is unscreened query hits, so coverage here measures the query, not curation.
- The global works come from an Atlas plastics query. The overlap with the pollution-core terms is therefore
  expected, and high coverage partly reflects shared query terms. This is an inference from the query design, not
  checked against the Atlas query text, so read the 97% to 99% figures as a query-overlap check, not as
  independent evidence of completeness.
- Coverage of a reference set, not a completeness rate; no confidence interval (A3-D24).
- MeSH indexing lags, so recent years look worse.
- Miss lists are not published. They sit only in the ignored cache `data/interim/pubmed_global/`
  (`r1_misses.csv`, `r2_misses.csv`, written by the builder). Stage 2 misses are not triaged; the H42 sheet
  covers stage 1 only.

Rerun (live, then offline rebuild from cache; add `--no-cache` for fresh counts, which the live run did not use):

```
py -3.14 scripts/qc_pubmed_coverage.py --reference-set r1 --scope global --start 1950/01/01 --live
py -3.14 scripts/qc_pubmed_coverage.py --reference-set r2 --scope global --start 1950/01/01 --live
py -3.14 scripts/qc_pubmed_coverage.py --reference-set r1 --scope global --start 1950/01/01 --offline
py -3.14 scripts/qc_pubmed_coverage.py --reference-set r2 --scope global --start 1950/01/01 --offline
py -3.14 scripts/build_pubmed_coverage_json.py --scope global
py -3.14 scripts/build_pubmed_coverage_json.py --scope global --check
```

Run the two live commands one after the other, never in parallel: the rate limit is per process. Outputs go to
ignored `data/interim/pubmed_global/` (cache in `data/interim/pubmed_global/cache/`).
