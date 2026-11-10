# SPK-2: Parquet writer ↔ browser engine compatibility (gate G-PARQ)

Status: **G-PARQ passed for part (b)** (plain DuckDB-Wasm). Part (a) (Framework
`FileAttachment`) is deferred to SPK-3 because the Framework project does not
exist yet.

Authorization: owner approved spike dependencies and network access on
2026-11-09 (ADR-SPK-AUTH). Spike code: `spikes/spk2_parquet/`. Raw results and
generated Parquet: `scratch/spk2/` (gitignored).

## Versions and dates

Selection rule: newest stable release at least 14 days old on 2026-11-09
(cutoff 2026-10-26). Prerelease/dev builds were excluded.

| Role | Component | Version | Released |
|---|---|---|---|
| Writer (pinned A1 C7 baseline) | `duckdb` (PyPI) | 1.1.1 | 2024-09-24 |
| Writer (newest eligible) | `duckdb` (PyPI) | 2.0.0 | 2026-10-21 |
| Browser (Framework-aligned) | `@duckdb/duckdb-wasm` (npm) | 1.29.0 | 2024-10-07 |
| Browser (newest eligible) | `@duckdb/duckdb-wasm` (npm) | 1.32.0 | 2025-12-16 |

Engine versions reported by `SELECT version()` in the page: wasm 1.29.0 runs
DuckDB **v1.1.1**; wasm 1.32.0 runs DuckDB **v1.4.3**. The browser engine is
therefore not the same DuckDB version as the 2.0.0 writer.

## Method

- Fixture: 30,000 rows, seed 20261109. Columns: `work_id` VARCHAR, `year`
  SMALLINT, `published` TIMESTAMP, `updated` TIMESTAMPTZ, `tags` VARCHAR[]
  (5% NULL, 10% empty, otherwise 1 to 4 items), `inst_ids` INTEGER[] (3% NULL),
  `score` DOUBLE (1% NULL), `ca_led` BOOLEAN (10% NULL), `title` VARCHAR with
  non-ASCII text (`Río`, `µm`).
- Writers: `uv run --no-project --with duckdb==<ver>` (no global installs, no
  `pyproject.toml` change).
- Options: `zstd_default` (COMPRESSION zstd), `zstd_rg10k` (zstd,
  ROW_GROUP_SIZE 10000), `snappy` (control).
- Browser: plain page `spikes/spk2_parquet/page.html` loads the pinned
  jsDelivr bundle (`getJsDelivrBundles` / `selectBundle`, worker from blob),
  sets `TimeZone='UTC'`, and registers each file with
  `registerFileURL(name, url, HTTP, false)`. Files come from a local Range-aware
  static server, so the Parquet reads use byte-range requests.
- Expected values come from the writer's own in-memory table. Each browser
  check returns a single VARCHAR, compared as an exact string.
- Checks (15 per file): COUNT(*), SUM(year), `list_contains(tags,'ecotox')`
  count, UNNEST(tags) row count, MAX(published), MAX(updated), NULL and TRUE
  counts of `ca_led`, non-ASCII title counts (`Río`, `µm`), exact title
  round-trip for two rows, a list-column round-trip (`tags`, `inst_ids`), and
  `SELECT * ... LIMIT 5`.

## Results

Both writers produced identical expected values (`expected.json` compared equal).

| Writer | Option | File bytes | wasm 1.29.0 (eng v1.1.1) | wasm 1.32.0 (eng v1.4.3) |
|---|---|---:|---|---|
| 1.1.1 | zstd_default | 925,066 | 15/15 pass, load 549 ms | 15/15 pass, load 508 ms |
| 1.1.1 | zstd_rg10k | 942,486 | 15/15 pass, load 137 ms | 15/15 pass, load 64 ms |
| 1.1.1 | snappy | 1,412,815 | 15/15 pass, load 121 ms | 15/15 pass, load 60 ms |
| 2.0.0 | zstd_default | 828,262 | 15/15 pass, load 106 ms | 15/15 pass, load 53 ms |
| 2.0.0 | zstd_rg10k | 846,602 | 15/15 pass, load 133 ms | 15/15 pass, load 68 ms |
| 2.0.0 | snappy | 1,143,904 | 15/15 pass, load 121 ms | 15/15 pass, load 90 ms |

- Engine init: 1534 ms (1.29.0), 1299 ms (1.32.0).
- Load time is the first-query time per file, which includes HTTP range reads
  and metadata. It is a single cold run in headless Chromium, so it is indicative only.
- Console errors: 0 in both pages. No check errored.
- Expected writer-side values: count 30000; sum_year 60389444; ecotox 9129;
  unnest 63730; max_published `2025-12-24 23:50:20.904937`; max_updated
  `2026-04-14 23:58:11.701899+00`; null ca_led 3056; true ca_led 10744.

## Decision (G-PARQ)

Per the contract rule (pin the writer version and options that read cleanly;
list-column fallback only if lists fail):

1. **List columns (`tags[]`, `inst_ids[]`) read cleanly. No fallback is needed.**
   Do not move tags into delimited strings or the bit-mask bundle.
2. **Pin the writer to DuckDB 1.1.1 with `COPY ... (FORMAT PARQUET, COMPRESSION zstd)`
   and default row groups.** It matches the A1 C7 baseline, and its files read
   in both browser engines. Engine 1.1.1 (wasm 1.29.0) is the Framework-aligned engine.
3. Also acceptable: DuckDB 2.0.0 with zstd (about 10% smaller) reads cleanly in
   both engines. Adopt it only if the owner moves the writer pin. Snappy also
   reads cleanly but is about 50% larger, so it is not recommended.
4. **Gate G-PARQ: PASS** for part (b), for the pinned writer and options above.

## Open items for the owner and SPK-3

- **Owner review needed:** wasm 1.32.0 runs DuckDB engine v1.4.3, not 1.1.1. A
  writer/engine version gap of this size is not what A1 C7 assumes. Confirm
  whether to keep the 1.29.0 pin (Framework's SQL blocks) and track 1.32.0 as
  a forward check only.
- **SPK-3 part (a):** repeat the same 15 checks through Framework's built-in
  `FileAttachment` once the Framework project exists. Note that FileAttachment
  may read via a different path than `registerFileURL`.
- **Not tested:** Firefox and Safari engines; the `coi` (threaded) bundle, since
  headless Chromium without COOP/COEP selected the `eh` bundle; a Python-side
  independent reader (pyarrow was not installed), so expected values rely on
  the writer's own DuckDB.
- Tooling caveat: the first end-to-end run failed one check I had designed
  incorrectly (a title containing both `Río` and `µm`, which no row has). It was
  corrected to separate checks and re-run. Reported results are from the corrected run.
