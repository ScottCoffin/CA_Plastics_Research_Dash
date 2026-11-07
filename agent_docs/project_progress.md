# Project Progress

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
