# UX-22 verification (2026-11-12)

Contract: `docs/EM_spec.md` UX-22 (from the Section 1A audit).

## Changes
- `framework/src/style.css`:
  - Framework's muted and faint text mixes go from 60% and 50% to 75% and 68% in both themes.
  - Links in running text (header, footer, `p`/`li`/`dd`/`td`/`figcaption`) are underlined.
  - The ported pages (Experts, Institutions, Monitoring, Funding) hardcode the classic light
    palette, with white inputs and buttons. In the dark theme they render as a light panel through
    `html #<page>-root` overrides of the Framework theme variables.
  - Facet-header links stay dark on their fixed light background.
- `framework/scripts/postbuild.mjs`: the sidebar toggle gets an `aria-label` (axe label-title-only).
- Test: `tests/test_ux_links.py` covers the aria-label rewrite and guards the style.css overrides.

## Evidence
- Before (local preview, axe-core 4.10.3, 9 routes): 219 color-contrast nodes and 41
  link-in-text-block nodes in the light theme. Examples: `#76787b` on `#f6f6f6` at 4.09:1, and
  `#536879` on `#1e1e1e` in the dark theme.
- After: color-contrast, link-in-text-block and label-title-only report 0 nodes on all 9 routes in
  both `color_scheme=light` and `dark`. The `list` rule still flags 1 node per page: Framework's
  sidebar close `<label>` sits directly inside the nav `<ol>`. It is left as a template limit,
  because moving it risks the sidebar layout.
- Dark-theme screenshots of /app/funding and /app/experts were reviewed: text is legible and
  panels are consistent. They also showed that the Funding fiscal-year inputs overflow their grid
  cell; that is added to UX-25.

## Gate
- Links and scaffolds; `make lint test build`: 1,370 passed, 9 skipped; `git diff --check`.
- `check_at5.py --dist dist`, `check_public_text.py` and the 9-page smoke all passed.
