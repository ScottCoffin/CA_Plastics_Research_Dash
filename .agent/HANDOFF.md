# Handoff — 2026-11-26 — GRP-NAME-FIX

## Done

- The optional Correct the name field sends name_correction with an organisation tag and keeps its draft across navigation and retries. H57 previously deployed the Worker validator.
- An approved non-organisation removal drops the proposed name and clears any older name correction for that ID. Other groups' names and all group IDs stay intact.
- AMB-POOL is on main at 4babd691. CI and Pages both succeeded. Worker be02af19 uses D1 0007.

## State of the repo

- Focused Python checks passed (98 tests). Clean-worktree pytest passed (3,830 passed and 18 skipped). Framework build passed with four existing feed-link warnings.
- Chromium checks passed at 1440 and 390 px, including invalid input focus, per-group drafts, retry and axe.
- The owner edits in curation/group_merges.csv remain uncommitted.

## Next task

1. Record the owner's A4 decisions. Use a short public BFFP permission acknowledgement and record the approved 14-day removal, 10-pair reporting minimum and reviewer sampling.
2. Implement the weekly BFFP refresh. Use the existing extractor, preserve all prior IDs, apply curated names and removals, and publish additive changes through GitHub Actions.
3. CG-7b introduces the regional 10% blind second-tag sample, reviewer sampling and the paired export. H59 is required for migration 0008 and the Worker deploy.

## Gotchas the next agent must know

- Set PYTHONPATH=<worktree>/src and put pytest --basetemp outside the repo. Main checkout denominator inputs can make the BQ-2.4 check stale.
- ENABLE_DATA_COMMITS was checked on GitHub and is true. Stage only the specific checkpoint paths.
- Both agreement curation CSVs are still header-only. AMB-POOL stores collision tags privately.

## Needs owner input

- H59 for the CG-7b migration and Worker deploy. See HUMAN_TASKS for the other open reviews.
