# VD-8 verification: Policy, resources, About, and glossary

Date: 2026-11-16

## Result

VD-8 updates `framework/src/about.md`, `framework/src/glossary.md`, and the
Policy, Resources, About, and Glossary stylesheets (`about.css`, `glossary.css`,
`policy.css`, `resources.css`). Focused assertions are in
`tests/test_vd8_context_pages.py`. Policy uses a vertical timeline with 10
items, visible caveat, and eight external source links. At 390 px its date rail
and content columns remain readable at 80 px and 219 px. Resources has 12
cards, 11 reuse badges, and 12 steward fields. About keeps its citation and
limitations visible, with the DOI in monospace. Glossary has 15 term IDs and
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

## Delegation and remaining work

Luna handled implementation and follow-up. An initial independent browser
tester hit the account usage cap; final independent Luna browser audits passed
all four routes, and independent code review approved after small fixes.
Historical Lighthouse baselines were measured against the live CDN and are not
comparable to this slower local assembled preview. A comparable pre-change
live About control scored performance 99, accessibility 100, and CLS 0; the
post-deployment live comparison required by the performance regression gate is
pending.

H25 owner review and VD-5 Overview acceptance remain open. This record covers
local assembled acceptance and does not claim deployment.
