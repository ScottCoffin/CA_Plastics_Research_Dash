# VD-6c verification: Institutions and Institution pages

Date: 2026-11-16

## Result

`framework/src/institutions.md` gains the page header (Explore eyebrow, lead,
glossary pills), keeps the "not a quality ranking" and tier-overlap text visible as
caution callouts, turns the leaderboard toggle into `.atlas-segmented`
(`aria-pressed` kept) and the zoom controls into 40 px `.atlas-btn--icon` buttons
with accessible names (same ids and keyboard handlers). `institutions.css` and
`institution.css` were rewritten on tokens (hex uses 52 -> 1 and 27 -> 0; the one
left is the state-waters fill, which has no token). Tier rows are cards with the
rank-range bar in brand colour and display-face tier headers; the land fill is
`--atlas-sunken`. Type chips and card badges use the VD-10 display labels. The
type-chip row reserves its height (2.75rem, 5.5rem at <= 40rem), fixing the
`.institution-sort-row` shift seen in the VD-10 check. The Institution page gets a
page header with a type badge, `.atlas-kpis` stat tiles and `.atlas-card`
sections. `inst_tiers.js` is untouched (classic drift test).

## Verification

- Tests: `tests/test_vd6c_institutions.py` (14) plus the existing institutions,
  institution, labels and monitoring suites.
- Assembled local site (`npm run build`, `check_at5.py`, SEO pages, `assemble_site.py`,
  `serve_framework_preview.py --assembled`): axe no violations on `/institutions`
  and `/institution#inst=CAAG-OEHHA` at desktop and 375 px; no overflow, console
  or HTTP errors; one h1 each. Lighthouse (local, mobile preset): accessibility
  100, CLS 0.027 on `/institutions` (0.199 before) and 0 on `/institution`.
  `ux_tasks.py` 6/6 (task 3 reaches a tier and reads the overlap text).
- Screenshot: `scratch/vdv/ux2/` (gitignored).

## Deviations

- Zoom in/out keep text glyphs (+/-): the Atlas sprite has no plus/minus symbol;
  reset uses `i-home`.
- Local Lighthouse performance (51 and 50) is not comparable with the live
  baseline; see the Deployed section for live numbers.
- Targets under 24 px remain (24-28 on `/institutions`, 17-18 on `/institution`);
  UX-32 owns them.
