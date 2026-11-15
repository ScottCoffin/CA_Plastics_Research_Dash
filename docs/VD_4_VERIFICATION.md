# VD-4 verification: shared components and icons

Date: 2026-11-15

## Result

VD-4 adds the Pacific Contour component layer in `framework/src/design/components.css` and an
unlisted living reference at `/styleguide`. The reference renders all 15 Section 5 component
families with Atlas copy: page head, pills, buttons, fields, filters, result line, callouts,
badges/topic chips, stat tiles, cards, table, chart/segmented control, disclosure, and skeleton.

`framework/src/components/shared/icons.js` supplies a hidden sprite exactly once per document and
returns DOM SVG elements. Decorative icons are hidden from assistive technology; labelled icons
use an accessible image role/name without creating duplicate IDs; unknown names fail visibly.
The source style tile contains 23 symbols although its copy says 24. ADR-VD4-ICONS-2026-11-15
preserves those 23 paths exactly and adds the already-needed Atlas `external` line icon as symbol
24. The module is force-tracked inside the otherwise generated/ignored shared directory;
`sync_shared.mjs` copies only four named legacy helpers and does not overwrite it.

The page carries `noindex, nofollow` and is deliberately absent from the sidebar `PAGE_GROUPS`,
static sitemap `PAGE_PATHS`, and `site/llms.txt`. Observable still builds and deploys the page, so
direct links remain available as the living component reference.

## Browser and visual evidence

The production-shaped assembly was served at
`http://127.0.0.1:8784/CA_Plastics_Research_Dash/styleguide`.

- Axe reported no violations at desktop and 390 px widths; the page had one h1, no heading skips,
  no unlabelled controls, no console/HTTP errors in the interactive audit, and no horizontal
  overflow.
- The DOM contained one sprite with 24 unique symbols. A second injection returned the existing
  node; decorative and labelled icon behavior and the unknown-name `RangeError` were exercised.
- All actionable controls were at least 24 px. The audit's sole small box was Framework's 1 x 1
  sidebar checkbox, which is `aria-hidden`, `tabindex=-1`, `pointer-events:none`, and replaced by
  the 40 px header menu button.
- Lighthouse reported performance 98, accessibility 100, LCP 2.0 s, and CLS 0.005. The local-only
  best-practices deduction was a preview `/favicon.ico` 404; the interactive page audit had no
  errors. The low SEO score is expected for an intentionally noindex reference page.
- Desktop and mobile evidence is under `scratch/ux_vd4_lead/`. Lead visual review confirmed the
  controls, typography, contour treatment, spacing, and responsive wrapping match the style tile.

## Verification commands

- `npm run build` in `framework/`: 13 pages and 75 links built; postbuild fixed all pages.
- `py -3.14 scripts/assemble_site.py --site site --dist framework/dist --out scratch/deploy_vd4`:
  production-shaped assembly included all 13 Framework pages (the reported 12 excludes home).
- `py -3.14 -m pytest tests/test_vd4_components.py -q`: 3 passed.
- `py -3.14 scripts/check_at5.py --dist dist`: passed; existing first-load gzip budgets remained
  within their limits.
- `py -3.14 scripts/check_design_tokens.py`: 259 non-token CSS hex uses, below 293.
- `py -3.14 scripts/check_public_text.py` and `scripts/check_doc_links.py`: passed.
- `py -3.14 -m ruff check .`, `py -3.14 -m ruff format --check .`, and
  `py -3.14 -m compileall -q src`: passed.
- `py -3.14 scripts/check_a1_scaffold.py` and `scripts/check_a2_scaffold.py`: passed. The Framework
  trigger emitted its expected T3 revisit warning.
- `py -3.14 -m pytest -q`: 1,577 passed, 9 expected placeholders skipped.
- `py -3.14 scripts/ux_tasks.py --base <local-base>`: 6 of 6 visitor tasks passed.
- `git diff --check`: passed while preserving the owner's unrelated unstaged
  `.agent/QUESTIONS.md` formatting.

## Delegation and review

A Luna executor implemented the bounded component/icon/styleguide package and focused test. A
separate Luna verifier performed read-only contract, DOM, axe, responsive, target-size, and icon
API review. The verifier found the ignored module path, invalid KPI definition-list children,
generic-container labelling risks, and two small component targets; the executor corrected the
semantics and sizes before lead acceptance. Lead review reconciled the sprite count, normalized a
reference glyph, repeated the production-shaped browser audit, and ran the full repository gate.

## Deployed-head correction

Commit `9e26e1a8` passed CI and Pages. Its deployed styleguide remained axe-clean, performance 100,
accessibility 100, LCP 1.5 s, and CLS 0.005. That live inspection also exposed a Framework behavior
not visible in source: page frontmatter `head` replaces the configured global head, so the required
noindex override had also removed the local Barlow `@font-face` block and data favicon. Lighthouse's
only best-practices failure was consequently `/favicon.ico` returning 404.

The correction keeps the frontmatter noindex directive and makes postbuild restore missing global
head elements by importing and reusing the exact `frameworkConfig.head` value. It also gives the
unlisted page a description and removes a duplicated product suffix from its title. The transform
is byte-idempotent. Independent Luna re-verification and 27 focused tests confirm the built page has
one product title, one description, two Barlow faces, one data favicon, one bold-font preload, and
the unchanged VD-3 skip-link/sidebar repairs. Final deployed measurements are recorded after the
corrective commit publishes.

The corrected live page then scored performance, accessibility, and best practices 100 with CLS 0,
and loaded both Barlow faces with HTTP 200. A target-box probe identified one remaining actionable
22 px Framework heading permalink (the other audit count was the inert sidebar checkbox). The
shared component layer now gives `.observablehq-header-anchor` a 24 px minimum height; the local
production-shaped rerun reports only the inert template checkbox and remains axe-clean.

Final commit `c7b1b000` passed CI and Pages. The live target rerun is axe-clean, has no horizontal
overflow, unlabelled controls, console errors, or HTTP errors, and reports only the intentionally
inert hidden checkbox below 24 px. This closes VD-4 deployed acceptance.
