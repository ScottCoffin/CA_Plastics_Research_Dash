# TODO (roadmap)

Check off only when the task Definition of Done and acceptance check in
`spec.md` Part E are met. `owner` marks tasks with required human action.

## S0 Bootstrap
- [x] **S0.1** Repository skeleton, tooling, memory files, and roadmap. Acceptance: `make test`; all `.agent` files exist; this roadmap is present. `owner: license choice`
- [x] **S0.2** CI lint/test, Pages placeholder deploy, keepalive, watchdog, and commit guard. Pages uses GitHub Actions; manual run `42092058401` succeeded; the placeholder was verified live at `https://scottcoff.in/CA_Plastics_Research_Dash/`; configuration names are documented. Acceptance: push deploys; manual dispatch works; secret names documented. `owner inputs complete: public visibility; ENABLE_DATA_COMMITS; OPENALEX_API_KEY`

## S1 Reference data
- [x] **S1.1** OpenAlex/ROR smoke tests and API cost logger. Acceptance: exact working filters, costs, URL limits, and pagination documented.
- [x] **S1.2** California institution registry and ROR join. Acceptance complete: 4,637 institutions; UC 10/10, CSU 23/23, major-private default 11/11; owner review 100/100; 22 owner type corrections are applied through `config/institution_overrides.csv`.
- [x] **S1.3** California land and 3-nm-water polygons. Acceptance complete: four known-point tests pass; 306,997-byte browser asset is <1 MB; full-resolution GeoParquet assets retain 565,997 source coordinates.
- [x] **S1.4** California gazetteer and ambiguity blacklist. Acceptance complete: 127,963 GeoNames California features and 187,760 normalized variants in SQLite; lookup tests and documented explicit blacklist pass.
- [ ] **S1.5** Versioned plastics query config and count estimate. Owner-supplied `plastic-v2-candidate` terms, exclusions, collision notes, taxonomy seeds, G-1/G-2 choices, and cache-version contract are recorded. Remaining acceptance: implement config rendering/cache invalidation, smoke-test encoding/cost, run and timestamp the count estimate, and complete precision/recall spot checks before activation. `owner: terms supplied; promotion review remains`

## S2 Works ingestion
- [ ] **S2.1** Incremental, resumable OpenAlex ingester. Acceptance: reruns dedupe; high-water mark, usage log, and <=200-work fixture exist.
- [ ] **S2.2** Normalize works, authorships, authors, institutions, and CA flags. Acceptance: C3 schemas and QC report.
- [ ] **S2.3** Provisional rule-based relevance and domain tags. Acceptance: labels populated and coverage logged.
- [ ] **S2.4** Daily works workflow with commit and budget guards. Acceptance: CI schedule succeeds and simulated rate limit resumes.

## S3 MVP front end
- [ ] **S3.1** Export slim site data and aggregates. Acceptance: schemas and payload sizes documented; budget met or exception explained.
- [ ] **S3.2** Accessible, mobile app shell and stub tabs. Acceptance: fixture and real data load.
- [ ] **S3.3** Experts filters, virtualized list, and detail drawer. Acceptance: full-data performance measured and screenshot test passes.
- [ ] **S3.4** Institution leaderboard, sparklines, and clustered map. Acceptance: all qualifying institutions render and link to experts.
- [ ] **S3.5** About/Methods and freshness metadata. Acceptance: last refresh and disclaimer display.
- [ ] **S3.6** Pages deployment and performance pass. Acceptance: metrics logged; DuckDB-Wasm used only by recorded decision.

## S4 Gold set
- [ ] **S4.1** Versioned labeling guide. Acceptance: edge cases covered and `guide_v1` approved. `owner: approval`
- [ ] **S4.2** Stratified sample, leak test, and frozen splits. Acceptance: split IDs committed and test set isolated.
- [ ] **S4.3** Annotation workflow, importer, and agreement stats. Acceptance: round-trip and Cohen's kappa work.
- [ ] **S4.4** Reproducible evaluation harness. Acceptance: dummy predictor produces all reports. `owner: thresholds`

## S5 Classifiers
- [ ] **S5.1** Plastic-relevance rules plus SetFit. Acceptance: G-9 targets met or gap and labeling plan documented.
- [ ] **S5.2** Gazetteer gate and measured toponym extractor. Acceptance: recall with CI and NER decision documented.
- [ ] **S5.3** Sampling-vs-mention classifier. Acceptance: per-class held-out metrics and model registration.
- [ ] **S5.4** Geocoding, polygon logic, and `ca_sampled` aggregation. Acceptance: test confusion matrix documented.
- [ ] **S5.5** Multi-label domain tagging and author aggregation. Acceptance: per-tag F1; weak tags merged or experimental.
- [ ] **S5.6** CPU classification workflow and override precedence. Acceptance: CI runtime stated and precedence tested.
- [ ] **S5.7** Candidate-pool leak-test report. Acceptance: widening decision recorded. `owner: decision`

## S6 Full text
- [ ] **S6.1** License-aware OA full-text locator. Acceptance: XML/PDF/none coverage report.
- [ ] **S6.2** Europe PMC JATS section parser. Acceptance: tests on 10 fixture articles.
- [ ] **S6.3** GROBID PDF extraction and fallback. Acceptance: 30-PDF spot check and failure rate.
- [ ] **S6.4** Full-text CA-sampling enrichment. Acceptance: abstract-vs-full-text performance delta.

## S7 Monitoring data
- [ ] **S7.1** Monitoring registry schema and >=15 verified seed entries. Acceptance: provenance, tier, URL, and `last_checked` recorded.
- [ ] **S7.2** Monitoring source smoke tests and tier decisions. Acceptance: access, format, license, frequency, and field maps documented.
- [ ] **S7.3** Tier-A ingesters and normalization. Acceptance: polygon flags, units QC, duplicate QC, fixtures, and tests.
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
