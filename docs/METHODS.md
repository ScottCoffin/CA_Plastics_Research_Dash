# Methods

This document will describe the versioned queries, data normalization,
classification, geographic logic, evaluation, and refresh process as stages are
implemented. The definitions in `spec.md` A2 are authoritative during bootstrap.

## Candidate plastics query

The owner-supplied `plastic-v2-candidate` vocabulary and Boolean design are in
`config/queries.yml`; supporting collision findings and literature-derived
taxonomy seeds are documented in `docs/query_design_v2.md`. The S1.2
`search=plastic` counts remain review-priority metadata and are not a
publication corpus or leaderboard.

Any term, Boolean, exclusion, or field-scope change increments the query
version. Count caches must store both the version and rendered query and must be
discarded when either differs. The candidate is not production-active until
S1.5 reproduces a timestamped count estimate and completes precision/recall
checks.

S1.5 implementation is in `src/atlas/query.py`. It renders the core Boolean
expression from the structured term lists, builds a fully encoded
`title_and_abstract.search` filter, and rejects count caches unless both
`query_version` and `rendered_query` match. The ignored local cache is
`data/interim/openalex_query_counts.json`; the live smoke/audit runner is:

```powershell
py -3.14 scripts/smoke/query_s1_5.py
py -3.14 scripts/check_s1_5.py
```

The count is metadata-only (`per_page=1`, grouped by publication year); the
smoke also compares the exclusion-bearing query with its positive control,
checks URL encoding and group-by response shape, and records OpenAlex response
credits/costs through the shared logger. Precision is a bounded manual
title/abstract review of UCSF, SLAC, and global samples, while recall uses the
four literature-informed anchors in
`tests/fixtures/s1_5_known_relevant.json`. These are screening checks, not a
replacement for the later owner promotion review or the gold-set evaluation.
