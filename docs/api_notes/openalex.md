# OpenAlex API verification

Verified 2026-11-05 with bounded anonymous requests from
`scripts/smoke/openalex.py`. The local process did not have
`OPENALEX_API_KEY`; the repository Actions secret was not read or exposed.

## Working filters and response shape

- `GET /institutions?filter=geo.region:California&per_page=2&page=1` returned
  HTTP 200, `meta.count=4614`, and results whose `geo.region` was exactly
  `California`. Page 2 returned different IDs. `California` is therefore the
  exact working `geo.region` value; do not substitute `CA`.
- `GET /works?filter=institutions.id:I97018004&per_page=1&cursor=*` returned
  HTTP 200 and `meta.count=534049`. The first work directly included Stanford
  (`I97018004`) in an authorship institution.
- The longer alias `authorships.institutions.id:I97018004` returned the same
  count. Use the documented canonical `institutions.id` spelling in new code.
- List responses contain `meta` (`count`, paging fields, `cost_usd`), `results`,
  and `group_by`. A cursor request also returned a non-null `next_cursor`.

Counts are observations, not invariants; OpenAlex updates continuously.

## Institution-ID batches and URL length

- OpenAlex permits at most 100 pipe-separated OR values in one filter. A live
  100-value institution batch returned HTTP 200; 101 values returned HTTP 400
  with an instruction to reduce the batch to 100 or fewer.
- The observed repeated-ID request URLs were 1,064 bytes for 100 values and
  1,074 bytes for 101. The value-count validation, not URL length, is the
  binding constraint for ordinary OpenAlex institution-ID batches.
- The API separately documents an 8,190-byte maximum GET URL for large search
  expressions. Keep every encoded URL below that limit. OQL POST is the
  documented no-URL-limit alternative for large Boolean searches, but the
  classic institution filter still has the 100-value OR cap.

## Cost and pagination

- Each successful list/filter request used 1 credit and reported
  `meta.cost_usd=0.0001` plus `X-RateLimit-Credits-Used: 1`.
- The rejected 101-value request reported 0 credits and no response cost.
- The accepted smoke run made six requests: five billable successes and one
  rejected validation request, totaling 5 credits and USD 0.0005.
- The institution smoke used basic `page`/`per_page` paging and observed
  disjoint pages 1 and 2. OpenAlex supports `per_page` through 100 and basic
  paging only through 10,000 results.
- Large works retrieval must use cursor paging: start with `cursor=*`, then
  follow `meta.next_cursor` until it is null. Following the cursor after the
  first page requires an API key; use the `OPENALEX_API_KEY` environment
  variable or an Authorization header, never a committed query-string key.

The logger at `src/atlas/util/cost.py` records one redacted JSONL request row
and one run summary in `data/logs/api_usage.jsonl`. Query-string credentials
are redacted, and arbitrary response bodies and headers are not stored.

## Rate, license, and documentation evidence

- OpenAlex documents a free anonymous daily budget and a larger free-key daily
  budget; pricing and limits can change, so callers must trust response cost
  metadata and headers rather than hard-code the budget.
- OpenAlex describes its metadata as CC0. A work location's own license is a
  separate field and still controls reuse of linked full text.

Official documentation checked 2026-11-05:

- <https://help.openalex.org/data/institutions/>
- <https://help.openalex.org/api/filtering/>
- <https://help.openalex.org/api/paging/>
- <https://help.openalex.org/api/authentication/>
- <https://help.openalex.org/access/example-costs/>
- <https://help.openalex.org/api/searching/#large-boolean-queries>
- <https://help.openalex.org/api/>

Acceptance rerun: `python scripts/smoke/openalex.py` completed successfully on
2026-11-05; output and usage logs are generated in ignored local paths.
