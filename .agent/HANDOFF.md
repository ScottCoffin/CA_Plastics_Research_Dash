# Handoff — 2026-11-26 — A4-POLICY

## Done

- The public community groups methods section credits Break Free From Plastic with permission. It keeps the Atlas independence statement. The lede describes the collective organisations and evidence the roster displays.
- The owner confirmed a 14-day removal window, 10 usable pairs per facet for agreement reporting, and a 100% review rate over an ambassador's first 25 primary group tags followed by 20%.
- AMB-POOL (4babd691) and GRP-NAME-FIX (0e2d8857) are live. Their CI and Pages runs passed. H57 Worker be02af19 uses D1 0007.

## State of the repo

- The group methods and agreement tests passed (95 focused tests). The clean-worktree gate passed (3,830 passed and 18 skipped).
- Agreement export CSVs are header-only. AMB-POOL stores incidental blind overlap tags. Deliberate 10% regional assignment is CG-7b.
- The owner's edits to curation/group_merges.csv are uncommitted.

## Next task

1. BFFP-REFRESH. Use the existing BFFP public About page and organization list. Preserve all established IDs, add new groups and rebuild the derived files. Run its manual GitHub Actions trigger and verify the result.
2. CG-7b. Implement the planned blind sample, reviewer checks, reason-coded edits and exports. H59 is required for D1 migration 0008 and its Worker deploy.

## Gotchas

- ENABLE_DATA_COMMITS is true on GitHub. Guard data commits with it and keep curation out of the scrape publish.
- The clean-worktree gate uses PYTHONPATH=<worktree>/src and a pytest --basetemp outside the repo.

## Needs owner input

- H59 and the open reviews in HUMAN_TASKS.
