# GA-2 build spec: the Global data app in Observable Framework

Status: owner approved the GA-1 prototype on 2026-11-18 ("global app OK", H33).
Audience: the lead and the workers who build GA-2.

## 1. What to build

Port the approved prototype `.impeccable/sketches/global_app.html` into the Framework site as one global
page at `/explore` (QUESTIONS GA-ROUTE). The prototype is the composition contract. Its direction
contract is `.impeccable/surfaces/impeccable-sketches-global-app-html.md`, and its tokens and components
are in `DESIGN.md` ("Platform-wide, app"). Decision record: ADR-GA-LAYOUT-2026-11-18.

The page keeps everything the prototype does:
- the landing header (light state);
- the sticky scope ladder (World > continent > country > regional atlas), the "Find a country"
  combobox and the phone drawer;
- the scope statement and the seven tabs (Countries/Overview, Evidence map, Trend, Experts,
  Institutions, Network, Works), with URL state in `#scope=..&view=..`;
- the pixel map, with the 450 ms viewBox zoom, the callouts and the atlas strip;
- the sortable country table, with the California sub-row and the Norway badge;
- the profile panels, the column chart with its Chart/Table toggle, the evidence matrix, the
  network, the works list, the empty states and the polite live region;
- the black footer.

Out of scope: the landing page (`framework/src/index.md`, `components/landing_story.*`); the California
pages; per-country data beyond what is listed in section 2 (that arrives with PLAT-4).

## 2. Data (pipeline, committed, no new dependencies)

| File | Writer | Contents | Refresh |
|---|---|---|---|
| `site/data/global/explore_sample.json` | `scripts/fetch_global_explore_sample.py` | Real OpenAlex samples: world, US, CN, NO (authors, institutions, topics, years, co-author countries, 12 newest works), plus co-author countries for the 15 largest countries | Daily ingest; skip while under 7 days old and the query version matches (same rule as `build_global_counts.py`). About 35 requests and 350 credits per refresh through `BudgetedRun` |
| `site/data/global/explore.json` | `scripts/build_global_explore.py` | Per-country pixel cells (runs), names, continents, counts (total, last 5 years, this week), California cells, world trend (years capped at the current year), the sample above inlined | Offline, after the two files above; run in the daily ingest after `build_global_counts.py` |

Rules carried from GA-1 (LESSONS 2026-11-18):
- Small countries that hold no cell centre take the land cell nearest their interior point.
- Zoom frames use a country's main body: the US without Alaska and Hawaii; elsewhere, cells within 16
  of the median.
- Country names come from `world.json`, plus a fixed table for the codes the 110m map lacks. No
  `pycountry`.
- Raw responses stay in ignored `data/raw/global_explore_sample/`.

## 3. Front end

- `framework/src/explore.md`: a global page (add it to `GLOBAL_PAGES` in `scripts/check_at5.py`).
  - Front matter follows `index.md`: `sidebar/header/footer/toc/pager: false`; the same `head`
    font faces, favicon and theme colour.
  - It holds the static header, scope bar, head and footer markup, so there is no CLS from a runtime
    header (VD-14).
  - It ends with a `js` block that calls `mountExplore(root)`.
- `framework/src/components/explore.js`: the prototype's script as an ES module.
  - It fetches `data/global/explore.json` through `siteRoot()` from `components/atlas.js`.
  - It never names a top-level variable `view`.
  - Its debug hook is `window.__explore = {go, setTab, scope}`.
- `framework/src/components/explore.css`:
  - `--pv-*` tokens only (CI `check_design_tokens.py` allows no hex literals; the select chevron's
    data URI uses `%2317263d`, which it accepts as an encoded hex).
  - Rules are scoped under `.gx` so nothing leaks into Framework pages.
- Links:
  - Regional atlas: `./california/`.
  - Ambassadors: `./ambassadors`.
  - Methods and About: `./california/about...` until global versions exist.

## 4. Acceptance

1. `py -3.14 scripts/check_at5.py --dist dist` passes with `/explore` built; `npm run build` is clean.
2. `tests/test_ga2_explore.py` (static, CI) passes. It checks:
   - the page and component wiring, and that `explore.json` matches its builder (`--check`);
   - that no hex literals appear in `explore.css`;
   - the empty-state copy;
   - that the source line for illustrative counts is present.
3. Local browser checks on an assembled build (`scripts/serve_framework_preview.py --assembled`):
   - axe-core reports 0 violations on world, US overview, network, evidence, works and trend at 1440 and 390;
   - there are no console errors;
   - nothing overflows horizontally at 375 px;
   - the map zoom lands on the scoped country;
   - the callouts sit off land at 1024 and 1440.
4. Screenshots match the GA-1 review set (`.impeccable/review/global_app/`) in arrangement. The Impeccable
   finish reviewer (Haiku) runs against the prototype as the approved composition.

## 5. Open choices (QUESTIONS)

- GA-ROUTE: `/explore`. This is the default in use.
- GA-LANDING-LINK: link "Explore the data" from the landing header and its regions band. That is a
  landing edit, so it waits for the owner's word and goes in with PLAT-2d.
