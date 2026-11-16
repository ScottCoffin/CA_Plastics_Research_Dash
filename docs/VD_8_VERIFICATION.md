# VD-8 verification: Policy, resources, About, and glossary

Date: 2026-11-16

## Result

VD-8 updates `framework/src/about.md`, `framework/src/glossary.md`, and the
Policy, Resources, About, and Glossary stylesheets (`about.css`, `glossary.css`,
`policy.css`, `resources.css`). Focused assertions are in
`tests/test_vd8_context_pages.py`. Policy uses a vertical timeline with 10
items, visible caveat, and eight external source links. At 390 px its date rail
and content columns remain readable at 80 px and 219 px. Resources has 12
cards, 11 reuse badges, and 12 steward fields in the local pre-deployment
snapshot. About keeps its citation and limitations visible, with the DOI in
monospace. Glossary has 15 term IDs and
15 matching self-anchor links; the Barlow display face is used and a hash
target receives a visible brand-wash and inset highlight.

## Verification

The final combined visual regression set reported 37 passed. The full gate
reported 1,706 passed and 9 expected placeholder skips. `npm run build`
produced 13 pages and 90 links.

The assembled local site was checked at 1440 x 900 and 390 x 844 on Policy,
Resources, About, and Glossary at `#current-affiliation`. Axe violations, horizontal
overflow, console errors, page errors, request errors, and actionable targets
below 24 px were zero; the accepted inert Framework sidebar checkbox was
excluded from the target count. Glossary's final source assertions also check
for exactly 15 terms. The standard desktop/mobile screenshots are in
`scratch/ux_vd_batch4_final/`; the final mobile captures are
`scratch/ux_vd_batch4/deep-policy-390.png`, `deep-resources-390.png`,
`deep-about-390.png`, and `deep-glossary#current-affiliation-390.png` in the
same directory.

Local mobile Lighthouse scores were Policy 98, Resources 98, About 85/85/84
(median 85), and Glossary 97. CLS was 0 on Policy, Resources, Glossary, and two
About runs; the third About run was 0.051 (median 0). Accessibility, Best
Practices, and SEO were 100 on all four routes.

## Live deployment acceptance

Deployment `47b0e56a` passed CI workflow `43952424277`, Pages workflow
`43952424293`, and legacy Pages workflow `43952424800`. Live checks at 1440 x
900 and 390 x 844 passed on Policy, Resources, About, and Glossary: all routes
returned HTTP 200, axe found zero violations, and there was no horizontal
overflow or console, page, or request error. Policy shows all 10 timeline items
and its caveat; About shows its citation, two monospace DOI references, and
limitations; Glossary has 15 unique targets and the current-affiliation
brand-wash highlight.

Live Resources lists 13 cards, 13 stewards, and 12 reuse badges. The additional
LO-13 consortium resource is an intended existing resource; the live count
difference from the local pre-source snapshot (12 cards, 12 stewards, 11
badges) is not a design regression.

Live Lighthouse performance scores (baseline to live) were Policy 100 to 100,
Resources 100 to 100, About 98 to 99, and Glossary 100 to 100. Policy CLS was
0; accessibility, Best Practices, and SEO were 100 on every route. All scores
met their acceptance floors.
The size audit found the known inert 1 x 1 control; Policy also has four 20 px
desktop text links. Axe passed, and the only small target on mobile was the
inert control. Live evidence is in `scratch/ux_vd8_live_acceptance/`.

## Delegation and remaining work

Luna handled implementation and follow-up. An initial independent browser
tester hit the account usage cap; final independent Luna browser audits passed
all four routes, and independent code review approved after small fixes.
The earlier local Lighthouse scores above are not comparable to the deployed
live measurements.

VD-8 deployment acceptance is complete. H25 owner review and VD-5 Overview
acceptance remain open.
