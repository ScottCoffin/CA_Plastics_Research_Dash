# Handoff - 2026-11-12 - Expert pages/metrics (H7 follow-up), H5 answers applied, MiniSearch, Framework installed, outreach contacts

## Done this session
- H3 AT2-REVIEW committed (e07b1ec). H4 photos (43 approve / 1 reject) ship in this export.
- Expert features (ADR-EXPERT-METRICS-2026-11-12): `site/expert.html#author=` full page (Haiku worker), primary affiliation, own affiliation history, citations-per-year histogram (plastics coloured), sortable/filterable works with topic-chip filters, default sort plastics citations, m-quotient, rising score + "Find up-and-coming researchers". Data from `fetch_author_metrics.py` (career group_by + plastics by year; 2,799/2,799 covered).
- H5 answers applied: AT11-WINDOW (cap at yesterday), CA-CARRY-ORCID (22 carry-forwards dropped), UNSURE-SEM (unsure = false), OUTREACH-EMAILS (S9.6a builder, data/private only), AT4-SEARCH (MiniSearch 7.2.0 vendored + wired, Haiku), EM5-FRAMEWORK (framework/ with @observablehq/framework 1.13.4 installed).
- Budget guard: 502/503/504 without credit header charged the 10-credit reserve (a 504 had locked the day's ledger).

## Next eligible (dependency order)
1. AT-5 Framework shell in `framework/` (cross-cutting: lead plans, Haiku builds bounded pages; keep `site/` live until parity checks pass). Check `npm audit` output first (scratch/npm_install.txt warned about deprecated glob).
2. 2026-11-13: CORE full-text audit after the owner renews the key; close S2.5.
3. Resume `fetch_escholarship_items.py` (148 pending).
4. After H9 gold labels: Claude second rater, kappa, S5.1 test eval, S5.0 engine.

## Owner actions (details in `.agent/HUMAN_TASKS.md`)
- H15: check the new expert pages and the up-and-coming list; answer RISING-METRIC.
- H8: approve the outreach email template (contacts ready: 660 experts).
- H2 relevance review, H9 gold labels (in progress), H1 CORE key 2026-11-13.
