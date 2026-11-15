# VD-3 verification: app shell

Date: 2026-11-15

## Result

VD-3 replaces the flat Framework shell with the Pacific Contour app shell on every route:

- grouped navigation for Explore, Data, Context, and Reference;
- coastline brand mark, link icons, hover treatment, and a non-colour-only active state;
- `aria-current="page"` on the active route and Overview labelling for the home link;
- a first-tab-order skip link, responsive product name/breadcrumb, 40 px menu control, and
  expert search that writes the existing `#search=` hash;
- a responsive footer with the unchanged independence disclaimer and links to About, Glossary,
  How to cite, correction reporting, and source code.

The postbuild transform removes Framework's invalid close label from the sidebar list, hides
the template checkbox from assistive technology after the real menu button takes control, and
moves the skip link to the first focusable position. The whole transform remains idempotent.

## Browser and visual evidence

The production-shaped assembly was served at
`http://127.0.0.1:8779/CA_Plastics_Research_Dash/`.

- All 12 routes reported `axe: none`. This closes the prior Framework `list` and `region`
  findings rather than accepting them as template exceptions.
- At 390 x 844, the first Tab focused `.atlas-skip-link`; its visible box did not overlap the
  menu. The menu opened with `aria-expanded="true"`, and the icon search submitted
  `Rochman` to `/experts#search=Rochman`; the Experts search field hydrated to the same value.
- At 1440 x 900, the sidebar showed the four groups, ten route icons, one active Policy link,
  and the expected five footer links. There were no console errors.
- The generated mark was corrected from browser-default black to the binding teal land/orange
  contour treatment from the style tile.
- Visual screenshots are `scratch/ux_vd3_mobile.png`, `scratch/ux_vd3_desktop.png`, and the
  route screenshots under `scratch/ux_vd3/`.

The first route-wide Lighthouse pass found two local async CLS signals: Institutions 0.139 and
Resources 0.181. A throttled `PerformanceObserver` reproduced no Institutions shift but showed
the Resources footer entering at y=647 before the JSON cards displaced it. Reserving one
viewport for `#resources-root` removed that shift. The targeted rerun measured CLS 0 on both
routes, accessibility 100, and Resources performance 98. All other route CLS values were 0 to
0.049 in the shell pass. The local Python preview remained connection-sensitive for JavaScript-
heavy route performance; deployed metrics are recorded after Pages publishes the checkpoint.

## Verification commands

- `npm run build` in `framework/`: 12 pages and 69 links built; postbuild fixed all pages.
- `py -3.14 scripts/check_at5.py --dist dist`: passed. First-load gzip increased by about 2 KiB
  for the global shell and remained within every AT-5 limit.
- `py -3.14 scripts/check_design_tokens.py`: 259 non-token CSS hex uses, below 293.
- `py -3.14 scripts/check_public_text.py`: passed.
- `py -3.14 scripts/check_doc_links.py`, `check_a1_scaffold.py`, and
  `check_a2_scaffold.py`: passed.
- `py -3.14 -m ruff check .`, `py -3.14 -m ruff format --check .`, and
  `py -3.14 -m compileall -q src`: passed.
- `py -3.14 -m pytest -q`: 1,574 passed, 9 expected placeholders skipped. An initial run had
  one unrelated Windows temp-directory `WinError 5`; that fixture passed alone and the complete
  rerun passed without a code change.
- `py -3.14 scripts/ux_tasks.py --base <local-base>`: 6 of 6 visitor tasks passed.
- `git diff --check`: passed, while preserving the owner's unrelated unstaged
  `.agent/QUESTIONS.md` formatting.

## Review notes

The Luna worker implemented the grouped shell, responsive header/search, footer, postbuild
repair, and focused tests. Lead review removed the skip-link/menu overlap, corrected the mark
colours, normalized Framework's footer-link defaults, diagnosed and fixed Resources CLS, and
ran the full repository and all-route browser gates.
