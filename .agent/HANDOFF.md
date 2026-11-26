# Handoff — 2026-11-26 — CG-6c

## Done

- The signed-in ambassador workspace has a **Tag local groups** stream for regional assignments. It supports lease renewal and release, organisation checks, Tier 1 evidence, optional Tier 2 fields, stated affiliations, and suggestions. The workspace preserves drafts on retry and keeps group submission history with the group task.
- Approved `not_an_organisation` rows are applied to the public roster and its manifest. The ambassador export workflow rebuilds and checks the roster and derived group files in the same owner-reviewed pull request. See [Ambassador export](../docs/AMBASSADOR_EXPORT.md).
- The clean-worktree full suite passed with 3,712 tests and 17 skips. The Framework build and mocked browser walk passed at 1440 and 390 px, with zero axe violations, overflow, or page errors. The ignored walk and screenshots are in `scratch/cg6c_*`.

## State of the repo

- CG-6a, CG-6b and CG-6c are implemented. CG-6 still requires production D1 migration 0007 and deployment of the group routes in `worker/src/groups.ts` under H56.
- The live Worker already serves existing ambassador flows and global co-authors (version cbc9e050, owner H54). The new group screen handles the pre-deployment 404 and can retry.

## Next task

1. When the owner authorizes H56, apply migration 0007 for `plastiverse-ambassadors` under `worker/`, deploy the Worker, and verify the group routes. Mark CG-6 complete once the production gate passes.
2. CG-7 follows CG-6 and covers the review queue, double tagging, and agreement statistics. While H56 is pending, CG-10 is eligible through CG-9. Continue with CG-11, CG-12, CG-12b, CG-14, the owner-led CG-15 pilot, and CG-16 as their dependencies permit.
3. Owner-queued tasks after the groups work are AMB-PARENT-REGION, AMB-MAIL-STYLE, and ALERTS-GLOBAL. The handoff roadmap then calls for BQ-S9b and BQ-G3.

## Gotchas

- The local ignored data can make `tests/test_bq24_denominators.py::test_check_mode_on_committed_file_exits_zero` fail in the main checkout. The clean gate passes. Rebuild `site/data/global/denominators.json` at the next global refresh.
- On this Windows checkout the direct Python 3.14 executable worked where the WindowsApps launcher could not run. Gate in a clean worktree with pytest `--basetemp` outside the repo. See [memory](MEMORY.md).
- The BFFP country defaults are in [questions](QUESTIONS.md). A4-D24 applies to published artifacts, docs, commit messages, and CI logs. The upstream member endpoint requires the already approved headless page workflow.

## Owner input

- H56 in [human tasks](HUMAN_TASKS.md) records the Worker deployment approval. The existing owner reviews include H39, H28, H42 and H2. Group decisions are in [questions](QUESTIONS.md).
- The earlier authenticated smoke still calls for trying a knowledge item, a setting, and the global co-author invitation list.
