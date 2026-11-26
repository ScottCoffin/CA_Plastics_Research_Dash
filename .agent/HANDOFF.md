# Handoff — 2026-11-26 — H56 deploy (CG-6 closed)

## Done

- Owner authorized H56. D1 migration 0007 (`group_leases`) was applied to the remote `plastiverse-ambassadors` database, and `npx wrangler deploy` published Worker version `cb95ec35` to api.plastiverse.live (cron unchanged).
- CG-6 is closed. CG-7 (review queue, audit log, agreement statistics) is now dependency-satisfied.

## Verification

- `npm test` in `worker/` before deploy: 202 passed (14 files).
- Production: `GET /groups/batch`, `POST /groups/renew` and `POST /groups/release` answer 401 `not_signed_in` without a session; `PUT /groups/batch` answers 405; an unknown `/groups/*` path answers 404. Remote D1 lists `group_leases` and `group_leases_ambassador_id`. `wrangler d1 migrations list` showed only 0007 pending before the apply.
- Not executed: a signed-in production walk of the Tag local groups task (needs a real ambassador session). The offline browser gates from CG-6c cover the flow.

## Next task

1. CG-11: read [BFFP V-NET](../docs/BFFP.md) §9.4 and T-GRAPH, the `groups_graph.json` builder, and `framework/src/components/graph_viewer.js`. Add the group-to-facet view, quoted stated affiliations and the labeled tag co-occurrence projection. Keep edge types distinct and reuse the group card.
2. CG-7 (now eligible), then CG-12, CG-12b, CG-14, the owner-led CG-15 pilot and CG-16 as dependencies permit. Then AMB-PARENT-REGION, AMB-MAIL-STYLE, ALERTS-GLOBAL, BQ-S9b and BQ-G3.

## Claude Code entry

Start with [CLAUDE.md](../CLAUDE.md) for the worker-role mapping and Windows commands. Delegate bounded work to Luna workers when possible. The lead owns clean-worktree verification, the handoff files, and each narrow commit and push. See [resume prompt](RESUME_PROMPT.md).

## Gotchas and owner input

- Gate with pytest `--basetemp` outside the repository. The ignored local data can make the denominator check fail in the main checkout, while clean worktrees pass.
- A4-D24 binds published assets, docs, commits and CI logs. Group defaults and country artefacts are in [questions](QUESTIONS.md).
- Optional owner check: sign in at plastiverse.live/ambassadors and open Tag local groups once to confirm a batch loads in production.
- The existing H39, H28, H42 and H2 reviews are in [human tasks](HUMAN_TASKS.md).
