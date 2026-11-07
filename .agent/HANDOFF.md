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
