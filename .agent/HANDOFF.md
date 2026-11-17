# Handoff — 2026-11-16 — H25 owner design feedback (VD-18, VD-19, VD-20)

## Done this run
- VD-18 visual polish (`docs/VD_18_VERIFICATION.md`): hero contour contrast, red eyebrow dots, larger
  card/task/KPI text, "Quick routes" removed, Start-here links not underlined, brand-link green square
  removed (nav-icon swatch on the home link), footer one line with no "Source code" link, drawer
  "Open full profile page" contrast, About pipeline/feed links render, trend ticks every 2 years,
  hero search icon inside the field.
- VD-19 site-wide search (`docs/VD_19_VERIFICATION.md`): header + hero combobox over experts,
  institutions, topics, funders, glossary, resources, pages; `/search#q=`; daily ingest rebuilds the index.
- VD-20 network (`docs/VD_20_VERIFICATION.md`): ForceAtlas2 default layout; algorithmic Louvain cluster
  labels (institution and/or over-represented topic) on canvas, legend and table.
- Records: H26 closed (logo permission confirmed in `config/research_networks.yml`); NET-1, VD-D8, VD-D9
  answers recorded; agent maxTurns raised (developer 90, tester 70, reviewer 60; next session).
- Gate: full local gate 1,834 passed; clean worktree 1,830 passed / 13 skipped; axe none on 6 routes.

## Repository state
- Commits `4a01550b` (VD-20), `1f11d4ac` (VD-18/VD-19), then this records commit; pushed to `main`
  (verify CI and Pages).

## Open findings
- H27: GitHub still reports the Pages certificate as `dns_changed` ("certificate has not finished being
  issued"); the API refused `https_enforced=true`. Retry with
  `gh api -X PUT repos/:owner/:repo/pages -F https_enforced=true` at the next session start.
- Search groups are fixed-order (experts first), so "davis" lists people named Davis above UC Davis.
- Network cluster names can overlap expert name labels.
- Carried over: VD-5 Overview LCP (absolute 1.1 s gate kept, VD-D9), classic expert.html icon (UX-13),
  `check_s3_1.py` pinned fixture counts, 390 px header menu second-click issue, MEMORY.md is over 200 lines.

## Next eligible
- UX-13 remaining (expert.html into the app shell; URL-saved state on Funding and Monitoring).
- VD-5: try inlining the Overview critical CSS (owner VD-D9).

## Owner actions (one line each)
- H25: re-check the live site after this deploy; reply "design OK" or list changes.
- H27: tick Enforce HTTPS once GitHub finishes issuing the certificate.
- H2: review the 277 low-confidence work-relevance decisions.
