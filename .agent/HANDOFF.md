# Handoff - 2026-11-11 (afternoon) - owner UX requests delivered; A1 gates cleared

This file is the live tracker for the current session: update it at every checkpoint
(owner requests, status, next steps) so a fresh session can resume without chat history.

## Owner request tracker (2026-11-11)
| # | Request | Status |
|---|---|---|
| 1 | Experts populated with real data | Done: v3.1 backfill live (1,424 works, ~1,950 CA experts) |
| 2 | Monitoring map interactive; expandable facet boxes | Done (zoom/pan/keyboard, details panel, legend toggles, `<details>` sections) |
| 3 | OpenAlex up to $1/day as a rule; fallback key when exhausted | Done (`config/budget.yml` 0.95; `OPENALEX_API_KEY_ALT` local + CI secret) |
| 4 | Grant relevance review app | Done; owner finished review; strong-term rule (plastic pollution, micro/nano-plastics, plastic/marine debris, plastic particles, anthropogenic debris, tire wear particles) |
| 5 | v3.1 unseen works checked by Haiku; owner reviews 215 low-confidence | Haiku done (`curation/work_relevance.csv`); owner review app `scripts/review_work_relevance_app.py` (owner in progress) |
| 6 | Why S5 was skipped | Answered: S5 needs the S4 gold set, which needed the corpus that never ingested |
| 7 | Expert topics readable, pretty labels, conserved colours | Done (`site/assets/topics.js`, two-line chips) |
| 8 | Expert sort by total citations, h-index, plastics citations | Done; plastics citations now whole-record (Rochman 98.7%) with `plastic_basis` |
| 9 | Institutions map with basemap, interactive, city/landmark labels | Done (shared map helpers, priority labels) |
| 10 | Institution topic weighting; sort by primary topic | Done (stacked topic bar, primary-topic chip, share-of-topic sort, filter) |
| 11 | "View publications" → institution SEM with abstracts + topic heatmap | Done (`site/sem.html#inst=<id>`) |
| 12 | Auto-merge same name + same institution | Done (`scripts/build_author_merges.py`, 108 merges, run in CI) |
| 13 | Expandable full abstracts in expert drawer | Done |
| 14 | Grants visualization suite with Sankey (funder → sector → institution → topic), filters | Done (`site/grants.html`; sectors in `config/grant_sectors.yml`) |
| 15 | Keep abstracts (emails redacted); DTSC dates confirmed | Recorded |
| 17 | Observable Framework: advantages written up; revisit automatically | Done: ADR-FRAMEWORK-REVISIT-2026-11-11; `scripts/check_framework_triggers.py` in CI |
| 18 | Drawer: affiliation history + co-author institutions collapsed; summary metrics | Done: collapsed boxes, metrics strip, "Frequent co-authors" (named CA experts, shared-work counts, click-through); fixed first-click-lost bug in the experts list |
| 19 | Expert collaboration network (deferred) | Written up: TODO S9.4, spec Part E S9.4, REUSE candidates (networkx, VOSviewer Online, sigma.js/graphology) |
| 16 | Gates: AT-5/AT-6 deferred; SPK-5/AT-7, SPK-6/AT-8, AT-9, AT-10 approved; gold set = owner + Claude second rater | Recorded (ADR-GATES-2026-11-11) |

## Next eligible (dependency order)
1. S4.2 DONE (splits_v2). Next: gold-label Streamlit app for the owner over the 580 sampled
   works (guide_v2 fields), Claude second rater on a blind 20%; kappa report via S4.3 tooling.
2. AT-3 SQL analytics -> AT-4 serving bundle (abstract-free Parquet) -> AT-10 release pipeline.
3. AT-11 CI guards for S2.
4. SPK-6/AT-8 maps (reuse today's map helpers); SPK-5/AT-7 bibliometrix (R, outside CI).
5. S5.x after the owner labels the gold set; AT-9 after S5.

## Owner actions (one line each)
1. Finish the 215 low-confidence works in `scripts/review_work_relevance_app.py` (Low confidence pending view).
2. AT2-REVIEW: types for 52 new top-100 institutions in `data/processed/institution_review_needs_v31.csv`.

## Notes
- Worktree leftovers not committed on purpose: `docs/SOURCES.md`,
  `docs/api_notes/source_watch_s7_6.json`, owner's `data/processed/p{5,25,100}.parquet`.
- Shell heredocs on this machine corrupt `\b` in regexes; write patch scripts with the Write tool.

Older handoff entries: `.agent/archive/HANDOFF_history.md`.
