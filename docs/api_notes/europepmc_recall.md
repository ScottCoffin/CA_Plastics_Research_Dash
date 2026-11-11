# Europe PMC recall audit (S2.5b)

Status: benchmark measured 2026-11-11; the targeted OpenAlex ingest did NOT run because the
budget guard deferred it (no records added, 0 credits spent by this task).

## Query and method

Europe PMC REST (keyless), `resultType=lite`, cursor-paged:

`AFF:"California" AND (microplastic* OR nanoplastic* OR "plastic debris" OR "plastic pollution" OR "tire wear")`

Raw pages are cached under `data/raw/europepmc/` (ignored). Recall is the share of benchmark
records with a DOI whose normalized DOI (lowercase, resolver prefix stripped) is in
`data/processed/normalized/works.parquet`; the CA-published variant also requires
`ca_any_author`. Code: `src/atlas/ingest/europepmc_audit.py`,
`scripts/audit_europepmc_recall.py` (`--dry-run`, `--max-credits`), tests in
`tests/test_europepmc_audit.py`.

## Counts (2026-11-11)

| Measure | Count |
|---|---|
| Europe PMC records | 864 |
| With a DOI | 858 |
| In corpus (DOI match) | 438 (51.0%) |
| In corpus and `ca_any_author` | 438 (51.0%) |
| Published on the site (`site/data/index.json`) | 428 |
| Missing DOIs (planned for 9 OpenAlex batches of at most 50) | 420 |

Recall before: 51.0% (438/858). Recall after: not measured (ingest deferred); the earlier
probe (639 records, 323 missing) predates the raw-affiliation scope, which already recovered
part of the gap on the narrower query.

## OpenAlex DOI ingest: deferred

The guard (`resolve_openalex_budget`, `daily_logged_usage`) reported 12,630 credits already
logged today against the 10,000/day ceiling (9,500 abort threshold), so the first request was
refused with "credit limit lacks reserve for the next planned request". Nothing was fetched or
merged and `data/interim/works_raw.parquet` is byte-identical to before. Re-run after the
daily window resets:

`PYTHONPATH=src py -3.14 scripts/audit_europepmc_recall.py --max-credits 300`

then `py -3.14 scripts/normalize_openalex.py`. Expected cost is about 90 credits (9 calls).
The ingest gate keeps a fetched work only if a strict CA raw-affiliation match or a registry
institution is present, so non-CA works are never merged; normalize still decides `ca_any_author`.

## Spot check (20 random added CA works)

Pending the ingest run; none added yet.

## Caveats

- Europe PMC is biomedical-leaning (mostly MEDLINE); recall against it is a floor for
  environmental-health papers, not for the whole corpus.
- Records without a DOI (6) cannot be matched; DOIs containing a comma or pipe cannot be batched
  into an OpenAlex filter and are skipped.
- Europe PMC `AFF:"California"` also matches CA-named strings that the strict local matcher
  may reject; those would not enter the corpus by design.
