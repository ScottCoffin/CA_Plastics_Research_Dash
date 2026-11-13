# UX-6 verification (2026-11-12)

Contract: `docs/EM_spec.md` UX-6 (explain Overview 211 vs Institutions 161; definitions beside
each number; numbers unchanged).

## Finding
The code explains the difference; it is not a data bug.
- Overview "California institutions" = `build_metadata.json` `counts.ca_institutions`, i.e. every
  institution in `institutions.json` with `ca_flag` (211). These are California institutions on
  at least one published work (`src/atlas/build/export_site.py`).
- Institutions page = California institutions with at least one work where
  `plastic_related === true` (`buildInstitutionWorksIndex` and the `taggedCount > 0` filter in
  `framework/src/components/institutions.js`): 161.
- Recomputed from the committed payloads: 211 CA-flagged institutions, 161 of them on a
  plastic-related work.

## Changes
- `framework/src/components/atlas.js`: each Overview/About stat carries a one-sentence definition,
  rendered as a second `<dd class="stat-note">` (`index.md`, `about.md`, `style.css`).
- `framework/src/components/institutions.js`: the count line defines "qualifying" and points to
  the Overview definition.
- Test: `tests/test_ux6_counts.py` (definitions present; the two counts differ only by the
  plastic-related rule on the committed payloads).

The "Labeled works" tile is left for UX-14.
