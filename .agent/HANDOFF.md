# Handoff - 2026-11-12 - AT-5 Framework app live at /app/; EM-5, EM-16, EM-18 pages

## Done this session
- AT-5 (partial, ADR-AT5-SHELL-2026-11-12, `docs/AT_5_VERIFICATION.md`): Observable Framework app in `framework/` (Overview, Experts, Institutions, Monitoring, Funding, About), ported lift-and-shift from `site/index.html` by Haiku workers. Deployed at https://plastiverse.live/app/ (confirmed live) beside the classic root; the Framework deploy step is best-effort.
- EM-5 done (ADR-EM5-SHELL-2026-11-12, `docs/EM_5_VERIFICATION.md`): `/app/evidence` with AT-4 bit-set facets, hash state, shared works drawer (`openWorksDrawer`), related-resources strip from `site/data/linkouts.json` (rules in `config/linkouts.yml`, default per QUESTIONS EM5-STRIP), V-1..V-5 placeholders.
- EM-16 `/app/resources` and EM-18 `/app/policy` (DTSC timeline, caveat always shown) done (`docs/EM_16_VERIFICATION.md`, `docs/EM_18_VERIFICATION.md`).
- Tooling: `scripts/check_at5.py`, `scripts/serve_framework_preview.py`, `scripts/smoke_framework_pages.py`, `scripts/build_linkouts_json.py --check`.

## Verified / not verified
- Verified: full gate (lint, 1,325 tests, build, links, scaffolds, diff check), clean-worktree tests, CI + deploy green for AT-5, live render of /app/ pages.
- Not verified: drawer dialog and keyboard walk-through in a real browser; dark theme; MiniSearch ranking on the new pages.

## Next eligible (dependency order)
1. After H16 ("switch"): Framework at the root; classic hashes redirect to the new pages.
2. 2026-11-13: CORE full-text audit (H1 key); resume `fetch_escholarship_items.py` (148 pending).

## Owner actions (details in `.agent/HUMAN_TASKS.md`)
- H16: compare https://plastiverse.live/app/ (incl. the new Evidence map) with the classic site; reply "Framework pages OK, switch" or list differences. Answer EM5-STRIP (keep default link-out rules?).
- H15 expert pages + RISING-METRIC; H8 outreach template; H2 relevance review; H9 gold labels; H1 CORE key.
