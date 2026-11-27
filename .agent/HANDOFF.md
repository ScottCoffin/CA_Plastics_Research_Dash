# Handoff — 2026-11-26 — BFFP-REFRESH awaiting live verification

## Done

- The weekly BFFP refresh is implemented with additive admission, stable IDs and approved curation precedence. The workflow runs Sunday 08:43 UTC or by manual dispatch. It checks the roster and six derived files before publishing.
- Local live browser probe received a valid organisation list from BFFP's public About page. Clean-worktree tests passed with 3,835 passed and 18 skipped. Focused roster, admission and build tests passed (202).
- Hosted run 45916544490 timed out before publication. The updated browser waits for navigation to commit and reports the page and API stages on timeout. The revised local live probe and clean gate passed. Repeat the hosted dispatch on the updated commit.
- AMB-POOL, GRP-NAME-FIX and A4-POLICY passed CI and Pages. Worker version be02af19 uses the existing D1 schema. The published Ambassadors page serves the name correction field.

## Next task

1. Run and confirm the manual BFFP Actions dispatch from main. If it writes a bot commit, verify only expected group JSON paths and fast-forward before sealing.
2. CG-7b needs the deliberate 10% sample per region, reviewer checks, reason-coded audit and public CSV export. H59 is required before migration 0008 and the related Worker deploy.

## Gotchas

- Keep curation/group_merges.csv unstaged. It holds uncommitted owner decisions.
- The clean gate uses PYTHONPATH=<worktree>/src and pytest --basetemp outside the repository. ENABLE_DATA_COMMITS is true on GitHub.

## Needs owner input

- H59. See HUMAN_TASKS for the other owner reviews.
