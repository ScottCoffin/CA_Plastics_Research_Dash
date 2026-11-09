# S7.4 DataCite and data-availability discovery

## Scope and method

The discovery module preserves DataCite DOI metadata as candidate records,
canonicalizes and deduplicates DOI identities, and leaves `source_work_id` null
unless a paper DOI is independently matched through a typed DataCite relation.
It also extracts bounded data-availability sections from caller-supplied JATS
XML and identifies DOI/URL mentions. It does not fetch article full text or
dataset payloads. Candidates are not registry entries and are not promoted to
links or published data.

On 2026-11-09, nine successful public DataCite metadata searches and one
rejected oversized query (HTTP 414) were made. Three bounded California/plastic
query variants returned 60 unique DOI records after deduplication. Fifty
distinct result landing pages were requested with a 200 KB response cap; only
HTML was read, and no data download URL was followed. Responses were 31 HTTP
200, 16 HTTP 202, one HTTP 410, one HTTP 429, and one HTTP 404. The 50-row
convenience sample is in `docs/S7_4_REAL_REVIEW.csv`; query union membership was
not retained per record, which is disclosed in every row.

## 50-link candidate spot check

Review criteria were applied at the DOI-record candidate level: explicit
California study/coverage evidence, plastic relevance, and an actual
DataCite-typed Dataset or Collection record. A California author affiliation
alone did not count as California dataset coverage. This is agent text review
of metadata and bounded landing-page excerpts, not owner labels. No local work
ID was asserted for query-only candidates.

| Result | Count |
| --- | ---: |
| Distinct DOI candidate records reviewed | 50 |
| Positive | 5 |
| Negative | 40 |
| Unresolved | 5 |
| Resolved denominator (positive + negative) | 45 |
| Precision among resolved records | 5/45 = 11.1% |
| Conservative positive share of all 50, treating unresolved as non-positive | 5/50 = 10.0% |

The five positive DOI links represent three apparent dataset projects after
version-family review: Chollas Creek; a rural California steelhead stream; and
California agricultural plastics remote sensing. Version DOIs remain separate
candidate links in the 50-link denominator; they must be canonicalized to a
project identity before registry promotion. Five records remain unresolved:
one with California affiliation evidence but no verified sampling extent and
four whose landing pages returned HTTP 202 without page text. Inaccessible
landing pages were not silently counted as negatives.

The sample is deterministic, ordered by the captured multi-query result order,
and includes heterogeneous resource types. It is not a random sample and the
estimate is not generalizable to the full DataCite corpus. The modest observed
precision indicates that query results need stronger filters and/or review
before promotion. The 50 candidates are dataset discovery records, not 50
verified paper-to-dataset links. DataCite relations in the captured results
were insufficient to establish a paper link for each candidate. No OpenAlex
calls were made.

## Verification

- `py -3.14 -m pytest tests/test_dataset_discovery_s7_4.py -q`
- `py -3.14 scripts/discover_s7_4.py --input-json tests/fixtures/s7_4/datacite.json --output <temporary-path>`
- Ruff check/format and `git diff --check`

An offline fixture and API notes are in `tests/fixtures/s7_4/` and
`docs/api_notes/datacite_s7_4.md`. No API request is needed for the tests.
