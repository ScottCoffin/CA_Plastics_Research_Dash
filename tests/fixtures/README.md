# Test fixtures

Commit only small, license-compatible fixtures with at most 200 records per
source. Record provenance and any transformations beside each fixture.

`s2_1_openalex_works.json` is a four-record synthetic works fixture used to
exercise ID compaction, raw JSON preservation, idempotent deduplication, and
publication-date high-water marks. It contains no live corpus snapshot.
