# Handoff - 2026-11-06 - S6.1 partial; S6.2 eligible

## Done
- Implemented S6.1 metadata-only Europe PMC XML/PDF/none selection, copy-specific license provenance, and conservative processing/storage decisions in `src/atlas/fulltext/__init__.py` and `scripts/locate_fulltext.py`.
- Added `scripts/check_s6_1.py`, six focused locator tests, an eight-row synthetic fixture, and verification/API notes. Trusted repository path and exact PMCID license evidence, PDF selected-copy evidence, unsafe URL handling, and missing/restricted license cases are covered.
- Acceptance passed: full suite 89, Ruff check and format, `git diff --check`, and one bounded Europe PMC smoke returned HTTP 200 with XML content type. No article text was saved.
- S6.1 remains unchecked. The fixture reports 2 XML, 4 PDF, and 2 none (25%, 50%, 25%), but no downloaded candidate corpus is available. The S1.5 query estimate is not a corpus, so the required candidate-corpus coverage report remains outstanding.

## State of the repo
- S6.1 locator tooling is implemented and synthetic behavior is verified, but its coverage DoD is incomplete pending a candidate corpus.
- S4.1 owner approval and S4.2 representative data/leak-hit source remain pending; S3.6 full-data performance remains open.
- Preserve the unrelated existing `README.md` edit.

## Next task (suggested)
- S6.2: implement the Europe PMC JATS section parser against ten license-safe article fixtures, as specified by the task contract. It may proceed independently of S6.1 production-corpus coverage; confirm each fixture's copy license and attribution.

## Gotchas
- Do not mark S6.1 complete or present synthetic percentages as production-corpus coverage.
- S5 acceptance still requires representative adjudicated gold after approved `guide_v1`; do not report synthetic values as model performance.
- Keep test data final-only for evaluation.
