# Handoff - 2026-11-14 - task VD-2

## Done
- Self-hosted Barlow Semi Condensed 600 and 700 Latin WOFF2 faces under
  `site/assets/fonts/`; recorded the SIL OFL provenance in `docs/REUSE.md`.
- Applied the Pacific Contour type scale, system UI body stack, sea-mist page, and white-card
  surfaces. Platform-font inspection on all 12 routes found Barlow headings and Segoe UI body
  text, with no rendered Palatino Linotype, Times New Roman, or Arial.
- Added one page-relative weight-700 preload per built page. The complete postbuild metadata and
  preload transform is idempotent.
- Corrected an exposed Policy async-layout regression: three Lighthouse runs now score
  performance 99, accessibility 100, LCP 1.9 s, and CLS 0.
- Full evidence is in `docs/VD_2_VERIFICATION.md`; local gate: 1,570 tests passed and 9 expected
  placeholders skipped, 6/6 visitor tasks passed, and all 12 routes scored accessibility 100.

## State of the repo
- Build with `cd framework; npm run build`; accept with
  `py -3.14 scripts/check_at5.py --dist dist` and `py -3.14 scripts/check_design_tokens.py`.
- WOFF2 transfer is 46,228 bytes (limit 60 KiB). Fonts deliberately live in `site/assets/fonts/`,
  not Framework source assets; the normal assembly step copies them beside the root pages.
- `.agent/QUESTIONS.md` had owner edits on entry; preserve its remaining unstaged formatting.

## Next task (suggested)
- VD-3: group the sidebar, add the shell icons/active state, header skip link/product name/expert
  search/mobile menu, and footer. Re-run the UX-32 Framework sidebar `list`/`region` checks.

## Gotchas the next agent must know
- Framework 1.13.4 has no loader for WOFF2 referenced from CSS. Keep the face URLs and preload
  page-relative so both the custom-domain root and repo-prefixed local preview resolve.
- `#policy-timeline` reserves the successful payload height because its JSON mounts after paint;
  removing the reservation restored mobile CLS 0.112.
- Run only one Observable Framework build at a time on Windows; concurrent builds lock `dist/`
  and produce `EPERM` while removing `_npm` folders.

## Needs owner input
- H25 is the final VD-12 side-by-side review; it does not block VD-3 through VD-11/VD-13.

## Files that are large or unsafe to read whole
- `site/data/` -> inspect schemas/counts only; `scratch/ux_vd2*/` -> read `results.json` and named
  screenshots rather than loading every Lighthouse JSON.
