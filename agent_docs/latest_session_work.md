# Latest Session Work

## Current State

S6.2 is complete and sealed. The Europe PMC JATS parser/cache acceptance
passed on ten license-attributed real article fragments and ten synthetic
edge fixtures. Ten complete selected documents yielded target sections in
9/10, a fixture-set result only. S6.3 GROBID and fallback is next and requires
a 30-PDF spot check. S6.1 remains unchecked pending actual candidate-corpus
coverage; do not infer it from synthetic counts.

S6.1 locator tooling is implemented and verified on a synthetic eight-row
fixture: 2 XML, 4 PDF, and 2 none (25%, 50%, 25%). These are not candidate
corpus coverage. No downloaded production candidate corpus is available, so
S6.1 remains unchecked until the required corpus report can be generated. The
S1.5 estimate is not a corpus. S6.2 is independently eligible with ten
license-safe article fixtures.

S4.4 evaluation tooling is complete against the dummy-predictor DoD.
`atlas.nlp.eval` and `scripts/evaluate.py` provide per-class/per-label metrics,
calibration, error analysis, and JSON; deterministic synthetic evidence is in
`docs/EVAL_synthetic_v1.md`. No corpus performance is claimed. S4.3 annotation
tooling remains complete with synthetic acceptance only; no real labels,
adjudications, or agreement metrics were created. S4.1 owner approval is complete; S4.2
representative sampling gates remain pending.

S4.1 `guide_v1` was approved and frozen by Scott Coffin on 2026-11-07; the
approved hash is recorded in `docs/LABELING_GUIDE_REVIEW.md`. Representative
sampling and annotation authorization remain separate open gates. S4.2 has fixture-only splits (2
pool rows, train 1/dev 0/test 1, zero leak rows) and remains incomplete until
an authorized representative export and versioned leak-hit source exist.
S3.6 likewise remains open pending query approval, representative export, and
full-data performance evidence.

## Verification

- `py -3.14 -m pytest tests/test_annotation.py`: 15 passed.
- `py -3.14 scripts/check_s4_3.py`: synthetic round-trip passed and pending
  `guide_v1` approval gate was rejected as expected.
- Full `py -3.14 -m pytest`: 71 passed.
- Ruff check/format check and `git diff --check`: passed.
- Verification details and human milestones are in
  `docs/S4_3_VERIFICATION.md`.

- S4.4: accepted focused and reproducibility checks, full 83-test suite, Ruff
  check/format, and `git diff --check` passed. G-9 thresholds are answered.
  Synthetic evaluation output is not corpus evidence.

## Next Entry Point

S4.4 is sealed. Continue with S6.1, the independent license-aware OA full-text
locator. S5 implementation may begin only where it does not claim trained or
validated performance; classifier acceptance still requires approved S4.1
guide and representative adjudicated gold. Do not treat synthetic values as
gold labels or metrics. S4.2 and S3.6 remain open under their documented data
and owner gates.
