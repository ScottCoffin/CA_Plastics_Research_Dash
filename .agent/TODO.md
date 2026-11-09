# TODO (roadmap)

Check off only when the task Definition of Done and acceptance check in
`spec.md` Part E are met. `owner` marks tasks with required human action.

## S0 Bootstrap
- [x] **S0.1** Repository skeleton, tooling, memory files, and roadmap. Acceptance: `make test`; all `.agent` files exist; this roadmap is present. `owner: license choice`
- [x] **S0.2** CI lint/test, Pages placeholder deploy, keepalive, watchdog, and commit guard. Pages uses GitHub Actions; manual run `42092058401` succeeded; the placeholder was verified live at `https://scottcoff.in/CA_Plastics_Research_Dash/`; configuration names are documented. Acceptance: push deploys; manual dispatch works; secret names documented. `owner inputs complete: public visibility; ENABLE_DATA_COMMITS; OPENALEX_API_KEY`
- [x] **SPK-7** Cost measurement. Adoption: L0. Depends: S0.2, owner-provided API key. Acceptance: 100-call 2026-11-09 measurement and S2.1 budget guard are recorded in `docs/api_notes/openalex_costs.md`; `config/budget.yml` supplies measured account limits. Meta cost USD 0.026 vs. conservative/account-decrement USD 0.028 discrepancy retained; owner authorized free-only use. `79301e7`.

## S1 Reference data
- [x] **S1.1** OpenAlex/ROR smoke tests and API cost logger. Acceptance: exact working filters, costs, URL limits, and pagination documented.
- [x] **S1.2** California institution registry and ROR join. Acceptance complete: 4,637 institutions; UC 10/10, CSU 23/23, major-private default 11/11; owner review 100/100; 22 owner type corrections are applied through `config/institution_overrides.csv`.
- [x] **S1.3** California land and 3-nm-water polygons. Acceptance complete: four known-point tests pass; 306,997-byte browser asset is <1 MB; full-resolution GeoParquet assets retain 565,997 source coordinates.
- [x] **S1.4** California gazetteer and ambiguity blacklist. Acceptance complete: 127,963 GeoNames California features and 187,760 normalized variants in SQLite; lookup tests and documented explicit blacklist pass.
- [x] **S1.5** Versioned plastics query config and count estimate. Owner-supplied `plastic-v2-candidate` terms, exclusions, collision notes, taxonomy seeds, G-1/G-2 choices, and cache-version contract are recorded. Remaining acceptance: implement config rendering/cache invalidation, smoke-test encoding/cost, run and timestamp the count estimate, and complete precision/recall spot checks before activation. `owner: terms supplied; promotion review remains`

## S2 Works ingestion
- [x] **S2.1** Incremental, resumable OpenAlex ingester. Acceptance: reruns dedupe; high-water mark, usage log, and <=200-work fixture exist. Acceptance check: `py -3.14 scripts/check_s2_1.py`; full suite: `make test`.
- [x] **S2.2** Normalize works, authorships, authors, institutions, and CA flags. Acceptance: C3 schemas and QC report; `py -3.14 scripts/check_s2_2.py` and `make qc` pass.
- [x] **S2.3** Provisional rule-based relevance and domain tags. Acceptance: labels populated and coverage logged. `py -3.14 scripts/check_s2_3.py`; `make test`, Ruff, build, and `git diff --check` pass. Candidate remains unpromoted.
- [x] **S2.4** Daily works workflow with commit and budget guards. Acceptance complete: `.github/workflows/ingest_works.yml` schedules a guarded refresh, simulated 429/budget stops preserve the high-water mark for the next run, and generated outputs commit only when `ENABLE_DATA_COMMITS=true`. `py -3.14 scripts/check_s2_4.py`; CI/local suite pass; hosted bounded smoke `42321442943` completed successfully with the expected budget defer.

