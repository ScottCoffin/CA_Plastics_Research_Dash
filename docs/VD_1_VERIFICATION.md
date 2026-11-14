# VD-1 verification - tokens and foundations

Date: 2026-11-14

## Delivered

- `framework/src/design/tokens.css` defines the exact Pacific Contour interface palette,
  seven-step sequential ramp, type stacks, spacing, radii, shadows, and Observable Framework
  mappings from `docs/VISUAL_DESIGN_SPEC.md` Section 3.
- `framework/src/style.css` imports the tokens after `theme-air.css`; the Experts, Funding,
  Institution, Institutions, and Monitoring local palettes alias the shared tokens.
- `scripts/check_design_tokens.py`, `tests/test_design_tokens.py`, and CI ratchet colour literals
  outside `tokens.css`: 259 uses after VD-1, below the 293-use baseline.

## Automated checks

- Framework: `npm run build` (12 pages, 35 links) and
  `py -3.14 scripts/check_at5.py --dist dist` passed.
- Full gate: doc links, A1/A2 scaffolds, Ruff check/format, compileall, public-text check,
  design-token check, and `git diff --check` passed.
- Tests: 1,565 passed, 9 documented Add-on A2 placeholders skipped.
- `py -3.14 scripts/ux_tasks.py --base http://127.0.0.1:8776/CA_Plastics_Research_Dash/`:
  6/6 visitor journeys passed.

## Browser inspection

The production layout was assembled under `scratch/vd1_assembled_20261114/` and audited with
`ux_audit.py` at 1440 x 900 and 390 x 844. Artifacts are in `scratch/ux_vd1/` and the targeted
rerun in `scratch/ux_vd1_rerun/`.

- All 12 routes: zero axe `color-contrast` nodes, no console errors, no horizontal overflow,
  one h1, and no unlabeled controls.
- Accessibility stayed at baseline: 100 on 11 routes and 96 on Evidence. The known Framework
  sidebar `list` and `region` rows remain on every route and are assigned to UX-32.
- Visual review: sea-mist page, white surfaces, teal links/actions, and readable responsive
  layouts match the foundation stage; screenshots show no new clipping.
- Local Lighthouse is not like-for-like with the live-CDN baseline: the preview logged browser
  connection resets and made data-heavy LCP/CLS substantially worse on repeat runs while built
  gzip sizes stayed within AT-5 limits. The deployed URL is therefore re-audited after push;
  those results are appended here before VD-2 begins.

## Review notes

The Luna implementation omitted the spec's sequential ramp and left the UX-22 test coupled to
the replaced `color-mix()` implementation. Lead review added the ramp, a regression assertion,
and changed UX-22 to require the named contrast tokens plus the running-link underline.
