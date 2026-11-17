# VD-20: Collaboration network first view and cluster names (owner H25)

## What changed

- **Default layout.** `build_network` now stores a ForceAtlas2 layout (networkx 3.6.1
  `forceatlas2_layout`) started from the seeded spring layout, instead of the spring layout
  itself. Settings mirror graphology's `inferSettings` (scaling ratio 10, strong gravity 0.05,
  node mass 1 + weighted degree, linear attraction), 1000 iterations, centred and scaled to
  [-1, 1]. Recorded in `method.layout`. "Re-run layout" is kept.
- **Cluster names.** New key `community_labels` (one entry per community of at least 4 experts,
  in community order): `institution` `{name, share}` and `topic` `{tag, share, lift}`, or null.
  Thresholds are module constants in `src/atlas/build/network.py` and are written into
  `method.community_labels`. `schema_version` is now `s9.4-v1.1`; `communities` and
  `network_counts` are unchanged.
- **Page.** The legend and the table's "Cluster n" cell read "Cluster n · institution · topic";
  unlabelled clusters keep "Cluster n". In cluster colour mode, up to eight of the largest
  labelled clusters get an aria-hidden overlay at the centroid of their visible experts (topic
  label text only, cluster colour, halo, no pointer events). Overlaps are skipped and names are
  clamped inside the stage.

## Layout verdict

Before: a tight central knot with a ring of isolated experts on first load, clusters visible
only after Re-run layout. After: the six coloured clusters are separated on first load and are
arranged much like the re-run result, which spreads them a little wider. No "Tip" hint was
added.

Caveat: networkx's ForceAtlas2 uses one global speed, while graphology uses a per-node speed
with `slowDown`, so the two are not identical. Between 500, 1000, 1500 and 2000 iterations the
mean change in normalised coordinates is 0.06, 0.05 and 0.05 (the cluster arrangement is stable,
but the layout keeps jittering, so it is not strictly converged).

## Generated cluster labels (`site/data/network.json`)

| Cluster | Size | Label |
|---|---|---|
| 1 | 66 | Analytical methods |
| 2 | 35 | Ecotoxicology & food webs |
| 3 | 25 | Lawrence Berkeley National Laboratory |
| 4 | 24 | (no label) |
| 5 | 23 | Plastic-associated chemicals |
| 6 | 17 | San Diego State University · Risk assessment |
| 7 | 16 | University of California, Los Angeles · Air & atmosphere |
| 8 | 13 | University of California, Santa Barbara · Fate & transport |
| 9 | 13 | Soil & agriculture |
| 10 | 11 | Ecotoxicology & food webs |
| 11 | 11 | California Department of Public Health · Ecotoxicology & food webs |
| 12 | 9 | San Diego State University · Soil & agriculture |
| 13 | 8 | Human exposure & health |
| 14 | 6 | Agricultural Research Service · Soil & agriculture |
| 15 | 5 | San Diego State University · Wastewater & treatment |
| 16 | 5 | University of California, Irvine · Wastewater & treatment |
| 17 | 5 | University of California, Irvine · Air & atmosphere |
| 18 | 5 | California State University, Northridge · Soil & agriculture |
| 19 | 4 | University of California, Santa Barbara · Analytical methods |
| 20 | 4 | University of Southern California · Wastewater & treatment |
| 21 | 4 | National University · Plastisphere |
| 22 | 4 | University of California San Diego · Analytical methods |
| 23 | 4 | Risk assessment |

Cluster 4 has no institution (no share reaches 35%) and no topic (no lift reaches 1.15).

## Screenshots (1440 px, `scratch/w3/`)

- Before: `before_first_load.png`, `before_topic_filter.png`, `before_after_rerun.png`
- After: `after_first_load.png`, `after_topic_filter.png`, `after_after_rerun.png`

## Checks

- CLS on first load and after Re-run layout: 0 before and after (`scratch/w3/*.png` runs).
- axe on `network` (`ux_audit.py`, `scratch/w3/ux/results.json`): no violations, no console errors.
- `py -3.14 -m pytest -q tests -k network`: 77 passed, 9 skipped (existing A2 placeholders).
- `py -3.14 scripts/build_network.py --check`: current.
- `py -3.14 scripts/check_at5.py --dist ../scratch/w3_fw/dist-w3`: AT-5 checks passed.
- `py -3.14 scripts/check_design_tokens.py`: 0 hex uses in Framework CSS.
- `ruff check .` and `ruff format --check .`: passed. `git diff --check`: clean.

## Build note

`cd framework && npm run build` failed on a concurrent in-flight edit: `observablehq.config.js`
loads `assets/site_search.css` and `.js`, which are not yet in `framework/src/assets`. The
verification build therefore used a scratch copy, `scratch/w3_fw`, with the working-copy config
and the two `site/assets/site_search.*` files copied into the copy only. The assembled site is
`scratch/w3_site`. `framework/dist-w3` still holds the pre-VD-20 build.

## Open items

- `docs/DATA_DICTIONARY.md` lists the network fields and does not yet mention `community_labels`
  or the ForceAtlas2 layout. It is outside this task's owned files.
- No reader checks `network.json`'s `schema_version`. The page reads `community_labels`
  defensively, so older files still render.
- Canvas names can sit over expert name labels. They are skipped when they would overlap each
  other, but not when they overlap expert names.

## Lead follow-up (2026-11-16)
- Canvas, legend and table labels shorten "University of California, X" to "UC X" and
  "California State University, X" to "CSU X" (`shortInstitutionName` in `network_model.js`, covered
  by `tests/framework_network_runtime.mjs`); `network.json` keeps the full names.
- `docs/DATA_DICTIONARY.md` documents `community_labels` and the ForceAtlas2 layout.
- Known limitation: cluster names can overlap expert name labels (labels only avoid each other).
