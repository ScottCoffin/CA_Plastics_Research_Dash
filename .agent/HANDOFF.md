# Handoff - 2026-11-15 - task VD-3

## Done
- Replaced the flat Framework navigation with four grouped sections, ten route icons, visible active
  state, and postbuild-applied `aria-current` on every built route.
- Added the responsive Pacific Contour header with a first-focus skip link, product/breadcrumb
  identity, expert search, 390 px menu behavior, and accessible footer links.
- Added the coastline mark and shell styling in `framework/src/design/shell.css`; the embedded mark
  is teal with an orange contour and does not require a runtime asset request.
- Removed Framework's invalid sidebar close-label child and hid its replaced checkbox from assistive
  technology. All 12 routes are now axe-clean, including the former sidebar `list` and `region` rows.
- Reserved the asynchronous Resources root height after tracing its initial footer displacement to
  CLS 0.181. The corrected Resources and Institutions checks both report CLS 0.
- Full evidence is in `docs/VD_3_VERIFICATION.md`; the full suite passed with 1,574 tests and 9
  expected placeholders skipped, and 6/6 visitor tasks passed.

## State of the repo
- Build with `cd framework; npm run build`; accept with
  `py -3.14 scripts/check_at5.py --dist dist` and `py -3.14 scripts/check_design_tokens.py`.
- VD-3 owns the config, shell stylesheet/import, idempotent postbuild accessibility transform,
  Resources height reservation, and `tests/test_vd3_shell.py`.
- One full-suite attempt exposed an unrelated transient Windows temp-directory `WinError 5` in
  `test_node_round_trip_counts_and_search`; the exact test and the complete rerun both passed.
- `.agent/QUESTIONS.md` had owner edits on entry; preserve its remaining unstaged formatting.

## Next task (suggested)
- VD-4: add the shared component library and icon sprite, then expose every Section 5 component on
  an unlisted `/styleguide`; require axe-clean output and interactive targets at least 24 px.

## Gotchas the next agent must know
- Framework 1.13.4 generates the sidebar close label inside its navigation list. Keep the postbuild
  transform idempotent unless the template structure itself changes.
- Framework footer selectors target pager links with ID specificity. Custom footer link resets must
  keep at least the existing specificity.
- Asynchronous roots can place the larger footer in the initial viewport before data mounts. Preserve
  explicit initial height reservations and diagnose shifts with `PerformanceObserver` before tuning.
- Run only one Observable Framework build at a time on Windows; concurrent builds can lock `dist/`.

## Needs owner input
- H25 is the final VD-12 side-by-side review; it does not block VD-4 through VD-11/VD-13.

## Files that are large or unsafe to read whole
- `site/data/` -> inspect schemas/counts only; `scratch/ux_vd3*/` -> read `results.json` and named
  screenshots rather than loading every Lighthouse JSON.
