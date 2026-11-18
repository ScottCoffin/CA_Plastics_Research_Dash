# PLAT-2 verification: the Plastiverse Live landing page

Date: 2026-11-17. Spec: `docs/PLAT_2_LANDING_SPEC.md`. Decisions: ADR-PLAT2-SPECTRAL-STORY-2026-11-17
(design) and ADR-PLAT2-BUILD-2026-11-17 (build deviations) in `.agent/DECISIONS.md`.

## What shipped

| Part | Files |
|---|---|
| Page (header, story, evidence map, regions, features, footer) | `framework/src/index.md` |
| Story engine (port of `.impeccable/sketches/src/story_engine7.js`) | `framework/src/components/landing_story.js` |
| Styles (scoped `.plv`, `--pv-*` tokens) | `framework/src/components/landing_story.css`, `framework/src/design/tokens.css` |
| Offline assets (picnic atlas, first paint, papers, logo, world raster) | `scripts/build_landing_assets.py` → `site/assets/landing/`, `site/data/global/world_raster.json` |
| Fonts (Schibsted Grotesk 400-700, Martian Mono 400, OFL) | `scripts/build_brand_fonts.py` → `site/assets/fonts/` |
| Global data (PLAT-2a) | `site/assets/world/world.json`, `site/data/global/global_counts.json` |
| Acceptance | `scripts/check_plat2.py`; static tests `tests/test_plat2_landing.py`, `tests/test_landing_assets.py`, `tests/test_brand_fonts.py` |

## Acceptance (spec section 9), local assembled build

`scripts/check_plat2.py --base <local>`: 0 failures.

1. Copy: all 19 caption strings of spec section 4 are in the DOM verbatim.
2. No overlap: 13 beats x (middle, end) x (1440x900, 390x844) = 52 positions; no visible caption
   text box intersects a drawn visual (picnic sprites and shards, crumbs, particles, papers,
   mandala, bulb, grid, maps, chart annotations).
3. Accessibility: axe 0 violations at both widths; one h1, no heading skips; the skip link targets
   `#evidence`.
4. Reduced motion: no sticky stage; 10 stills, each with its caption.
5. External requests: none; console errors: none.
6. Contact sheets: `scratch/plat2/contact_1440.png`, `contact_390.png` (reviewed).

Lighthouse (mobile, simulated, same machine, local Python server):

| Page | Performance | Accessibility | CLS | LCP |
|---|---|---|---|---|
| Landing `/` | 85 | 100 | 0.03 | 3.6 s |
| California overview `/california/` (A/B control) | 84 | 100 | 0 | 4.2 s |
| `/ambassadors` | 98 | 100 | 0 | 2.1 s |

The local server reads about 8 points lower than the live host for the same page (the California
overview scores 92+ live), so the spec's live target of 90 is checked after deploy. The path to
these numbers: the LCP image is CSS-sized from the first frame, phones get an 800 px variant, the
landing preloads its own text face, and the engine starts after load + a painted frame + idle,
decodes bitmaps off the main thread and cuts shards in yielded chunks (TBT 750 ms → 120 ms).

## Live (https://plastiverse.live/, after deploy of `2b3df7ba`)

- `scripts/check_plat2.py --base https://plastiverse.live/`: 0 failures.
- Lighthouse mobile: landing performance 93, accessibility 100, best practices 96, SEO 100,
  LCP 2.3 s, CLS 0 (spec: >= 90, 100, LCP <= 2.5 s, CLS <= 0.05). Same run: `/california/` 95,
  `/ambassadors` 98. UX audit: 0 console errors, one h1, no heading skips on all three.

## Impeccable finish review

The `impeccable-finish-reviewer` compared 52 build/prototype frame pairs (13 beats x middle/end x
1440 and 390) plus the first viewport: the story matches the approved prototype frame for frame;
the coral-ink change, the first-paint image and the ambassador links in the picker were accepted
as adaptations. It ordered six fixes, all applied:

1. Evidence table on phones: short row/column labels below 600 px (full names stay for screen
   readers), no minimum width; all six columns and the gap cells fit at 390 px.
2. Regions map moire on phones: the canvas is sized from the box (no CSS downscaling), no gutter
   on cells under 4 px, ResizeObserver redraw, token colours, outlines hidden below 860 px.
3. Evidence cells: vertical centring, no white chips, tabular numbers; light text only on the
   darkest cell (white on mid slate fails AA).
4. Map shading: fixed log breaks at 30, 300 and 3,000 works (terciles had put 56 countries in the
   top step; now 14); the legend states the breaks.
5. Phone stage: each beat's visual fills the space between its own caption and the screen bottom
   (or its bottom caption); the mandala's dust halo fades at its edges instead of a hard clip.
6. Mono only for data and source lines: the scroll cue, picker status lines and the toggle note
   are now Schibsted Grotesk.

Persistence: `impeccable concept-seed --check-seed seed:2c42143eccc874ce` exits 0 ("rolled on
this machine"). No `.impeccable/build/state.json` or measured comp diff exists; the 52 frame pairs
in `scratch/finish_review/` and `scratch/plat2/` stand in as the fidelity evidence.
`DESIGN.md` was written from the shipped page by the `impeccable-documenter`.

## Known limits

- Evidence-grid counts and the network are illustrative and labelled (PLAT-2b waits on H30).
- `papers.json` licence sentences are truncated in the source `credits.json` (for example
  "CC-BY 4"); every page is CC BY (no NC), and the footer credits use full titles.
- Country counts are capped at 200 countries by OpenAlex `group_by` (missing countries have at
  most 1 work each).
