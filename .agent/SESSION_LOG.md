# Session Log

| Date | Task | Outcome | Commit |
|---|---|---|---|
| 2026-11-05 | S0.1 | Completed; test/lint/build pass | `024fc66` |
| 2026-11-05 | S0.2 | Implementation and Actions checks complete; live Pages blocked by private-repo plan | `3f5e832` |
| 2026-11-05 | S0.2 | Completed; manual Pages deploy and live URL verified | `8a80fca` |
| 2026-11-05 | S1.1 | Completed; live OpenAlex/ROR contracts and cost logging verified | `0950ffe` |
| 2026-11-05 | S1.2 | Implementation and machine acceptance complete; owner review pending 0/100 | `aa1b64f` |
| 2026-11-05 | S1.2 | Completed; owner review 100/100 and 22 type corrections applied | `0cec765` |
| 2026-11-05 | S1.3 | Completed; land/state-waters polygons and known-point acceptance pass | `68828c3` |
| 2026-11-05 | S1.5 prep | Integrated owner-supplied candidate query/taxonomy evidence; no live query run | `b25c2df` |
| 2026-11-05 | S1.4 | Completed; GeoNames SQLite subset, aliases, blacklist, tests, and acceptance pass | pending commit |
| 2026-11-06 | S1.5 | Completed; versioned query renderer/cache, live count, precision/recall audit, tests, and acceptance pass | `cb2ef4f` |
| 2026-11-06 | S2.1 | Completed; resumable OpenAlex works ingester, filter smoke, fixture, tests, and acceptance pass | `15321be` |
| 2026-11-06 | S2.2 | Completed; C3 normalization, CA flags, QC report, fixture, tests, and acceptance pass | `7c80e60` |
| 2026-11-06 | S2.3 | Completed; deterministic provisional labels, topic joins, coverage QC, fixture, tests, and acceptance pass | `2ea7253` |
| 2026-11-06 | S2.4 | Completed; guarded daily workflow, typed 429/budget deferral, output commit guard, hosted smoke, and acceptance pass | `b3a315c` (implementation `3c31bd0`, smoke-input `4307477`) |
| 2026-11-06 | S3.1 | Completed; deterministic static-site exporter, schema/size contract, fixture payloads, acceptance, and full suite | pending commit |
| 2026-11-06 | S3.2 | Completed; accessible responsive app shell, hash filters, keyboard tabs, CSV export, stub tabs, acceptance, and full suite | `b701058` |
| 2026-11-06 | S3.3 | Completed; Experts filters, virtualized list, researcher drawer, browser screenshot smoke, acceptance, and full suite | pending commit |
| 2026-11-06 | S3.4 | Completed; institution leaderboard, sparklines, type chips, clustered map, Experts links, acceptance, and full suite | `f5877c3` |
| 2026-11-06 | S3.5 | Implementation and acceptance complete; 49 tests, Ruff, Chromium desktop/mobile and regression path pass; sealed in this Git checkpoint | sealed in this Git checkpoint |
| 2026-11-07 | S3.6 partial | Pages deployment and fixture C5 measurements verified; full-data performance DoD remains unmet pending approved query and representative export | pending commit |
| 2026-11-07 | S4.1 partial | Draft `guide_v1`, independent edge-case review, and preparation checks recorded; exact guide hash presented for owner approval; no annotation authorized | pending commit |
| 2026-11-07 | S4.2 partial | Deterministic fixture sampling/splits and author-group isolation verified; production sample remains gated on authorized export and leak-hit source | pending commit |
| 2026-11-06 | S4.3 | Tooling complete; synthetic CSV round-trip, Cohen's kappa, 15 focused tests and 71-test suite pass; human annotation gates remain pending | pending commit |
| 2026-11-06 | S4.4 | Evaluation harness complete; synthetic reproducibility, full 83-test suite, Ruff, and diff checks pass; corpus metrics remain gated | pending commit |
| 2026-11-06 | S6.1 partial | License-aware metadata locator and synthetic acceptance implemented; full 89-test suite, Ruff, diff check, and bounded Europe PMC HTTP 200 smoke pass. Eight synthetic rows (2 XML, 4 PDF, 2 none) are not candidate-corpus coverage; S6.1 remains unchecked pending corpus | pending commit |
| 2026-11-07 | S6.2 | Europe PMC JATS parser/cache complete; ten real CC BY article fragments and ten synthetic fixtures pass; 148 tests, Ruff, and diff checks pass; fixture-only section coverage is documented | pending commit |
| 2026-11-07 | S6.3 | GROBID/pdfminer PDF extraction and 30-PDF text-level spot check complete; 0 technical failures, 21 GROBID no-target, six fallback recoveries, 15 final no-target; 163 tests, Ruff, and diff checks pass; convenience sample only | `0c0293d` |
| 2026-11-07 | L1 | Inserted SPK-1..SPK-7 and AT-1..AT-11 in section 5 order with adoption levels and section 9 acceptance row references; focused roadmap validation and git diff --check pass | pending integration |
| 2026-11-07 | L1 retry | Corrected SPK/AT dependencies against add-on sections 5 and 8; recorded AT-3/AT-5 gate differences; SPK-7 has no direct section 9 cost row; focused diff review and `git diff --check` pass | pending integration |
| 2026-11-07 | L2 | Added gate markers to the 8 L2 and 6 L3 entries; verified all 18 SPK/AT adoption flags and marker assignments; `git diff --check` passes | pending integration |
| 2026-11-07 | L3 | Added a namespaced 15-entry Add-on A1 open-conflict register with section-2-derived task mappings and explicit unknown markers | pending integration |
| 2026-11-07 | L3 retry | Corrected Add-on A1 mappings: C4 S3.1/S11.2, C6 S3.6, C7 S3.2-S3.6; verified C1-C15 each once, Open, and concretely mapped; copied conflict/rule text and prior ADR prefix unchanged; `git diff --check` passes | pending integration |
| 2026-11-07 | L4 | Added A1-D1..A1-D7 with exact add-on defaults and proceed-with-default status; focused table validation and git diff --check pass | pending integration |
| 2026-11-07 | L5 | Created inactive Appendix A `config/query_v2.txt` and constant-only `src/atlas/query_v2.py`; no activation or API call. | Query 821 bytes SHA-256 `3b6d707346262437f6d5eb2f14dae814fd6d24a890782002e350ec1e2c842de1`; module 29 bytes SHA-256 `334c2798f81da267179fc00057ade956bb9cd9ae4c2135e03b2db84c9b760c3b`; exact checks and compile passed. |
| 2026-11-07 | L6 | Appended the Add-on A1 §0/§7 licence ledger with 28 named tools/projects, explicit unknowns, and the required reuse rules; prior REUSE entries preserved; handoff updated; `git diff --check` passed. | pending integration |
| 2026-11-07 | L7 | Added reciprocal base/add-on spec links, a dependency-free offline Markdown target checker, and a CI check. Repository scan, isolated missing-target failure, Python compile, existing CI steps, and diff check verified. | pending integration |
| 2026-11-07 | L8 | Added the exact 11 empty Add-on A1 acceptance stubs, zero-row fixture placeholders, offline scaffold checker, and CI step; positive and negative scaffold checks, compile, and diff check verified. | pending integration |
| 2026-11-07 | L9 | Completed the L1-L8 formatting and consistency pass; identifier, dependency, adoption, gate, mapping, default, hash, link, scaffold, compile, Ruff, and diff checks passed | pending integration |
| 2026-11-07 | L9 retry | Corrected the session-log table to one contiguous table; `git diff --check` passed | pending integration |
| 2026-11-07 | Orchestrator final review | Link/scaffold checks, 170 tests, build, Ruff rule checks, and diff check passed; Ruff format-check failed on both new checker scripts, triggering the two-failed-review stop | blocked pending owner direction |
| 2026-11-09 | L9 resume | Applied Ruff formatting; format, Ruff, compile, link, and script whitespace checks passed; scaffold check found a pre-existing `__pycache__` under acceptance stubs | pending integration |
| 2026-11-09 | L9 resume retry | Scoped the scaffold exception to a real `__pycache__` directory; exact 11-stub set, unexpected entry rejection, empty-stub enforcement, Ruff, compile, and diff checks passed | pending integration |
| 2026-11-09 | Orchestrator final acceptance | Link and scaffold checks, full Ruff rule/format checks, 178 tests, build, and diff check passed; Add-on A1 integration accepted locally | ready for owner review |
| 2026-11-09 | SPK-7 | Closed measured OpenAlex cost and S2.1 budget checkpoint from `79301e7`; 100/100 calls, free-only authorization, USD 0.026 metadata vs. USD 0.028 conservative account decrement retained; 199 tests, Ruff, and network-forbidden final rerun recorded by task verification. HTTP 500 without accounting metadata stops before retry; known-credit HTTP 500 retry remains accepted. AT-1 audit/promotion stays open. | `79301e7` |
| 2026-11-09 | AT-1 partial | Isolated audit query/cache path and identity validation, bounded resumable runner and partial outputs; recorded all 20 strata (405 rows, 354 unique, 51 repeated IDs, 95-row shortfall), four baseline counts within 10%, 240 credits / USD 0.024 metered cost; owner kept sample unsupplemented and left 500-row gate open. Labels remain blank; query not promoted. Network-blocked full suite: 222 passed; Ruff and format checks pass. | partial checkpoint; AT-1 unchecked |
| 2026-11-09 | S7.1 reconciliation | Reconciled unchanged registry implementation `46e58e7`; 24 records, 15 distinct eligible seed identities, required provenance/tier/URL/last_checked fields documented; prior independent focused and full-suite acceptance evidence retained. Records-only closure. | closure commit |
| 2026-11-09 | S7.2 | Verified all 15 eligible monitoring source identities and documented access, format, license, cadence, tier rationale, and field-map state. Only SF Bay / 5 Gyres is Tier A; raw particle count and sample volume remain separate, with concentration and size/mesh normalization deferred. Focused: 11 passed; network-blocked full suite: 226 passed; Ruff and diff checks pass. | pending checkpoint commit |
| 2026-11-09 | S7.3 partial | Added local-only SF Bay / 5 Gyres normalization and QC; reviewed 315 sample rows / 314 identities, 44,226 particle rows, 63 computed / 251 null concentrations, raw/unique invalid-volume counts 15/14, and one duplicate-conflict category. Focused 10 tests, offline full 232 tests, Ruff, and diff checks pass per executor/tester. Rights remain unresolved (ODC BY package metadata, empty resource license, historical CC BY 4.0 note, official redirect HTTP 403); no raw or normalized data committed/published; S7.3 remains unchecked. | pending partial checkpoint commit |
| 2026-11-09 | S7.4 | Added DataCite DOI candidate discovery, caller-supplied JATS data-availability extraction, CLI, fixtures, and real 50-record review. Results: 5 positive, 40 negative, 5 unresolved; resolved precision 5/45 (11.1%), all-candidate positive share 5/50 (10.0%), and five positive DOI candidates across three apparent dataset families. Candidate-level agent labels are not owner labels or verified paper links; historical per-record query membership is unavailable and future collection now records it. No payload downloads or auto-ingest. Focused 5 tests, full 237 tests, Ruff, and diff checks accepted by executor/tester. S7.4 complete; S7.3 rights gate remains. | pending checkpoint commit |
| 2026-11-09 | S7.5 partial | Added cited monitoring catalogue, filterable sample table, schematic clustered map, and sample-derived matrix/region/year coverage view. Public catalogue contains 24 records (15 verified seeds, 9 discovery) and zero observations; private local preview contains 314 rows / 277 valid coordinates. Focused six tests and runtime CI wrapper accepted; browser measurements were 314 rendered / 277 mapped, 37 valid-coordinate unknown-matrix rows, and 240 unknown-matrix filter rows / 206 with valid coordinates. Public output and private alias rejection checks passed. S7.5 remains unchecked pending rights-cleared observations for public map/gaps acceptance. Node.js 20+ runtime requirement recorded for later S10 environment pinning. | partial checkpoint |
| 2026-11-09 | A2 integration | Integrated Add-on A2 into TODO (EM-1..18), DECISIONS (ADR-A2-OWNER, A2-C1..C15), QUESTIONS (A2-D1..D11, A2-INT-1..3), spec.md, REUSE.md, CLAUDE/AGENTS/MEMORY, and an A2 scaffold checker plus CI step; links/scaffolds/lint/build pass; 246 tests pass, 2 pre-existing UTC-date failures in test_openalex_budget fixed separately in 4b2154f; owner accepted all pending defaults | this commit |
| 2026-11-09 | EM-1 | A2 vocabularies, keyword rules, Need Ledger XLSX→CSV validator/QC (70/70, 0 hard errors), local-only quote checker, draft guide_v2 addendum; check_em1 and full gate pass (367 tests) | this commit |
| 2026-11-09 | EM-2 partial | Fetched Regional Board layer (9 features), committed simplified GeoParquet, offshore rule vs CDFW state waters, EAT-12 real test; full gate 407 passed; unchecked pending S5.4 and view wiring | this commit |
| 2026-11-09 | S8.1 | Grant C3 schema, frozen grant_key, normalization/validation/Parquet writer, provisional rule labels; 64 tests; full gate 471 passed | this commit |
| 2026-11-09 | EM-1 follow-up | Quote regression 69/70 (+1 accepted exception) vs Zotero PDFs; checker handles elisions and one layout interruption; N2.9/N4.1 shortened (N3.2 source typo accepted as owner exception); guide_v2 approved; A2-D11 confirmed; SPK-1..4 authorized; gate 477 passed | this commit |
| 2026-11-10 | SPK-1 partial | Opt-in Pages deploy of 5/25/100 MB synthetic Parquet: 206 + CORS *, lazy DuckDB-Wasm reads (1.2 MB for 100 MB); G-HOST = Pages only ≤25 MB; R2 leg pending owner | this commit |
| 2026-11-10 | SPK-2 partial | Parquet writer×option×DuckDB-Wasm matrix all 15/15 (lead re-ran); G-PARQ = DuckDB 1.1.1 + zstd; Framework leg deferred to SPK-3 | this commit |
| 2026-11-10 | SPK-4 | Bit-mask vs Mosaic at 30k/100k × 5 runs: bit-masks win cold start and meet budgets with exact counts; G-FACET = bit-masks main page; Mosaic correctness to AT-6 | this commit |
| 2026-11-10 | S8.2 | NIH RePORTER ingester (CA + terms-only sweeps, backfill/incremental, defer pattern); live backfill 196 grants; 505 tests pass | this commit |
| 2026-11-10 | S10.4 partial + CI repair | Lock/Dependabot/SECURITY.md; fixed CI-only failures (S3.5 link to ignored file; untracked A1 release .gitkeep); CI now fails only on owner S7.6 WIP test/lint | this commit |
| 2026-11-10 | S8.4 | USAspending ingester with pagination ceiling defer, CA sweeps, bulk path, noise notes; live backfill 66 grants; 537 tests pass | this commit |
| 2026-11-10 | SPK-3 + SPK-2 | Shell bake-off (clean lead re-run): G-SHELL = Framework 1.13.4; SPK-2 part (a) 5/5 so SPK-2 complete | this commit |
| 2026-11-10 | S8.9 | Grants Portal open-calls panel + daily deploy refresh; lead tightened keywords (all 9 initial hits were water recycling); browser smoke ok | this commit |
| 2026-11-10 | S8.3 | NSF ingester; lead ran incremental (25) and backfill (316 grants, 936 free requests) | this commit |
| 2026-11-10 | S10.1 | Status page + drift alarms + run-history log; lead fixed spend matching (since job start), works_added floor, `/build/` ignore anchor, export_site format; 565 tests | this commit |
| 2026-11-10 | S8.6 | OPC/Delta adapters, cross-source dedupe (593→514 clusters) + overlap report, manual curation CSV; COAST/SCC gaps documented | this commit |
| 2026-11-10 | S8.5 | Sea Grant scraper; 14 relevant projects; all 5 OPC microplastics projects cross-checked | this commit |
| 2026-11-10 | S9.1 | Work-grant links: 17 exact award-ID links, all spot-checked (0 incorrect); questions S9.1-A/B with defaults | this commit |
| 2026-11-10 | S8.10 | Funding awards UI + grants export (514 grants); perf ≤64 ms; lead all-tab smoke clean | this commit |
| 2026-11-10 | S9.2 | Work-dataset links (1 DataCite link), drawer/registry evidence display, opt-in export; site payloads unchanged | this commit |
| 2026-11-10 | S11.4 | Atom digest feed (2 papers + 30 awards) rebuilt on deploy; lead added a future-date cutoff | this commit |
| 2026-11-10 | Overnight handoff | All ungated tasks done; HANDOFF owner actions + RESUME_PROMPT written; REUSE spike licences; MEMORY gate line | this commit |
| 2026-11-10 | S7.6, S10.4, SPK-1 | S7.6 watch fix + CI green (96d09e5); S8.9 test date pinned; R2 leg measured at data.plastiverse.live; owner defaults confirmed | this commit |
| 2026-11-10 | Domain move | Site on plastiverse.live; feed links updated (ids frozen); R2 CORS verified from live origin | this commit |
| 2026-11-10 | S8.7 | NOAA Marine Debris awards FY2015+ via USAspending ALN 11.999 (22 awards, 8 new) | this commit |
| 2026-11-10 | S7.3 | SF Bay / 5 Gyres closed: owner CC BY 4.0; license object on outputs; REUSE row | this commit |
| 2026-11-10 | S7.5 | 314 cleared SF Bay / 5 Gyres observations public; clearance file gates publication | this commit |
| 2026-11-10 | S8.8 | SWRCB awards via FAAST public search (2 awarded rows; contacts never stored) | this commit |
| 2026-11-10 | S7.7 | Sierra snow literature rows (40) published; S7.8 CEDEN task added | this commit |
| 2026-11-10 | S7.8 | CEDEN concentrations joined (63 kept, 78 filled); 56 QA samples removed from public map; weekly CEDEN watch | this commit |
| 2026-11-10 | AT-1 | Owner labels complete (82.8%); v3 candidate + ingester support; 76-work repeat sample; licenses; Zenodo release v2026.11.10; review app fixes | this commit |
| 2026-11-10 | S2.2 / S10.2 | Near-duplicate collapsing; governance gaps (issue link, REUSE, disclosure, suppression/overrides/merges) | this commit |
| 2026-11-11 | AT-1 | Owner scope: plastics LCA/recycling/alternatives added to v3; repeat sample regenerated (143) | this commit |
| 2026-11-11 | S10.3, EM-16, EM-18, S7.5 | Zenodo DOI 10.5281/zenodo.24124016; link-out registry + checker; DTSC timeline; monitoring paging | this commit |
| 2026-11-11 | AT-1, S2.1-B, S8, S7.5, S10.2, EM-16 | Query v3.1 promoted; grant relevance review; monitoring basemap + matrices; CI experts export; GOV-B | this commit |
| 2026-11-11 | S2.1-B, S3.6, S7.5-UX, S11.3 | Real v3.1 backfill live; owner labels + Haiku work relevance at export; experts filter 519->5.5 ms; interactive monitoring map; grant review app | this commit |
| 2026-11-11 | AT-2 | Institution types carried forward to v3.1 ranking (168 rows, 52 new top-100 entrants queued); labeled_works count fix | this commit |
| 2026-11-11 | S3-UX, S8 | Experts topics/sort/citations; interactive institutions map + topic bars; institution evidence maps; author auto-merges; grant strong-term rule; owner grant review applied; works review app | this commit |
| 2026-11-11 | S8-VIZ, S3-UX2, gates | Grants Sankey suite; map labels; topic sort; drawer abstracts; whole-record plastics citations; fallback OpenAlex key; owner clears A1 gates | this commit |
| 2026-11-11 | ADR | Observable Framework deferral recorded with CI-checked revisit triggers | this commit |
| 2026-11-11 | S9.3-UX, S9.4 (spec) | Drawer metrics strip and collapsible sections; frequent co-authors; first-click bug fix; collaboration network written up | this commit |
| 2026-11-11 | S4.2 | splits_v2: 500-work stratified v3.1 pool + 80 leak-test works; size-aware author-group splits | this commit |
| 2026-11-11 | S2-COVERAGE | Karapetrova forensics; raw-affiliation and carry-forward CA inference; raw-affiliation scope and author-anchored ingest; CA-only export; corpus 1,896 works | this commit |
| 2026-11-11 | S1.2-AGENCIES, S5.1-AL, S8-TABLE | State agencies differentiated; owner top-100 review restored and protected; active-learning relevance app; sortable funding table | this commit |
| 2026-11-11 | S3-INST, topics, specs | Collaborator clarity (Doñana), top experts per institution, Risk assessment topic (hatched), grant tags recomputed at export; specs S9.5 bios/photos, S9.6 outreach, S3.8 SEO | this commit |
| 2026-11-11 | handoff | Context at 80%: handoff to a fresh orchestrator via RESUME_PROMPT.md | this commit |
| 2026-11-11 | AT-3 | SQL analytics (DuckDB 2.0.0): fractional counts, bootstrap stability, year x tag, co-occurrence; `works.is_retracted`; owner confirmed two state-agency overrides | this commit |
| 2026-11-11 | AT-4 | Serving bundle: Appendix C bit-sets, facets.js, title search, abstract-free Parquet, institution tiers; wired into ingest_works and CI | this commit |
| 2026-11-11 | AT-11 | CI guards: raw/normalized schema and payload checks before the daily commit; failure-mode tests | this commit |
| 2026-11-11 | AT-10 (partial), AT-4 UI | Release pipeline (methods card, checksums, release.json, About DOI); Institutions tiers view; check_s10_3 abstract check made key-based | this commit |
| 2026-11-11 | S2.5 (partial) | Europe PMC recall benchmark 51.0%; DOI ingest deferred by the budget guard | this commit |
| 2026-11-11 | S2.5c, S9.5 (partial) | ORCID enrichment (employments, carry-forward evidence, bios) and Wikidata photo metadata | this commit |
| 2026-11-11 | S2.5d (partial) | DataCite outputs by expert ORCID (98 plastic-related, 84 not in corpus) | this commit |
| 2026-11-11 | handoff | Usage window at 91%: handoff via RESUME_PROMPT.md; audit script gains --extra-dois | this commit |
| 2026-11-11 | review-apps | Search-term highlighting in the three review apps; Streamlit watcher off (torchvision traceback); .agent/HUMAN_TASKS.md; photo review sheet | this commit |
| 2026-11-11 | review-apps | Owner rule: >10-case reviews get Streamlit apps; institution-type and expert-photo review apps; atlas.csv_review | this commit |
| 2026-11-11 | topic | Plastisphere topic (taxonomy seeds, topics.js per-topic hatch); labels, site data, analytics, bundle rebuilt | this commit |
| 2026-11-11 | relevance-rules | Plastisphere narrowed; micro-nano plastics always relevant; mis-attached OpenAlex abstracts blanked; stale author files pruned | this commit |
| 2026-11-12 | S2.5/S6.1/S9.5 | ORCID DOI ingest (+117), eScholarship evidence + basis (+19), S6.1 corpus report (PMCID fix), drawer profiles (worker), email redaction in committed tables | this commit |
| 2026-11-12 | S2.5/S5.1/S6 | Owner decisions committed; 146 additions queued; S5.1 dev eval (closed via gap); S6.2/S6.3 closed; gold-labelling app; ROR researcher ingest (+1) | this commit |
| 2026-11-12 | S9.3/H5/AT4/S9.6a | Expert full page + metrics (m-quotient, rising, histogram, primary affiliation); H5 answers applied; MiniSearch; Framework installed; outreach contact builder; gateway-504 budget fix | this commit |
| 2026-11-12 | AT-5 | Framework app: all five tabs + Overview ported lift-and-shift (4 Haiku workers), deployed under /app/ beside the classic site; check_at5, preview + headless smoke | this commit |
| 2026-11-12 | EM-5 | Evidence Map shell as Framework page (facets, hash, drawer, link-out strip); linkouts.json export with trigger rules (2 Haiku workers) | this commit |
| 2026-11-12 | EM-16/EM-18 | Related Resources page and DTSC timeline (Policy) page in Framework; linkouts.json fields extended; dtsc_timeline.json export (2 Haiku workers) | this commit |
| 2026-11-12 | EM-6/EM-7 | Evidence Map V-3 pipeline flow (methods card) and V-4 trend panel (topic trends + CA share of global output, 1 OpenAlex request) (2 Haiku workers) | this commit |
| 2026-11-12 | UX-0/UX-1/UX-21 | Owner UX spec integrated (TODO UX section, ADR-UX-SPEC, UXD-1..9); live Playwright+axe+Lighthouse audit (spec Section 1A); Classic-site link fixed, new-version banner, lang/viewport via postbuild | this commit |
| 2026-11-12 | UX-2 | expert.html: parseExpertId (hash, ?author=, ?id=), plain missing/malformed/not-found messages (1 Haiku worker) | this commit |
| 2026-11-12 | UX-3 | Internal vocabulary removed from public text (classic + Framework + DTSC labels); check_public_text.py in CI and deploy (1 Haiku worker) | this commit |
| 2026-11-12 | UX-22 | Contrast and link underlines (style.css), ported pages as light panels in dark theme, sidebar toggle aria-label (postbuild); axe 0 contrast nodes light+dark | this commit |
| 2026-11-12 | UX-4 | Evidence map: one in-development notice, placeholders removed, intro matches controls, loaded/failed status with Retry (1 Haiku worker) | this commit |
| 2026-11-12 | UX-23 | One h1 on Experts and Funding; heading skips removed on every /app/ route (1 Haiku worker) | this commit |
| 2026-11-12 | UX-24 | Monitoring CLS 0.52 -> 0.04 (static quality-note lead), no headings inside summary; grants.html aria/dl/th/nested fixes (1 Haiku worker) | this commit |
| 2026-11-12 | UX-6 | Institution counts explained (211 any work vs 161 plastic-related) and defined on Overview, About and Institutions (lead inline) | this commit |
| 2026-11-12 | UX-8 | Funding: headline dollar sum removed (app + grants.html), per-source subtotals with caveat, rows-per-page default stated (1 Haiku worker) | this commit |
| 2026-11-12 | UX-9 | Monitoring: filtered CSV download with citations and licences, ISO dates, unit headers, licence glosses (1 Haiku worker) | this commit |
| 2026-11-12 | UX-11 | Related resources: single reuse badge, unstated fields hidden, NCEI and Plastiverse stewards with source links (lead inline) | this commit |
| 2026-11-12 | UX-12 | Policy timeline: '1 Oct 2026' dates in <time>, acronyms expanded on first use (1 Haiku worker) | this commit |
| 2026-11-12 | UX-14 | Overview: refresh time '12 Nov 2026, 17:09 UTC' in <time>, duplicate Labeled works tile hidden, Start here row (lead inline) | this commit |
| 2026-11-12 | UX-10 | About: How to cite, licence statement from the committed licence files, developer sentences rewritten, Glossary link (lead inline) | this commit |
| 2026-11-12 | UX-7 | Glossary page linked from every footer; inline term links on Experts and Institutions (1 Haiku worker) | this commit |
| 2026-11-12 | UX-25 | Mobile and metadata: 375 px overflow gone, favicon 404 fixed, meta descriptions, 24 px targets (1 Haiku worker) | this commit |
| 2026-11-12 | UX-18 | Naive-user Playwright task scripts; 6/6 tasks pass locally (1 Haiku worker) | this commit |
| 2026-11-12 | UX-15/UX-16 | Experts list loading/failed/no-results states and axe-clean rows (1 Haiku worker); volume-not-strength captions on Experts, Funding, Evidence (lead) | this commit |
| 2026-11-12 | S2.5 | eScholarship fetch complete (72 remaining items, no 403); evidence parquet updated for the next export | this commit |
| 2026-11-12 | UX-26 | Owner batch: light theme, drawer/header fix, bylines + named co-authors, proportional topic chips, Spring photo, reactive Evidence map (table, heatmap, trends, 2-week callout, collapsed flow) | this commit |
| 2026-11-13 | REL-1, UX-27, UX-28, UX-29, S9.4 (partial), S3.8 (partial) | Relevance audit + plastic-only Evidence map with heatmap-driven table; funding viz merged into Framework; current-affiliation filter; collaboration network page; SEO pages/sitemaps; Spring photo credit | 6 commits |
| 2026-11-14 | AT-5 (H16 root switch), UX-30, UX-31, REL-2, S9.3 (partial), S9.4 (sigma.js, networkx), S3.8 (AI crawlers), UX-19, UX-20 | Framework app at the site root with redirect stubs; Evidence map selection feedback; institution page; auxiliary chemicals topic; expert badges; sigma.js network; robots allows AI crawlers; WCAG failure table; session materials refreshed; daily ingest date-cap fix (failed 2026-11-12/13) | this commit |
| 2026-11-14 | VD-0 | Visual design assessment (ux_audit + Lighthouse on 12 live routes, design probe, palette validator, contrast) and spec `docs/VISUAL_DESIGN_SPEC.md` ("Pacific Contour"), style tile, baseline JSON, motif script; TODO section VD (VD-1..VD-13), ADR-VD-SPEC, VD-D1..D8, H24/H25 | this commit |
| 2026-11-14 | VD-1 | Pacific Contour design tokens, Framework mappings, five page palette aliases, CSS-literal ratchet/test/CI; 1 Luna agent; 1565 tests and all-route axe/browser inspection | this commit |
| 2026-11-14 | VD-2 | Self-hosted Barlow Semi Condensed 600/700, Pacific Contour type scale and surfaces, relative preload; all-route platform-font/axe inspection, Policy CLS 0 median; 1 Luna agent; 1570 tests | this commit |
| 2026-11-15 | VD-3 | Grouped icon sidebar, accessible responsive header/menu/hash search, footer and coastline mark; Framework list/region violations closed on all routes; Resources CLS guard; 1 Luna agent; 1574 tests | this commit |
| 2026-11-15 | VD-4 | Section 5 shared component layer, unlisted/noindex living styleguide, 24-symbol accessible icon sprite; axe-clean responsive reference with actionable targets >=24 px; 2 Luna agents; 1577 tests | this commit |
| 2026-11-15 | VD-6a | Experts adoption complete; 1,595 passed, 9 expected placeholder skips; local assembled desktop/mobile browser acceptance | this commit |
| 2026-11-15 | VD-6b | Collaboration network adoption; 19 focused tests, 1,595 passed with 9 expected skips, 13-page build, local assembled desktop/mobile acceptance | this commit |
| 2026-11-15 | S2.6 | Null OpenAlex author IDs repaired (ORCID / name+institution / curated); Jeff Wagner restored; +21 experts; 1,655 passed, 9 expected skips | this commit |
| 2026-11-15 | UX-28 follow-up | Funding Sankey click drill-down restored (owner request); built-page click test + axe clean; 1,659 passed, 9 expected skips | this commit |
| 2026-11-15 | NET-1 | Land to Sea Microplastics Consortium linked: UC Davis host card with logo, member pointers, expert badges, LO-13, SEO subOrganization, owner disclosure; 1,702 passed, 9 expected skips | this commit |
| 2026-11-16 | VD-7a | Monitoring visual adoption deployed: shared caution/disclosures/filter/map surface, 320 px reflow and complete marker/filter/details interactions; 1,702 passed, 9 expected skips; live Lighthouse 97/100 with CLS 0 | implementation `6e89d172` + this records commit |
| 2026-11-16 | VD-7c | Evidence visual adoption deployed: four callouts, topic dots, chart cards, UX-30 preserved; one details load and row-derived trend; 1,706 passed/9 expected skips; live Lighthouse median 92, a11y 100, CLS .088 | implementation chain through `435ba318` + this records commit |
| 2026-11-16 | VD-8 | Policy/Resources/About/Glossary visual adoption deployed; 1,706 passed/9 expected skips; eight exact-viewport route checks axe clean; live Lighthouse performance 100/100/99/100, a11y 100, CLS 0 | implementation `47b0e56a` + this records commit |
| 2026-11-16 | VD-10 | Display labels for vocabulary slugs: shared/labels.js on Experts, Institutions, Institution, Funding, Evidence and Network; no F10 slug on screen, URL values unchanged; clean-worktree pytest 1,706 passed (+28 rerun outside the repo temp root) | this commit |
| 2026-11-16 | VD-13 | Overview entry-card counts in build_metadata.json (awards, monitoring samples/sources, network experts/links, plastic-related works); cards match their pages; clean-worktree pytest 1,719 passed | this commit |
| 2026-11-16 | VD-9 | Chart and map colour system: shared/palette.js (Okabe-Ito 7/6 + Other, teal ramp, chrome), monitoring/funding/network/heatmap sets replaced; full gate 1,728 passed/13 skipped; found pre-existing /network CLS 0.421 (VD-14) | this commit |
| 2026-11-16 | VD-14 | /network CLS fix: static page header and callout instead of a runtime display() cell; local CLS 0.42 -> 0 | this commit |
| 2026-11-16 | VD-6c | Institutions/Institution visual adoption: headers, callouts, segmented toggle, tier cards, icon map controls, reserved chip row; CSS on tokens | this commit |
| 2026-11-16 | VD-7b | Funding visual adoption: single head, caution/info callouts, filter panel + More filters, Chart/Table on all five charts; CSS on tokens | this commit |
| 2026-11-16 | VD-11 | Classic expert profile and SEO template on Atlas tokens and local Barlow fonts; S3.8 abstract guard ignores DOIs | this commit + `S3.8` fix commit |
| 2026-11-16 | UX-32 | Accessibility rows fixed; axe 0 on 14 routes; remaining rows are accepted 2.5.8 exceptions; pass-script false positives fixed | this commit |
| 2026-11-16 | VD-17 | Framework stylesheets have 0 hex literals outside tokens.css; ratchet cap 0 | this commit |
| 2026-11-16 | VD-15 | Context pages (Policy, Resources, About, Glossary) get the shared page header and icons | this commit |
| 2026-11-16 | VD-16 | Evidence map Trends, Heatmap and Pipeline flow get Chart/Table controls with table panes | this commit |
| 2026-11-16 | VD-12 (partial) | design_snapshots.py and global acceptance record; Evidence eyebrow icon; owner review H25 pending | this commit |
| 2026-11-16 | records | Handoff and memory for the VD-9..VD-17 / UX-32 run | this commit |
| 2026-11-16 | VD-18/VD-19/VD-20 | H25 owner feedback: visual polish, site-wide search, network layout and cluster labels; H26 closed; H27 waits on certificate | 4a01550b, 1f11d4ac, this commit |
| 2026-11-16 | VD-21..VD-24 | H25 round 2: top nav, Overview rework, Monitoring map tools, headings/page heads/tooltips; Impeccable intro option and owner decision to adopt Plane Poster (VD-25) | this commit |
| 2026-11-17 | VD-25 | Plane Poster world site-wide (tokens, shell, Overview, task colours, Archivo); Pacific Contour kept as release design-pacific-contour-2026-11-16 | this commit |
| 2026-11-17 | VD-27 + EM-17 (partial) | Owner feedback round 3 (favicon/mark, full-width notices, Funding heatmap filtering, Experts/Network filters, Overview pipeline, About rewrite with living flow) and the OPC Solutions track panel with review app; owner review H28 | this commit |
| 2026-11-17 | VD-28 | Network mobile search, full-screen details sheet, exit button | this commit |
| 2026-11-17 | VD-29 | Tooltips clamped to the viewport, smaller help icon, boxed text full width, favicon encoding fix; owner switched Pages back to GitHub Actions | this commit |
| 2026-11-17 | VD-29 follow-up | Page titles no longer self-links (postbuild unwraps h1 anchors) | this commit |
| 2026-11-17 | VD-29 fix + VD-31 | Favicon as base64 (live icon was a black square: Framework double-escaped %23); creator credit replaces disclaimer and About disclosure; larger footer links | this commit |
| 2026-11-17 | VD-30 | Homepage map spring intro (Web Animations, no library); About section text full width | this commit |
| 2026-11-17 | VD-32..VD-35, ING-LOOKBACK/403/SAFETY | Resources icons and links, no repo links (mailto corrections), Evidence journal filter and 2-yr mean citedness, owner logos and compact page heads; daily ingest fixed (paid from_updated_date filter) with lookback, deep sweep and alert issue | this commit |
| 2026-11-17 | end of session | NOTIFY-AB, platform plan, Impeccable global-landing structure locked (Tile cartogram + steer), MAIL-1 partial (cron off); PLAT-1/PLAT-2a not started (workers stopped for budget) | this commit |
| 2026-11-17 | PLAT-2 design | Landing scroll story approved (Plastiverse Live, logo palette); build spec docs/PLAT_2_LANDING_SPEC.md, direction contract v2, ADR-PLAT2-SPECTRAL-STORY; agent state tracked for cross-machine handoff | 1ed81e31, 2e53fb02, this commit |
| 2026-11-17 | MAIL-1 fix | Digest "new this week" also requires pub_date within 60 days (19 works, not 1,565); Monday cron re-enabled (no-op without secret); owner accepted PLAT2 defaults (ambassador page describes the role) | this commit |
| 2026-11-17 | PLAT-1 | California moved to /california/ (clean break, no redirects; expert.html and SEO pages under site/california/; search, feed, ntfy, llms retargeted); 6/6 UX tasks, axe 0 on 14 routes | this commit |
| 2026-11-17 | PLAT-2a | World geometry and global country counts for the landing (40 credits); release design-plane-poster-2026-11-17 cut before the PLAT-1 deploy (owner request) | this commit |
| 2026-11-17 | PLAT-2c | /ambassadors placeholder with the owner role list (QC institutions/experts, community groups, monitoring data, policy goals); axe 0 | this commit |
| 2026-11-17 | PLAT-2 | Plastiverse Live landing: scroll-story engine port, offline assets, self-hosted fonts, check_plat2 0 failures, finish review 6 fixes, DESIGN.md; Lighthouse 85 local (control 84) | this commit |
| 2026-11-18 | GA-1 | Global data app design (Impeccable): Scope ladder chosen with owner steer; prototype with real OpenAlex sample (350 credits); finish review fix -> ship (8/8); axe 0; DESIGN.md merged | this commit |
| 2026-11-18 | GA-2 | /explore built in Framework from the GA-1 prototype (Haiku x2 + lead); explore data pipeline in the daily ingest; axe 0, no console errors; Haiku finish review fix -> ship (5/5) | this commit |
| 2026-11-18 | GA-3, PLAT-2d | Phone Menu drawer and 70-82% phone map on /explore; landing links /explore; network label removed; /explore in sitemap and llms.txt; global expert profile assessment ($0 plan GX-1..7) | this commit |
| 2026-11-18 | LOGO-1 | Landing footer logo animation (MP4 near-viewport, poster fallback, Pause/Play); Explore agent on Haiku; GX owner decisions recorded; handoff for a fresh orchestrator | this commit |
| 2026-11-18 | A3-INT | Add-on A3 integrated: 52 BQ tasks, A3-D/C/Q registers, ADR-GOLD-GLOBAL (proposed), ADR-A3-PUBMED, H36-H40, REUSE ledger, docs/A3_SOURCES.md, scripts/check_a3_scaffold.py in CI; owner rule: OpenAlex verified facts over spec | this commit |
| 2026-11-18 | PLAT-2b | Live global evidence-map counts (30 cell queries/day, 300 credits), landing table + canvas use them; owner A3 answers recorded (A3-ANSWERS + Q8/Q11/Q15, PLAT-4a split) | this commit |
| 2026-11-18 | BQ-0 | A3 [VERIFY] recon (root is global; no pmid stored; PubMed cap 10,000; NCBI 3/10 rps + tool/email registration, H41; T10753 via primary_topic.id; ca_basis/ca_any_author provenance); pyproject licence MIT; baseline 2,283 passed | this commit |
| 2026-11-18 | BQ-S8 | Operator-limit test (burst 429 retried, 0.25 s throttle) + caller table; gap: run_at1_audit.py bypasses the client (manual --live) | this commit |
| 2026-11-18 | BQ-3.1 | Network build documented (constants, layout, communities, schema s9.4-v1.1); possible select_nodes docstring/code mismatch noted | this commit |
| 2026-11-18 | BQ-G1 | Gold status: 38/150 evaluation works labelled (dev 17, test 21), no gold release; scripts/report_gold_status.py | this commit |
| 2026-11-18 | BQ-1.2 | Failure taxonomy (20 classes, 2 pending BQ-S9 placeholders) seeded from REL-1 and A3 | this commit |
| 2026-11-18 | BQ-1.6 | Count reconciliation: 1,919/1,583/1,849/2,037/1,749 traced to fields; possible bugs: >=10 curation exclusions match no work, Now line omits 70 works | this commit |
| 2026-11-18 | BQ-R1 | "Authors" rename: /california/authors + redirect stub, visible text, glossary term, terminology lint (text, attributes, JSON method); Haiku review found the /explore PANELS bug (fixed) | this commit |
| 2026-11-18 | BQ-G0 | Guide addendum A3 (guide_v3): candidate sets, anchor rule, lifecycle tier + tie-break, scope list, tags, centrality, lenses, 6 template fields, calibration cases with OpenAlex IDs, CA backfill; Haiku review (14 findings) applied; owner approved | this commit |
| 2026-11-18 | LIC-1 | Code licence PolyForm Noncommercial 1.0.0 (owner); data licence question LICENSE-DATA-NC | this commit |
| 2026-11-18 | PLAT-2b v2 | Stricter evidence cells (owner): topic terms in titles only, title vocabulary per row; live grid refreshed (300 credits) | this commit |
| 2026-11-18 | LIC-2 | Atlas-made data licence CC BY-NC 4.0 (owner); third-party rows keep their terms | this commit |
| 2026-11-19 | LAND-1 | Landing stage full bleed above 1440 px; Regions nav unboxed; evidence-table contrast (70% ramp) | this commit |
| 2026-11-19 | LAND-2 | Landing logo intro (MP4 once, hold on poster), 2x scroll cue with arrow, 2x skip link | this commit |
| 2026-11-19 | LAND-3 | Logo intro 2x (100vh box, 105vw on phones), continuous loop, toggle hidden until keyboard focus | this commit |
| 2026-11-19 | LAND-4 | Intro logo 20% faster, plays once and holds on the full logo, tagline clipped, no toggle | this commit |
| 2026-11-22 | NET-2 | select_nodes counts only Atlas co-authors; network rebuilt; stale networkx comments fixed | this commit |
| 2026-11-22 | CNT-2 | California Now line remainder entry and population label | this commit |
| 2026-11-22 | OA-2 | run_at1_audit routed through the shared OpenAlex client | this commit |
| 2026-11-22 | BQ-G7 | Boundary cases recorded with verified quotes | this commit |
| 2026-11-22 | BQ-S1 | Search vocabulary register (163 terms) with schema test | this commit |
| 2026-11-22 | BQ-V.0 | Sigma benchmark spike, N_MAX proposal | this commit |
| 2026-11-22 | BQ-S6 | Theme anchor sets (42 anchors) | this commit |
| 2026-11-22 | CNT-1 | Unmatched exclusions classified; 2 carried to duplicate keepers | this commit |
| 2026-11-22 | BQ-G2 | Gold design freeze with HT weights | this commit |
| 2026-11-22 | BQ-S9 | PubMed coverage stage 1, payload, triage app | this commit |
| 2026-11-22 | BQ-2.1 | Denominator series definitions and builder | this commit |
| 2026-11-22 | BQ-S4 | Language probe (16 term sets, USD 0.064) | this commit |
| 2026-11-22 | BQ-3.2 | Collaboration network metrics payload | this commit |
| 2026-11-22 | BQ-2.2 | Denominator fetch/cache, pollution-core v0, R2 rerun | this commit |
| 2026-11-22 | BQ-1.5 | Anchor overlap probes (no large independent set) | this commit |
| 2026-11-22 | BQ-S10 | Review-string replay (2 of 3) | this commit |
| 2026-11-22 | BQ-2.3 | Trend metrics with CAGR CIs | this commit |
| 2026-11-23 | BQ-S5 | Taxonomy crosswalk + owner proposal (D1-D10); open for H40 | this commit |
| 2026-11-22 | BQ-3.4 | Collaboration panel on the network page | this commit |
| 2026-11-22 | BQ-R2 | Glossary entries and Further reading | this commit |
| 2026-11-25 | BQ-1.3 | Language and theme recall probes (Wilson CIs, anchors 37/42, T10753 82%); new machine onboarded | this commit |
| 2026-11-25 | BQ-2.4 | denominators.json + C/A share on V-4 + B/A on /explore Trend | this commit |
| 2026-11-25 | PLAT-4a (partial) | Global raw fetch tooling + estimate; paging blocked on OpenAlex key (H43); budget guard 401/403 reserve | this commit |
| 2026-11-25 | BQ-S2 | Candidate plastic-v3.2 (64 terms, +1.3% records), recycler removed after per-term probe | this commit |
| 2026-11-25 | PLAT-3 (slice 1) | Region registry, loader and region-name ratchet; no behaviour change | this commit |
| 2026-11-25 | PLAT-3 (slice 2) | Scope constants from the registry, --region on pipeline CLIs; outputs unchanged | this commit |
| 2026-11-25 | UX-13 (part a) | Monitoring filters saved in the URL hash; PLAT3-DATA-PATH question recorded | this commit |
| 2026-11-25 | PLAT-3 (slice 3) | Region data folder from the registry; California stays at site/data (default PLAT3-DATA-PATH) | this commit |
| 2026-11-25 | PLAT-4 (slice 1) | Local partition of the global raw store (unscreened, pmid, regions); data/processed/global ignored | this commit |
| 2026-11-25 | PLAT-4 (slice 2) | Institution-registry join for region predicates; shared ca_flag rule | this commit |
| 2026-11-25 | PLAT-4a (fix) | OpenAlex request spacing 0.6 s (free keys: 2 boolean-heavy req/s); H43 done | this commit |
| 2026-11-25 | PLAT-4a (backfill day 1) | 80,795 global works fetched; network errors defer instead of crashing | this commit |
| 2026-11-25 | BQ-3.3 | Degree-preserving null model for collaboration metrics (worker hit its turn limit; lead finished --check and caveats) | this commit |
| 2026-11-25 | PLAT-3 (slice 3b) | California data moved to site/data/california (owner); 0 failed data requests on 15 routes | this commit |
| 2026-11-25 | PLAT-4a | Global backfill complete (136,086 works); data move live | this commit |
| 2026-11-25 | PLAT-4 (slice 3) + BQ-V.2 + BQ-S9b | Tier B country aggregates; global PubMed coverage 99.1% / 97.3% (one commit: shared doc files) | this commit |
| 2026-11-25 | Owner decisions | H40 approved (BQ-S5-APPLY queued); H25 design kept, VD-SM deferred; REG-1 Norway+Belgium and AMB-1 ambassadors added; H42 reminder | this commit |
| 2026-11-25 | REG-1 | Norway and Belgium region pages (global theme, placeholders to confirm) | this commit |
| 2026-11-25 | AMB-1 (spec) | Ambassador spec with owner decisions (Workers + D1, Resend, region leads, institutes eligible); H44 setup steps | this commit |
