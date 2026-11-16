# VD-7c verification: Evidence map

Date: 2026-11-16

## Result

VD-7c updates `framework/src/evidence.md`, `framework/src/components/evidence.css`,
`framework/src/components/evidence.js`, and `framework/src/components/ev_table.css`;
focused coverage is in `tests/test_vd7c_evidence.py`. The lead is exactly two
sentences, the How-to section is a disclosure, and the development and auxiliary-topic
messages use `role="note"` development and info callouts; the volume caveat is a
caution callout, and “New in the last 2 weeks” uses the New callout container. All
11 topic dots render. Trends, Evidence heatmap, and Publications use three chart
cards with the shared padded body. Selecting a heatmap item preserves UX-30
behavior, showing the 294-work selection banner and clear control. Final review added standard
`.atlas-disclosure__body` padding and an exact two-sentence assertion.

## Verification

The final VD-7c, Framework Evidence, and UX-30 focused checks reported 20 passed;
the combined visual regression set reported 37 passed. The full gate reported
1,702 passed and 9 expected skips; its pytest command is `py -3.14 -m pytest -q`
(see `CLAUDE.md` for the full gate). The Framework build produced 13 pages and 90
links with `cd framework && npm run build` and `py -3.14 scripts/check_at5.py --dist dist`.

The post-fix assembled preview was checked at 1440 x 900 and 390 x 844. Each of
the three chart bodies had 16 px padding on all sides. The development, info,
caution, and recent-items callouts were visible, and all 11 topic options had
dots. Axe found zero violations; there was no horizontal overflow or page error.
The only actionable target below 24 px was Framework's inert 1 x 1 sidebar
checkbox. The final screenshots are
`scratch/ux_vd7c_postfix_luna/evidence-1440x900.png` and
`scratch/ux_vd7c_postfix_luna/evidence-390x844.png`.

UX-30 interactions remained intact: selecting a cell showed 294 works (1–25 of
294); row and column selections showed 452 and 404 works. Clearing restored
1–25 of 1,579, and “Show in table” focused the Publications heading. Axe remained
clean after selection.

The latest informational local-preview Lighthouse run scored 70 performance and
100 accessibility, with CLS 0.03 and LCP 11.7 s. The historical baseline was
measured on the live CDN; the comparable live pre-change control was performance
92, accessibility 100, and CLS 0. Local and live results are not directly
comparable. Post-deployment live performance acceptance remains pending and is
not waived.

## Delegation and remaining work

Luna handled multiple production and follow-up sessions. The initial independent
tester hit the usage cap; final independent browser verification and review were
completed, with requested fixes incorporated. H25 owner review and VD-5 Overview
acceptance, including LCP, remain open. Recheck live Lighthouse performance after
deployment against the live baseline before closing VD-7c acceptance.
