# USAspending API notes (S8.4)

Source: `POST https://api.usaspending.gov/api/v2/search/spending_by_award/` (search)
and `POST https://api.usaspending.gov/api/v2/search/spending_by_award_count/`
(count, used only for probing). Keyless and free. Send
`User-Agent: ca-plastics-atlas/0.1 (research dashboard)`. The live ingester contacts
only `api.usaspending.gov`. The bulk path (`--bulk`) also downloads from
`files.usaspending.gov` and has not been run live.

## Verified facts (live, 2026-11-09)

- Request filters used: `keywords` (list), `time_period` (list of
  `{start_date, end_date}`), `award_type_codes` (required), and
  `recipient_locations` or `place_of_performance_locations` (list of
  `{country: "USA", state: "CA"}`). Body: `fields`, `page`, `limit`, `sort`, `order`.
- `limit` above 100 is rejected: HTTP 422, `Field 'limit' value '500' is above max
  '100'`. The ingester uses 100.
- Response: `results`, `page_metadata` (`page`, `hasNext`, `last_record_unique_id`,
  `last_record_sort_value`), `messages`, `limit`, `spending_level`.
- Result keys: `internal_id` (numeric), `generated_internal_id` (string such as
  `ASST_NON_<award>_<agency suffix>`), `Award ID`, `Recipient Name`, `Start Date`,
  `End Date` (`YYYY-MM-DD`), `Award Amount` (number), `Awarding Agency`,
  `Awarding Sub Agency`, `Description`, `Recipient State Code`,
  `Place of Performance State Code`, `awarding_agency_id`, `agency_slug`.
  There is no award title field, so the ingester derives the title from the
  description.
- `sort: "Award ID"` with `order: "asc"` is accepted and gives stable pages.
- Page 101 at limit 100 (offset 10,000) returned HTTP 200 with an empty `results`
  and `hasNext: false`. No error is raised, so the ceiling is silent. The ingester
  enforces its own cap of 100 pages and defers a unit that still reports
  `hasNext` at that point. Whether a non-empty query above 10,000 rows errors
  differently was not tested.
- Earliest accepted `time_period` start is 2007-10-01 (response `messages`). The
  backfill window (FY2013 onward) is inside it.
- Count endpoint: for the grant codes, every hit landed in the `grants` category,
  with `contracts`, `loans`, and `direct_payments` at 0. The codes `02`-`05` are
  therefore grant codes. Each code was not tested on its own.
- Keywords are OR-joined across the list. Single keyword `microplastic` gave 12 hits
  (FY2025, CA recipients). `nanoplastic` gave 2. Both together gave 13, which is
  a union, not an intersection.
- Plurals are covered by the singular. `microplastics` gave 12, the same as
  `microplastic`.
- A multi-word keyword is far more restrictive. `microplastic pollution` gave 2,
  `plastic pollution` gave 1, and `marine debris` gave 8. Whether the server applies
  a phrase match or requires every token was not separated.
- Matching is substring-like on long description text, not word-based. `plastic`
  gave 156 hits and `polymer` gave 131. The page-1 descriptions contain these
  strings inside longer words, such as `PLASTICITY` and `POLYMERIZATION`.
- `generated_internal_id` was unique across all sampled rows, and the sampled
  `Award ID` values were also unique. Duplicates across the full data were not
  checked. The ingester keys on `generated_internal_id` because it is the
  record-level identifier, it is the value in the award URL, and the `_<suffix>`
  distinguishes records that share an award number. `Award ID` alone was not used
  because it is an agency award number and may repeat across awarding
  sub-agencies. That repetition was not observed live.

## Keyword noise (FY2025, CA recipients, page 1 read by eye)

Counts are FY2025, recipient state CA, award codes 02-05.

- `plastic` (156 hits): the ingester does not use it. In the first 10 titles, 3 are
  `PLASTICITY` awards (phenotypic plasticity, colony behaviour, and similar), and
  every description contains the substring. Excluded as too noisy.
- `polymer` (131 hits): the ingester does not use it. At least 2 of the first 10
  titles are unrelated to plastics (a beekeeping loss report and a crime-laboratory
  award). Many others are polymer chemistry or nanocomposites. Excluded.
