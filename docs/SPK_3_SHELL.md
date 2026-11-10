# SPK-3: Shell bench (Observable Framework vs single-file) and SPK-2(a)

Measured 2026-11-09 (ADR-SPK-AUTH). Harness: `py -3.14 spikes/spk3_shell/run_bench.py`.

## Versions

| Item | Value |
|---|---|
| @observablehq/framework | 1.13.4 (pinned exact; published 2026-03-02, `npm view ... dist-tags.latest` = 1.13.4, ~8 months old) |
| Node / npm | v25.6.1 / 11.11.1 |
| DuckDB writer (SPK-2) | duckdb 1.1.1 via `uv run --no-project --with duckdb==1.1.1` |
| Framework's DuckDB-WASM | @duckdb/duckdb-wasm 1.29.0 (bundled by Framework) |

## Method

- Same app in both: 7 controls for 6 facets (year from/to, domain tags x8,
  facet tags x6, institution type, CA basis, OA toggle), a bar chart per year,
  a 100-row windowed table (24 px rows, spacer scroll), and a map placeholder.
- Datasets: `syn30k` and `syn100k` from `spikes/spk3_shell/gen_data.py`
  (seed 20261109+n, atlas works shape plus `institution_type` and `oa`), and the
  real fixture `site/data/index.json` (4 works; lacks those two fields, so they
  fall back to `unknown` / false).
- Framework side: no loaders; the page fetches `/data/<ds>.json` itself.
  Single-file side: one `index.html`, vanilla JS, no dependencies.
- Wire bytes: CDP `Network.loadingFinished.encodedDataLength` (includes
  headers), cache disabled, all responses gzip-encoded by the local server.
  Medians over 3 loads; bytes from the first load.
- TTI: `window.__ttiMs` (navigation start to first facet counts + table rendered).
- Facet latency: 20 scripted toggles x 3 loads = 60 samples; input event to render.

## Results

| App | Dataset | Shell gz | Data gz | Total gz (MiB) | TTI ms (med) | Facet ms med / max |
|---|---|---|---|---|---|---|
| single | syn30k | <0.01 | 0.98 | 0.98 | 273 | 4.0 / 7.8 |
| single | syn100k | <0.01 | 3.25 | 3.25 | 411 | 8.6 / 20.5 |
| single | fixture | <0.01 | 0.00 | 0.00 | 29 | 0.6 / 0.9 |
| framework | syn30k | 0.34 | 0.98 | 1.32 | 300 | 12.9 / 15.3 |
| framework | syn100k | 0.34 | 3.25 | 3.59 | 553 | 13.4 / 20.6 |
| framework | fixture | 0.34 | 0.00 | 0.34 | 185 | 13.1 / 15.7 |

Budgets:

| Budget | single | framework |
|---|---|---|
| Landing first load <= 3 MiB gz (shell only) | PASS | PASS (0.34) |
| Landing first load <= 3 MiB gz (shell + 100k data) | FAIL (3.25) | FAIL (3.59) |
| TTI <= 2 s (all datasets) | PASS | PASS |
| Facet latency median <= 50 ms at 30k | PASS (4.0) | PASS (12.9) |
| Facet latency median <= 150 ms at 100k | PASS (8.6) | PASS (13.4) |

The landing budget fails at 100k in both apps only because the synthetic
payload (40 MB raw JSON) is shipped to the page. The shell itself is well
under budget. Data delivery (pre-aggregated or Parquet) is a separate decision
and does not discriminate between shells.

Other measures:

| Measure | single | framework |
|---|---|---|
| Build time (median of 2) | n/a | 7.44 s |
| Dist, shell only (excl. DuckDB; 91.8 MB total) | 1 file, 123 LOC source | 48 files, 6.2 MB |
| LOC (non-blank: app source) | 123 (`single/index.html`) | 119 (`index.md` 114 + config 5) |
| Hours to parity (estimate, not measured) | ~3 h | ~4 h |
| Effort ratio (framework / single) | | ~1.3x (< 2x trigger) |

## WASM (SQL / DuckDB block)

Bench gap: DuckDB-WASM worker requests are not on the page CDP session, so the
measured WASM reads 0 KiB and is invalid (VERIFY). Dist 91.8 MB includes DuckDB
assets for the SPK-2 page; the shell's own dist is 6.2 MB. Static file
sizes from the build, gzip-compressed (what the browser fetches, Chromium
likely the `wasm_eh` build in Chromium; UNVERIFIED):

