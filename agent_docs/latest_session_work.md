# Latest Session Work

## Current State

S4.1 has a draft `guide_v1` plus independent review and bounded consistency
checks. The review SHA-256 is
`A88B164F67CB60249064A13A529FC21762023037DAF444CDD30B7FCF33481C15`, matching
the current guide. Owner approval is pending; S4.1 remains unchecked and no
annotation is authorized. S4.2 label-independent sample/split preparation can
proceed, but the four-work fixture is not representative corpus evidence.

Prior S3.6 deployment and fixture performance evidence remains in
`docs/S3_6_VERIFICATION.md`. Pages run 42334138365 deployed successfully and
direct live checks passed; full-data performance remains open.

## Verification

- Independent review accepted the guide after the initial relevance gate was
  clarified to include chemicals-in-plastics subjects; see
  `docs/LABELING_GUIDE_VERIFICATION.md`.
- `Get-FileHash docs/LABELING_GUIDE.md -Algorithm SHA256` matched the review
  artifact hash above.
- S3.6 fixture measurement and live deployment checks are recorded in
  `docs/S3_6_VERIFICATION.md`; full-data C5 remains an open gate pending owner
  query review and authorized representative export. See `.agent/HANDOFF.md`.

## Next Entry Point

Proceed with S4.2 label-independent sample/split preparation; do not annotate,
and do not describe the four-work fixture as representative. Ask the owner the
S4.1-A question in `.agent/QUESTIONS.md`; only freeze the guide after explicit
approval and date. Keep S3.6 open until full-data performance is measured.
