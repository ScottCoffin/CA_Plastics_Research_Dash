# VD-6b verification: Collaboration network adoption

Date: 2026-11-15

## Result

VD-6b updates the Framework collaboration network in
`framework/src/network.md`, `framework/src/components/network.css`, and
`framework/src/components/network.js`; the focused test is
`tests/test_vd6b_network.py`. The toolbar has four primary controls (Find an
expert, Colour by, Size by, Research topic) and six filters under More filters
(Institution sector, Institution contains, From year, To year, Minimum
co-authored works, Now in California only). Six 40 x 40 canvas controls cover
Zoom in, Zoom out, Reset view, Full screen, Re-run layout, and Restore saved
layout; each has a visible tooltip and accessible name. The page has nine
legend chips, a card detail panel, a two-sentence lead, a "How to read the
network" disclosure, and the visible volume caveat. The selected-expert panel
is a labeled section, not a nested complementary landmark.

## Verification

Focused acceptance reported 19 passed; Node, Ruff, and diff checks passed. The
consolidated suite reported 1,595 passed and 9 expected placeholder skips. The
Framework build produced 13 pages and 76 links.

The local production-shaped assembly was checked at 1440 x 900 and 390 x 844.
Axe violations, horizontal overflow, console errors, page errors, request
errors, and actionable targets below 24 px were all zero. The only excluded
target was Framework's accepted inert 1 x 1 sidebar checkbox. The page reported
400 experts and 1,241 links; the graph rendered seven canvases. Setting Colour
to topic, zooming in, resetting the view, and opening the explanatory
disclosure left the graph present and the URL stable.

## Delegation and remaining work

Luna production took two sessions: initial implementation and an accessibility
landmark correction. One independent Luna browser tester was dispatched but
hit the account usage cap; the primary agent completed the local assembled
browser verification. VD-6a commit `3f088f2e` is deployed and accepted;
Pages/CI passed, with live acceptance recorded in follow-up `fe340a34`. VD-6b
evidence remains local pending its narrow push.

H25, the owner side-by-side design review in VD-12, and VD-5 Overview
acceptance, including LCP, remain open.
