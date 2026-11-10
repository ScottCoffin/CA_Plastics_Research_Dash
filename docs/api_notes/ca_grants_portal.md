# California Grants Portal (open funding calls, S8.9)

## Source
- Dataset page: https://data.ca.gov/dataset/california-grants-portal (CKAN name `california-grants-portal`; publisher California State Library).
- Official CSV (resource "California Grants Portal - Updated Daily"): https://publish.data.ca.gov/dataset/e1b1c799-cdd4-4219-af6d-93b79747fffb/resource/111c8c88-21f6-453c-ae2c-b4785a0624f5/download/california-grants-portal-data.csv
- Licence: `other-pd`, "Other (Public Domain)" (CKAN `license_title`). Update periodicity `R/P1D`.
- The dataset lists grants and loans *offered* (calls). It is not an awards source.
- Discovered via the CKAN API `package_show?id=california-grants-portal` on 2026-11-09. The CSV was fetched once that day (6,614,728 bytes, CKAN resource `last_modified` 2026-11-09T08:01:18Z).

## Columns used
`PortalID`, `Status`, `AgencyDept`, `Title`, `Purpose`, `Description`, `Categories`, `ApplicationDeadline`, `GrantURL`, `EstAvailFunds`. The CSV also carries `GrantID` (portal-specific, sometimes blank) and `AgencyURL`, which are not used.

## Vocabulary observed (2,028 rows, 2026-11-09)
- `Status`: `closed` 1,873; `active` 153; `forecasted` 2. Open = `active` or `forecasted`.
- `ApplicationDeadline`: `YYYY-MM-DD HH:MM:SS` (1,901), `Ongoing` (125), blank (2). Blank deadlines are excluded.
- `Categories`: `;`-separated labels such as "Environment & Water".
- Encoding: a few values are not valid UTF-8 (cp1252 bytes such as the em dash). The loader tries UTF-8 and falls back to cp1252.

## Selection rules (`atlas.ingest.grants.open_calls`)
1. Open: status in {active, forecasted}, and deadline is `Ongoing` or on/after today (California standard time, UTC-8).
2. Plastic-related: `atlas.nlp.labels.classify_plastic_text` over Title, Purpose, Description and Categories with `config/queries.yml`. Any `exclude:` hit overrides everything.
3. Otherwise, a keyword match on the funding-language list: marine debris, litter, trash, plastic pollution, microplastic, packaging, recycl.

## Snapshot (2026-11-09 fetch, deadlines compared to 2026-11-09 Pacific)
- 153 open rows of 2,028. 9 passed the plastic filter at generation.
- All 9 were matched by the keyword `recycl` alone (water recycling, recycling loans, and the like). None matched the classifier.

## Precision caveats
- `recycl` and `packaging` are broad. In this snapshot the `recycl` hits are mostly not plastic-specific. The owner should decide whether to drop `recycl` or require a plastic term alongside it. Until then the panel is a keyword-level filter, not a validated plastic-relevance judgement.
- `litter`, `trash` and `packaging` can also match non-plastic solid-waste or packaging-law programmes.
- Only title and listing text are searched. Eligibility, scope and actual plastic focus must be checked on the portal page linked from each call.
- A call is an opportunity, not an award.

## Refresh
- `py -3.14 scripts/build_open_calls.py` (live fetch) or `--csv PATH` (local copy). Output: `site/data/open_calls.json`.
- A failed fetch or unusable CSV is `deferred`, exits 0, and leaves the existing JSON untouched. The CI step `Refresh open funding calls` runs with `continue-on-error: true`.
- The licence is public domain; no attribution is legally required, but the source is shown in the panel.

## Precision decision (lead, 2026-11-10)

The first live build matched 9 calls, all through the bare keyword `recycl`
(water recycling, recycling loans), and none were plastic-related. Bare
`recycl` and `packaging` were dropped and replaced by `plastic recycl`,
`plastic waste`, `single-use` and `packaging waste`. The rebuilt live payload
has **0 open plastic-related calls** of 153 open calls (2,028 rows); the panel
shows its empty state until a qualifying call appears. The daily deploy step
refreshes it.
