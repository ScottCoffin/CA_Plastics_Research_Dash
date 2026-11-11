# CEDEN microplastics via the data.ca.gov CKAN datastore (S7.8a)

## Endpoint and filters
- `GET https://data.ca.gov/api/3/action/datastore_search?resource_id=<id>&filters=<json>&limit=1000&offset=<n>`
- Filters: `{"Unit": ["particles/L", "particles/g"], "ParentProject": "Regional Monitoring Program-Microplastics"}`.
  List values are ORed.
- Do not pass `facets`: the datastore returns HTTP 409 for it.
- Pages are archived under `data/raw/ceden/api/` (ignored) as `<year>_offset<n>.json`.
- Client: `atlas.ingest.monitoring.ceden.fetch_ceden_microplastics` (stdlib urllib, User-Agent
  `ca-plastics-atlas/0.1 (research dashboard)`, 0.3 s between requests).

## Resources (Surface Water - Chemistry Results)
| Year | Resource id | Rows (filtered) |
|---|---|---|
| 2018 | f638c764-89d5-4756-ac17-f6b20555d694 | 763 |
| 2017 | 68787549-8a78-4eea-b5b9-ef719e65a05c | 1948 |
| 2016 | 42b906a2-9e30-4e44-92c9-0f94561e47fe | 83 |
| 2015 | 7d9384fa-70e1-4986-81d6-438ce5565be6 | 121 |
| 2014 | 7abfde16-61b6-425d-9c57-d6bd70700603 | 60 |
| pre-2000 | 158c8ca1-b02f-4665-99d6-2c1c15b6de5a | 70 (1950-01-01 placeholder dates) |

Total 3,045 rows, matching the owner TSV export (`data/raw/ceden/export.tsv`, ignored).

## Fields
- Datastore names are CamelCase (`SampleID`, `SampleDate` ISO, `MatrixName`, `Analyte`, `Unit`,
  `Result`, `SampleTypeCode`, `StationCode`, `Latitude`, `Longitude`). The export uses UPPERCASE
  names and `M/D/YYYY H:MM:SS AM` dates. The loader lower-cases field names, so both shapes match.
- **The live datastore has no `ISQA` field.** The owner export carries `ISQA` (35 QA sample IDs).
  Live QA therefore falls back to blank sample types and blank names. The live `COLLECTIONREPLICATE`
  is not a substitute: the rule `replicate != 1` disagrees with `ISQA` on 15 sample IDs.
- `Result` values are stored to about 6-8 significant digits, so sums differ from the workbook
  concentration by 2e-8 to 2.5e-6 relative (see the verification note).
- Matrix families come from the text before the first comma in `MatrixName` (samplewater,
  sediment, effluent, runoff, blankwater). Size fractions come from the text after the last comma.

## Counts (verified 2026-11-10)
- Live run: 3,045 records, 141 CEDEN SampleIDs, 0 unmatched to the workbook.
- Owner export: 3,045 records, 141 SampleIDs. Per-sample sums, units, analyte counts, dates and
  stations are identical to the live aggregate (maximum absolute sum difference 0.0).

## Licence
CEDEN data are CC BY 4.0 (owner decision 2026-11-10). Enriched concentrations carry the citation
suffix "concentrations from CEDEN, California Environmental Data Exchange Network (CC BY 4.0)".
