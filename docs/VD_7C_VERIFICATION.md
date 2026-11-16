# VD-7c verification: Evidence map

Date: 2026-11-16

## Result

VD-7c updates `framework/src/evidence.md`, the Evidence styles and runtime, and
the shared publication table's optional preloaded-row path. The lead is exactly
two sentences; How-to is a disclosure; development, auxiliary-topic, volume,
and recent-work messages use the shared callout styles. All 11 topic dots render.
Trends, Evidence heatmap, and Publications use padded chart bodies. UX-30
selection, clear, and focus behavior is preserved.

Performance work moves the five page stylesheets before rendered markup, places
the asynchronously shown recent-work callout below the filters/charts, and waits
two animation frames before mounting Evidence data views. The page passes its
already-normalized plastic-related works to the trend and table. This avoids
repeating normalization and filtering the details payload and replaces 324
full-facet trend count queries with a single pass over those rows. Other table
callers retain the default fetch path.

## Verification

The final full local suite reported 1,706 passed and 9 expected placeholder
skips with `py -3.14 -m pytest -q`. Ruff lint/format, Node runtime checks, the
Framework build (13 pages/90 links), and `py -3.14 scripts/check_at5.py --dist
dist` passed.

The live site was checked at 1440 x 900 and 390 x 844 on deployed commit
`f8877c4c`. Both routes returned HTTP 200; axe found zero violations, with no
overflow, console/page/request errors, and one known inert 1 x 1 Framework
sidebar checkbox below 24 px. The page loaded 1,915 works and showed 1,579
plastic-related works, 27 trend years, 11 topic dots, and 16 px padding in each
chart body. Each page load requested `works_detail.json` once. Filtering changed
the count from 1,579 to 93 and updated the trend and table. UX-30 cell selection
showed 294 works (1–25 of 294); clear restored 1,579 and “Show in table” focused
Publications. Table search returned 201 rows; axe stayed clean after interaction.
Browser evidence: `scratch/ux_vd7c_row_reuse_live/functional-results.json` and
the `run1`–`run3` screenshots/reports.

Three comparable live Lighthouse runs scored 92, 92, and 97 (median 92, matching
the baseline of 92). LCP was 1.737–1.820 s, TBT 105–284 ms, and CLS 0.088;
accessibility, Best Practices, and SEO scored 100 throughout. LCP identified the
page lead. Evidence: `scratch/ux_vd7c_row_reuse_live/run1/` through `run3/`.

The first row-reuse CI run failed because its runtime test imported undeclared
`jsdom`; the next fresh-checkout run exposed a generated-module import in that
test. The final test imports the DOM-free row-resolution helper from the table
model, adding no dependency and retaining fast-path, fallback, snapshot, and
validation coverage. The live-tested implementation is `f8877c4c`; the final
behavior-preserving CI follow-up is `435ba318`. CI run `43950760535`, Pages run
`43950760513`, and legacy Pages run `43950758055` all passed.

## Delegation and remaining work

Luna handled the implementation, independent reviews, performance diagnosis,
bounded corrections, and live audits. H25 owner review and VD-5 Overview
acceptance, including its absolute LCP target, remain open.
