# Handoff — 2026-11-16 — H25 round 2 (VD-21..VD-24) and the Plane Poster decision

## Done this run
- VD-21 desktop top nav (dropdowns from PAGE_GROUPS; sidebar hidden above 52rem; mobile drawer unchanged).
- VD-22 Overview: full-bleed hero and bands, eyebrow removed, KPI overlap fixed, three-colour one-line Start-here cards, trimmed Explore text, "How it works".
- VD-23 Monitoring: icon map toolbar with tooltips, full screen (API + fallback), sticky filter sidebar at >= 64rem.
- VD-24 larger headings, Evidence page-head fix, full-bleed page-head bands, shared `[data-atlas-tip]` tooltip and `.atlas-help` buttons on tricky components (not the hero).
- Impeccable: skill installed (owner also installed it into the repo; those untracked folders are owner work). `PRODUCT.md` written from owner answers; direction round served; owner chose "Plane Poster"; reference page `docs/design/intro_option_plane.html` published as a private artifact.
- Gate: lint, format, links, scaffolds, tokens, public text, Framework build, check_at5, full pytest (1,881 passed, 10 skipped), axe none on 9 routes.

## Repository state
- This commit holds VD-21..VD-24 plus records; tag `design-pacific-contour-2026-11-16` marks the last Pacific Contour design (GitHub release with screenshots).
- Untracked and not ours: `.agent/skills/`, `.agents/`, `.claude/agents/impeccable-*`, `.claude/skills/`, `.codex/`, `.github/agents|hooks|skills/`, `skills-lock.json`. `.impeccable/reference` and `.impeccable/sketches` are local scratch.

## Open findings
- H27 HTTPS enforcement still pending (retry `gh api -X PUT repos/:owner/:repo/pages -F https_enforced=true`).
- 833-900 px header search is narrow (~150 px). Breadcrumb hidden on mobile (unchanged). Institutions map h2 stays 1.05rem. Callout `border-left: 4px` flagged by the Impeccable hook (pre-existing).
- Impeccable finish review and DESIGN.md not run for the reference page; due at the end of VD-25.

## Next eligible
- VD-25 Plane Poster site-wide (owner decision; see TODO and ADR-VD25-PLANE-POSTER-2026-11-16).

## Owner actions (one line each)
- H27: tick Enforce HTTPS once GitHub finishes issuing the certificate.
- H2: review the 277 low-confidence work-relevance decisions.
- Decide whether to commit the Impeccable install folders you added to the repo.
