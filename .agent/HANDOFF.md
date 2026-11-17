# Handoff — 2026-11-16 — Visual design checkpoints VD-9..VD-17, UX-32

## Done this run (all deployed, CI + Pages green)
- VD-10 labels, VD-13 Overview counts, VD-9 colour system (ADR-VD9-PALETTE), VD-14 network CLS fix,
  VD-6c Institutions, VD-7b Funding, VD-11 classic/SEO pages, UX-32 accessibility rows,
  VD-15 context-page headers, VD-16 Evidence Chart/Table, VD-17 0 stylesheet hex literals.
- VD-12 machine part: `scripts/design_snapshots.py` + `docs/VD_12_VERIFICATION.md`; owner review H25 pending.
- Fixes found on the way: `check_s3_8.py` DOI false positive (deploy step was silently failing),
  `check_s3_5.py` counts subset, two `ux19_a11y_pass.py` false positives, ux_tasks task 5 opens More filters.
- Last full gate (clean worktree): 1,791 passed / 13 skipped; Ruff, links, scaffolds, token (0), public text.
- Every verification doc: `docs/VD_{9,10,13,14,6C,7B,11,15,16,17,12}_VERIFICATION.md`, `docs/UX_19_ACCESSIBILITY_PASS.md`.

## Repository state
- `main` pushed; the last commit is the records commit for this handoff (verify `origin/main`).
- `labels.js` and `palette.js` are force-tracked in gitignored `framework/src/components/shared/`.
- Owner's `.agent/QUESTIONS.md` formatting edit is still uncommitted (only the VD-D9 row was committed).

## Open findings
- Live Lighthouse performance on experts/institutions/institution is below the 2026-11-14 baseline in
  single runs; a same-machine A/B shows no cost from VD-6c/VD-7b; unchanged /policy shows ~0.6 s host drift.
- VD-5 LCP gate (1.1 s) vs live 1.9-2.0 s: owner question VD-D9.
- Classic `expert.html` has no sprite icon (moves into the shell with UX-13).
- `scripts/check_s3_1.py` fails on pinned fixture counts at HEAD (not in CI).
- At 390 px a second pointer click on the header menu button is blocked by the open sidebar (pre-existing).

## Next eligible
- UX-13 remaining (expert.html into the app shell; URL-saved state on Funding and Monitoring).
- VD-12 closes when the owner answers H25. Most other open TODO items are owner-gated (labelling,
  reviews, decisions) or wait on S5 (S3.7 hero is "do last").

## Owner actions (one line each)
- H27: enable GitHub Pages "Enforce HTTPS".
- H26: Land to Sea Microplastics Consortium link.
- H2: review the 277 low-confidence work-relevance decisions.
- H25: final design review (steps in HUMAN_TASKS).
- VD-D9: keep the 1.1 s Overview LCP target, or use the relative gates?
