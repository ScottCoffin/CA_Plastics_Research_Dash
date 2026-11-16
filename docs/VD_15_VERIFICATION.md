# VD-15 verification: page header on the context pages

Date: 2026-11-16

Policy, Related resources, About and Glossary now open with a static `.atlas-page-head`:
eyebrow with the nav group and icon (Context: scale, link; Reference: info, book), one h1 and
a lead of at most two sentences. Each page calls `injectIconSprite()`. Resources moves its third
intro sentence below the header; Glossary's intro becomes the lead. Policy caveat, About
limitations/corrections/DOI and the 15 Glossary anchors are unchanged. Found by the VD-12
snapshots (routes had no page header or icon).

Verification: `tests/test_vd15_context_heads.py` plus the VD-8, policy, resources, UX-7/10/12/23
suites; assembled local site: axe no violations at desktop and 375 px, one h1, no overflow or
console errors on all four routes; `ux_tasks.py` 6/6. Screenshot `scratch/vd15/policy.png`.