- `_npm/@duckdb/duckdb-wasm@1.29.0/dist/duckdb-eh.wasm`: 35.7 MB raw, 7.09 MB gz
- `_duckdb/parquet-*/v1.1.1/wasm_eh/parquet.duckdb_extension.wasm`: 2.80 MB raw, 0.69 MB gz

A DuckDB-backed page adds roughly 7-8 MB gz on first use (UNVERIFIED load set).

## SPK-2(a): Parquet via FileAttachment in Framework: PASS (5/5)

Fixture: `zstd_default.parquet` (DuckDB 1.1.1, zstd, 30,000 rows, list columns
and timestamps), loaded by `DuckDBClient.of({fx: FileAttachment(...)})` in
Framework 1.13.4, queried with DuckDB-WASM 1.29.0. Expected values come from the
writer's own run.

| Check | Got | Want | Result |
|---|---|---|---|
| COUNT(*) | 30000 | 30000 | PASS |
| list_contains(tags,'ecotox') | 9129 | 9129 | PASS |
| UNNEST(tags) count | 63730 | 63730 | PASS |
| MAX(published) | 2025-12-24 23:50:20.904937 | same | PASS |
| MAX(updated) | 2026-04-14 23:58:11.701899+00 | same | PASS |

Caveat: a `DuckDBClient` JS block, not a ```sql block (same DuckDB-WASM).

## G-SHELL decision

Contract rule: Framework unless (a) it cannot meet budgets after tuning, or
(b) it needs more than 2x the effort. Default if inconclusive: Framework.

- (a) Not triggered. Framework meets every budget that the single-file app
  meets, and its shell (0.34 MiB gz) is far under 3 MiB. Its facet latency
  (13 ms median) is well under 50 ms.
- (b) Not triggered. Estimated effort ratio ~1.3x (hours are an estimate).

**Decision: G-SHELL = Framework.** The cost is the ~7-8 MB gz DuckDB-WASM payload
on any page that queries Parquet in the browser, and 84 MB of DuckDB assets in
the build output. That cost matters for the Parquet-in-browser design, not for
the shell choice.

## Caveats

- The fixture lacks `institution_type` and `oa`; those facets do nothing useful on it.
- Hours-to-parity is one author's estimate, not a timed exercise.
- Contention: for part of the final run, a second harness run (started with
  `--skip-build`) was still running and could not be killed (permission
  denied). Latency and TTI numbers may be inflated; a clean rerun is needed
  before treating the 30k/100k latency margins as final. The G-SHELL decision
  is robust to a 2x error (framework 13 ms vs 50 ms budget).

## Clean re-run (lead, 2026-11-10, no overlapping runs)

| App | Data | Total gz MiB | TTI ms | Facet median / max ms | Landing / TTI / facet |
|---|---|---:|---:|---|---|
| single | 30k | 0.98 | 172 | 3.9 / 8.7 | PASS / PASS / PASS |
| single | 100k | 3.25 | 316 | 7.8 / 13.7 | FAIL / PASS / PASS |
| single | fixture | 0.00 | 28 | 0.5 / 0.9 | PASS / PASS / n/a |
| framework 1.13.4 | 30k | 1.32 | 299 | 13.3 / 16.3 | PASS / PASS / PASS |
| framework 1.13.4 | 100k | 3.59 | 471 | 13.6 / 38.7 | FAIL / PASS / PASS |
| framework 1.13.4 | fixture | 0.34 | 191 | 13.5 / 18.0 | PASS / PASS / n/a |

Framework build median 5.83 s; shell-only output 6.2 MB / 48 files (DuckDB assets
only when SQL is used). The 100k landing failure is the bench's full JSON payload
(3.25 MiB gz) and affects both shells equally. It is solved by the SPK-4
Appendix C payload (bit-mask bundle 0.89 MB gz at 100k), not by the shell choice.
SPK-2 part (a) passes 5/5 on the clean run.

**G-SHELL decision (contract rule):** Framework. Neither trigger fires: it meets
the budgets (with the SPK-4 payload), and the estimated effort ratio is ~1.3×, below
2×. The single-file shell remains the documented fallback (A1 C1). DuckDB-Wasm
transfer size when SQL blocks are used was not measurable from the page session
(worker requests); static assets are duckdb-eh.wasm 7.09 MB gz, so SQL blocks
belong only on the lazy Explore page (A1 C9).
