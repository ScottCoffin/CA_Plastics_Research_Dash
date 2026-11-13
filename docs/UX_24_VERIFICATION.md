# UX-24 verification (2026-11-12)

Contract: `docs/EM_spec.md` UX-24 (Monitoring CLS < 0.1; no nested interactive controls on
/app/monitoring and grants.html; grants.html aria-prohibited-attr, definition-list and
empty-table-header).

## Changes
- `framework/src/monitoring.md`: the quality note renders a static lead sentence before the data
  loads; the per-source licence and citation text fills a disclosure "Licences, citations and
  caveats" (sample rows still carry their citation). Facet summaries use a styled span instead of
  an h3, so Framework adds no anchor link inside `<summary>`.
- `framework/src/components/monitoring.js` and `monitoring.css`: the detail text target and the
  map-selection heading (h2) follow the new markup.
- `site/grants.html`: the chips container is a labelled `role="group"`; the metrics `<dl>` holds
  only dt/dd pairs; empty row-header cells carry visually hidden text ("Topic", "Recipient
  sector"); the stacked bar is `role="group"` instead of `role="img"` with focusable children.
- Test: `tests/test_ux24_monitoring_grants.py`.

## Evidence
- Lighthouse (mobile preset, local preview) on /app/monitoring: CLS 0.521 -> 0.036; Performance 60 -> 99.
- axe /app/monitoring: nested-interactive 5 -> 0, heading-order 1 -> 0.
- axe grants.html: aria-prohibited-attr, definition-list, empty-table-header and nested-interactive
  -> 0. Follow-up the same day: the 15 color-contrast nodes on the heat-map cells are fixed by choosing
  the higher-contrast of white and black text for each fill (at least 4.58:1); grants.html is now
  axe-clean.

## For owner review
- The licence/citation text is now behind a closed disclosure on the same page. CC BY attribution
  stays on the page and in every sample row; reopen it by default if you prefer it always visible.

## Gate
- Same gate run as UX-4 (`docs/UX_4_VERIFICATION.md`).
