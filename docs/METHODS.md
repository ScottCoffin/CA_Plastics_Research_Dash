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
