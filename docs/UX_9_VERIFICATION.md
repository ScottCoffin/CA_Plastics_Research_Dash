# UX-9 verification (2026-11-12)

Contract: `docs/EM_spec.md` UX-9 (CSV download with citation and licence; YYYY-MM-DD dates; units in
headers where constant; licence glosses). Presentation only; no data files changed.

## Changes
- `framework/src/components/monitoring_view.js`: `samplesCsv(rows, datasets, downloadedOn)` builds
  the CSV from the currently filtered rows (all pages). Leading `#` lines carry each source
  citation, each licence id with its gloss, the empty-cell note and "Downloaded from ... on
  YYYY-MM-DD"; then a header and RFC 4180 rows. `formatSampleDate` gives YYYY-MM-DD (partial dates
  stay as recorded; missing -> "Unknown date"). A licence gloss map covers CC-BY-4.0, ODC-BY,
  CC0-1.0 and fair-use-factual-values, with the fallback "Reuse terms not recorded; check the source".
- `monitoring.md` / `monitoring.js` / `monitoring.css`: "Download observations (CSV)" button in
  Sample observations; a shared concentration unit moves into the column header (mixed units stay
  inline, or become a unit column in the CSV); the source registry shows the gloss under each
  licence and links to `./glossary#licences` and `./glossary#access-tiers` (targets added by UX-7).
- Test: `tests/test_ux9_monitoring.py` (node runtime checks of the CSV, date and gloss helpers).

## Evidence
- Playwright download on the local preview: `ca-plastics-observations-2026-11-12.csv`, 298 data
  rows = the on-page "298 rows" count (table pages show 50). The default view mixes units, so the
  CSV has unit columns.
- axe on /app/monitoring: only the Framework sidebar `list`/`region`.

## Owner check (TODO-OWNER)
- The four licence glosses were drafted by the agent, not quoted from the licensors. Please
  confirm the fair-use-factual-values wording in particular.
- Licence glosses use the structured `publication_license.id`; 23 rows with a free-text licence
  only get the fallback text. The CSV has no UTF-8 BOM, so Excel on Windows may misread
  non-ASCII citations.
