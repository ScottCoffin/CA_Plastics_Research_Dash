# SPK-4: bit-mask facets vs Mosaic crossfilter (gate G-FACET)

Status: **INCOMPLETE.** Partial measurement at N = 30,000 with one run per page.
N = 100,000 was not measured. The Mosaic page fails its correctness check, so
its timings are not yet trustworthy as a comparison.

## Versions and dates

| Item | Version | Date / source |
|---|---|---|
| Mosaic core and sql (jsdelivr `+esm`) | @uwdata/mosaic-core 0.34.1 | npm `time`: 2026-10-24 (newest release at least 14 days old on 2026-11-09; 0.35.0 is 2026-11-03 and was excluded) |
| Mosaic DuckDB-Wasm | 1.33.1-dev57.0 (pulled in by mosaic-core) | via mosaic-core dependency |
| vgplot | 0.34.1 (2026-10-24) | pinned in the design; not loaded, because the spike needs no plots |
| Parquet writer | DuckDB 1.1.1 via `uv run --no-project --with duckdb==1.1.1` | nothing installed globally |
| Browser | Chromium 145.0.7632.6, headless | Playwright 1.58.0 (Python) |
| Interpreter | Python 3.14 (`py -3.14`) | |

## Method

- Data: seeded synthetic corpus (`build_bitsets.py`, seed 20261109). Twenty
  facets: year (37 labels), institution type (7), institution (150, Zipf-like),
  CA basis (4), OA status (5), study type (15), compartment (12, multi-label),
  8 domain tags and 5 flags (each one "yes" label).
- Bit-mask files (Appendix C): `works_index.json`, `facets.json`,
  `facets.bin` (header `BMF1`, version, N, nsets; uint32 LE words). Served
  gzipped by the local server.
- Filtering: AND across facets, OR within a facet. A label count is
  popcount(AND of the other facets' unions AND the label's bit-set), so each
  facet is counted without its own filter (cross-filter semantics).
- Mosaic: one `MosaicClient` per facet on a `Selection.crossfilter()`. Counts
  come from one SQL `count(*) FILTER` query per facet, run in DuckDB-Wasm over
  a Parquet table. Each query carries a sequence tag so stale results are ignored.
- Runner: `run_spike.py`. It serves pages from `scratch/spk4/www`, drives
  them in fresh browser contexts (cold start), applies 20 scripted filter
  changes, and checks 10 random states against a Python reference.

## Results (N = 30,000, 1 run per page)

| Metric | Bit-mask | Mosaic | Budget |
|---|---|---|---|
| Payload, raw | 1,223,017 B (3 files) | Parquet 186,163 B | landing <= 3 MB gz |
| Payload, transferred | 280,145 B (gzip) | 8,319,938 B (JS 300,957; DuckDB-Wasm 7,126,536; Parquet 186,163) | landing <= 3 MB gz |
| Cold start (navigation to first full counts) | 256 ms | 2,548 ms | interactive <= 2 s |
| Facet update, median of 20 ops | 1.35 ms | 127.9 ms | <= 50 ms |
| Facet update, max of 20 ops | 5.1 ms | 164.8 ms | <= 50 ms |
| Correctness vs Python (10 states, 2,430 counts) | 0 mismatches | 2,360 mismatches | must match |

Notes on the table:

- Payload raw for the bit-mask is the three uncompressed files. Gzip
  (level 9) of the same files is 275,146 B.
- Mosaic transferred bytes are measured per response with
  `Request.sizes()`. The DuckDB-Wasm binary dominates.
- The Mosaic update figures were taken before the final `setTimeout` change
  described below. They were not re-measured.

## Correctness

- Bit-mask counts match the Python reference on every state tested (0 of 2,430
  mismatched).
- Mosaic counts do not match. Counts for facets other than the last-updated
  one ignore the other facets' filters. Example: with year = 2010 and
  dom_marine = yes, the year count for 1990 was 131 (expected 15).
- Diagnosis so far: `Selection.predicate(client)` returns no filter when the
  active clause belongs to that client. Passing `noSkip = true` removed that
  path, but the mismatch remained. Next, `Param` writes `_value` only when its
  emitter flushes, so `predicate()` can read stale clauses right after
  `update()`. A macrotask yield was added before building queries, and the
  mismatch still remained. The bug is therefore not yet fixed or fully explained.

## G-FACET decision

Contract rule: main page = bit-masks if they win cold start (expected); Mosaic
for Explore only.

- Bit-masks win cold start at 30k (256 ms vs 2,548 ms) and win on payload and
  update latency. They meet the 30k budgets: facet <= 50 ms, landing <= 3 MB
  gzipped, interactive <= 2 s. **Provisional PASS for the main page.** The
  100k budgets (facet <= 150 ms) are not yet measured.
- Mosaic cannot be recommended for Explore yet. Its counts are wrong, and at
  30k it misses the facet budget (median 128 ms) and the interactive budget
  (2.5 s). **Mosaic leg: FAIL / unresolved.**

## Caveats

- Headless desktop Chromium on a development CPU. Numbers are relative, not
  production figures.
- Cold runs use a fresh browser context, so the browser cache is empty. The
  jsdelivr edge cache was warm from earlier requests, so the CDN leg is
  optimistic.
- Only one run per page was measured. Median and max are over 20 update
  samples, not five runs.
- Model-label confidence arrays are not shipped. Precedence (human label over
  thresholded model label) is applied at build time. The text-search bit-set
  (MiniSearch) is not implemented.
- The Mosaic page infers facet kinds from label names, not from a schema.
- Synthetic data only. Institution and domain distributions are illustrative.

## Reproduce

`py -3.14 spikes/spk4_facets/run_spike.py --sizes 30000 100000 --runs 5`
(outputs under `scratch/spk4/`, gitignored). This full run has not been completed.

## Final 5-run results (lead re-run, 2026-11-10)

`py -3.14 spikes/spk4_facets/run_spike.py --sizes 30000 100000 --runs 5`

| N | Engine | Cold start median / max (ms) | Update median / max (ms) | Transferred | Mismatches vs Python |
|---|---|---|---|---|---|
| 30k | bit-mask | 81.7 / 236.4 | 1.4 / 6.1 | 280,145 B (payload 275,146 B gz) | 0 / 12,150 |
| 30k | Mosaic 0.34.1 | 2,423.1 / 2,736.2 | 155.1 / 319.0 | 8,319,927 B (WASM 7,126,411) | 11,800 / 12,150 |
| 100k | bit-mask | 80.4 / 496.6 | 2.1 / 9.2 | 897,967 B (payload 892,872 B gz) | 0 / 12,150 |
| 100k | Mosaic 0.34.1 | 2,479.8 / 2,726.6 | 241.6 / 453.3 | 8,753,760 B | 11,580 / 12,150 |

**G-FACET decision (contract rule):** bit-masks win cold start at both sizes and
meet the budgets (facets ≤ 50 ms at 30k and ≤ 150 ms at 100k; landing ≤ 3 MB gz),
so the **main page uses Appendix C bit-masks**. Mosaic is not approved for Explore
(AT-6) until its counts match the Python reference. The suspected cause is a harness
crossfilter-semantics mismatch (Mosaic excludes a facet's own selection from its
counts), which AT-6 must settle before adoption.
