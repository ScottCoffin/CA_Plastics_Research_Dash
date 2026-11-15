# Handoff - 2026-11-15 - task VD-4

## Done
- Added the token-based Section 5 component surface in `framework/src/design/components.css` and
  imported it globally after the VD-1/VD-3 layers.
- Added the accessible icon helper and one-per-document 24-symbol sprite. The style tile's 23 source
  paths are exact; `i-external` is the reconciled 24th Atlas icon (ADR-VD4-ICONS-2026-11-15).
- Added the unlisted `/styleguide` living reference with every Section 5 family and real Atlas copy.
  It is noindex/nofollow and absent from sidebar, sitemap, and `llms.txt`, but remains deployed by
  the normal Framework assembly.
- Independent Luna review and lead browser inspection found no axe violations or 390 px overflow.
  All actionable targets are at least 24 px; the one audit count is Framework's inert, hidden 1 x 1
  checkbox, replaced by the 40 px menu button.
- Full evidence is in `docs/VD_4_VERIFICATION.md`; the full suite passed with 1,577 tests and 9
  expected placeholders skipped, and 6/6 visitor tasks passed.

## State of the repo
- Build with `cd framework; npm run build`; accept with
  `py -3.14 scripts/check_at5.py --dist dist` from the repository root and
  `py -3.14 scripts/check_design_tokens.py`.
- `framework/src/components/shared/icons.js` is deliberately force-tracked inside an ignored
  generated directory. `sync_shared.mjs` copies four named files and leaves it intact.
- Local styleguide Lighthouse: performance 98, accessibility 100, LCP 2.0 s, CLS 0.005. Its only
  best-practices deduction was a local preview favicon request; no interactive audit errors occurred.
- `.agent/QUESTIONS.md` had owner edits on entry; preserve its remaining unstaged formatting.

## Next tasks (suggested)
- After this shared-file checkpoint, the contract permits up to three disjoint Luna workers. Start
  VD-5 Overview, VD-6a Experts, and VD-6b Collaboration network in parallel, then review and seal
  each as its own narrow checkpoint. VD-6c remains blocked on VD-10; VD-7b remains blocked on VD-9.

## Gotchas the next agent must know
- The style tile claims 24 symbols but contains 23. Do not replace the locked paths or remove the
  Atlas-drawn external icon; the focused test protects the reconciliation.
- A direct `framework/dist` preview lacks assembled font assets. Use `assemble_site.py` before visual
  QA so page-relative WOFF2 requests resolve.
- Framework's hidden sidebar checkbox appears as 1 x 1 in naive target scans, but is aria-hidden,
  untabbable, pointer-events disabled, and not actionable. Do not enlarge it into a second control.
- Run only one Observable Framework build at a time on Windows; concurrent builds can lock `dist/`.

## Needs owner input
- H25 is the final VD-12 side-by-side review; it does not block VD-5 through VD-11/VD-13.

## Files that are large or unsafe to read whole
- `site/data/` -> inspect schemas/counts only; `scratch/ux_vd4*/` -> read `results.json` and the two
  named screenshots rather than loading every Lighthouse JSON.
