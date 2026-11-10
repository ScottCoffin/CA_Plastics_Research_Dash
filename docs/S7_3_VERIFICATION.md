# S7.3 SF Bay / 5 Gyres normalization

## Implemented scope

`src/atlas/ingest/monitoring/sfbay.py` reads a locally held XLSX, verifies the
S7.2 SHA-256 by default, joins each sample worksheet to `Particle Data` by
`SampleID`, and writes deterministic `samples.json`, `particles.json`, and
`qc.json` outputs. Outputs go under ignored `data/processed/normalized/` by
default. The workbook is never copied into the repository. Override of the
pinned hash is explicit and should only follow inspection of a changed schema.

The verified `manta` matrix code maps to surface water, as documented in the
S7.2 field map. Source codes `sed`, `eff`,
`sw`, and `fish` are preserved but not mapped to canonical matrices. The
canonical `particle_count` is the number of particle-detail rows; source
`Count` is kept separately and count/detail differences are reported. For
manta only, `Count / Volume.L` is emitted as `particles/L` when the count
matches particle-detail rows and both values are finite with positive volume.
Overflow, missing/invalid denominators, and mismatches remain null with QC.
Particle dimensions retain `Length.mm` and `Width.mm` in particle-level
records. Mesh and size class remain null. Plastic confirmation is per particle;
the sample flag is true if one or more records name a recognized polymer,
false only if every particle record has an explicit negative label, otherwise
null. Sample and particle outputs carry source hash, URL, attribution, and
structured package-license evidence.

## Verification and limits

- Fixture normalization, invalid-unit, matrix-conflict, duplicate-header,
  date, particle-count consistency, and overflow tests:
  `py -3.14 -m pytest tests/test_monitoring_sfbay_s7_3.py tests/test_monitoring_sources_s7_2.py -q`
  (10 passed).
- The retained local workbook exists at the exact S7.2 path, is 1,589,496
  bytes, and matches SHA-256
  `8fc7c636413e8030d9648d295c3263fe3dbf30a04c64c765e267cb71611d2684`.
  Local normalization completed into ignored `data/processed/normalized/`.
- Current official CKAN `package_show` and `resource_show` calls resolved the
  same package/resource IDs and 1,589,496-byte XLSX URL. Package metadata
  reports Open Data Commons Attribution; resource-level license and checksum
  are empty. This differs from the S7.2 note's CC BY 4.0 statement.
- A no-follow request to the exact resource URL returned HTTP 302 to a
  time-limited URL in the publisher's `og-production-open-data-cnra` S3 bucket.
  The official-resource follow attempt returned HTTP 403. Processing used the
  already-held hash-matched workbook, not a new fetch. No unlisted mirror or
  redirect bypass was used. The package-level ODC BY metadata is recorded
  separately from the earlier S7.2 CC BY 4.0 note; resource-level license is
  null. Normalized outputs are local/ignored and carry the observed license
  evidence; they are not published or committed.
- Actual workbook QC: 315 nonblank sample-sheet rows produced 314 unique
  samples (one repeated ID), and all 44,226 particle rows were retained. Eight
  samples have no particle rows; one source-count/detail mismatch remains.
  Raw-row QC found 15 invalid/missing `Volume.L` values; after unique sample
  selection there are 14, with the extra invalid value belonging to the
  conflicting duplicate below. There are 37 samples with missing/invalid
  coordinates and 277 classified coordinates (94 CA land, 165 state waters,
  18 outside both polygons). 63 manta concentrations were computed; 251
  sample concentrations remain null. Particle matrix codes: manta 20,164;
  sw 12,525; sed 6,022; eff 3,510; fish 2,005. Only manta maps to a canonical
  matrix; the other source codes remain explicit and unmapped.
- Duplicate conflict: one sample identity has conflicting duplicate source
  rows across particle count, sample volume, and collection method. One sample
  identity is retained; conflicting canonical count, volume, method, and
  concentration are suppressed, while associated particle details are kept.
  The ignored QC output retains per-row diagnostics for local review. This
  committed report records only aggregate counts and conflict categories.

## Checkpoint status (closed 2026-11-10)

The owner determined on 2026-11-10 that the SF Bay / 5 Gyres data are CC BY 4.0
(QUESTIONS S7.3-A). Every sample, particle and QC output now carries a
`license` object (`CC-BY-4.0`, basis: owner determination) alongside the
unchanged observed `license_evidence` (package metadata ODC BY; resource field
empty). Both are attribution licenses, so the attribution string names SFEI,
5 Gyres, OPC and the CNRA Open Data portal. Re-running the normalizer on the
same hash-matched workbook gave identical QC counts (314 samples, 44,226
particle rows). Acceptance (polygon flags, units QC, duplicate QC, fixtures,
tests) was already met; the rights decision was the last open item. Raw
workbook and particle rows remain local; S7.5 publishes display fields only.
The other S7.3 candidates (NCEI, MDMAP, drinking water) are below Tier A per
S7.2 and are not ingested.

## Run locally

```powershell
py -3.14 scripts/ingest_s7_3_sfbay.py C:\Users\Scott.Coffin\Downloads\2020-09-11_microparticledata.xlsx
```
