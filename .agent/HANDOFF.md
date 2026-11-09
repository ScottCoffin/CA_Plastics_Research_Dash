# Handoff - 2026-11-07 - S6.3 complete; S7.1 next

## Done
- Implemented GROBID TEI extraction and bounded pdfminer fallback/cache in `src/atlas/fulltext/grobid.py`, with focused acceptance and 30-PDF spot-check scripts.
- S6.3 spot check processed 30 selected Frontiers CC BY PDFs with per-copy license evidence and PDF hashes. Text review matched all 16 extracted target headings and evidence prefixes against source PDF text. This is a convenience sample; visual PDF layout was not assessed and it is not candidate-corpus performance.
- GROBID technical failure rate was 0/30. It returned no target sections for 21/30; pdfminer recovered targets for 6 of those, leaving 15 final no-target records (13 reviews, 2 editorials). Two PDFs were rejected before caching because their own copy lacked a CC BY statement.
- Focused acceptance, full 163-test suite, Ruff check/format, and `git diff --check` pass.

## State of the repo
- S6.2 is complete. S6.1 remains unchecked pending candidate-corpus XML/PDF/none coverage; its synthetic fixture is not corpus evidence.
- S4.2 representative split/leak evidence and S3.6 representative performance remain open. S4.1 guide approval is recorded.
- Preserve the unrelated README URL edit. The S6.2 `docs/REUSE.md` entry is part of this checkpoint.

## Next task
- S6.4 requires an abstract-vs-full-text evaluation delta and real gold subset; do not fabricate corpus metrics. Continue with independent S7.1 registry schema and at least 15 verified seed entries. First read its exact contract and preserve S6.3's sample-scope caveats.

## Gotchas
- Do not claim corpus-wide section recall from the ten selected articles.
- Check each selected-copy license before processing or caching full text; cache only in the ignored raw-data directory.
- Keep test data final-only for evaluation.

# Handoff - 2026-11-09 - SPK-7 complete; AT-1 next

## SPK-7 measured cost and budget checkpoint

### Done
- Closed SPK-7/G-COST against `79301e720d2e375c85b7f70774dc13856a274f50`; owner authorized free-only account use, and the 100-call benchmark completed successfully.
- The response metadata total is USD 0.026; the provider's post-run allowance decrement implies USD 0.028. The discrepancy remains explicit and the S2.1 budget guard accounts conservatively. Full and conservative totals are in `docs/api_notes/openalex_costs.md`.
- Final acceptance recorded 199 tests, Ruff, and a network-forbidden rerun. HTTP 500 without credit/accounting metadata stops before retry or output advancement; known-credit HTTP 500 bounded retry remains accepted.

### State and next
- AT-1 is still under review: query-v2 rendering/cache invalidation and precision/recall audit are unfinished. The independent candidate-promotion decision and S3.6 representative live-data performance evidence remain open.
- Continue with AT-1 after resolving its recorded review findings; do not activate/promote the candidate or claim S3.6 complete from the SPK-7 measurement.

### Files changed for this closure
- `.agent/TODO.md`, `.agent/QUESTIONS.md`, `.agent/MEMORY.md`, `.agent/SESSION_LOG.md`, `.agent/HANDOFF.md`, and `agent_docs/project_progress.md`.
