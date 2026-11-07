# S4.3 annotation tooling verification

## Tooling acceptance

The specification's tooling DoD is met: a spreadsheet-compatible CSV template round-trips through a validator, and a reproducible agreement report computes Cohen's kappa. Implementation is in `src/atlas/nlp/annotation.py`; `scripts/annotation_workflow.py` exposes export, import, and agreement commands. The CSV carries source title/abstract/year as read-only fields, frozen split/sample-role, annotator and guide version, guide labels, evidence provenance, and separate adjudication fields. The importer validates IDs, source metadata, split isolation, duplicate assignments, guide version, label values, taxonomy IDs, unresolved cases, and evidence/adjudication consistency. Human operations require owner approval, a non-placeholder owner, ISO approval date, frozen status, and exact guide SHA-256 before reading the works snapshot or operating on files. Agreement output includes a per-work disagreement list with per-field annotator values, evidence, and an explicit unresolved state; adjudication values remain empty.

Held-out rows are excluded from template exports and imports by default. Explicit `--include-test` is needed for either operation; agreement reports require an explicit split, with `--split test` documenting deliberate test-report access. No suggestions are exposed. Per F3, test items must not be used for threshold tuning or development error analysis. Leak-test entries must remain in `test`.

## Synthetic evidence

- `py -3.14 -m pytest tests/test_annotation.py`: 15 passed. Tests cover template/import round-trip; synthetic nontrivial kappa and actionable disagreement records; undefined single-category and no-pair cases; invalid values, tier conflicts, duplicate assignments, unknown IDs, guide mismatch, split mismatch, held-out gating, unresolved rows, and owner/date/hash approval gates.
- `py -3.14 scripts/check_s4_3.py`: synthetic round-trip passed and the actual pending `guide_v1` gate rejected the workflow as expected.
- Full `py -3.14 -m pytest`: 71 passed.
- `py -3.14 -m ruff check .`, `py -3.14 -m ruff format --check .`, and `git diff --check`: passed.

Synthetic values exist only in temporary test files and are not corpus annotations. No real annotation CSV, gold labels, adjudications, or performance results were created. The real CLI currently refuses to run because S4.1-A is pending; it also requires the review's approved hash to match the exact guide bytes.

## Human milestone still required

The remaining S4.3 operational milestone is blocked by the existing owner approval gate, not by missing tooling: approve and freeze `guide_v1`; provide an authorized representative split after S4.2's export/leak-test conditions are met; assign annotators and double-annotate at least 20% of that sample; adjudicate unresolved/disagreement cases under the guide; then retain the real agreement report and provenance hashes. This implementation does not claim that human milestone or G-9's proposed `kappa >= 0.7` target has been reached. S4.2 remains partial, and the present two-row fixture is not appropriate for human gold annotation.
