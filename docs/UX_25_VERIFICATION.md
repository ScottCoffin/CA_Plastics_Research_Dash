# UX-25 verification (2026-11-12)

Contract: `docs/EM_spec.md` UX-25 (no 375 px overflow; 24 px touch targets; meta description per
page; fix the per-page console 404; Funding fiscal-year inputs at 1366 px).

## Changes
- `framework/scripts/postbuild.mjs`: inserts a one-sentence `<meta name="description">` into each
  built /app/ page (10 pages, Glossary included). Test: `tests/test_ux25_mobile_meta.py`.
- 404: every page requested `/favicon.ico`, which does not exist. `framework/observablehq.config.js`
  now sets an inline SVG favicon through `head` (committed with UX-7, same file).
- 375 px overflow: on Evidence the cause was the trend panel's visually hidden data table (1,592 px
  wide); `evidence.css` clips it and lets the layout shrink. About overflowed on long DOI URLs;
  `style.css` wraps long words in running text.
- Funding fiscal-year inputs: `width: 100%; min-width: 0` in `funding.css`.
- Touch targets: chips, checkboxes and table links in `evidence.css`, `funding.css`,
  `monitoring.css` and `resources.css` reach 24 px.

## Evidence (local preview, Playwright + axe + Lighthouse)
- Horizontal overflow at 375 px: before on Evidence, Funding and About; after on none of the
  10 routes.
- Console errors and HTTP >= 400 responses: 0 on all routes.
- Lighthouse SEO: 90 -> 100 on the seven routes measured (accessibility and best practices 100).
- Small targets left: links inside sentences and the shared header/footer links (inline text
  links are exempt from WCAG 2.5.8).

## Not done
- Local cleanup by the worker was blocked: preview servers on ports 8778/8779 and the gitignored
  `framework/dist-h` folder may still exist on the owner's machine.
