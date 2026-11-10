# State funder sources (S8.6)

Module: `src/atlas/ingest/grants/state_funders.py`. CLI: `scripts/ingest_state_funders.py`.
Output: `data/interim/grants/state_funders.parquet` (git-ignored). Status:
`data/interim/grants/state_funders_status.json` (git-ignored). Raw cache:
`data/raw/state_funders/` (git-ignored; no PDFs or spreadsheets are committed).
Curated rows: `curation/grants_manual.csv`.

Rules: polite fetching. robots.txt is checked per host; requests are at least 2 s apart;
`User-Agent: ca-plastics-atlas/0.1 (research dashboard)`; default cap 60 requests per run.
Any HTTP, robots, or budget error defers the whole run and leaves the output untouched.

## Access log (live, 2026-11-09)

| Host | robots.txt | Result |
|---|---|---|
| opc.ca.gov | `User-agent: *` with empty `Disallow:` (all allowed); sitemap listed | 200 |
| www.deltacouncil.ca.gov | disallows `/ssi/`, `/css/`, `/js/`, `/modules/`, `/source/`, `/templates/` and some test pages | 200 (landing page only) |
| sciencetracker.deltacouncil.ca.gov | Drupal rules disallow `/core/`, `/profiles/`, `/admin/`, `/search/`, `/user/*`, `/node/add/`; `/activities` and `/excel-export` are not disallowed | 200 |
| scc.ca.gov | disallows `/wp-admin/` only | 200 |
| csucoast.org | not fetched; DNS lookup failed (`getaddrinfo`) for both apex and `www.` | unreachable |

## OPC (`opc_council`)

- Council summaries live at `https://opc.ca.gov/YYYY/MM/<month-day-year>-council-meeting-summary/`.
  Monthly archives `https://opc.ca.gov/YYYY/MM/` link to them. The run scans
  2025-01 through 2026-11.
- Approvals appear as `Title : Up to $N ...`. The parser keeps items whose title and text
  match the S2.3 plastic rule. A title is the run of Title-Case words before the colon.
  Items whose title does not read that way are counted as `unparsed`, not guessed.
- Verified item (June 16 2026 summary, `https://opc.ca.gov/2026/06/june-16-2026-council-meeting-summary/`):
  "Pilot Statewide Plastics Monitoring Program : Up to $2,500,000 was approved to develop
  and implement a pilot statewide microplastics monitoring program". The recipient is not
  named, so `org` is null and `funder_chain` is `["California Ocean Protection Council"]`.
  The amount is an "up to" cap.
- Same page, not plastic: "California Sea Grant : Up to $401,622 to support administration
  of previously approved Track 1 and Track 2 projects". It is excluded by the plastic rule.
- Not verified: the 2023 annual report plastic-approvals total ($4,002,797) and the five
  microplastics projects administered by Sea Grant. Neither was found in the fetched
  pages, so neither is in the curation file. The Council staff recommendation PDFs were not
  parsed.

## Delta Science Tracker (`delta_science_tracker`)

- Export: `https://sciencetracker.deltacouncil.ca.gov/excel-export?/activities`
  (`application/vnd.ms-excel`, but the bytes are an OOXML zip; read with openpyxl).
- Sheets used: `Science Activities` (text filter: Title, Description, Science topics,
  Science themes, Notes) and `Funding Awards` (joined on `Science Activity ID`).
  Award fields: `AwardID`, `Funding organization`, `Funding program`,
  `Total award amount ($)`, `Date awarded`. Export size: 389 activities, 272 funding
  awards, 5 activities match the plastic rule on the live export.
- Amounts are the export's `Total award amount ($)`. Per the S8.1 caveat, the basis
  (total vs. annual) is unverified.

## CSU COAST (`csu_coast`): gap

`csucoast.org` did not resolve from this machine on 2026-11-09. No awardee list was
retrieved, and no parser was written. The status file records the gap. Retry later.

## SCC (`scc_board`): gap

`https://scc.ca.gov/public-meetings/` lists agendas and staff reports as PDFs. No
item-level HTML parser was built, so no rows are emitted. The gap reason records how often
the listing mentions plastic and COAST.

## Curation

`curation/grants_manual.csv` has the C3 columns plus `curation_note` and
`evidence_url`. Derived columns are blank and computed on ingest. A curated row replaces a
scraped row with the same `grant_key` (`merge_curated`).

## Dedupe

See `docs/grants_overlap_report.md` (generated) and `src/atlas/ingest/grants/dedupe.py`.
Row-level map: `data/interim/grants/grants_dedupe_map.csv` (git-ignored).

## Live run (2026-11-09)

- 29 network requests (robots files, 23 OPC monthly archives, 1 Delta export, the SCC
  listing, and the COAST robots attempt). Default cap is 60.
- OPC: 7 summary pages, 74 `Title : Up to $` items, 1 plastic-related item kept
  (the June 16 2026 pilot). 7 titles were unparsed and skipped.
- Delta: 389 activities, 5 plastic-related activities (IDs 50098, 50119, 50167, 50169,
  50189). None of the 5 has a row in `Funding Awards`, so the export gives no fund
  source or amount for them. Zero Delta award rows is a source fact, not a parser error.
- COAST: DNS failure. SCC: gap, no item-level parser.
