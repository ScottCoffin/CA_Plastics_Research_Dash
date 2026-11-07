# Latest Session Work

## Current State

S4.3 annotation tooling is complete. `atlas.nlp.annotation` and the workflow
CLI provide gated CSV template export/import and per-label Cohen's kappa
reports; see `docs/S4_3_VERIFICATION.md`. The implementation has synthetic
acceptance only. No real labels, adjudications, or real agreement metrics were
created. S4.1 approval and S4.2 representative sampling gates remain pending.

S4.1 has a reviewed `guide_v1` draft with matching hash, but owner approval is
pending and annotation remains unauthorized. S4.2 has fixture-only splits (2
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

## Next Entry Point

S4.3 is sealed. Continue at the next dependency-satisfied roadmap task after
re-reading `.agent/TODO.md` and `.agent/HANDOFF.md`. Human annotation still
requires S4.1-A approval and an authorized representative split; do not treat
synthetic values as gold labels or metrics. S4.2 and S3.6 remain open under
their documented data and owner gates.
