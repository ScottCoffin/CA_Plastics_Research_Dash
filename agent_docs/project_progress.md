# Project Progress

## 2026-11-09 Checkpoint

SPK-7 is complete at `79301e7` (full hash:
`79301e720d2e375c85b7f70774dc13856a274f50`). The 100-call benchmark and
measured S2.1 budget guard are documented in
`docs/api_notes/openalex_costs.md`; the owner confirmed free-only authorization.
Response metadata summed to USD 0.026 while the post-run provider balance
decrement implied USD 0.028. The guard uses the conservative higher accounting
and the discrepancy remains explicit. HTTP 500 without credit accounting stops
before retry or output advancement; known-credit HTTP 500 bounded retry is
accepted. The checkpoint verification records 199 tests and Ruff, with the
final rerun network-forbidden.

AT-1 remains next and under review: query-v2 rendering/cache invalidation and
precision/recall audit are unfinished. The owner’s independent candidate
promotion decision and S3.6 live-data performance evidence remain open.


## Goal

Complete the staged CA Plastics Research Atlas roadmap one dependency-satisfied
atomic checkpoint at a time.

## Overall Progress

S0 through S2.4 and S3.1 through S3.5 are implemented and verified. S3.6 has a
partial evidence checkpoint: Pages deployment and fixture C5 budgets pass, but
the full-data performance DoD remains unmet. The static atlas has deterministic
slim exports, an accessible shell, Experts filters and lazy details, an
institution leaderboard/map, and About/Methods content.

## Current Position

S3.6 partial evidence is recorded in `docs/S3_6_VERIFICATION.md`. It remains
unchecked until representative full-data performance is measured. Query
promotion remains an owner decision and separate from this checkpoint.

## Next Milestone

S4.1 `guide_v1` was approved and frozen by Scott Coffin on 2026-11-07; the
approved hash and edge-case verification are recorded in
`docs/LABELING_GUIDE_REVIEW.md` and `docs/LABELING_GUIDE_VERIFICATION.md`. S4.1
is complete. Representative sampling and annotation authorization remain open. S4.2 has a partial evidence
checkpoint in `docs/S4_2_VERIFICATION.md`: 2 fixture pool rows (train 1, dev 0,
test 1), zero leak rows, and verified author-group isolation. S4.2 remains
unchecked because the fixture is not representative and no versioned leak-hit
source exists. Separately, after owner query review and an authorized bounded
export, rerun full-data C5 and close S3.6 only when acceptance is met.

S4.3 tooling is complete: gated CSV round-trip/import and per-label Cohen's
kappa reporting pass synthetic acceptance. No real annotations were created.
an authorized representative sample, double annotation of at least 20%,
adjudication, and a real agreement report remain human operational milestones; see `docs/S4_3_VERIFICATION.md`.

S4.4 evaluation tooling is complete against its dummy-predictor DoD. The
reproducible synthetic report includes per-class/per-label metrics, calibration,
error analysis, and JSON; see `docs/EVAL_synthetic_v1.md`. No corpus performance
is claimed. G-9 thresholds are answered. S5 classifier training/evaluation
remains gated on approved `guide_v1` and representative adjudicated gold data;
S6.1 locator tooling is implemented and verified on an eight-row synthetic
fixture (2 XML, 4 PDF, 2 none), but remains unchecked because no downloaded
candidate corpus is available for the required coverage report. The S1.5 count
estimate is not a corpus. S6.2 JATS parsing can proceed independently using ten
license-safe fixtures under its contract.

S6.2 is complete: ten real CC BY JATS excerpts and ten synthetic edge fixtures
pass; full XML stays in the ignored local cache. Parsing ten selected XML
documents found target sections in 9/10, fixture-set evidence only. S6.3 is
complete: a 30-PDF licensed convenience sample had zero technical GROBID
failures, 21 GROBID no-target outcomes, six pdfminer recoveries, and 15 final
no-target outcomes (13 reviews, two editorials). All 16 extracted target
headings/evidence prefixes matched source PDF text. This is not visual PDF QA
or corpus performance. S6.1 remains open pending candidate-corpus coverage.
S7.1 registry schema and at least 15 verified seed entries is the next
independent eligible task; S6.4 still requires real gold for an evaluation
delta.

AT-1 partial checkpoint (2026-11-09): explicit audit mode leaves legacy production ranking/cache as default and validates audit cache identity/path separation. The bounded runner saved the owner-approved top-20 sample (405 rows, 354 unique works, 51 repeated-ID rows, 95-row shortfall across eight strata), with four count baselines within 10%; it used 24 metered requests, 240 credits and USD 0.024 accounted cost plus one status snapshot. The owner chose no supplements/query changes and left the 500-work gate open. Labels remain blank and candidate promotion is pending. Network-blocked full suite passed (222); see `docs/QUERY_AUDIT.md`. AT-1 remains unchecked; next independent roadmap task is S7.1.

S7.1 records-only reconciliation (2026-11-09): existing implementation `46e58e7` remains unchanged. `config/datasets.yml` has 24 source records and 15 distinct eligible underlying dataset identities; provenance, tier, verification URL, and `last_checked` evidence are in `docs/S7_1_VERIFICATION.md`. Prior focused and full-suite acceptance evidence is retained. S7.2 source review is complete; next is S7.3 normalization for the cleared SF Bay / 5 Gyres source. Owner-gated SPK-1..4 remain skipped; AT-1 is partial and AT-2 remains blocked.


S7.2 (2026-11-09): bounded smoke evidence covers all 15 eligible monitoring identities. Only the SF Bay / 5 Gyres CC BY 4.0 XLSX is cleared Tier A, with its sample and particle sheets joined by `SampleID`; count and volume are preserved separately and concentration/size-class/mesh harmonization stays for S7.3. The other sources remain B/C/D with no auto-ingest pending rights, row-level access, California scope, or mapped fields. Focused tests: 11 passed; network-blocked full suite: 226 passed; Ruff and whitespace checks passed. See `docs/S7_2_VERIFICATION.md`. Other Tier A candidates require documented clearance before ingestion.
