# BQ-S9: PubMed coverage check, stage 1 (California)

Run: 2026-11-23 05:01 UTC (NCBI E-utilities, no API key, 3 requests per second). Payload:
`site/data/pubmed_coverage.json` (schema `bqs-pm-v1`), built by `scripts/build_pubmed_coverage_json.py`.

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
translation and per-partition counts. Stage 2 (global works) waits for BQ-V.2.