## S3 MVP front end
- [x] **S3.1** Export slim site data and aggregates. Acceptance complete: deterministic slim index, per-author details, institution/map payloads, year/type/tag aggregates, schema documentation, and gzip payload sizes are recorded; fixture payload is below the 3 MB C5 target.
- [x] **S3.2** Accessible, mobile app shell and stub tabs. Acceptance complete: single-file responsive shell loads the S3.1 fixture/real-data contract, preserves filters in the URL hash, supports keyboard tab navigation and CSV export, and includes Monitoring/Funding stubs.
- [x] **S3.3** Experts filters, virtualized list, and detail drawer. Acceptance complete: hash-shareable tag/institution/year/CA-basis/OA filters, bounded virtual rows, lazy researcher drawer, browser screenshot smoke, and full suite pass. Performance and browser evidence are in `docs/S3_3_VERIFICATION.md`.
- [x] **S3.4** Institution leaderboard, sparklines, and clustered map. Acceptance complete: qualifying tagged-work institutions render with type chips, all-time/five-year trends, a coordinate-aware clustered map, and links into Experts.
- [x] **S3.5** About/Methods and freshness metadata. Acceptance complete: the About view shows metadata-based refresh time and counts, Methods, the G-12 disclaimer, and correction path; fixture and unavailable metadata have explicit fallbacks. `py -3.14 scripts/check_s3_5.py`, prior S3.2-S3.4 checks, 49-test suite, Ruff, and `git diff --check` pass. Independent Chromium verified About and the Institutions-to-Experts drawer path at desktop/mobile sizes; only harmless favicon 404s occurred. Evidence: `docs/S3_5_VERIFICATION.md`.
- [ ] **S3.6** Pages deployment and performance pass. Acceptance: metrics logged; DuckDB-Wasm used only by recorded decision.

## S4 Gold set
- [x] **S4.1** Versioned labeling guide. Edge-case checks are recorded in `docs/LABELING_GUIDE_VERIFICATION.md`; owner Scott Coffin approved and froze `guide_v1` on 2026-11-07. Acceptance: required edge cases covered and explicit approval recorded; approved guide hash is in `docs/LABELING_GUIDE_REVIEW.md`. This does not authorize representative sampling or annotation.
- [ ] **S4.2** Stratified sample, leak test, and frozen splits. Label-independent sample/split preparation may proceed; do not annotate or claim representative-corpus coverage from the four-work fixture. Acceptance: split IDs committed and test set isolated.
- [x] **S4.3** Annotation workflow, importer, and agreement stats. Tooling acceptance: CSV round-trip and per-label Cohen's kappa report work; human annotation remains pending guide approval and a representative sample.
- [x] **S4.4** Reproducible evaluation harness. Dummy predictor produces per-class/per-label metrics, calibration plot, error-analysis table, and machine-readable output reproducibly; synthetic-only evidence is in `docs/EVAL_synthetic_v1.md`. G-9 thresholds are answered; no corpus-performance claim is made.

## S5 Classifiers
- [ ] **S5.1** Plastic-relevance rules plus SetFit. Acceptance: G-9 targets met or gap and labeling plan documented.
- [ ] **S5.2** Gazetteer gate and measured toponym extractor. Acceptance: recall with CI and NER decision documented.
- [ ] **S5.3** Sampling-vs-mention classifier. Acceptance: per-class held-out metrics and model registration.
- [ ] **S5.4** Geocoding, polygon logic, and `ca_sampled` aggregation. Acceptance: test confusion matrix documented.
- [ ] **S5.5** Multi-label domain tagging and author aggregation. Acceptance: per-tag F1; weak tags merged or experimental.
- [ ] **S5.6** CPU classification workflow and override precedence. Acceptance: CI runtime stated and precedence tested.
- [ ] **S5.7** Candidate-pool leak-test report. Acceptance: widening decision recorded. `owner: decision`

## S6 Full text
- [ ] **S6.1** License-aware OA full-text locator. Tooling and deterministic synthetic acceptance are implemented; the 8-row fixture reports 2 XML, 4 PDF, and 2 none (25%, 50%, 25%). The required candidate-corpus XML/PDF/none coverage report remains unmet because no downloaded production candidate corpus is available; the S1.5 count estimate is not a corpus. Do not close S6.1 or present fixture counts as corpus coverage. S6.2 parser work may proceed independently on ten license-safe article fixtures per its contract.
- [x] **S6.2** Europe PMC JATS section parser. Acceptance: ten real-article fragments plus ten synthetic edge fixtures pass `py -3.14 scripts/check_s6_2.py`; provenance confirms CC BY metadata and selected-copy XML license blocks. Full-text extraction from the ten complete local articles found target sections in 9/10, a fixture-set result only. Verification: 148 tests, Ruff, and `git diff --check` pass.
- [x] **S6.3** GROBID PDF extraction and fallback. Acceptance complete: 30 selected Frontiers CC BY PDFs have hash/license provenance; text-level review confirms 16/16 extracted target headings and evidence prefixes. GROBID technical failures: 0/30; GROBID returned no target sections for 21/30, pdfminer fallback extracted targets for 6/21, and 15/21 remained without targets (13 reviews, 2 editorials). Convenience sample only; no PDF visual QA or corpus performance claim. Evidence: `docs/api_notes/s6_3_pdf_spotcheck.json`.
- [ ] **S6.4** Full-text CA-sampling enrichment. Acceptance: abstract-vs-full-text performance delta.

