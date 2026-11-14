# Handoff - 2026-11-14 - Visual design assessment and spec (VD-0)

## Done this session (checks: doc links, A1/A2 scaffolds, ruff, full pytest, build,
## git diff --check, clean-worktree pytest)
- VD-0 (owner: the Framework site "lacks any meaningful design elements"; wants colour and
  modern, comfortable components). Assessed the live site with `ux_audit.py` (axe +
  Lighthouse, 12 routes), a design probe (rendered fonts via DevTools, computed styles,
  first-screen colourfulness), a CSS/JS colour inventory, the dataviz palette validator and
  contrast checks. Probe scripts and screenshots: `scratch/design_audit_2026-11-14/`.
- Findings (spec Section 1): Windows renders Palatino Linotype and Arial (Framework font
  fallbacks); colourfulness 14-23 on every route; 78 hard-coded CSS hex colours and two visual
  languages; three control styles; data below the fold on Experts, Evidence and Network; the
  monitoring-matrix and funding-agency palettes fail the colour-blind check; Overview CLS 0.17;
  no icons. Lighthouse accessibility 100 on 11 of 12 routes (Evidence 96), SEO 100 on all 12.
- Deliverables: `docs/VISUAL_DESIGN_SPEC.md` ("Pacific Contour"); style tile
  `docs/design/style_tile.html` (private artifact for the owner:
  https://claude.ai/code/artifact/c25b9435-7488-4fae-b889-109a581e17e4); baseline
  `docs/design/baseline_2026-11-14.json`; `scripts/build_design_motif.py` (coastline motif and
  mark, reproduces the tile's SVGs byte for byte).
- Records: TODO section VD (VD-1..VD-13); notes on UX-32, UX-13 and S3.7; ADR-VD-SPEC-2026-11-14;
  QUESTIONS VD-D1..VD-D8 (defaults in use); owner tasks H24 (optional) and H25.

## Not verified / left
- No visitor has seen the direction; fonts on macOS, iOS and Android were not measured.
- Unverified until VD-2: whether Framework copies CSS `url()` font files into `dist`.
- Unverified until VD-3: the Experts hash key for search (`search`, from the field name).
- Carried over: confirm the next scheduled `Daily works ingestion` run succeeds; UX-19 rows are
  recorded, not fixed (UX-32, now after VD-4); network hover, drag, wheel zoom and full screen
  not automated; UX-13 remainder (expert.html in the shell; URL state on Funding and
  Monitoring). Lighthouse SEO is now measured: 100 on all 12 routes (S3.8 can cite it).

## Next eligible
0. Confirm the next scheduled `Daily works ingestion` run succeeds.
1. VD-1, then VD-2, VD-3, VD-4 one at a time; then VD-5..VD-8 (up to 3 workers, disjoint
   files) with VD-9 before VD-7b and VD-10 before VD-6c; UX-32 after VD-4.
2. After H21/H23 answers: close S9.4 and S9.3. After H20b: close S3.8.
3. S5 chain (then EM-4 -> EM-8..13) after H9.

## Owner actions (details in `.agent/HUMAN_TASKS.md`)
- H24: look at the style tile; answer VD-D1..VD-D8 only where you disagree (defaults apply).
- Carried: H1 CORE key (daily), H2 work-relevance review, H21 network review, H23 institution
  pages + 10 expert profiles; optional H22 screen reader, H20b Bing + Rich Results, H18 sessions.
- QUESTIONS open: H16-STUBS, S9.3-NAMES, REL-TITLE, VD-D1..VD-D8.
