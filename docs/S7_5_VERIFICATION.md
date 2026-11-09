# S7.5 monitoring view verification

Checked 2026-11-09. The Monitoring tab now provides a cited source registry,
filterable sample table, schematic clustered sample map, and a sample-derived
matrix/region/year coverage table. The public build and local review build use
the same schema, with an enforced publication boundary.

## Public catalogue and rights boundary

`py -3.14 scripts/build_monitoring_export.py` writes
`site/data/monitoring.json`. The payload contains 24 registry records: 15
verified seed entries and 9 discovery records, each identified in the UI. It
includes source URLs, provenance URLs, citation text, license statements,
access tier, checked date, region, matrices, and cadence. It contains zero
sample observations (47,230 bytes). The source registry is a catalogue, not
evidence of measurements or statewide coverage. Unknown contributor-location
values remain unknown.

The SF Bay / 5 Gyres terms remain unresolved: current package metadata reports
ODC BY, the resource-level license is empty, and the prior CC BY 4.0 evidence
conflicts. Public output therefore contains no local QC observations. The
private-preview CLI mode writes outside `site/` by default and rejects resolved
targets inside the public tree, including relative path aliases. The preview
contains only the fields needed for the UI and is tagged
`private_preview` / `private_local_preview_rights_unresolved`; detailed QC row
provenance and license-evidence objects are stripped.

During initial browser setup, before adding that output-path guard, a private
export briefly wrote the 314 local rows to `site/data/monitoring.json`. A local
server was already bound on the checkout; whether it read the temporary file
was not verified. The public zero-row payload was restored immediately.
Subsequent preview generation and browser checks used only the ignored isolated
preview directory. The current public payload and staged-file check contain no
sample records, and this task agent made no commit or push.

## Local data and performance

For browser review, the existing `site/` shell and public assets were copied to
the ignored `data/processed/normalized/sf_bay_5gyres/site_preview/` directory;
the 314 actual locally normalized sample rows were exported there only. The
local data remain ignored and were not put into the public site payload.

Chromium on the repository's WSL Playwright setup reported:

| View | Monitoring JSON | Browser transfer | Resource duration | DOMContentLoaded | Result |
|---|---:|---:|---:|---:|---|
| Public catalogue | 47,230 B | 47,530 B | 19.7 ms | 39.7 ms | 24 source rows; no sample table/map points or sample-derived coverage cells |
| Local preview | 238,465 B | 238,765 B | 18.8 ms | 51.6 ms | 314 samples rendered; 277 valid coordinate pairs; filter to 2017 produced 237 rows in 3.3 ms |

These are single local-browser observations, not production-network latency
claims. On the actual local preview, the Unknown matrix filter returned 240
rows, of which 206 had valid coordinates; returning to all matrices rendered
in 6.0 ms. The unknown-matrix rows include 31 displayed zero particle counts.
The actual rows had no missing dates. A dependency-free Node runtime regression
uses tiny synthetic edge cases to verify null/undefined/blank/nonfinite and
out-of-range coordinate rejection, valid `(0, 0)` retention, zero count/value
rendering, unknown-matrix filtering, and missing/malformed-date filtering as
“Unknown date”. No “Unknown date” option is shown when the actual data has no
unknown dates. The sample table is capped at 500 rendered rows. Map markers are
schematic clusters, not a basemap or statewide spatial analysis. The coverage
view counts observed sample rows only; blanks and the empty public state are
not labelled as data gaps.

## Checks

```powershell
py -3.14 scripts/build_monitoring_export.py
py -3.14 scripts/check_s7_5.py --check-private-preview
py -3.14 -m pytest tests/test_monitoring_s7_5.py tests/test_monitoring_view_runtime.py -q
py -3.14 -m ruff check src/atlas/build/monitoring.py scripts/build_monitoring_export.py scripts/check_s7_5.py tests/test_monitoring_s7_5.py
py -3.14 -m ruff format --check src/atlas/build/monitoring.py scripts/build_monitoring_export.py scripts/check_s7_5.py tests/test_monitoring_s7_5.py
git diff --check
```

The public-boundary checker confirmed 24 registry rows, source and provenance
HTTPS links, citation text, no sample IDs or source hashes, and a payload below
100 KB. Focused tests cover public-empty output, mandatory private-preview mode,
private-field filtering, unknown datasets, and rejection of public-tree output
including an alias path. The actual local sample check confirmed exactly 314
rows were available and could be reduced to the preview UI schema.
`pytest` invokes `tests/monitoring_view_runtime.cjs` through its Python wrapper,
so Node.js 20 or newer must be installed on `PATH` for focused and full test
runs. If Node is missing, the wrapper fails with an installation message; it
does not skip the runtime regressions.

## Acceptance status

The interface, citations, honest empty-state behavior, and private local
performance check are implemented. S7.5 remains partial because no
rights-cleared monitoring observations can be included in the public build;
the public sample map and measurement-based coverage view therefore remain
empty. Do not present the local preview as public data or statewide coverage.
