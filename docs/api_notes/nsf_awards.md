# NSF Award Search API notes (S8.3)

Source: `GET https://api.nsf.gov/services/v1/awards.json`. Keyless and free.
Send `User-Agent: ca-plastics-atlas/0.1 (research dashboard)`. The ingester
contacts no other host. The NSF API reference (research.gov `awardapisearch-v1`)
was not fetched: that host is outside the S8.3 network allowance. All facts below
come from live probes on 2026-11-09.

## Verified facts (live, 2026-11-09)

- **Keyword syntax.** `keyword` takes quoted phrases and bare words. Uppercase `OR`
  joins terms. Lowercase `or` is not an operator: `microplastic or nanoplastic`
  returned `totalCount: 10000`.
- **One quoted phrase per query.** Two quoted phrases joined by `OR` return HTTP 200
  with `totalCount: 0`, with no error. Observed for `"microplastic" OR "nanoplastic"`
  and `"plastic pollution" OR "plastic debris"` (and with a third term). One quoted
  phrase plus bare words works: `"plastic pollution" OR microplastic` returned 185.
- **Unquoted multi-word text is not a phrase.** `plastic pollution` (unquoted)
  returned `totalCount: 10000`. Quoted `"plastic pollution"` returned 101.
- **Bare single words** behave like quoted single words. `microplastic` and
  `"microplastic"` both returned 113. `"nanoplastic"` returned 18.
- **State filters.** `awardeeStateCode=CA` returned only CA awardees (3 of 3 checked).
  `perfStateCode=CA` returned only CA performance locations (7 of 7 checked).
  Other two-letter codes are accepted. Filters are AND-combined with the keyword,
  so the awardee and performance sweeps are separate queries.
- **Dates.** `dateStart` and `dateEnd` take `mm/dd/yyyy`. The window filters on the
  `date` field (award or latest amendment date), not on `startDate` or `expDate`.
  Check: for the FY2024 window (10/01/2023 to 09/30/2024), 3 of 19 hits had a
  `startDate` after 09/30/2024. A grant can therefore appear in the window of its
  latest amendment rather than its start year. Backfill still covers every award
  whose `date` falls in the last 15 fiscal years.
- **Malformed date.** `dateStart=2024-01-01` was not rejected. It returned 47
  results with no error. Always send `mm/dd/yyyy`.
- **Paging.** `rpp` 1000 and 3000 were accepted, and `meta` echoed the value. The
  ingester uses 1000. `offset` is a record offset. An offset beyond the total
  (`offset=5000`, total 113) returns HTTP 200 with no `award` key and no error.
  No offset ceiling was reached. Maximum `rpp` was not found (3000 is the largest
  tested).
- **Response shape.** Success: `{"response": {"award": [...], "metadata":
  {"offset", "rpp", "totalCount"}}}`. A zero-result query omits `award`. Each award
  has about 62 keys.
- **`printFields`** is accepted, but the response still returned all 62 keys with
  `printFields` set. The ingester sends it anyway and does not rely on it.
- **Error shapes.**
  - Invalid parameter: HTTP 200 with `{"response": {"serviceNotification":
    [{"notificationCode": "AwardAPI-002", "notificationType": "ERROR",
    "notificationMessage": "Invalid parameter(s) sent in the request. ..."}]}}`.
    The ingester treats this as a deferred error, not as zero results.
  - Malformed request (for example, an unencoded `"`): HTTP 400 with a Tomcat HTML
    page. The ingester treats this as a deferred HTTP error.
- **Fields used:** `id`, `title`, `abstractText`, `piFirstName`, `piLastName`,
  `pdPIName`, `awardeeName`, `awardeeStateCode`, `perfStateCode`, `startDate`,
  `expDate` (both `mm/dd/yyyy`), `estimatedTotalAmt` (string, whole USD),
  `fundsObligatedAmt`, `agency`, `fundProgramName`, `date`.

## Amount mapping

`amount` maps to `estimatedTotalAmt`, the anticipated total award value. It is
not `fundsObligatedAmt`, which is cumulative obligations to date. The fiscal-year
and obligation caveat in `docs/GRANTS_SCHEMA.md` applies. Whether
`estimatedTotalAmt` is the life-of-award total or a current figure is not verified.
Both are kept in the fixture, so the owner can check.

## Term set and request cost

Phrases come from `core_terms` in `config/queries.yml`, through the S8.2
`search_phrases` helper. Keyword queries:

- one bare OR-group of the single-word phrases (`microplastic`, `microplastics`,
  `nanoplastic`, `nanoplastics`);
- one quoted query per multi-word or hyphenated phrase (23 queries).

That is 24 keyword queries per unit. Each fiscal year has two sweeps:

- `ca`: each keyword query twice (awardee CA, then performance CA), so 48 per year;
- `terms`: each keyword query once, nationwide, so 24 per year.

Every unit is 24 to 48 first-page requests, plus pages. Incremental (2 years) is
144 requests. Backfill (15 years) is roughly 1,080 requests. This exceeds the S8.3
task budget of 60 requests by a wide margin. Owner decision needed: shrink the term
set, or authorise the request budget, before a full backfill.

## Live runs (2026-11-09)

Requests used by S8.3 in total: 60 of 60. That is 26 probes, 15 incremental, and
19 backfill.

- `--incremental --max-requests 15`: status `partial`, 15 requests, 0 units
  completed, 0 rows written. The first unit (2027:ca) needs 48 requests.
- `--backfill --max-requests 19`: status `partial`, 19 requests, 0 units
  completed, 0 rows written.

No `nsf_awards.parquet` was written. The state file was not written either.
Output and state are left to the next run with a larger budget.

## Not verified

- Whether `estimatedTotalAmt` is a life-of-award total or a current figure.
- Whether `printFields` is honoured by the live API under any parameter form.
- The maximum `rpp` value (3000 was accepted; higher values not tested).
- Whether NSF caps `totalCount` at 10000. Broad queries return exactly 10000,
  so the ingester treats any count of at least 10000 as a ceiling and defers.
- Whether unquoted OR-groups of several single words are stable when combined with
  a quoted phrase. Only one bare word plus one quoted phrase was tested.

## Lead live runs (2026-11-10)

The 60-request cap in the worker brief was a self-imposed budget, not a cost
limit (the API is free and keyless), so the lead ran the full workload at ≥1.1 s
spacing:
- `--incremental --max-requests 160`: 144 requests, 4/4 units, 25 grants (FY2026–2027), status ok.
- `--backfill --max-requests 1200`: 936 requests, 26/26 units, 316 grants (FY2013–2027), status ok, 0 skipped.

Cost driver: one quoted phrase per query (multi-phrase OR returns 0), so 24
terms × 2 sweeps × fiscal-year units. An incremental run is about 144 requests
(about 3 minutes).
