# ROR API v2 verification

Verified 2026-11-05 with bounded unauthenticated requests from
`scripts/smoke/ror.py`.

## Working endpoints and response shape

- `GET /v2/organizations/01an7q238` returned HTTP 200 for the University of
  California, Berkeley. The record has `admin.last_modified.schema_version`
  `2.1`, lowercase `types` values (`education`, `funder`), and a `locations`
  array.
- The sample `locations[0].geonames_details` contained city name, latitude,
  longitude, country, subdivision, and continent fields. California is encoded
  as `country_code=US`, `country_subdivision_code=CA`, and
  `country_subdivision_name=California`; the subdivision code is not `US-CA`.
- The advanced query
  `locations.geonames_details.country_subdivision_name:California` returned
  5,151 active records at the time of the smoke test. Every record on the two
  inspected pages had the expected subdivision name.

Counts are observations, not invariants; ROR is updated regularly.

## Pagination, rate behavior, and intended use

- ROR list/search responses use a top-level `number_of_results`, `items`, and
  summary facets. The API returns 20 items per page; `page=1` and `page=2`
  returned disjoint IDs in the live smoke test.
- ROR documents a maximum of 500 pages/10,000 retrievable records. It warns
  that exhaustive paging can produce duplicates or omissions as data changes;
  use the data dump for a complete registry.
- No rate-limit response headers were observed in the three smoke requests.
  The current REST documentation states 2,000 requests per five minutes per IP.
  The client-ID page says registration is temporarily paused and no client-ID
  rate limits are currently enforced. Recheck before a production backfill.
- ROR has no per-request credit billing. The shared usage logger records ROR
  request counts with zero credits and zero USD so run accounting remains
  complete across sources.

## License and documentation evidence

ROR IDs and metadata are CC0. Location details are derived from GeoNames,
whose data is CC BY 3.0; retain source attribution when publishing those
fields.

Official documentation checked 2026-11-05:

- <https://ror.readme.io/docs/rest-api>
- <https://ror.readme.io/docs/api-single>
- <https://ror.readme.io/docs/api-advanced-query>
- <https://ror.readme.io/docs/api-paging>
- <https://ror.readme.io/docs/ror-data-structure>
- <https://ror.readme.io/docs/schema-v2-1>
- <https://ror.readme.io/docs/client-id>
- <https://ror.org/about/terms/>

Acceptance rerun: `python scripts/smoke/ror.py` completed successfully on
2026-11-05; output and usage logs are generated in ignored local paths.

## S1.2 data-dump join (2026-11-05)

- The build resolved Zenodo concept record `6347574` to ROR release v2.15,
  DOI `10.5281/zenodo.23500708`, file
  `v2.15-2026-10-20-ror-data.zip`, MD5
  `5522990688eb1b94811a8145e131b41e`.
- The checksum-verified dump matched all 4,637 known ROR IDs in the final
  OpenAlex registry. The ZIP is ignored raw input; only the slim joined
  Parquet is committed.
- The downloader retains a partial `.tmp` file and resumes with an HTTP Range
  request after a connection reset. It verifies the advertised checksum before
  loading JSON.
- Dump retrieval follows the official ROR/Zenodo instructions at
  <https://ror.readme.io/docs/zenodo>. ROR metadata remains CC0; GeoNames-derived
  location fields require CC BY 3.0 attribution.
