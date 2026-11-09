# S7.2 monitoring source smoke and tier decisions

Checked 2026-11-09. Source endpoint requests were public unauthenticated GETs;
no paid service, login, terms acceptance, or anti-bot bypass was used. The smoke
run made 15 source-page requests plus six metadata/data requests (21 requests
total). The only data file downloaded and parsed was the 1,589,496-byte XLSX;
the SCCWRP PDF's 3,271,174-byte content length was observed during a streaming
header check, but its body was not read. The per-file ceiling is 10 MB and the
planned request ceiling is 50. A page response is recorded
as page access only, never as proof of a dataset export.

## Results

All 15 eligible S7.1 identity URLs were checked: 14 returned HTTP 200, while
the SCCWRP Shiny app returned HTTP 202 with HTML. The NCEI and California Open
Data pages were also checked against their official product metadata. Actual
row-level content was downloaded and parsed only for the SF Bay / 5 Gyres XLSX
(1,589,496 bytes). The local copy at
`C:/Users/Scott.Coffin/Downloads/2020-09-11_microparticledata.xlsx` has SHA-256
`8fc7c636413e8030d9648d295c3263fe3dbf30a04c64c765e267cb71611d2684`; it was
already present and was not downloaded during the repair. The workbook has six
sheets. Its `manta` sample sheet has `Volume.L` and `Count`, but no
`SampleMatrix`; the separate `Particle Data` sheet has `SampleMatrix` source
code `manta`, particle type, morphology, dimensions, and color. The two rows
join on `SampleID`. The dataset resource identifies surface-water particle
data, and the manta sample row records a 5Gyres Manta Trawl at
`PositionWaterColumn=Surface`, supporting the explicit `manta` -> `surface
water` mapping while retaining the raw code. `Count` is preserved as
`particle_count`; observed `Volume.L` is preserved from that same sample row,
not joined from another sheet. Concentration remains unset until S7.3 confirms
the measurement denominator and units. Particle `Length.mm` and `Width.mm`
remain separate dimensions; `size_class` and `mesh_um` are explicitly unknown
or deferred, not inferred from dimensions or `MatrixName`.

## Tier decisions

| Tier | Sources | Decision |
|---|---|---|
| A | SF Bay / 5 Gyres | Public machine-readable XLSX parsed; CC BY 4.0; source/sample fields map to canonical samples; raw count and volume retained separately while concentration harmonization is deferred. |
| B | NCEI; NOAA MDMAP; SoCal Bight; Bight '13; Monterey Bay; NHMLA; SoCal biofilter app; dryer microfiber; LA BMP; SEAPLEX | Primary program/data identity exists, but row-level access, rights, California scope, or mapped sample records remain unresolved. No automatic ingest. |
| C | SB 1422 drinking-water monitoring | Reporting program exists; no public observation export was confirmed. |
| D | LA/San Gabriel Rivers SCCWRP 1389; SCCWRP wastewater report 1378; Bight '23 | Secondary report evidence; no primary row-level observations confirmed. |

Tier A requires machine access, plastic relevance, cleared reuse terms, and a
documented source-to-canonical field map. Unmapped fields are recorded as
unknown or deferred; no numeric values are guessed. Public HTTP access alone does not clear license or reuse
rights. In particular, NCEI says access/use is free but source-record
attribution and terms can vary, so it remains B. SEAPLEX catalog guest terms
restrict use and prohibit redistribution absent permission; no agreement was
accepted or data downloaded. The remaining eight excluded S7.1 discovery
records retain their prior exclusion reasons in `docs/S7_1_VERIFICATION.md`;
S7.2 did not promote them or repeat discovery research.

## Reproduction and checks

```powershell
py -3.14 scripts/check_s7_2.py
py -3.14 scripts/check_s7_2.py --smoke-urls
py -3.14 -m pytest tests/test_monitoring_sources_s7_2.py tests/test_monitoring_registry.py -q
py -3.14 -m ruff check .
py -3.14 -m ruff format --check .
git diff --check
```

The URL smoke option is bounded to the 15 eligible verification URLs, with a
15-second timeout and a 10 MB per-response ceiling. It does not fetch bulk
exports. Detailed endpoint results, formats, license findings, cadences, and
the field map are recorded in `docs/api_notes/monitoring_sources_s7_2.json`.
No Tier-A ingester was added; that is S7.3.
