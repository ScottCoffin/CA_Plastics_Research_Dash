# Handoff - 2026-11-07 - task S4.1 partial

## Prior S3.6 checkpoint
- Pages deployment and four-work fixture C5 measurements are recorded in `docs/S3_6_VERIFICATION.md`; the live check passed and the fixture is below the C5 payload target.
- S3.6 remains unchecked because no representative work export exists. The 98,118 S1.5 count is an estimate, not downloaded data. Resume only after S1.5-A is answered and a bounded export is authorized; do not activate the candidate to manufacture a benchmark.

## Done
- Prepared `docs/LABELING_GUIDE.md` as a work-level `guide_v1` draft with plastic relevance/tier, California sampling, multi-label domains, evidence and source constraints, adjudication, and required edge cases.
- Independent review accepted the guide after clarification that chemicals-in-plastics subjects, including primary 6PPD-quinone exposure, pass the initial relevance gate. The guide explicitly says this at the first decision in Section 1; the bounded example is recorded in `docs/LABELING_GUIDE_VERIFICATION.md`.
- Verified the exact review artifact hash: `A88B164F67CB60249064A13A529FC21762023037DAF444CDD30B7FCF33481C15`.
- Owner checklist and reply instructions are in `docs/LABELING_GUIDE_REVIEW.md`; S4.1-A in `.agent/QUESTIONS.md` asks for approval and date or an exact requested revision.

## State and gates
- S4.1 remains unchecked. Approval and freezing `guide_v1` are still required before annotation; no annotation, gold adjudication, or guide freeze occurred.
- S4.2 label-independent sample/split preparation is eligible while approval is pending. It must isolate test records and must not use the four-work fixture as evidence of a representative corpus.
- S3.6 remains open pending approved query promotion, authorized representative export, and full-data performance measurement. The fixture-only evidence does not satisfy that gate.
- Preserve the unrelated pre-existing `README.md` edit; it is not part of the S4.1 checkpoint.

## Next eligible work
- Continue S4.2 sample/split preparation under its contract, without annotation or gold labels. Keep S4.1 owner approval pending and return to freeze the reviewed guide only after an explicit owner decision.
- S3.6 can resume separately after S1.5-A is answered and a representative export is authorized.

## Verification and release
- Independent labeling-guide review passed with no finding after the initial relevance-gate clarification.
- `Get-FileHash docs/LABELING_GUIDE.md -Algorithm SHA256` matched the review hash above.
- This is a draft/handoff checkpoint, not S4.1 acceptance. Commit only the guide, its review/verification artifacts, and S4.1 roadmap/handoff records; exclude `README.md` and S3 files.
