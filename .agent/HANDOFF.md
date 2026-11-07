# Handoff - 2026-11-06 - task S4.4 complete

## Done
- Added `src/atlas/nlp/eval.py` and `scripts/evaluate.py` for validated, provenance-bound evaluation of canonical adjudicated labels.
- Added deterministic acceptance check `scripts/check_s4_4.py`, focused tests in `tests/test_eval.py`, and synthetic report/JSON/calibration artifacts in `docs/EVAL_synthetic_v1.md`, `docs/EVAL_synthetic_v1.json`, and `docs/EVAL_synthetic_v1_calibration.png`.
- Documented evaluation workflow and held-out restrictions in `docs/ANNOTATION_WORKFLOW.md`; marked S4.4 tooling complete in `.agent/TODO.md`.
- G-9 thresholds are answered. Synthetic results demonstrate reproducible output only; they are not corpus performance.

## State of the repo
- S4.4 dummy-predictor DoD is complete. Parent verification reports focused acceptance and artifact reproducibility after four fixes; full suite (83), Ruff check/format, and `git diff --check` pass.
- Evaluation requires canonical, adjudicated gold, explicit split/model/data provenance, and matched prediction IDs. Test evaluation requires `--final-test`.
- S4.1 owner approval and S4.2 representative data/leak-hit source remain pending; no real labels or validated classifier metrics exist. S3.6 full-data performance remains open.

## Next task (suggested)
- S6.1: implement the license-aware OA full-text locator independently of classifier training. First inspect its Part D source/contracts, inventory the candidate-work schema and available OA metadata, then implement and report XML/PDF/none coverage with license/storability handling.

## Gotchas the next agent must know
- S5 acceptance requires representative adjudicated gold after approved `guide_v1`; do not weaken these requirements or present synthetic numbers as model performance.
- S4.4 reports metrics but does not tune thresholds. Keep test data final-only.
- Preserve the unrelated existing `README.md` edit.

## Needs owner input
- None blocks S6.1. S4.1-A guide approval and S3.6 query/export authorization remain pending for their respective tasks.

## Files that are large or unsafe to read whole
- None for S6.1 entry; inspect only relevant schema/source files and the named spec sections.
