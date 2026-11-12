# Handoff - 2026-11-13 - AT-5 Framework app beside the classic site (overnight)

## Done this session
- AT-5 (partial, ADR-AT5-SHELL-2026-11-12, `docs/AT_5_VERIFICATION.md`): Observable Framework app in `framework/` with Overview, Experts, Institutions, Monitoring, Funding and About pages, ported lift-and-shift from `site/index.html` by four Haiku workers. The deploy builds it into `/app/` with a best-effort step; the classic site stays the root.
- Tooling: `scripts/check_at5.py` (static in CI; `--dist` in deploy), `scripts/serve_framework_preview.py` (local Pages layout), `scripts/smoke_framework_pages.py` (headless Edge DOM smoke). Tests `tests/test_framework_*.py` (Node runtime for each page's pure helpers).
- Gate: lint, 1,306 tests, build, doc links (now skips `framework/src`, whose clean URLs Framework validates), scaffolds, diff check.

## Verified / not verified
- Verified: local build, AT-5 checks, all six pages render real data in headless Edge, deep links.
- Not verified: CI deploy of `/app/` (check the first run after this push), keyboard and dark-theme walk-through, MiniSearch ranked search in a browser.

## Next eligible (dependency order)
1. Confirm the deploy run published `/app/` (https://plastiverse.live/app/).
2. After H16 ("switch"): make Framework the root, move classic-only pages alongside, redirect `index.html#<tab>?...` hashes.
3. EM-5 Evidence Map shell as a Framework page (after the switch, or as a new `/app/` page sooner).
4. 2026-11-13: CORE full-text audit (H1 key); resume `fetch_escholarship_items.py` (148 pending).

## Owner actions (details in `.agent/HUMAN_TASKS.md`)
- H16: compare https://plastiverse.live/app/ with the current site; reply "Framework pages OK, switch" or list differences.
- H15 expert pages + RISING-METRIC; H8 outreach template; H2 relevance review; H9 gold labels; H1 CORE key.
