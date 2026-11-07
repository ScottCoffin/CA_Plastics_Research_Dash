# Handoff - 2026-11-07 - S6.2 complete; S6.3 next

## Done
- Implemented Europe PMC JATS parsing in `src/atlas/fulltext/jats.py`, a license-gated fetch/cache interface in `src/atlas/fulltext/cache.py`, and a local parser CLI.
- Acceptance passes on ten real CC BY article fragments and ten synthetic edge fixtures. Provenance records attribution, DOI/source URLs, metadata and selected-copy XML license evidence, and source hashes. Full XML is only in ignored local cache; committed real snippets are bounded to two excerpts of 180 characters per article.
- Parser/cache security regression tests reject internal DTD subsets, including one hidden between comment tokens resembling CDATA delimiters; external DTDs are not resolved. Focused and full checks pass: 148 tests, Ruff lint/format, and `git diff --check`.
- Complete local XML parsing found target sections in 9/10 selected articles (Methods 8, Study Area 1, Sampling 4, Data Availability 7); fixture-set counts are not corpus estimates.

## State of the repo
- S6.2 is complete. S6.1 remains unchecked pending candidate-corpus XML/PDF/none coverage; its synthetic fixture is not corpus evidence.
- S4.2 representative split/leak evidence and S3.6 representative performance remain open. S4.1 guide approval is recorded.
- Preserve the unrelated README URL edit. The S6.2 `docs/REUSE.md` entry is part of this checkpoint.

## Next task
- S6.3: implement GROBID PDF extraction and fallback; use a 30-PDF spot check and report extraction failure rate. It is independent of S6.1 corpus coverage.

## Gotchas
- Do not claim corpus-wide section recall from the ten selected articles.
- Check each selected-copy license before processing or caching full text; cache only in the ignored raw-data directory.
- Keep test data final-only for evaluation.
