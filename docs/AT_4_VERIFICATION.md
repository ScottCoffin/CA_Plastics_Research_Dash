# AT-4 verification: serving bundle and facet module

Date: 2026-11-11. Builder: `atlas.build.bundle` (`scripts/build_bundle.py`). Browser
module: `site/assets/facets.js` (dependency-free; classic script sets
`window.AtlasFacets`, Node gets `module.exports`). Acceptance: `py -3.14 scripts/check_at4.py`
(also in `ci.yml` and in `ingest_works.yml` after the export).

## Output (`site/data/bundle/`, committed; rebuilt by the daily ingest)

- Appendix C bit-sets: `works_index.json` (1,774 published works, ordered by work_id),
  `facets.json` (294 labels over year, type, topic, plastic, ca_led, institution,
  sector, oa), `facets.bin` (`BMF1` header + one little-endian Uint32Array per label).
- Text search is a title-token bit-set (all tokens must occur), intersected like a facet.
  MiniSearch was not vendored (QUESTIONS AT4-SEARCH, default in use).
- `inst_tiers.json` / `parquet/inst_tiers.parquet`: owner decision "tiers with ranges".
  Walk CA institutions in fractional rank order; an institution joins the current tier
  while its bootstrap rank_lo <= the tier leader's rank_hi, otherwise it starts a new tier.
  Result: 161 institutions in 5 tiers (sizes 7, 8, 20, 62, 64).
- `parquet/works.parquet` (slim, no abstract), `inst_counts`, `year_tag`; DuckDB 2.0.0 zstd.

## Acceptance (A1 section 9)

| Test | Result |
|---|---|
| Landing first load (<= 3 MB gz) | 88,833 B gz for works_index + facets.json + facets.bin (whole bundle 293,881 B gz) |
| Facet latency (<= 50 ms at 30k, <= 150 ms at 100k) | Node, 100k synthetic works, 365 sets: median 1.9 ms with search, 1.8 ms without |
| Parquet compatibility | 4 files read with pyarrow; writer is the G-PARQ pin (DuckDB 2.0.0 + zstd, browser-verified in SPK-2) |
| No abstracts | No column containing "abstract" in any public Parquet |
| Builder <-> module round trip | 25 seeded selections (with search tokens): node `facets.js` totals, counts and ids equal the Python reference |
| Tests | `tests/test_bundle_at4.py` 9 passed (layout, counts, node round trip, search, tiers, no-abstract, missing inputs, determinism) |

## Not done here

- The Institutions tab does not show the tiers yet; that follows as a UI step.
- Interactive timings were measured in Node, not a browser; the SPK-4 browser
  measurements of the same engine (81.7 ms cold start at 30k) still apply.
