# S7.1 monitoring registry verification

Checked 2026-11-07. This checkpoint creates the registry contract and curated
source seeds only; it does not ingest, harmonize, or rank sample observations.
Registry inclusion does not approve comparability or reuse rights.

## Acceptance result

`config/datasets.yml` contains 24 source records. Exactly 15 are eligible seeds
with distinct `underlying_dataset_id` values. Each eligible record includes a
short factual evidence excerpt, identity rationale, verification URL, and
check date. The content evidence distinguishes actual observations from
program descriptions and secondary reports; the access matrix separately
records matrices, access method, cadence, tier, and license status. Unknown
licenses remain explicitly unknown. No single HTTP success is treated as proof
of observations or an open license.

The NCEI San Francisco Bay accession remains in the registry for geographic
discovery, but is linked to `noaa_ncei_marine_microplastics` and excluded from
the seed count because it is a child record in that archive. The stormwater
collection-method evaluation and Clean Swell participation page are also
excluded because the verified pages did not establish distinct California
microplastic observation datasets. Three additional independent records bring
the count to 15: the California Current LTER SEAPLEX data table, SCCWRP's
coastal California wastewater-treatment study, and the Bight '23 sediment and
shellfish assessment. The latter report documents completed measurements but
does not provide a row-level download; its seed is marked literature-secondary.

## Schema

The YAML uses `schema_version: 1`. `atlas.ingest.monitoring.registry` validates
required fields, enumerations, unique IDs and source URLs, unique underlying
dataset identities among eligible seeds, HTTPS evidence links, ISO dates,
explicit license text, nonempty factual evidence and the 15-seed minimum.
`seed_eligible` is an audited eligibility decision; it is not inferred from
the existence of a program or methods page.

Each eligible row records identity and kind, geographic and sample-matrix
scope, plastic classes, tier, access method, format, cadence, license,
provenance, a short evidence excerpt, an identity/deduplication rationale, a
verification URL, and `last_checked`. Tier A indicates a source page identifies
public data or a download. Tier B indicates a documented program or dataset
whose export, subset, or license needs review. Tier C describes reporting or
future sources without a confirmed public observation endpoint. Tier D marks
literature/report-derived evidence. Tiers describe access and evidence, not
data quality.

## Verified seed records

| ID | Evidence and identity | Access matrix / cadence / license note |
|---|---|---|
| `noaa_ncei_marine_microplastics` | NOAA product page identifies the global marine microplastics archive. Child accessions share this archive identity and are not counted separately. | Marine water and seafloor sediment; CSV/JSON/GeoJSON portal; quarterly cadence reported in source literature; record-level license/attribution vary. |
| `sf_bay_5gyres_microplastics` | California Open Data lists particle-level data linked to sample IDs for an independent SFEI/5 Gyres project. | Stormwater, wastewater effluent, surface water, sediment, prey fish; public XLSX/PDF; irregular updates; CC BY metadata, recheck resource terms. |
| `ca_drinking_water_microplastics` | State Water Board page documents SB 1422 monitoring and reporting requirements; public observation export is not confirmed. | Source and treated drinking water; statutory reporting; unknown observation license. |
| `noaa_mdmap` | NOAA's California partner highlight documents monthly MDMAP surveys at four Greater Farallones beaches from 2012 to 2018. | Shoreline macrodebris; monthly partner surveys; record-level rights unknown. |
| `socal_bight_microplastics` | SCCWRP describes the regional monitoring program and its cycle-based portal. | Southern California Bight habitats; approximately five-year cycles; microplastics-specific files and license need review. |
| `bight_2013_benthic_plastic` | SCCWRP identifies Bight '13 benthic plastic type and size data. | Sediment grabs; one 2013 cycle; dataset-specific download and license unconfirmed. |
| `monterey_bay_watershed_to_whales` | California Sea Grant reports nearly 25,000 identified particles from independent Monterey Bay field sampling. | Rivers, beaches, coastal water and wildlife; project results public, row-level file/license unknown. |
| `nhmla_plastics_past_present` | California Sea Grant reports processing 353 historical California fish specimens. | Archived fish gut contents; retrospective study; specimen-level file/license unknown. |
| `la_san_gabriel_rivers_sccwrp_1389` | SCCWRP report describes measured microplastics in Los Angeles and San Gabriel River water, sediment and fish. | Surface water, bed sediment, fish; report-derived secondary evidence; data/license unknown. |
| `socal_stormwater_biofilter_microplastics` | SCCWRP-linked study reports paired influent/effluent samples at seven Southern California installations. | Stormwater and biofilter media; view/download reported; format/license need review. |
| `bay_area_clothes_dryer_microfibers` | California Sea Grant reports exhaust sampling in 19 households and one shared laundry. | Dryer lint and filter captures; source-pathway measurements; underlying data/license unknown. |
| `la_bmp_microplastic_retention` | California Sea Grant reports soil sampling at 18 Los Angeles County stormwater systems. | Biofilter soil and runoff experiments; project results public; data/license unknown. |
| `cce_lter_seaplex_microplastic_particle_type` | California Current LTER catalog describes North Pacific Gyre and California Current measurements, a reference station off San Diego, and a 560-row table; coordinate-level California coverage is unverified. | Manta-net samples; catalog guest-form terms restrict use to scholarship, require owner contact before publication, and prohibit redistribution without permission. No form acceptance or download was performed; no general license established. |
| `california_wastewater_treatment_microplastics_sccwrp_1378` | SCCWRP report describes measured microplastic levels and compositions at selected coastal California plants. | Wastewater process samples and biosolids; report-derived secondary evidence; data/license unknown. |
| `bight_23_microplastics_sediment_shellfish` | SCCWRP reports completed Bight '23 measurements for sediment and shellfish tissue; distinct cycle from Bight '13. | Seafloor sediment and shellfish; report describes findings, row-level file/license unknown. |

## Excluded from the seed minimum

| ID | Reason |
|---|---|
| `ncei_sf_bay_bivalves_2018` | NCEI accession child, linked to its global archive through `underlying_dataset_id`; not double-counted. |
| `stormwater_collection_method_evaluation` | Methods/collection evaluation page did not establish an observation dataset. |
| `ocean_conservancy_tides_cleanswell` | App/program page documents item logging but California observations were not verified. |
| `sf_bay_rmp_cd3_microplastics` | Direct SFEI page was blocked and the microplastics subset/export was not verified. |
| `ceden_microdebris` | Plastic analyte vocabulary was found, but California observation rows were not confirmed. |
| `moore_drinking_water_open_data` | Current alpha/mock versus observation content could not be verified. |
| `statewide_plastics_pilot` | Planned future pilot, not existing observation data. |
| `swamp_spot_context` | Relevant platform, but no current plastics measurements were verified. |
| `california_coastal_cleanup_day` | Annual summaries report total trash without a plastic-specific observation category. |

## Checks

```powershell
py -3.14 scripts/check_s7_1.py
py -3.14 scripts/check_s7_1.py --smoke-urls
py -3.14 -m pytest tests/test_monitoring_registry.py -q
py -3.14 -m pytest
py -3.14 -m ruff check .
py -3.14 -m ruff format --check .
git diff --check
```

S7.2 remains responsible for source-specific endpoint, format, license,
frequency, and field-map checks before ingestion.
