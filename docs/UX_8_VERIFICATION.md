# UX-8 verification (2026-11-12)

Contract: `docs/EM_spec.md` UX-8; owner default UXD-6 (no headline dollar sum on the first screen;
per-source subtotals with the not-a-total caveat).

## Changes
- `framework/src/components/funding.js`: the status line gives counts only ("503 of 524 awards
  match. 492 report an amount."). The Amount basis section shows a per-source table (source,
  awards with an amount, reported amount, amount basis) whose caption says, in the same sentence
  as the figures, that they "are not a total: sources use different amount bases and cannot be
  added". Styles in `funding.css`.
- `framework/src/funding.md`: the selector reads "Rows per page (default 50)", and 50 is selected.
- `site/grants.html`: the "Reported amount" tile is removed from the first-screen metrics. Sankey
  tooltips already state "source bases differ" and are unchanged.
- Test: `tests/test_ux8_funding.py`.

## Evidence
- Local preview: 6 sources in the subtotal table (for example NSF 309 awards, NIH 126,
  USAspending 72; California Sea Grant "None reported").
- axe: no new violations (Framework sidebar `list`/`region`; the 15 grants heat-map contrast
  nodes predate this task).
