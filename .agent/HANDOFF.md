# Handoff ? 2026-11-26 ? AMB-POOL and H57

## Done

- The Worker atomically claims untagged groups with a two-hour hold. The open form refreshes its own hold every 15 minutes, and the release and renew controls and routes were removed.
- Any accepted tag closes primary assignment globally. The first accepted tag is the canonical candidate. Later tags from other ambassadors are privately linked for agreement and the form advances after acknowledging the second tag.
- H57 deployed Worker version be02af19-ebc2-4425-bc43-17a887aaf563 using the existing D1 schema. Both retained batch requests returned 401 without a session and both retired routes returned 404.

## State of the repo

- 211 Worker tests passed, including 46 focused group cases. Typecheck and Worker dry run passed.
- Clean-worktree pytest passed with 3,829 passed and 18 skipped. The main checkout's ignored denominators input triggers a stale BQ-2.4 check. The clean checkout passed that test.
- The Framework build passed with four existing feed-link warnings. The mocked Chromium tagging flow passed at 1440 and 390 px with axe showing zero violations.
- The owner's uncommitted changes to curation/group_merges.csv stay in the main checkout.

## Next task

1. GRP-NAME-FIX. Add the optional Correct the name field to the existing tagging form. H57 deployed its validator. Preserve the stable group ID and verify draft and payload behavior.
2. Record the owner?s A4 decisions and implement the weekly BFFP refresh with stable roster IDs and additive admission.
3. Implement CG-7b for the regional 10% random sample and agreed review fractions. Both agreement curation CSVs are still header-only. H59 is required for migration 0008 and the follow-on Worker deploy.

## Gotchas the next agent must know

- Use PYTHONPATH=<worktree>/src with pytest --basetemp outside the repo. The direct Python 3.14 path in LESSONS works if WindowsApps py is inaccessible.
- Keep second_tag_for private. The submission receipt and the ambassador's own history expose a boolean second_tag only.
- D1 migration 0007 and the old renewals column remain in place. H57 needs no schema change.

## Needs owner input

- H59 for migration 0008 and the CG-7b deploy. Also see the open review items in HUMAN_TASKS.
