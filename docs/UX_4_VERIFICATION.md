# UX-4 verification (2026-11-12)

Contract: `docs/EM_spec.md` UX-4; owner default UXD-5 (keep the Evidence map in the nav with one
"In development" notice; hide only the placeholder sections).

## Changes
- `framework/src/evidence.md`: the Evidence matrix, Sampled-location atlas and Review overlay
  placeholder sections are removed. One notice remains: "In development: an evidence matrix, a map
  of sampled locations and a review overlay will be added here." The intro names only the rendered
  controls (title words, year range, topic, sector, work type, open access, California leadership,
  plastic relevance). Section headings are h2 under the page h1.
- `framework/src/components/evidence.js`: the bundle load is wrapped in try/catch. The status ends
  as "Loaded N works." or "Could not load the evidence data." with a Retry button that re-runs the
  load. The Pipeline flow and Trend panel sections stay hidden until their container has content.
  Facet groups with no options are skipped.
- `framework/src/components/evidence.css`: `.ev-notice` replaces `.ev-placeholder`.
- Test: `tests/test_ux4_evidence.py`.

## Evidence
- Local preview: status "Loaded 1,909 works."
- Failed fetch simulated with Playwright (bundle requests aborted): status "Could not load the
  evidence data. Retry"; pressing Retry re-requests the bundle (aborted requests 3 -> 6) and shows
  the same failed state. Screenshot kept locally in `scratch/ux4/failed.png` (gitignored).
- axe on /app/evidence: no heading-order violation after the UX-23 change to the V-4 headings
  (`v4_trend.js` h4 -> h3). Remaining `list`/`region` nodes come from the Framework sidebar template.

## Gate
- Links, scaffolds, ruff, `compileall`, `git diff --check`; full pytest 1,392 passed, 9 skipped.
- `check_at5.py --dist dist` and `check_public_text.py framework/dist` passed.
