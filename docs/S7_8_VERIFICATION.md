# S7.8a verification: CEDEN concentrations for SF Bay / 5 Gyres samples

Status: implementation and checks complete; the publication wiring (`site/`, `build/monitoring.py`)
is left to the lead.

## Method
- `atlas.ingest.monitoring.ceden`: aggregates CEDEN rows per SampleID (sum of `Result` across
  analytes and size fractions). Workbook concentrations are kept when present and must match
  CEDEN within `rel_tol`. Null concentrations are filled, with a source label and citation suffix.
  QA is `ISQA == 1` (export) or a blank sample type, or "blank" in the sample ID.
- `scripts/ingest_ceden.py`: live fetch (default) or `--from-export`. Writes
  `data/processed/normalized/sf_bay_5gyres/samples_enriched.json` and `ceden_qc.json` (ignored).

## Tolerance deviation (needs orchestrator review)
The brief specified 1e-9 relative. Exact agreement fails on the real data: all 63 kept samples
differ from CEDEN by 2.4e-8 to 2.5e-6 relative, because `Result` is stored to 6-8 significant
digits. The module default stays at 1e-9. The script default is `--rel-tol 1e-5`, which clears
every observed difference (no difference exceeds 1e-5). A real mismatch still raises.

## Results
| Measure | Owner export | Live CKAN |
|---|---|---|
| CEDEN records | 3,045 | 3,045 |
| CEDEN SampleIDs | 141 | 141 |
| Matched to workbook | 141 of 141 | 141 of 141 |
| Kept (workbook value equal to CEDEN) | 63 | 63 |
| Filled from CEDEN | 78 | 78 |
| Max kept relative difference | 2.54e-6 | 2.54e-6 |
| CEDEN QA samples (ISQA or blank type) | 35 | 24 (no ISQA field live) |
| Workbook QA samples published (`qa_sample`) | 56 | 45 |
| Blank-named workbook IDs | 44 | 44 |

Export QA breakdown: 35 CEDEN IDs flagged `ISQA=1` (LabBlank 13, FieldBlank 11, Grab 10,
Integrated 1). The 56 workbook QA samples are these 35 plus blank-named workbook IDs.
Note: the 56 export count is the authoritative QA figure. The live run lacks `ISQA`, so its 45
undercounts the 11 non-blank ISQA samples.

## Consistency report (counts only; no rows dropped)
- Date (matched 141): same day 127; 1950 placeholder skipped 14; different day 0; missing 0.
- Location (within 1 km): within 104; beyond 1 km 20; skipped (missing coordinates) 17.
- Matrix family: consistent 131; not comparable 10 (blank-water or no workbook code); inconsistent 0.

## Checks run
- `py -3.14 -m pytest -q tests/test_ceden_s7_8.py`: 14 passed.
- `py -3.14 scripts/check_s7_8.py`: PASS (fixture; local export gives kept 63, filled 78, QA 56).
- `py -3.14 -m ruff check` on the four new files: all checks passed; `ruff format --check`: 4 files already formatted.
- `py -3.14 scripts/check_doc_links.py`: Markdown links OK (111 files).
- Live run: one authorized call set (7 datastore requests, 0.3 s spacing), no API keys used.

## Not done / limitations
- `docs/api_notes/` and `docs/REUSE.md` are not changed beyond the new API note.
- `build/monitoring.py` and `build_monitoring_export.py` are not wired (lead task).
- Live QA can under-flag while the datastore lacks `ISQA`; use `--from-export` for published QA.

## Publication (lead, 2026-11-10)

- Tolerance: the default is now `rel_tol=1e-5`. CEDEN stores results to 6-8 significant
  digits, and the 63 kept samples differ from the workbook by 2.4e-8 to 2.5e-6 relative.
- `scripts/build_monitoring_export.py --public-samples` reads
  `samples_enriched.json` when it exists, which is the export-based run because only the
  export carries `ISQA`. Public builds drop every `qa_sample` row and report the number
  dropped as `excluded_qa_samples`. Private previews keep QA rows.
- Public payload: 298 observations (258 SF Bay / 5 Gyres + 40 Sierra snow); 56 QA samples
  excluded; 0 blank-named IDs published; 146 rows carry a concentration (previously 103
  of 354). All 298 rows have coordinates (the uncoordinated rows were QA blanks).
  Browser smoke: 298 located, 16 gap cells, no console errors.
- Before this change, the 2026-11-10 S7.5 publication (`afa988a`, `474e827`) briefly
  listed QA blanks and replicates as observations.

## Weekly CEDEN watch (S7.8b)

`atlas.ceden_watch` (`scripts/watch_ceden_microplastics.py`) runs in the weekly
source-watch workflow after the S7.6 step. It lists the CEDEN chemistry package's
yearly CSV resources and counts rows in microplastics units per resource and project.
The run is metadata only (≤ 40 requests, 0.3 s apart) and writes
`docs/api_notes/ceden_watch.json` plus the marked S7.8 block in `docs/SOURCES.md`. A
failed lookup is recorded as failed, never as zero. A new project is flagged. The
"Parquet - All Years" ZIP resource is skipped: it is flagged datastore-active, but its
count lookup fails, and it duplicates the yearly tables. Baseline on 2026-11-11 UTC:
3,045 rows (2014-2018 plus the pre-2000 table), one project (RMP 2017-2018 Moore
Foundation), and 0 rows for 2019-2026.