## S7 Monitoring data
- [x] **S7.1** Monitoring registry schema and >=15 verified seed entries. Acceptance: provenance, tier, URL, and `last_checked` recorded.
- [x] **S7.2** Monitoring source smoke tests and tier decisions. Acceptance complete: all 15 eligible identities have access, format, license, cadence, tier rationale, and field-map status documented; SF Bay / 5 Gyres is the only cleared Tier A source. See `docs/S7_2_VERIFICATION.md` and `docs/api_notes/monitoring_sources_s7_2.json`.
- [ ] **S7.3** Tier-A ingesters and normalization. Acceptance: polygon flags, units QC, duplicate QC, fixtures, and tests. Partial local-only SF Bay / 5 Gyres implementation and QC are recorded in `docs/S7_3_VERIFICATION.md`; rights clarification remains open in `QUESTIONS.md` (S7.3-A), so do not publish source or normalized data.
- [ ] **S7.4** DataCite and full-text dataset discovery. Acceptance: 50-link precision spot check.
- [ ] **S7.5** Monitoring table, sample map, and gaps view. Acceptance: performance budget met and source citations shown.
- [ ] **S7.6** Future-source watch list and weekly checks. Acceptance: changes update `docs/SOURCES.md`.

## S8 Grants
- [ ] **S8.1** Grant schema, normalization, and classifier reuse. Acceptance: C3 schema tests.
- [ ] **S8.2** NIH RePORTER ingester. Acceptance: backfill, incremental path, fixture, and usage notes.
- [ ] **S8.3** NSF ingester. Acceptance: documented parameters, backfill, increment, and fixture.
- [ ] **S8.4** USAspending ingester. Acceptance: pagination, bulk backfill, and keyword-noise notes.
- [ ] **S8.5** California Sea Grant scraper. Acceptance: OPC microplastics projects cross-checked.
- [ ] **S8.6** State funder sources and pass-through dedupe. Acceptance: overlap report and manual-curation path.
- [ ] **S8.7** NOAA Marine Debris awards. Acceptance: CA awards captured for owner-confirmed period. `owner: years`
- [ ] **S8.8** State Water Board funding investigation/implementation. Acceptance: ingest, curate, or defer decision. `owner: guidance`
- [ ] **S8.9** California Grants Portal open-calls panel. Acceptance: relevant open calls and deadlines display.
- [ ] **S8.10** Funding filters, charts, chains, and links. Acceptance: performance met and amount caveats shown.

## S9 Linking
- [ ] **S9.1** Evidence-backed work-to-grant links. Acceptance: 50-link precision spot check; uncertain links omitted.
- [ ] **S9.2** Work-to-dataset links in profiles and registry. Acceptance: evidence type displays.
- [ ] **S9.3** Expert badges and profile/network polish. Acceptance: 10 profiles reviewed. `owner: review`

## S10 Hardening
- [ ] **S10.1** Pipeline status page and drift alarms. Acceptance: run health, deltas, spend, and label-rate drift display.
- [ ] **S10.2** Governance, license, privacy, corrections, dictionary, and citation. Acceptance: owner checklist sign-off. `owner: sign-off`
- [ ] **S10.3** Fixture rebuild and versioned reproducibility release. Acceptance: tagged snapshot archived as chosen. `owner: archive choice`
- [ ] **S10.4** Dependency, security, notification, and secret-rotation hardening. Acceptance: CI passes and docs are current.

## S11 Fallback/extras
- [ ] **S11.1** Optional stlite fallback reading shared outputs. Acceptance: static runtime and Pyodide compatibility tested.
- [ ] **S11.2** Optional evidence-map heatmaps.
- [ ] **S11.3** Optional local-model review assist; never run in CI.
- [ ] **S11.4** Optional scheduled paper/award digest.
- [ ] **S11.5** Optional Plastiverse and ToMEx cross-listing. `owner: lead`
