# UX-15 and UX-16 verification (2026-11-12)

Contracts: `docs/EM_spec.md` UX-15 (Experts list: pagination or virtual list, visible loading state,
no-results state with "Reset filters") and UX-16 ("volume, not strength" caption on every
count-based view that lacks one).

## UX-15 (Haiku worker)
- The Experts list stays virtual. `framework/src/components/experts.js` adds a visible loading panel,
  a failure panel with Retry that re-runs the load, and a no-results panel ("No experts match these
  filters.") with a Reset filters button that clears every filter and returns focus to the search
  box.
- `experts_model.js`: rows are `<div role="listitem">` (the old `<article role="listitem">` failed
  axe aria-allowed-role); the count reads "N of M experts".
- Styles in `experts.css`; markup in `experts.md`. Test: `tests/test_ux15_experts_states.py`.
- Evidence: axe aria-allowed-role is gone from /app/experts. Playwright: the search "zzzzqqq" shows
  the no-results panel and "0 of 2,614 experts"; Reset gives "2,614 of 2,614 experts" with focus on
  the search box. Loading and failure panels were not exercised in a browser.
- `scripts/ux_tasks.py` (UX-18) now reads the new count format.

## UX-16 (lead)
- Captions modelled on the Institutions wording ("not a quality ranking"):
  - Experts: "Counts show volume, not strength: more works or citations do not mean better or more
    relevant research, and the list is not a ranking of expertise."
  - Funding: "Award counts show volume, not strength: more awards do not mean larger or better
    research programmes."
  - Evidence map: "Counts show how much has been published, not the strength or quality of the
    evidence." (The future evidence matrix will reuse it.)
- Test: `tests/test_ux16_volume_captions.py`.
