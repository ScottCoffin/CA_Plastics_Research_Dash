# UX-23 verification (2026-11-12)

Contract: `docs/EM_spec.md` UX-23 (one visible h1 on /app/experts and /app/funding; no heading-level
skips on any /app/ route).

## Changes
- Experts: page title is the h1; a visually hidden h2 "Expert list" sits above the cards, whose
  names stay h3 (`experts_model.js` unchanged).
- Funding: "Funding" h1; "Awards" and "Open funding calls" h2; "Amount basis" h3.
- Institutions: map title h2; card names h2; "Top experts" and map-details headings one level up.
  CSS selectors were moved so sizes are unchanged.
- Resources: resource names h2. About: the four card headings are `##`.
- Evidence: V-4 trend headings h4 -> h3 (`v4_trend.js`; styled by class, so the look is unchanged).
- Test: `tests/test_ux23_headings.py`.

## Evidence
- Before (local axe-core 4.10.3): page-has-heading-one on experts and funding; heading-order on
  institutions, monitoring, evidence, resources and about.
- After: no page-has-heading-one or heading-order violation on any of the 9 /app/ routes
  (monitoring fixed under UX-24). Remaining findings: Framework sidebar `list`/`region` (template
  limit, see UX-22) and `aria-allowed-role` on the Experts virtual rows (pre-existing; UX-15 rework).

## Gate
- Same gate run as UX-4 (`docs/UX_4_VERIFICATION.md`).
