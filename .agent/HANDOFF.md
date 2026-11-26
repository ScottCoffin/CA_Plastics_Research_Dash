# Handoff — 2026-11-26 — CG-6c and CG-10

## Done

- CG-6c (`ee1b3819`) adds the signed-in **Tag local groups** workspace, lease actions, evidence and suggestions. Approved group removals update the roster and derived files in one reviewed export pull request. GitHub CI and Pages deployment passed.
- CG-10 adds the keyboard-operable tree on `/groups`. Geography opens at region level. Function and plastics-focus views support all-activities placement with distinct organisation counts. Tree search and disclosure state share the URL hash with the existing roster and group card.
- The tree builder adds `hierarchies_all_activities` to `cg-tree-v1`. Explicit `US-CA` place evidence puts tagged US records under California. Untagged records remain aggregated by country.

## Verification

- CG-10 clean-worktree suite: 3,714 passed and 17 skipped. Ruff lint and format, design tokens, and all six group assets passed their checks.
- The mocked Framework walk passed at 1440 and 390 px. It exercised keyboard navigation, expanded views, hash roundtrip, group-card and roster navigation, and distinct counts. Axe, page errors, and document and tree overflow were zero. The 5,000-group fixture rendered in 0.23 s on this checkout.
- Ignored browser harnesses and screenshots are in `scratch/cg6c_*` and `scratch/cg10_*`. Use the current committed files as the base for each clean gate.

## Next task

1. H56 still requires the owner's explicit approval. When authorized, apply D1 migration 0007 for `plastiverse-ambassadors` under `worker/`, deploy the group routes, and verify production. CG-6 can then close and unlock CG-7 review and agreement work.
2. While H56 is pending, take CG-11. Read [BFFP V-NET](../docs/BFFP.md) §9.4 and T-GRAPH, the `groups_graph.json` builder, and the existing `framework/src/components/graph_viewer.js`. The task adds the group-to-facet view, quoted stated affiliations, and the labeled tag co-occurrence projection. Keep edge types distinct and reuse the existing group card.
3. Follow with CG-12, CG-12b, CG-14, the owner-led CG-15 pilot, and CG-16 as dependencies permit. Then resume AMB-PARENT-REGION, AMB-MAIL-STYLE, ALERTS-GLOBAL, BQ-S9b, and BQ-G3.

## Claude Code entry

Start with [CLAUDE.md](../CLAUDE.md) for the worker-role mapping and Windows commands. Delegate bounded work to Luna workers when possible. The lead owns clean-worktree verification, the handoff files, and each narrow commit and push. See [resume prompt](RESUME_PROMPT.md).

## Gotchas and owner input

- Gate with pytest `--basetemp` outside the repository. The WindowsApps launcher was inaccessible here, and the direct Python 3.14 executable worked. The ignored local data can make the denominator check fail in the main checkout, while clean worktrees pass. Rebuild denominators at the next global refresh.
- A4-D24 binds published assets, docs, commits and CI logs. Group defaults and country artefacts are in [questions](QUESTIONS.md). The upstream member endpoint uses the approved headless page workflow.
- H56 and the existing H39, H28, H42 and H2 reviews are in [human tasks](HUMAN_TASKS.md). The earlier authenticated smoke still asks for a knowledge item, a setting, and the global co-author invitation list.
