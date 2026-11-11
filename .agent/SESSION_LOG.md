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
