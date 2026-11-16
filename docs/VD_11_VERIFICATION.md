# VD-11 verification: classic profile and generated SEO pages

Date: 2026-11-16

## Result

`site/expert.html` re-points its own palette variables to the token values
(`--ink` #17324d, `--text` #1d2a33, `--muted` #4a5d6c, `--boundary` #6f8590,
`--brand` #075a46, `--brand-dark` = brand-strong #043e32, `--canvas` = page
#f3f6f5, `--line` #d5e0dd, `--focus` = accent #c45100), loads Barlow Semi Condensed
600/700 from `assets/fonts/` (page-relative, `font-display: swap`) for headings,
keeps the system UI body face, and gains a footer with About, Glossary and How to
cite links. Only the metric tiles keep a shadow. Scripts, ids and the
`#author=<id>` routing are unchanged (the test pins the routing script hash).
The SEO template CSS in `src/atlas/build/seo.py` uses the same token values, the
brand-strong header band, brand-action call to action and root-relative
`/assets/fonts/` faces; page structure and JSON-LD are unchanged.

## Verification

- Tests: `tests/test_vd11_classic_pages.py` (8: token values equal `tokens.css`,
  local font faces with swap, no remote font or CDN URLs, routing unchanged) plus
  the SEO, expert-page, UX-29, design-token and assemble suites (85 passed).
- SEO build into a scratch copy: 2,635 expert and 206 institution pages;
  `check_s3_8.py` passes after the guard fix below.
- Browser (local scratch site, 1440 x 900 and 390 x 844): profile h1 renders in
  Barlow Semi Condensed; no horizontal overflow on the profile or an SEO page.
  In the prefixed local preview the SEO pages' root-relative font URL does not
  resolve, so they fall back to the system face; on the root domain it resolves.

## Related fix

`scripts/check_s3_8.py` flagged "abstract text found" on an expert page whose DOI
contains `.abstracts.` (a false positive; the deploy step is `continue-on-error`,
so it had been failing silently). The guard now ignores URLs and DOIs and still
fails on prose (`tests/test_seo_s3_8.py`).