- `microplastic` (12 hits): the ingester keeps it. Every hit contains the term in
  the description. Reading 60-character windows around the term, about 5 of 12 are
  passing mentions in contaminant lists or water-quality boilerplate (for example
  "PHARMACEUTICALS, PESTICIDES, AND MICROPLASTICS" or "CAPTURE OF MICROPLASTICS").
  The rest are topical (for example "MICROPLASTIC POLLUTION", "DETECTING OCEAN
  MICROPLASTICS"). The fraction is by eye on a small sample.

Context words that appear in topical hits and are useful for downstream review:
POLLUTION, OCEAN, MARINE, SAMPLE, QUANTIFYING, DETECTING. Context cannot be
applied server-side, because keywords are OR-joined. The downstream rule is
`plastic_related` (provisional S2.3 rule in `normalize_grant`), which reads title
and abstract. Rows that pass the keyword but not that rule keep `plastic_related`
false or null, and they are not dropped.

## Term set

`USASPENDING_TERMS` in `src/atlas/ingest/grants/usaspending.py`:
`microplastic`, `nanoplastic`, `plastic pollution`, `marine debris`,
`tire wear particle`.

- Excluded: `plastic` and `polymer` (substring noise, above). Plurals are not
  listed separately, because the singular already matches them.
- `tire wear particle` is kept from the brief but was not measured on its own.
  Its share of the live counts is unknown.
- Qualified terms such as `microfiber` and `plastic waste` were not measured and
  are not used. They need context that the server cannot apply.

## Sweeps and fiscal years

- Fiscal years run 1 October to 30 September and take the ending year's name. Each
  FY is one window in `time_period`.
- Two sweeps per FY: `ca_recipient` (`recipient_locations`) and `ca_pop`
  (`place_of_performance_locations`). Results are merged by `grant_key`, derived
  from `generated_internal_id`. An award found by both sweeps is stored once.
- The `agencies` filter is not used. Every row carries its own
  `Awarding Agency`, so the CA sweeps are the scope, and an agency filter would
  not remove the water-quality noise described above.

## Paging and budget

- Pages are read in order, following `page_metadata.hasNext`. The cap is 100 pages
  (10,000 rows). Reaching the cap defers the unit, and nothing is written.
- Every request and retry counts toward `--max-requests`. A 429 or 5xx retries up
  to three times with backoff. Other 4xx responses fail at once. Requests are spaced
  at least 1.1 s apart.
- Reaching the cap yields status `partial`, with completed units applied and
  recorded. Backfill resumes from `completed` in the state file.

## Mapping to C3

- `source` = `usaspending`. `source_award_id` = `generated_internal_id`.
- `title` = the first 200 characters of `Description` with whitespace collapsed,
  or `Award <Award ID>` when the description is blank. This is an excerpt, not an
  official award title.
- `abstract` = `Description`. `pi_names` = `[]` (not reported).
- `org` = `Recipient Name`. `org_state` = `Recipient State Code`. `ca_led` follows
  from it.
- `start` and `end` = `Start Date` and `End Date`. `amount` = `Award Amount`, with
  `currency` = `USD`. The amount's meaning (total obligation, or the current
  transaction) is not verified.
- `funder` = `Awarding Agency`. `program` = `Awarding Sub Agency`.
  `funder_chain` = `[agency, sub agency]`.
- `url` = `https://www.usaspending.gov/award/<generated_internal_id>`.

## Bulk path (`--bulk`, backfill only): not run live

- `POST /api/v2/bulk_download/awards/` with `filters.prime_award_types` = the
  grant codes, `date_type` = `action_date`, `date_range`, and `file_format` = `csv`.
  The response must carry an HTTPS `file_url` on an allowed host. The archive is
  read in memory with `zipfile` and never extracted.
- The bulk path cannot apply keywords, so it keeps CA recipients whose description
  contains a term by a local substring test. It does not read place of
  performance.
- The CSV column names in `BULK_COLUMNS` are UNVERIFIED. They were not checked against
  a real archive. Tests use a fake archive built from those names.
- Each FY costs two budget units: one submit and one download.

## Costs and live runs (2026-11-09)

Requests used by S8.4: 14 probes (1 smoke search; 3 counts for microplastic,
nanoplastic, and both; 4 counts for plastic, polymer, and two phrases; 2 searches
for plastic and polymer; 2 for the limit and page-101 checks; 2 counts for the
plural and phrase tests), 4 for `--incremental`, and 26 for `--backfill`. Total 44
of the 60 authorised. Every unit fit on one page.

- `--incremental --max-requests 15`: status `ok`, 4 requests, 4 units, 0 invalid
  rows skipped, 12 rows written.
- `--backfill --max-requests 42`: status `ok`, 26 requests, 26 units planned and
  completed (the 4 incremental units were already complete), 0 invalid rows
  skipped, 66 rows written in total. The output is
  `data/interim/grants/usaspending.parquet`.

Only counts are recorded here. The records themselves are not committed.

## Not verified

- Whether the `grants` categories for codes `02`-`05` match the statutory grant
  types one for one. Only the aggregate `grants` count was checked.
- Whether the keyword match is a phrase match or requires every token.
- Whether `Award ID` repeats across awards in the full dataset.
- The meaning of `Award Amount`.
- The bulk CSV column names, and whether a real bulk archive loads at all.
- Whether a non-empty query above 10,000 rows errors or truncates.
