# Data Source Registry

Source status, refresh cadence, access tier, license, and last successful refresh
are recorded here. Detailed observed contracts are in `docs/api_notes/`.

| Source | Status | Access / cadence | License | Last verified |
|---|---|---|---|---|
| Natural Earth 1:10m Admin 1 v5.1.1 | Active for California land polygon | Public static archive; refresh when upstream version changes | Public domain | 2026-11-05 |
| CDFW ds3158 three-nautical-mile limit | Active; use `ds3158_poly` from official archive | Public static archive; upstream cadence irregular | CC BY 4.0 | 2026-11-05 |
| GeoNames U.S. extract, California subset | Active; 127,963-feature SQLite subset filters `US.zip` to `country_code=US`, `admin1_code=CA` | Public static ZIP; upstream updated daily | CC BY 4.0; credit GeoNames | 2026-11-05 |

## Monitoring-source seeds (S7.1)

The per-source evidence and caveats live in `config/datasets.yml` and
`docs/S7_1_VERIFICATION.md`. Eligibility requires a distinct underlying study
or program identity and factual evidence of observations or an active
monitoring program. A successful HTTP response alone does not establish
observation coverage or reuse rights. Unknown rights remain explicit pending
S7.2 review.

| Source | Entity / evidence status | Access tier | Access, cadence, and license notes | Last verified |
|---|---|---:|---|---|
| NOAA NCEI Marine Microplastics | Global archive; underlying identity includes its accession children | A | CSV/JSON/GeoJSON portal; source-record license and attribution vary | 2026-11-07 |
| SF Bay / 5 Gyres | California Open Data particle records linked to samples; independent SFEI/5 Gyres project | A | XLSX/PDF; CC BY metadata; irregular updates; recheck resource terms | 2026-11-07 |
| California SB 1422 drinking-water monitoring | State Water Board describes statutory reporting program; public observation export unconfirmed | C | Source/treated water; observation license unknown | 2026-11-07 |
| NOAA MDMAP | NOAA documents monthly California partner surveys at four Greater Farallones beaches, 2012-2018 | A | Shoreline macrodebris; record-level rights need review | 2026-11-07 |
| Southern California Bight plastics | SCCWRP regional program and data portal | B | Approximately five-year cycles; plastics files and rights need review | 2026-11-07 |
| Bight '13 benthic plastic type data | SCCWRP identifies historical sediment-grab plastic data | B | Dataset-specific download and license unknown | 2026-11-07 |
| Monterey Bay watershed-to-whales | California Sea Grant reports almost 25,000 field-identified particles | B | River, beach, coastal-water, wildlife samples; row-level data/license unknown | 2026-11-07 |
| NHMLA Plastics Past and Present | California Sea Grant reports 353 processed fish specimens | B | Retrospective samples; sample-level data/license unknown | 2026-11-07 |
| Los Angeles / San Gabriel Rivers study | SCCWRP report documents measured river, sediment, fish microplastics | D | Secondary report evidence; data/license unknown | 2026-11-07 |
| SoCal biofilter field dataset | SCCWRP-linked study reports paired samples at seven Southern California sites | A | View/download reported; format and license need review | 2026-11-07 |
| Bay Area dryer microfiber study | California Sea Grant reports sampling at 19 homes and one shared laundry | B | Source-pathway measurements; raw data/license unknown | 2026-11-07 |
| Los Angeles stormwater BMP retention study | California Sea Grant reports soil sampling at 18 stormwater systems | B | Project results public; row-level data/license unknown | 2026-11-07 |
| CCE LTER SEAPLEX particle measurements | Catalog describes North Pacific Gyre and California Current with a reference station off San Diego; coordinate-level California coverage remains unverified | B | 560-row manta-net dataset; guest-form terms limit scholarly use, require owner contact before publication, and prohibit redistribution without permission; no download/form acceptance | 2026-11-07 |
| California coastal wastewater treatment study | SCCWRP report describes measurements at selected coastal plants | D | Secondary report evidence; row-level data/license unknown | 2026-11-07 |
| Bight '23 sediment and shellfish assessment | SCCWRP reports completed 2023-cycle measurements | D | Separate cycle from Bight '13; row-level data/license unknown | 2026-11-07 |

The NCEI San Francisco Bay accession, stormwater collection-method study, and
Clean Swell page remain as excluded discovery records. The accession shares
the global NCEI archive identity. RMP/CD3, CEDEN, Moore drinking-water, the
planned statewide pilot, SWAMP/SPoT, and California Coastal Cleanup Day are
also excluded. See the verification note for evidence and reasons. S7.2 will
check endpoint access and terms before any ingestion decision.
