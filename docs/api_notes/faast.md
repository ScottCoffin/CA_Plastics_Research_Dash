# SWRCB FAAST public search (S8.8)

Source name `swrcb_faast`. Adapter: `src/atlas/ingest/grants/faast.py`; run with
`py -3.14 scripts/ingest_faast.py` (live) or `--html-fixture-dir` (offline).
Output: `data/interim/grants/swrcb_faast.parquet`; status: `swrcb_faast_status.json`.

## Flow (ASP.NET postbacks, one cookie session, 1 s spacing, budget 120)

1. GET `https://faast.waterboards.ca.gov/` (robots.txt is checked first; a 404 means no rules).
2. POST the same URL with the hidden fields and `PublicTool=PUBLIC SEARCH TOOL`.
3. POST the form on `Public_Interface/PublicPropSearchMain.aspx` with `GotoSearch=Public Search Tool`.
4. POST `Public_Interface/PublicSearch.aspx` with hidden fields, select values,
   `ctl00$ContentPlaceHolder1$AccrodianPane2_content$DescriptionText=<keyword>`,
   `...AccordianPaneMain_content$StatusDDL=AWARDED` and the search button.
5. Follow GridView pager postbacks (`__doPostBack('...PublicProposalSearchGV','Page$N')`), capped at 20 pages.
6. GET `PublicProposalDetails.aspx?Pin=..&PropId=..` once per unique awarded PIN.

Keywords: microplastic, plastic, trash, litter, debris, tire wear, 6PPD, polystyrene.
A zero-hit keyword returns the grid with "No Records available for your Search Criteria."

## Fields

Grid columns: Pin #, Agreement No, Proposal Title, Applicant, County, WaterShed, RWQCB,
Req Funds, Status. Requested funds become `amount`; the program text carries the caveat
("amount = requested funds"). Detail labels read: "RFP/Survey Title:", "Submitting
Organization:", "Project Title:", "Project Description:". Detail pages have no explicit
start or end dates, so `start` and `end` are null. `org_state` is "CA" (fixed by the brief).
The abstract starts with "Agreement No. ...".

## Privacy rule (spec F4)

The detail page has a Contacts section with personal names, phones and emails. It is never
parsed, stored, logged or snapshotted. Only the four labelled fields above are read. Only
search-result grid HTML is cached, under `data/raw/faast/` (git-ignored). Tests and
`scripts/check_s8_8.py` assert that no contact token, email or phone reaches the output.

## Live run (2026-11-10)

- 14 requests: robots, home, main, 8 keyword searches, 2 detail fetches. No pager was needed.
- Per-keyword awarded hits: trash 2, debris 1, all other keywords 0.
- Unique awarded PINs: 2 (24090, 24184). Rejected: 0. Amount unparsed: 0.
- After dedupe and export, 2 swrcb_faast rows reach `site/data/grants.json`. Both are
  `plastic_related` false.

## Known limitation

`grants_export.py` has no `AMOUNT_BASIS` entry for `swrcb_faast`. The export therefore shows
the default caption, "As reported by the source. Amount basis not documented." The owner
should decide whether to add an entry for "Requested funds (not awarded)". That file is out
of scope for S8.8.
