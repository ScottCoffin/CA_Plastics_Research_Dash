# Latest Session Work

## Current State

S4.1 has a draft `guide_v1` plus independent review and bounded consistency
checks. The review SHA-256 is
`A88B164F67CB60249064A13A529FC21762023037DAF444CDD30B7FCF33481C15`, matching
the current guide. Owner approval is pending; S4.1 remains unchecked and no
annotation is authorized. S4.2 has deterministic label-independent sampling,
fixture splits, and author-group isolation documented in
`docs/S4_2_VERIFICATION.md`. The two fixture pool rows split train 1, dev 0,
test 1; leak rows are 0 because no versioned hit source was supplied. The
fixture is not representative corpus evidence and S4.2 remains unchecked.

Prior S3.6 deployment and fixture performance evidence remains in
`docs/S3_6_VERIFICATION.md`. Pages run 42334138365 deployed successfully and
direct live checks passed; full-data performance remains open.

## Verification

- Independent review accepted the guide after the initial relevance gate was
  clarified to include chemicals-in-plastics subjects; see
  `docs/LABELING_GUIDE_VERIFICATION.md`.
- `Get-FileHash docs/LABELING_GUIDE.md -Algorithm SHA256` matched the review
  artifact hash above.
- `py -3.14 scripts/check_s4_2.py` passed; 7 focused tests and the full 56-test
  suite passed; Ruff check/format and `git diff --check` passed.
- S3.6 fixture measurement and live deployment checks are recorded in
  `docs/S3_6_VERIFICATION.md`; full-data C5 remains an open gate pending owner
  query review and authorized representative export. See `.agent/HANDOFF.md`.

## Next Entry Point

S4.3 annotation roundtrip/import/agreement tooling may use synthetic labels;
human gold annotation remains gated on explicit S4.1-A approval. Keep S4.2
unchecked until an authorized representative export and versioned gazetteer-hit
source produce the planned pool and leak-test samples. Keep S3.6 open until
full-data performance is measured.
