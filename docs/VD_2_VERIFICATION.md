# VD-2 verification: typography and surfaces

Date: 2026-11-14

## Result

VD-2 self-hosts the two approved Barlow Semi Condensed Latin faces, applies the Pacific
Contour type scale, and keeps body text on the system interface stack. The site uses the
sea-mist page surface with white cards. No runtime font or CDN host is contacted.

Observable Framework 1.13.4 does not configure a loader for WOFF2 files referenced from
Framework CSS. The faces therefore live in `site/assets/fonts/`, use page-relative URLs in
the configured head, and are copied by the existing assembly step. `postbuild.mjs` adds one
page-relative preload for weight 700 after Framework has built each page. The complete
postbuild transform is idempotent.

## Font provenance and budget

- Source: Barlow Semi Condensed v16 from the Google Fonts repository; SIL Open Font License
  1.1 recorded in `docs/REUSE.md` and stored as `site/assets/fonts/OFL.txt`.
- `BarlowSemiCondensed-SemiBold-latin.woff2`: 22,984 bytes; SHA-256
  `F158417E9207B5362F9B71A2FE779CE5BB836AD972F38445C3163AF39D2C998D`.
- `BarlowSemiCondensed-Bold-latin.woff2`: 23,244 bytes; SHA-256
  `FB958C8C20A05552AC8A85D925D96028D52565792650E941A5FE96B6997AA5CB`.
- Total WOFF2 transfer: 46,228 bytes, below the 60 KiB limit.

## Browser evidence

The assembled site was served at
`http://127.0.0.1:8778/CA_Plastics_Research_Dash/`.

- A Chromium DevTools platform-font probe covered all 12 routes. Every route loaded Barlow
  Semi Condensed and rendered headings with it; body text rendered with Segoe UI. No sampled
  heading, paragraph, or sidebar link rendered Palatino Linotype, Times New Roman, or Arial.
- Both WOFF2 requests returned HTTP 200. Every built page contained exactly one relative
  weight-700 preload, and no page requested Google Fonts or another external font host.
- The all-route axe pass scored Lighthouse accessibility 100 on every route, with zero
  `color-contrast` nodes. The only axe rows were the existing Framework `list` and `region`
  template rows assigned to UX-32.
- The first Policy audit exposed async CLS 0.112 after the new type metrics. Lighthouse
  identified the paragraph after `#policy-timeline` as the shifted node. Reserving the
  successful timeline height produced three consecutive Policy runs at performance 99,
  accessibility 100, LCP 1.9 s, and CLS 0 (median CLS 0).
- Other local CLS values were 0 to 0.070 except the pre-correction Policy sample. Local
  Lighthouse performance was connection-sensitive on the Python preview; deployed route
  metrics are recorded after Pages publishes the checkpoint.
- Visual review found the 1440 x 900 and 390 x 844 Overview layouts readable, with the
  expected Barlow hierarchy, system body face, mist page, white cards, and no clipping.

Artifacts are in `scratch/ux_vd2/`, `scratch/ux_vd2_policy_fixed_1/` through
`scratch/ux_vd2_policy_fixed_3/`, and the screenshots named
`127_0_0_1_8778_CA_Plastics_Research_Dash_*_{desktop,mobile}.png`.

## Verification commands

- `npm run build` in `framework/`: 12 pages and 35 links built; postbuild fixed all pages.
- `py -3.14 scripts/check_at5.py --dist dist`: passed; every first-load gzip size remained
  below the AT-5 limit.
- `py -3.14 scripts/check_design_tokens.py`: 259 non-token CSS hex uses, below 293.
- `py -3.14 scripts/check_public_text.py`: passed.
- `py -3.14 scripts/check_doc_links.py`, `check_a1_scaffold.py`, and
  `check_a2_scaffold.py`: passed.
- `py -3.14 -m ruff check .`, `py -3.14 -m ruff format --check .`, and
  `py -3.14 -m compileall -q src`: passed after formatting one new assertion.
- `py -3.14 -m pytest -q`: 1,570 passed, 9 expected placeholders skipped.
- `py -3.14 scripts/ux_tasks.py --base <local-base>`: 6 of 6 visitor tasks passed.
- `git diff --check`: passed, excluding the owner's unrelated unstaged
  `.agent/QUESTIONS.md` formatting changes from this checkpoint.

## Review notes

The Luna worker implemented the faces, type scale, surfaces, preload, and focused tests. Lead
review added the licensed assets and provenance, verified platform fonts and every route,
fixed the Policy CLS regression, and corrected combined metadata/preload idempotence found by
the full suite.
