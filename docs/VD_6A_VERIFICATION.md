# VD-6a verification: Experts adoption

Date: 2026-11-15

## Result

VD-6a updates the Framework Experts page in `framework/src/experts.md`,
`framework/src/components/experts.css`, and `framework/src/components/experts.js`.
The page presents Search, Domain or matrix tag, Institution type, and Sort by as
the four primary filters; Institution, Current affiliation, Career stage, From
year, To year, CA basis, and OA are under More filters. Rows use the shared
design system, with active filter chips, a visible result line and volume
caption, primary Export and secondary Reset actions, a terminology disclosure,
and the shared detail drawer.

The change includes `tests/test_vd6a_experts.py`. Focused worker verification
reported 33 passed, with Node, Ruff, and diff checks passing. The consolidated
suite reported 1,595 passed and 9 expected placeholder skips. The Framework
build produced 13 pages and 76 links.

## Assembled browser acceptance

The local production-shaped assembly was checked at 1440 x 900 and 390 x 844.
At both widths axe reported zero violations; horizontal overflow, console
errors, page errors, and request errors were all zero. The primary filter group
contains four controls and More filters contains seven. The browser interaction
check preserved `#search=Smith`, showed one active chip, opened the drawer with
the `dialog` role, closed it, and confirmed Reset clears the hash.

At 1440 x 900, exactly three expert rows were fully visible; the third row's
bottom edge was 897.375 px. No actionable target was below 24 px. The target
scan's only excluded 1 x 1 box was Framework's accepted inert sidebar checkbox.

## Delegation and remaining work

Production implementation was Luna delegated in four turns/sessions: the
initial implementation plus three bounded corrections for row/target sizing,
the pixel-safe viewport, and duplicate-selector cleanup. One independent Luna
browser auditor was dispatched but hit the account usage cap; the primary agent
completed the browser verification above. Evidence is local to the assembled
site; this check does not claim a live deployment.

H25, the owner side-by-side design review in VD-12, remains open. VD-5 Overview
acceptance also remains open, including its LCP requirement. VD-6b status is
tracked separately.
