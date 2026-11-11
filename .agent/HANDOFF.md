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
| 20 | Forensics: why Karapetrova missing/incomplete | Done: absent until the first real export (07:02 PST); fixed raw-affiliation + carry-forward CA inference, raw-affiliation ingest scope, author-anchored units, SSRN 'Title ' near-dup. Corpus 1,486 -> 1,896; site 1,774 works / 2,422 experts; her alpine poster included. 414 newly added works await Haiku relevance screening (after the owner finishes `curation/work_relevance.csv`) |
| 21 | Other sources to fill OpenAlex gaps (ORCID, Crossref, CORE, Semantic Scholar) | Assessed live: `docs/api_notes/supplementary_sources.md`; biggest gap is inside OpenAlex (raw-affiliation-only CA works, 35/40 sampled misses) — raw-affiliation scope added to the S2-COVERAGE worker; Europe PMC audit, ORCID enrichment, DataCite/CORE queued as TODO S2.5 |
| 22 | State institutions don't differentiate agencies | Done: 15 CA state agencies with works on site (OEHHA 37, SWRCB 35, DWR 34, CDPH 12, ...); State of California 41->5; owner's 11-05 top-100 review restored (was wiped 11-06); two state-agency overrides pending owner confirmation |
| 23 | Smarter human-in-the-loop (active learning) | Done: Smart queue default in `scripts/review_work_relevance_app.py`; CV AUC 0.92; accuracy panel; audit-round button; covers all 1,448 unlabeled non-test works; accept writes `curation/work_relevance_model.csv` |
| 24 | Extend active learning to other classification tasks | Spec written: `docs/ACTIVE_LEARNING.md`, TODO S5.0, spec Part E S5.0 (gold set stays separate; order S5.1 -> engine -> S5.5 -> S5.3 -> EM-4 -> grant topics) |
| 25 | HERO landing page, after all other substantive tasks | Specified: TODO S3.7 and spec Part E S3.7 (scheduled last; re-check Framework triggers first) |
| 26 | Funding page: filtering and sorting as an interactive table | Done: 10 sortable columns, search, sector/agency filters, chips, rows-per-page, sorted CSV, collapsible filters on phones |
| 27 | Doñana (non-CA) / top experts per institution | Done: CA-only default + collaborator toggle/badge; collaborator SEM pages with 'California connection'; Top experts table, year filter, experts×year view; top 3 on cards; `#experts?author=` deep links |
| 29 | Expert bios/photos (ORCID?) | Assessed: ORCID bios 8%, links 17% (CC0); Wikidata photos 3.5% (Commons licences); opt-in form is the main route. TODO S9.5 + spec |
| 30 | More bio/photo sources; capture emails; email outreach for consent (also advertises the Atlas) | Specified: `docs/OUTREACH.md`, TODO S9.6, ADR-OUTREACH; owner chose local private store, own-account mail-merge, Google/Microsoft Form; `data/private/` gitignored. Emails measured: 207 in OpenAlex affiliations, ~11% ORCID public |
| 31 | SEO / findability by robots for prime time | Specified: TODO S3.8 + spec Part E S3.8 (pre-rendered entity pages, sitemap, robots, JSON-LD Person/Organization/Dataset, Search Console owner actions, AI-crawler policy decision); Framework ADR notes S3.8 as a reason to weigh static routes |
| 28 | 'Risk assessment' topic | Done: 65 works, 39 grants; hatched violet + diamond in chips, bars, heatmaps, Sankey; grant topics now recomputed at export |
| 16 | Gates: AT-5/AT-6 deferred; SPK-5/AT-7, SPK-6/AT-8, AT-9, AT-10 approved; gold set = owner + Claude second rater | Recorded (ADR-GATES-2026-11-11) |

## Next eligible (dependency order)
1. S4.2 DONE (splits_v2). Next: gold-label Streamlit app for the owner over the 580 sampled
   works (guide_v2 fields), Claude second rater on a blind 20%; kappa report via S4.3 tooling.
2. AT-3 SQL analytics -> AT-4 serving bundle (abstract-free Parquet) -> AT-10 release pipeline.
3. AT-11 CI guards for S2.
4. SPK-6/AT-8 maps (reuse today's map helpers); SPK-5/AT-7 bibliometrix (R, outside CI).
5. S5.x after the owner labels the gold set; AT-9 after S5.

## Owner actions (one line each)
0. **2026-11-12: renew the CORE API key** (owner said it expires; the new value goes in `.env`). Remind the owner at the start of the next session.
1. Finish the 215 low-confidence works in `scripts/review_work_relevance_app.py` (Low confidence pending view).
2. Confirm the two pending state-agency overrides (`config/institution_overrides.csv`, rows marked pending).
3. AT2-REVIEW: types for 52 new top-100 institutions in `data/processed/institution_review_needs_v31.csv`.

## Notes
- Worktree leftovers not committed on purpose: `docs/SOURCES.md`,
  `docs/api_notes/source_watch_s7_6.json`, owner's `data/processed/p{5,25,100}.parquet`.
- Shell heredocs on this machine corrupt `\b` in regexes; write patch scripts with the Write tool.

Older handoff entries: `.agent/archive/HANDOFF_history.md`.
