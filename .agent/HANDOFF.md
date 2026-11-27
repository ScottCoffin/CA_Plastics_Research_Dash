# Handoff — 2026-11-26 — Group pool, name corrections and weekly BFFP refresh

## Done

- AMB-POOL (4babd691) uses invisible two-hour holds. The active form refreshes them every 15 minutes. Retired renew and release routes return 404. Any accepted tag closes ordinary assignment globally, including after moderation rejection. The first accepted tag is the canonical candidate. Later tags from different ambassadors stay private as blind agreement records.
- H57 deployed Worker be02af19-ebc2-4425-bc43-17a887aaf563 using D1 0007. Both retained batch requests returned 401 without a session. The live Ambassadors page serves GRP-NAME-FIX (0e2d8857). Approved corrections retain the group ID. Approved non-organisation removals omit the proposed name and clear that ID's earlier correction.
- The live Community groups page credits Break Free From Plastic with permission and confirms removal within 14 days for requests from a group's own domain (9dfd18d9). The owner confirmed 10 usable pairs per facet for agreement reporting and review of each ambassador's first 25 primary group tags, then a random 20%.
- BFFP-REFRESH (ae073190, 7da916ce) runs Sundays at 08:43 UTC. It admits new groups, preserves established IDs and dates, honours reviewed same/different decisions and applies approved name changes and removals. It stages only the checked roster, manifest and six derived JSON files. The first manual run timed out. The retry fetched and validated successfully and found no changed data. [Hosted verification](https://github.com/ScottCoffin/CA_Plastics_Research_Dash/actions/runs/45917107414)

## State of the repo

- 211 Worker tests passed. The clean-worktree Python gate passed with 3,835 passed and 18 skipped. The Framework build passed with four existing feed-link warnings. Desktop and phone Chromium checks for tagging and name corrections passed with zero axe violations.
- AMB-POOL and name corrections passed CI and Pages. Public source and removal wording was verified on the live site. The weekly workflow uses ENABLE_DATA_COMMITS, which is true.
- curation/group_merges.csv contains the owner's uncommitted decisions. It has stayed outside every index and commit. Both agreement curation CSVs are still header-only.

## Next task

1. CG-7b. Read docs/BFFP.md sections 5.2 and 7 and the A4 decisions before editing. Draft migration 0008 and the Worker changes for deliberate blind assignment to a different active ambassador in the same region. Randomly select 10% of primary tags per region. Keep AMB-POOL's first-wins tag and private second_tag_for link. The current Worker collects overlap records when two ambassadors happen to submit the same group. Record whether each pair came from the deliberate sample or an overlap in the private audit.
2. Add reviewer selection for each ambassador's first 25 primary group tags and a random 20% thereafter. Preserve the original and reviewed values with a reason code. Deliver group_double_tags.csv and group_reviews.csv using the existing CG-7a contracts. Preserve the 10-usable-pair minimum per facet and keep ambassador identifiers private. Test the assignment and decision races and the export.
3. H59 is required before applying D1 migration 0008 or deploying the CG-7b Worker. While production awaits approval, use any eligible offline work or continue AMB-ROSTER-QC, then FAVICON-MAIN. Keep one checkpoint at a time.

## Gotchas

- Read CLAUDE.md and spec.md Part B. Use a clean worktree with PYTHONPATH=<worktree>/src and an external pytest --basetemp. The main checkout's ignored denominators input can fail the otherwise green BQ-2.4 check.
- The BFFP browser reads the member request initiated by BFFP's public About page. The task uses the incremental CLI. A hosted timeout reports the About-page and member-request stages. Public data commits preserve baseline IDs and use a fast-forward push.

## Needs owner input

- H59 in HUMAN_TASKS for the CG-7b migration and deploy. Other open reviews include H39, H28, H42, H2 and H9. H58 is optional.
