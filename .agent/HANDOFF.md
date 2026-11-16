# Handoff — 2026-11-16 — task VD-7c

## Done
- VD-7c Evidence visual adoption is implemented, deployed, and accepted. The page has a two-sentence lead, How-to disclosure, four shared callouts, 11 topic dots, and three padded chart cards; UX-30 selection/clear/focus behavior remains intact.
- Performance corrections yield the static first paint, request/normalize `works_detail.json` once, reuse plastic-related rows for the trend/table, and keep the table's default loader for other pages. The trend no longer performs 324 full-facet count queries.
- Live desktop/mobile checks: axe 0, no overflow/errors, one details request, filter/trend/table reactivity, table search, cell selection 294, clear to 1,579, and Publications focus all pass.
- Live Lighthouse 92/92/97 (median 92, baseline 92), accessibility/best-practices/SEO 100, LCP 1.737-1.820 s, TBT 105-284 ms, CLS 0.088. Final CI `43950760535`, Pages `43950760513`, and legacy Pages `43950758055` passed. Evidence: `docs/VD_7C_VERIFICATION.md`.

## State of the repo
- VD-8 implementation and verification files remain intentionally uncommitted for their own atomic checkpoint.
- The owner's unrelated formatting edits in `.agent/QUESTIONS.md` remain untouched and uncommitted.
- H27 still tracks GitHub Pages HTTPS enforcement; the live HTTPS site and deployment workflows work.

## Next task
- Finish only the already-started VD-8 checkpoint: commit its implementation, deploy, live-audit Policy/Resources/About/Glossary, update records, push, and inspect. Do not begin another roadmap item.

## Gotchas
- The source `framework/src/components/shared/` directory is generated before Framework builds; Node tests that run before build must import stable source modules instead.
- Compare Lighthouse only between equivalent live runs; local preview timing is not comparable.
- Preserve `.agent/QUESTIONS.md` and stage only VD-8 files.

## Needs owner input
- H25 (VD-12 design review), VD-5's absolute LCP target, and H27 HTTPS enforcement remain open.
