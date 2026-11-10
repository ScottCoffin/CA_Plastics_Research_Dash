# S8.8 State Water Board research funding: investigation (2026-11-10)

Owner direction (2026-11-10, QUESTIONS G-6): ingest automatically if possible.
Finding: no machine-readable source lists State Water Resources Control Board
(SWRCB) research awards with titles or descriptions. Automatic ingestion is not
feasible today. All checks below were keyless public requests.

| Source checked | Result |
|---|---|
| data.ca.gov CKAN, organization `california-state-water-resources-control-board` | 57 datasets; none has funding, grant, loan, award, agreement or contract in its title |
| data.ca.gov keyword search ("financial assistance water board", "SWRCB grant agreements", "water board funded projects") | No SWRCB funding dataset; hits are water-quality and other agencies' data |
| Open FI$Cal expenditure downloads (`open.fiscal.ca.gov/download-expenditures.html`) | Bulk CSVs exist, but the page states they exclude data from May 2021 onward; transactions are vendor payments without project descriptions |
| USAspending subawards with `recipient_search_text` = State Water Resources Control Board, FY2015–FY2026 | 0 results |
| `waterboards.ca.gov/about_us/contracts/` | HTTP 404 |
| SWRCB microplastics program page | Program narrative and links to Financial Assistance pages; no award list |

What is already captured automatically:

- SWRCB co-funding that passes through OPC Council actions (for example the
  Dec 2022 "Microplastic Sample Collection Method Standardization", OPC $750,000 +
  State Water Board $250,000) is in the S8.6 OPC adapter's funder chain.
- SWRCB solicitations appear in the S8.9 California Grants Portal open-calls panel.
- Federal awards to California researchers are in S8.2–S8.4 regardless of state pass-through.

Proposed fallback (pending owner confirmation, QUESTIONS S8.8-A): record any
SWRCB-only research agreements the owner knows of in `curation/grants_manual.csv`
(already the S8.6 manual-curation path) and re-check these sources when S7.6-style
watch coverage is extended. S8.8's acceptance ("decision logged: ingest, curate
manually, or defer") is met when the owner confirms or replaces that fallback.

## Outcome (2026-11-10): FAAST Public Search Tool

The owner pointed to FAAST (https://faast.waterboards.ca.gov/), whose Public Search Tool
lists grant and loan applications with a keyword search of project descriptions and an
"Awarded Only" status filter. `atlas.ingest.grants.faast` (source `swrcb_faast`,
`scripts/ingest_faast.py`, notes in `docs/api_notes/faast.md`) replays the public
search postbacks with the standard library: 1 s spacing and no browser. It reads only
the grid and four labelled detail fields (RFP title, organization, project title,
project description). The detail page's Contacts section (names, phones, emails) is
never parsed or stored.

The first live run (14 requests) used the keywords microplastic, plastic, trash,
litter, debris, tire wear, 6PPD and polystyrene. It returned 2 awarded proposals:
24090 "Tracking California's Trash" (BASMAA, $870,000) and 24184 "Machado Lake Trash
TMDL" (City of Torrance, $1,968,850). "Trash" without the status filter returns 23
applications, most of them rejected. Both awarded rows are in `site/data/grants.json`,
with the amount captioned as requested funds. Neither matches the current
plastic-relevance rules (trash capture is not a plastic term there), so both are
`plastic_related = false`. S8.8's decision is logged: ingest automatically from
FAAST. Programs that do not use FAAST are not covered (FAAST states this itself).
