# AT-5 verification: Observable Framework shell (partial, 2026-11-12)

ADR-AT5-SHELL-2026-11-12. The Framework app is built in `framework/` and deployed under
`/app/` next to the classic `site/`, which stays the live root until the owner approves
the switch (HUMAN_TASKS H16).

## What exists

| Page | Source | Ported from `site/index.html` |
|---|---|---|
| Overview | `framework/src/index.md` | header + key counts (`build_metadata.json`) |
| Experts | `experts.md`, `components/experts.js`, `experts_model.js`, `experts.css` | Experts tab + researcher drawer |
| Institutions | `institutions.md`, `components/institutions.js`, `inst_tiers.js`, `institutions.css` | Institutions tab (cards, tiers, map) |
| Monitoring | `monitoring.md`, `components/monitoring.js`, `monitoring_view.js`, `svg_map.js`, `monitoring.css` | Monitoring tab (map, facets, tables) |
| Funding | `funding.md`, `components/funding.js`, `funding.css` | Funding tab (filters, charts, table, CSV, open calls) |
| About | `about.md` | About tab |

- Ports are lift-and-shift: the classic markup, CSS (scoped per page root) and JavaScript
  moved into ES modules with the same logic. DOM-free helpers are exported and tested in Node.
- Data: pages fetch the classic site's committed payloads at runtime from `../data/`
  (`components/atlas.js`), so both shells show the same snapshot and nothing is duplicated.
- Shared helpers (`topics.js`, `facets.js`, `expert_page.js`, MiniSearch) are copied from
  `site/assets/` by `framework/scripts/sync_shared.mjs` before every build (gitignored copy).
- Hash links keep the classic parameter names without the tab prefix (`experts#author=<id>`);
  the legacy `#experts?...` form is still read.

## Checks run

- `cd framework && npm run build`: exit 0, 6 pages, Framework link validation passes.
- `py -3.14 scripts/check_at5.py --dist dist`: pass. First-load gzip (HTML + preloaded
  modules + CSS): index 23 KB, about 25 KB, funding 35 KB, monitoring 37 KB,
  institutions 43 KB, experts 62 KB (budget 3 MB). No external hosts (Framework's default
  Google Fonts link removed with `globalStylesheets: []`), no root-absolute paths.
- `scripts/smoke_framework_pages.py` (headless Edge, local Pages layout): all six pages PASS
  with no cell errors. Experts shows "2614 experts shown"; `#author=A5046986222` opens the
  drawer; legacy `#experts?search=Rochman` shows 1 expert. Institutions shows 161 tier rows.
  Monitoring shows 298 samples (the count in the committed `monitoring.json`). Funding shows
  award rows, pages and open calls.
- Node runtime tests: `tests/test_framework_{shell,experts,institutions,monitoring,funding}.py`.
  The Monitoring test repeats every assertion of the classic `monitoring_view_runtime.cjs`
  against the ported module.
- Full gate: lint, 1,306 tests, build, doc links, A1/A2 scaffolds, `git diff --check`.

## Not yet verified

- The deploy run that builds `/app/` in CI (first push after this checkpoint).
- Keyboard and screen-reader walk-through, dark theme, 400 px layout (markup is the classic
  markup, so behaviour should match, but it was not checked by hand).
- MiniSearch ranked search in a real browser (the substring fallback was exercised).
- Owner parity review (H16) and the switch of the site root to the Framework build.

## `npm audit` (2026-11-12)

6 findings (3 low, 3 moderate) in build-time tooling: esbuild dev-server file read on
Windows (local `npm run dev` only), glob and minimatch. The only offered fix downgrades
Framework to 1.10.1, so the 1.13.4 pin stays. The deployed output is static files and
includes none of these packages.
