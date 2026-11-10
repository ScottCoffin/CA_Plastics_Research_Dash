# Funding data export and Funding tab (S8.10)

`scripts/build_grants_export.py` writes `site/data/grants.json`, the slim payload
behind the Awards section of the Funding tab in `site/index.html`. The export is
built from the S8.6 de-duplicated grants table, so each award appears once on its
lowest-level record. The browser loads the file only when the Funding tab opens.

## Inputs and rebuild

| Input | Role |
|---|---|
| `data/interim/grants/grants_merged.parquet` | One row per deduplicated grant (C3 columns). Read with pyarrow. |
| `data/interim/grants/grants_dedupe_map.csv` | Checked, when present, so every exported `grant_key` is a cluster representative. |
| `data/processed/institutions.parquet` | Joined for `institution_type` (see below). |

```powershell
py -3.14 scripts/build_grants_export.py
py -3.14 scripts/check_s8_10.py
```

The build prints counts only. Abstracts and contact fields are never copied: the
row mapping in `src/atlas/build/grants_export.py` copies a fixed set of keys
(`ROW_KEYS`), and the tests and the check script reject any key containing
`abstract` or `email`.

## Payload

`schema_version` is `s8.10`. Top-level keys: `generated_at`, `caveat`, `counts`
(`input_rows`, `exported_rows`, `undated_rows`), `sources` (per source: `rows`,
`amount_rows`, `funder_type`, `amount_basis`), `columns`, `rows`, and `aggregates`.

Each row has these keys: `grant_key`, `source`, `title`, `pi_names` (first three),
`org`, `org_state`, `institution_type`, `start`, `end`, `fiscal_year`, `amount`,
`currency`, `amount_basis`, `funder`, `funder_type`, `program`, `funder_chain`,
`url`, `plastic_related`, `domain_tags`, `ca_led`. Unknown values are `null` or
`[]`; they are never coerced to `false`.

Rows are sorted by `(start, grant_key)`, with undated rows last. The JSON is compact,
sorted, and ASCII, so the same input and `generated_at` give identical bytes.

`aggregates.by_year_funder_type` counts and sums amounts per fiscal year and funder
type, for dated rows only. `aggregates.by_institution_type` does the same per
recipient institution type, for all rows.

## Derived fields

- **`funder_type`** is set by source. `nih_reporter`, `nsf_awards`, and
  `usaspending` are `federal`. `ca_sea_grant`, `opc_council`,
  `delta_science_tracker`, `scc_board`, and `state_funders` are `state`. California
  Sea Grant is NOAA-funded but state-hosted, and the brief classes it as state.
  Any other source is `other`, including `csu_coast`, which has no rows yet.
- **`fiscal_year`** comes from `start`. Federal sources and Sea Grant use the October
  to September year, named by its ending year. State sources use the July to June
  year. Other sources use the calendar year. A row without `start` has no fiscal year.
- **`institution_type`** comes from `atlas_type` in the institutions table. The join
  tries the ROR ID first, then the exact normalized organization name (casefolded,
  accents and punctuation removed). A name that maps to more than one institution
  type gives `unknown`, and so does a missing organization. In the current merged
  table no row carries an `org_ror`, so the name join does all the work.
- **`plastic_related`** and **`domain_tags`** are the provisional S2.3 rule labels
  carried through from the grants table. They are not reviewed classifications.

## Amount basis by source

`amount` is never summed as if the bases were the same. Each row carries its
source's `amount_basis`, and the `sources` block repeats it.

| Source | Basis as recorded in the export |
|---|---|
| `nih_reporter` | `award_amount`, reported as the fiscal-year total cost. Not verified as life-of-award. |
| `nsf_awards` | `estimatedTotalAmt`, the anticipated total award value. Not `fundsObligatedAmt`. Life-of-award or current-year basis not verified. |
| `usaspending` | `Award Amount`, the obligated total as the award record reports it. It may cover obligations to date. |
| `ca_sea_grant` | Amount as announced. Most records report no amount, so `amount` is `null`. |
| `opc_council` | Amount as approved by the Ocean Protection Council (staff summary). |
| `delta_science_tracker`, `scc_board`, `state_funders` | Amount as reported by the funder export. Some are "up to" caps. |

The NIH and NSF bases are the brief's working assumptions. The source notes in
`docs/api_notes/` still mark them unverified, and the UI shows that caveat.

## Current snapshot

From the merged table on the build date: 514 rows. `nsf_awards` 309, `nih_reporter`
126, `usaspending` 64, `ca_sea_grant` 14, `opc_council` 1. Seven rows have no start
date. The export is about 417 KB raw and about 64 KB gzip, well inside the
1 MB slim budget and the 3 MB C5 initial-payload budget.

## Funding tab

- **Filters**: funder type, funder, program, fiscal year range, amount range (USD),
  recipient institution type, topic tag, led from California (`ca_led`), and a
  "provisional plastic relevance only" toggle. The toggle is on by default and
  hides rows whose `plastic_related` is `false`. Unknown rows stay in.
- **State in the URL hash**: `#funding?ft=federal&yf=2020&pl=0`. The keys are `ft`,
  `fn`, `pg`, `yf`, `yt`, `amin`, `amax`, `it`, `tg`, `ca`, and `pl`.
- **Table**: 50 rows per page, so at most 50 DOM rows. Titles link to the source
  `url`. The funder chain reads as `funder_chain` followed by the recipient
  organization, joined with arrows. Amounts show the basis in a tooltip.
- **Charts**: inline SVG. Counts by fiscal year stacked by funder type, and counts
  by recipient institution type. Both follow the filters.
- **CSV**: "Download filtered CSV" exports the filtered rows with the columns in
  `ROW_KEYS`. List fields are joined with `|`, and the funder chain with `>`.
- **Open calls**: the S8.9 "Open funding calls" section stays below the awards
  section and keeps its own loader.

## Limits

- Amounts are as reported by each source. They are not normalized to a common
  basis, not inflation-adjusted, and not additive across sources or fiscal years.
  The status line sums amounts for the filtered rows, and it says the bases differ.
- Awards are records of funding, not evidence that the funded work was completed
  or is current.
- Pass-through de-duplication is the S8.6 pass. A cluster that the rules do not
  join stays as two rows.
- Charts count awards and do not weight them by amount.
- Institution types are sparse. The exact-name join matches 40 of 514 rows in the
  current snapshot, so 474 rows show `unknown`. Fuzzy or ROR-based matching is
  not implemented; it needs an owner decision.
