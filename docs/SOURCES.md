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
| NOAA NCEI Marine Microplastics | Global archive; underlying identity includes its accession children | B | CSV/JSON/GeoJSON portal; source-record license and attribution vary; no record-level field map verified | 2026-11-09 |
| SF Bay / 5 Gyres | California Open Data particle records linked to samples; independent SFEI/5 Gyres project | A | XLSX parsed; CC BY 4.0; irregular updates; manta sample and particle sheets map by SampleID | 2026-11-09 |
| California SB 1422 drinking-water monitoring | State Water Board describes statutory reporting program; public observation export unconfirmed | C | Source/treated water; observation license unknown | 2026-11-07 |
| NOAA MDMAP | NOAA documents monthly California partner surveys at four Greater Farallones beaches, 2012-2018 | B | Shoreline macrodebris; record-level rights and export fields need review | 2026-11-09 |
| Southern California Bight plastics | SCCWRP regional program and data portal | B | Approximately five-year cycles; plastics files and rights need review | 2026-11-07 |
| Bight '13 benthic plastic type data | SCCWRP identifies historical sediment-grab plastic data | B | Dataset-specific download and license unknown | 2026-11-07 |
| Monterey Bay watershed-to-whales | California Sea Grant reports almost 25,000 field-identified particles | B | River, beach, coastal-water, wildlife samples; row-level data/license unknown | 2026-11-07 |
| NHMLA Plastics Past and Present | California Sea Grant reports 353 processed fish specimens | B | Retrospective samples; sample-level data/license unknown | 2026-11-07 |
| Los Angeles / San Gabriel Rivers study | SCCWRP report documents measured river, sediment, fish microplastics | D | Secondary report evidence; data/license unknown | 2026-11-07 |
| SoCal biofilter field dataset | SCCWRP-linked study reports paired samples at seven Southern California sites | B | Shiny app returned HTTP 202 HTML; no sample payload parsed; format and license need review | 2026-11-09 |
| Bay Area dryer microfiber study | California Sea Grant reports sampling at 19 homes and one shared laundry | B | Source-pathway measurements; raw data/license unknown | 2026-11-07 |
| Los Angeles stormwater BMP retention study | California Sea Grant reports soil sampling at 18 stormwater systems | B | Project results public; row-level data/license unknown | 2026-11-07 |
| CCE LTER SEAPLEX particle measurements | Catalog describes North Pacific Gyre and California Current with a reference station off San Diego; coordinate-level California coverage remains unverified | B | 560-row manta-net dataset; guest-form terms limit scholarly use, require owner contact before publication, and prohibit redistribution without permission; no download/form acceptance | 2026-11-07 |
| California coastal wastewater treatment study | SCCWRP report describes measurements at selected coastal plants | D | Secondary report evidence; row-level data/license unknown | 2026-11-07 |
| Bight '23 sediment and shellfish assessment | SCCWRP reports completed 2023-cycle measurements | D | Separate cycle from Bight '13; row-level data/license unknown | 2026-11-07 |

S7.2 confirmed Tier A only for the SF Bay / 5 Gyres XLSX, which was parsed
under its CC BY 4.0 terms and mapped to canonical sample fields. Raw particle
count and sample volume are preserved separately; concentration is deferred to
S7.3 harmonization. The three
former Tier A candidates above remain B pending record-level terms or fields.
See `docs/S7_2_VERIFICATION.md` and `docs/api_notes/monitoring_sources_s7_2.json`
for all 15 endpoint observations, rights decisions, cadence, and field-map
status. Unknown terms block automatic ingestion.

The NCEI San Francisco Bay accession, stormwater collection-method study, and
Clean Swell page remain as excluded discovery records. The accession shares
the global NCEI archive identity. RMP/CD3, CEDEN, Moore drinking-water, the
planned statewide pilot, SWAMP/SPoT, and California Coastal Cleanup Day are
also excluded. See the verification note for evidence and reasons. S7.2 will
check endpoint access and terms before any ingestion decision.

## Future-source watch (S7.6)

<!-- S7.6 WATCHLIST START -->

Weekly metadata-only checks. HTTP status, validators, and limited response metadata do not establish data availability, quality, or reuse rights.

| Source | Reason / next review | URL | Last checked | Observed status / change | Tier |
|---|---|---|---|---|---|
| California statewide plastics monitoring pilot | OPC describes a SWAMP-supported statewide pilot planned for 2027; public data availability is not established. / 2027-01-15 | [https://opc.ca.gov/2026/06/june-16-2026-council-meeting-summary](https://opc.ca.gov/2026/06/june-16-2026-council-meeting-summary) | 2026-11-09T22:09:18+00:00 | 200; baseline; manual review | C |
| CEDEN 2.0 microplastics module | CEDEN says microplastics data types will be added over time; implementation and data availability need confirmation. / 2027-01-15 | [https://ceden.org/](https://ceden.org/) | 2026-11-09T22:09:18+00:00 | None; baseline; manual review | C |

<!-- S7.6 WATCHLIST END -->

<!-- S7.8 CEDEN WATCH START -->

Weekly metadata-only CEDEN check. Row counts are availability metadata from the data.ca.gov datastore, not data quality, completeness, or reuse rights.

Checked 2026-11-11T00:11:51+00:00 against [surface-water-chemistry-results](https://data.ca.gov/dataset/surface-water-chemistry-results); units: particles/L, particles/g, particles/kg, particles/m3.

| Resource | Rows | Distinct projects | Projects (rows) |
|---|---|---|---|
| 2014 CEDEN Water Chemistry Data | 60 | 1 | SF Bay Regional Monitoring for Water Quality / Regional Monitoring Program-Microplastics / 2017-2018 Microplastic Study - Moore Foundation (60) |
| 2015 CEDEN Water Chemistry Data | 121 | 1 | SF Bay Regional Monitoring for Water Quality / Regional Monitoring Program-Microplastics / 2017-2018 Microplastic Study - Moore Foundation (121) |
| 2016 CEDEN Water Chemistry Data | 83 | 1 | SF Bay Regional Monitoring for Water Quality / Regional Monitoring Program-Microplastics / 2017-2018 Microplastic Study - Moore Foundation (83) |
| 2017 CEDEN Water Chemistry Data | 1948 | 1 | SF Bay Regional Monitoring for Water Quality / Regional Monitoring Program-Microplastics / 2017-2018 Microplastic Study - Moore Foundation (1948) |
| 2018 CEDEN Water Chemistry Data | 763 | 1 | SF Bay Regional Monitoring for Water Quality / Regional Monitoring Program-Microplastics / 2017-2018 Microplastic Study - Moore Foundation (763) |
| CEDEN Water Chemistry Data Prior to 2000  | 70 | 1 | SF Bay Regional Monitoring for Water Quality / Regional Monitoring Program-Microplastics / 2017-2018 Microplastic Study - Moore Foundation (70) |

Total microplastics rows across checked resources: 3045.
New projects flagged: none.

<!-- S7.8 CEDEN WATCH END -->
