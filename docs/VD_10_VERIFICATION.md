# VD-10 verification: display labels for vocabulary slugs

Date: 2026-11-16

## Result

`framework/src/components/shared/labels.js` (new, force-tracked like `icons.js`;
not copied by `sync_shared.mjs`) holds the display labels for the 13 Atlas
institution types plus `other` (also the sector vocabulary) and 20 OpenAlex work
types. Unknown values fall back to a humanised string; `sectorLabel` keeps the
raw fallback the network runtime test pins. Display text now goes through the
helpers in:

- Experts: institution-type select option text (sorted by label) and its filter chip.
- Institutions: type chips, card chips, map detail chips and tier-row chips. The
  tier helper `inst_tiers.js` must stay a code-identical port of the classic
  helper, so `institutions.js` filters tiers on the raw type and passes labelled rows.
- Institution page: header chip and search detail line.
- Funding: recipient-type cell and the institution-type select.
- Evidence map: Sector and Work type facet names.
- Network: `sectorLabel` delegates to `labels.js`.

Option `value` attributes, URL hashes, data and CSV exports keep the raw slug.

## Verification

- Tests: `tests/test_vd10_labels.py` (every `ATLAS_TYPES` value in
  `src/atlas/ingest/institutions.py` and every work type in code has a label;
  call sites import the module; the sync script does not copy it) and
  `tests/framework_labels_runtime.mjs`.
- Clean worktree of HEAD plus only this change: links, both scaffolds, Ruff check
  and format, compileall, the design-token check (176 < 293) and the public-text
  check passed; pytest 1,706 passed with 13 skips. Two failures in that run came
  from a `--basetemp` inside the repository (a release test expects to run outside
  git); both files pass with the default temp root (28 passed).
- Assembled local site (`npm run build`, `check_at5.py`, `build_seo_pages.py`,
  `assemble_site.py`, served with `serve_framework_preview.py --assembled`):
  a Playwright text check of `/`, `/experts`, `/institutions` (tiers and list),
  `/institution#inst=CAAG-OEHHA`, `/funding`, `/evidence` and `/network` found no
  F10 slug (`community-college`, `intergovernmental-organization`,
  `local-agency`, `nonprofit/NGO`, `state-agency`, `other-public`,
  `book-chapter`, `conference-abstract`, `proceedings-article`). The script's one
  hit was its extra bare token "nonprofit" matching the display label "Other
  nonprofit & institutions" on Funding, which is not a slug.
- URL values unchanged: choosing "Local agency" in the Experts select gives
  `#institution_type=local-agency`.
- axe: no violations on the eight touched routes at desktop and 375 px; no
  horizontal overflow, console or HTTP errors. `scripts/ux_tasks.py`: 6/6 passed.

## Deviations and follow-ups

- The classic `site/index.html` still shows slugs; it is outside the Framework app.
- Lighthouse: `/institutions` showed CLS 0.199 in two of three local runs (0 in
  the third and 0 live at HEAD). The shifted node is the sort row under the type
  chips, which render after the data loads; longer labels can enlarge the shift
  when it happens. VD-6c (which owns that toolbar) should reserve the chip row.
- Evidence: `scratch/vdv/` (gitignored): `ux/results.json`, `slug_check.json`,
  `shots/`, `tasks/`.
