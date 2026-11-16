# VD-7b verification: Funding page

Date: 2026-11-16

## Result

`framework/src/funding.md` now has one page header (Data eyebrow, h1 "Funding",
lead) and no "Awards" h2. The amount-basis text is a visible caution callout and
the volume note an info callout. Filters use the shared panel: Search, Funder
agency, Topic tag and fiscal year from/to as primary fields; nine more under "More
filters (9)", which opens when a hidden filter is active; active filters show as
removable chips with an "N on" count. Five stat tiles reserve their height. All
five charts are `.atlas-chart` cards with a Chart/Table segmented control
(`aria-pressed`), replacing the "View ... as a table" links; the heatmap table pane
is uncoloured. `funding.css` and `funding_viz.css` are on tokens (hex 30 -> 0 and
1 -> 0). Element ids and the URL hash are unchanged.

`scripts/ux_tasks.py` task 5 now opens "More filters" before choosing "Led from
California", as a visitor would.

## Verification

- Tests: `tests/test_vd7b_funding.py` (12); `tests/test_framework_funding_viz.py`
  updated for Chart/Table controls; UX-8, UX-16, UX-23 and VD-10 suites pass.
- Assembled local site: axe no violations at desktop and 375 px; no overflow,
  console or HTTP errors; one h1. Lighthouse (local): accessibility 100, CLS 0.
  `ux_tasks.py` 6/6 (task 5 reads the NIH RePORTER amount basis).
- Screenshot: `scratch/vdv/ux2/` (gitignored).

## Deviations

- At 40rem and below the primary fields stack one per row, so charts start lower
  on phones.
- 50 targets under 24 px remain (unchanged from before; UX-32).
- Local Lighthouse performance (55) is not comparable with the live baseline; see
  Deployed.

## Deployed

Deployed with `d93dbb00` (CI `43970006962`, Pages `43970006785` passed). Live Lighthouse (mobile, 3 runs): accessibility 100 and CLS 0 to 0.027 on `/institutions`, `/institution`, `/funding` and `/network`; performance medians 57, 54, 82 and 72, below the 2026-11-14 baseline. A same-machine A/B of the pre-change build (`2cc15d30` files, `dist-ctl`) against the new build, alternating 3 runs each, gave medians before/after of funding 77/77, institution 72/72 and institutions 61/71 with equal or lower TBT, so the change does not cost performance; the live gap is host variance and data growth (unchanged `/policy` measured 1.59 s LCP vs 0.99 s baseline the same day). Network CLS on live is now 0 (VD-14).
