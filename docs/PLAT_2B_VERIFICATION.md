# PLAT-2b verification: live global evidence-map counts (2026-11-18)

## What shipped
- `config/evidence_cells.yml` (`evidence-cells-v1.1`): the owner-approved 5 x 6 cells (rows occurrence,
  effects, methods, fate and transport, solutions; columns ocean, freshwater, soil, air, food and biota,
  people; H30) with agent-drafted search terms and links to the A2 compartment vocabulary.
- `scripts/fetch_evidence_cells.py`: one OpenAlex count query per cell,
  `title_and_abstract.search:((active query, with exclusions)) AND (row terms) AND (column terms)` plus the
  active query's type exclusions, `per-page=1`, `select=id`. OR lists are never split (A3-C1); no paid
  filters. Each request passes the budget guard (10-credit reserve, run cap 330 credits, daily USD 0.95
  stop) through the shared throttled `_request_json` path (5 req/s, "wait 1s" retry). Cache: same query
  version and cells version and under 20 hours old. Any failed cell or guard stop writes nothing.
- `site/data/global/evidence_cells.json` (`plat2b.v1`), committed daily by `ingest_works.yml`.
- Landing (`framework/src/index.md` `#evidence`, `components/landing_story.js`): the table and the canvas
  grid use the live counts when the file is valid, and keep the illustrative fallback otherwise.

## Live run (2026-11-18 22:2x UTC)
- 30 requests, 300 credits per run (about USD 0.03). Longest URL 3,626 characters (limit 8,000).
- A probe of the solutions terms in the ocean column (8 requests, 80 credits) showed "regulation" at
  1,386 hits, partly gene up-/down-regulation (stem collision), so v1.1 drops it. "mitigation" (3,556) and
  "policy" (3,193) dominate the row, often as closing-sentence mentions: counts are title/abstract
  mentions, which the source line under the table states. Owner question PLAT2B-GAP.
- Grid (v1.1): occurrence 12,988 / 8,929 / 5,172 / 1,769 / 8,026 / 3,978; effects 4,430 / 4,040 / 3,877 /
  1,175 / 6,460 / 4,669; methods 7,483 / 6,160 / 4,130 / 1,621 / 5,793 / 3,302; fate and transport
  10,398 / 8,429 / 8,537 / 2,370 / 7,333 / 4,166; solutions 8,533 / 6,166 / 6,000 / 1,681 / 7,429 / 4,374.
  The smallest cell is 9% of the largest, so no cell is drawn as a gap at `gap_share` 0.02.

## Checks
- Focused tests: `tests/test_fetch_evidence_cells.py` (25), `tests/test_plat2b_landing_cells.py` (7),
  `tests/test_plat2_landing.py`; full suite 2,286 passed, 10 skipped, 1 known local-only failure
  (`test_opc_actions_em17.py::test_committed_json_is_not_stale`, the owner's uncommitted H28 CSV).
- Assembled preview (Playwright, 1280 px and 390 px): all 30 cells show formatted counts, no cell overflows,
  source line shows the fetch date; jsdom check by the worker: 8 invalid/404 cases keep the fallback.
