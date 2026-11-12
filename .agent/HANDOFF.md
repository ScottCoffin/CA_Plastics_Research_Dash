# Handoff - 2026-11-11 (session end, 91% of usage window) - AT-3/4/11 done; AT-10, S2.5, S9.5 partial

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
| 22 | State institutions don't differentiate agencies | Done: 15 CA state agencies with works on site (OEHHA 37, SWRCB 35, DWR 34, CDPH 12, ...); State of California 41->5; owner's 11-05 top-100 review restored (was wiped 11-06); two state-agency overrides owner-confirmed 2026-11-11 |
| 23 | Smarter human-in-the-loop (active learning) | Done: Smart queue default in `scripts/review_work_relevance_app.py`; CV AUC 0.92; accuracy panel; audit-round button; covers all 1,448 unlabeled non-test works; accept writes `curation/work_relevance_model.csv` |
| 24 | Extend active learning to other classification tasks | Spec written: `docs/ACTIVE_LEARNING.md`, TODO S5.0, spec Part E S5.0 (gold set stays separate; order S5.1 -> engine -> S5.5 -> S5.3 -> EM-4 -> grant topics) |
| 25 | HERO landing page, after all other substantive tasks | Specified: TODO S3.7 and spec Part E S3.7 (scheduled last; re-check Framework triggers first) |
| 26 | Funding page: filtering and sorting as an interactive table | Done: 10 sortable columns, search, sector/agency filters, chips, rows-per-page, sorted CSV, collapsible filters on phones |
| 27 | Doñana (non-CA) / top experts per institution | Done: CA-only default + collaborator toggle/badge; collaborator SEM pages with 'California connection'; Top experts table, year filter, experts×year view; top 3 on cards; `#experts?author=` deep links |
| 29 | Expert bios/photos (ORCID?) | Assessed: ORCID bios 8%, links 17% (CC0); Wikidata photos 3.5% (Commons licences); opt-in form is the main route. TODO S9.5 + spec |
| 30 | More bio/photo sources; capture emails; email outreach for consent (also advertises the Atlas) | Specified: `docs/OUTREACH.md`, TODO S9.6, ADR-OUTREACH; owner chose local private store, own-account mail-merge, Google/Microsoft Form; `data/private/` gitignored. Emails measured: 207 in OpenAlex affiliations, ~11% ORCID public |
| 31 | SEO / findability by robots for prime time | Specified: TODO S3.8 + spec Part E S3.8 (pre-rendered entity pages, sitemap, robots, JSON-LD Person/Organization/Dataset, Search Console owner actions, AI-crawler policy decision); Framework ADR notes S3.8 as a reason to weigh static routes |
| 28 | 'Risk assessment' topic | Done: 65 works, 39 grants; hatched violet + diamond in chips, bars, heatmaps, Sankey; grant topics now recomputed at export |
| 32 | DuckDB dependency for AT-3 | Done: owner chose duckdb==2.0.0 and moved the G-PARQ writer pin (ADR-DUCKDB-2-2026-11-11) |
| 33 | AT-3 SQL analytics | Done: `atlas.analytics`, `docs/AT_3_VERIFICATION.md`; every ranked CA institution overlaps a neighbour, so show tiers/intervals, not strict ranks |
| 34 | AT-4 serving bundle (tiers with ranges, owner-confirmed) | Done: `site/data/bundle/`, `site/assets/facets.js`; Institutions tab tier UI next |
| 35 | AT-11 CI guards | Done: schema/payload guards before the daily commit; analytics + bundle rebuilt daily |
| 36 | AT-10 release pipeline | Pipeline done; owner cuts the next GitHub release (mints a Zenodo DOI) |
| 37 | S2.5 Europe PMC recall | Benchmark 51.0% (438/858); DOI ingest after the OpenAlex daily reset |
| 38 | S2.5c ORCID / S2.5d DataCite / S9.5 photos | ORCID 1,604 profiles (carry-forward 90/19/121); DataCite 98 plastic outputs (84 not in corpus); 44 licensed Wikidata photos (metadata only) |
| 39 | Review apps highlight the admitting search terms in title + abstract | Done 2026-11-11: `atlas.review_highlight` (core / qualified+context / tier-2 / grant keywords / exclusions / plastic* stems; matched-terms line + legend) in all three `scripts/review_*_app.py` |
| 40 | Streamlit torchvision / `__path__` traceback spam in the work review app | Fixed: `.streamlit/config.toml` `fileWatcherType = "none"` (the watcher probes transformers' lazy zoedepth aliases, which import the missing torchvision); restart the app after code edits |
| 41 | Persistent human-task list with simple instructions | Done: `.agent/HUMAN_TASKS.md` (CLAUDE.md session entry step 6); photo review sheet `curation/expert_photo_review.csv` via `scripts/build_photo_review.py` |
| 42 | Rule: human reviews with >10 cases get a Streamlit app | Recorded (CLAUDE.md step 6, HUMAN_TASKS.md); applied: `scripts/review_institution_types_app.py` (AT2-REVIEW, 47 rows) and `scripts/review_expert_photos_app.py` (44 photos), shared `atlas.csv_review` |
| 43 | 'Plastisphere' as its own topic | Done: `config/taxonomy.yml` phrase seeds (59 published works, 37 grants); hatched ecotox pink in `site/assets/topics.js` (hatch patterns now one per topic: `#atlas-hatch-<tag>`); site data rebuilt from the committed `work_relevance.csv` (owner edits in progress left out); scope question PLASTISPHERE-SCOPE |
| 44 | Plastisphere excludes soil-community effects and biodegradation-only works | Done: title-only seeds + exclusions (29 works, 7 grants); ADR-RELEVANCE-RULES-2026-11-11 |
| 45 | 'Micro-nano plastics' always relevant | Done: `always_relevant_patterns` (all spellings) above model/Haiku/rule; shared OpenAlex abstracts ignored (26 works; removed 1 false positive); grants unchanged (503) |
| 46 | Wrong abstract on 'A new formalism in perturbation theory' | Root cause: OpenAlex attached one scraped micro-nano teaser abstract to 10 unrelated PNAS papers. Fixed locally: `atlas.ingest.abstract_qc` blanks it at normalization (also in labels/export/review app); export prunes 171 stale author files. Upstream: owner report text in HUMAN_TASKS H6b |
| 47 | eScholarship (portal blocked; owner: leverage its UC affiliation evidence) | Done: OpenAlex-indexed eScholarship audit; GraphQL campus evidence; CA basis `escholarship`; 19 works added (66/214 items fetched before a rate-limit block; resumable) |
| 48 | Workers per CLAUDE.md | Resumed: S9.5 drawer (Haiku, accepted), eScholarship audit (Haiku, superseded); logged in DELEGATION_LOG |
| 49 | Emails in committed normalized tables (found while spot-checking) | Fixed forward: normalization redacts raw_affiliation/abstract emails (808 strings); history purge is owner question HIST-EMAILS |
| 50 | Owner not editing work_relevance.csv: unblock | Done: 62 owner decisions committed; 146 new works Haiku/lead-screened and queued (low-confidence queue now 278) |
| 51 | Continue unblocked TODO | S6.2/S6.3 closed (already met); S5.1 closed via documented gap (`docs/S5_1_VERIFICATION.md`); gold-labelling app (`scripts/review_gold_labels_app.py`, H9); ROR researchers ingest (+1) |
| 16 | Gates: AT-5/AT-6 deferred; SPK-5/AT-7, SPK-6/AT-8, AT-9, AT-10 approved; gold set = owner + Claude second rater | Recorded (ADR-GATES-2026-11-11) |

## Next eligible (dependency order) - as of 2026-11-12
1. 2026-11-13: CORE full text by DOI and CA place-name audit (owner renews the key), then close S2.5.
2. Resume `scripts/fetch_escholarship_items.py` (148 pending; 5 s spacing) on a later day, then `ingest_escholarship_works.py` + rebuild.
3. After owner gold labels (H9): Claude second rater on 20%, kappa (EM-3/S4.3), S5.1 test evaluation; then S5.0 engine (also needs owner validation of the Smart queue).
4. S9.4/SPK-6 depend on S5.5; EM-5+ needs the Framework revisit decision with the owner.
5. Last: S3.7 hero page and S3.8 SEO.

## Owner actions (one line each; step-by-step instructions in `.agent/HUMAN_TASKS.md`)
0. **2026-11-12: renew the CORE API key** and put the new value in `.env`.
1. Finish the 215 low-confidence works in `scripts/review_work_relevance_app.py` (not started as of 2026-11-11 afternoon).
2. AT2-REVIEW: types for 52 new top-100 institutions in `data/processed/institution_review_needs_v31.csv`.
3. Review the 44 Wikidata photos (`data/processed/expert_photos.parquet`, `docs/api_notes/wikidata_photos.md`) and decide CA-CARRY-ORCID, AT4-SEARCH, AT11-WINDOW (defaults in use).
4. AT-10: cut a GitHub release (for example v2026.11.12) when you want a new archived snapshot; then update `config/release.yml` with the new Zenodo DOI.

## Notes
- Worktree leftovers not committed on purpose: `docs/SOURCES.md`,
  `docs/api_notes/source_watch_s7_6.json`, owner's `data/processed/p{5,25,100}.parquet`.
- Shell heredocs on this machine corrupt `\b` in regexes; write patch scripts with the Write tool.

Older handoff entries: `.agent/archive/HANDOFF_history.md`.
