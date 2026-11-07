# Handoff - 2026-11-07 - task S4.2 partial

## Prior S3.6 checkpoint
- Pages deployment and four-work fixture C5 measurements are recorded in `docs/S3_6_VERIFICATION.md`; the live check passed and the fixture is below the C5 payload target.
- S3.6 remains unchecked because no representative work export exists. The 98,118 S1.5 count is an estimate, not downloaded data. Resume only after S1.5-A is answered and a bounded export is authorized; do not activate the candidate to manufacture a benchmark.

## Done
- Added deterministic, label-independent sample and split preparation in `src/atlas/nlp/sampling.py`, with CLI and acceptance check in `scripts/build_gold_sample.py` and `scripts/check_s4_2.py`.
- Committed fixture-derived `curation/splits_v1.csv` and its hash manifest. The 2 pool rows split train 1, dev 0, test 1; leak-test rows are 0 because no versioned gazetteer-hit source was supplied. Author groups do not cross splits.
- `docs/S4_2_VERIFICATION.md` records the contract, hashes, fixture-only limitation, commands, and owner gates. The 7 focused tests and 56-test full suite pass; Ruff check/format and `git diff --check` pass.

## State and gates
- S4.1 remains unchecked. Approval and freezing `guide_v1` are still required before annotation; no annotation, gold adjudication, or guide freeze occurred.
- S4.2 remains unchecked and partial: fixture plumbing is verified, but the ~400–600 representative pool and leak-test sample cannot be produced without an authorized representative export and separately versioned gazetteer-hit list. The fixture is not representative corpus evidence.
- S3.6 remains open pending approved query promotion, authorized representative export, and full-data performance measurement.
- Preserve the unrelated pre-existing `README.md` edit; it is not part of this checkpoint.

## Next eligible work
- S4.3 annotation roundtrip/import/agreement tooling may use synthetic labels; human gold annotation remains gated on S4.1-A approval. Keep S4.2 open until an authorized representative export and leak-hit list allow production splits.
- S3.6 can resume separately after S1.5-A is answered and a representative export is authorized.

## Verification and release
- `py -3.14 scripts/check_s4_2.py` passed; focused tests: 7 passed; full `make test`: 56 passed. Ruff check, Ruff format check, and `git diff --check` passed.
- Prior independent labeling-guide review/hash remain recorded in `docs/LABELING_GUIDE_VERIFICATION.md`; owner approval is still pending.
- Stage only S4.2 code, fixture split artifacts, verification document, and closure records; exclude `README.md` and unrelated S3 work.
