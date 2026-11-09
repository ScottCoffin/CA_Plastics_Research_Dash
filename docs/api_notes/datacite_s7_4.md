# DataCite public REST API notes for S7.4

Checked 2026-11-09 against the official [REST API guide](https://support.datacite.org/docs/rest-api), [query guide](https://support.datacite.org/docs/api-queries), and [related works guide](https://support.datacite.org/docs/connecting-to-works).

## Request and observed shape

- Endpoint: `GET https://api.datacite.org/dois`
- Parameters used: `query=<DataCite field query>&page[size]=100`; no authentication or key.
- Queries used in the retained sample included title/description searches combining `microplastic(s)` or `plastic` with `California`.
- Response shape: JSON:API `data[]`; each record has `id` and `attributes`, including `titles`, `types.resourceTypeGeneral`, `url`, and optional `relatedIdentifiers[]` with `relatedIdentifier`, `relatedIdentifierType`, and `relationType`.
- The public API documentation describes unauthenticated retrieval of findable DOI metadata. It describes the query syntax and relation metadata; no numeric rate limit was established from the documentation reviewed.
- Observed during bounded discovery: nine HTTP 200 metadata responses and one HTTP 414 for an oversized OR query. The 414 is a URI-length limit signal; queries were then shortened. This is not a formal service rate-limit measurement.
- Historical provenance gap: the retained 50-row review has the union of the query strings but not per-record query membership, sanitized request URLs, or response hashes. These fields were not captured at collection time and are intentionally not reconstructed or imputed.

For future runs, record per returned DOI: the exact query membership, the
sanitized metadata request URL (remove credentials and sensitive parameters),
retrieval timestamp, and SHA-256 of the canonical sanitized JSON:API `data`
records; store the hash rather than copying another response body into the
provenance file.
These fields must be captured during the request; do not infer membership from
the union of results. `scripts/discover_s7_4.py` now emits these fields for
future live queries. The historical review rows remain unchanged and do not
claim per-record query membership or hashes.

## Use and limits

The implementation stores metadata and short, attributed landing-page excerpts
only. It does not follow dataset file/download URLs. DataCite `relatedIdentifiers`
are retained with their relation type and are not by themselves proof that a
California plastics paper used a dataset. Data-availability parsing accepts
caller-supplied JATS only; the module does not fetch full text or determine its
reuse license. A separate rights check is required before any full-text cache
is read or extended.

## Reproducible commands

```powershell
py -3.14 scripts/discover_s7_4.py --input-json tests/fixtures/s7_4/datacite.json --output $env:TEMP/s7_4_candidates.json
py -3.14 -m pytest tests/test_dataset_discovery_s7_4.py -q
```
