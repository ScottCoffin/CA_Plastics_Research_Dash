# Handoff - 2026-11-14 - task VD-1

## Done
- Added Pacific Contour tokens and Framework mappings in `framework/src/design/tokens.css`;
  aliased the five task-owned page palettes and retained UX-22 link underlines.
- Added the deterministic non-token CSS literal ratchet, eight focused tests, and CI step.
- Verified 259 CSS literal uses vs 293 baseline, 1,566 tests, 6/6 UX tasks, and all-route axe;
  details and screenshot paths are in `docs/VD_1_VERIFICATION.md`.
- Reserved async stats and institution surfaces after the first live audit. The deployed rerun
  scored Overview 100/CLS 0, Institution 99/0, and About 100/0.047.
- Owner accepted VD-D1..VD-D8; H24 is closed.

## State of the repo
- Build with `cd framework; npm run build`; accept with
  `py -3.14 scripts/check_at5.py --dist dist` and `py -3.14 scripts/check_design_tokens.py`.
- CI and Pages succeeded for both VD-1 commits; the correction stylesheet and live metrics are
  verified at `https://plastiverse.live/`.
- `.agent/QUESTIONS.md` had owner edits on entry; preserve any remaining unstaged formatting.

## Next task (suggested)
- VD-2: record the Barlow SIL OFL entry first, add the two local WOFF2 faces and surface/type
  scale, then verify Framework copies the font URLs and measure platform fonts/transfer/CLS.

## Gotchas the next agent must know
- Run only one Observable Framework build at a time on Windows; concurrent builds lock `dist/`
  and produce `EPERM` while removing `_npm` folders.
- The design checker excludes `tokens.css` intentionally and ratchets each existing stylesheet
  as well as the 292-use global ceiling.

## Needs owner input
- H25 is the final VD-12 side-by-side review; it does not block VD-2 through VD-11/VD-13.

## Files that are large or unsafe to read whole
- `site/data/` -> inspect schemas/counts only; `scratch/ux_vd1*/` -> read `results.json` and named
  screenshots rather than loading every Lighthouse JSON.
