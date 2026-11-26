# Handoff — 2026-11-26 (end of Claude session) — ambassadors slice 3 live, global co-authors live, works graph and Works view, Add-on A4 groups layer through CG-6b

## State in one paragraph
All work is committed and pushed; the tree is clean. Sealed today, in order: AMB-1 front end slice 3 (local knowledge
forms, notification settings, co-author invitations; email links open settings and the reminder's case), BQ-V.1 slice 3
(global works similarity graph) and BQ-V.4 (Works view), WORKS-FILTER (slider and year range), REG-CA (California
region.json), AMB-COAUTHORS-GLOBAL (Worker route deployed, version cbc9e050, owner H54), Add-on A4 integration (CG-0;
spec docs/BFFP.md; A4-D0..D27, A4-C1..C11, A4-Q1..Q9) and CG-1, CG-2, CG-3, CG-4, CG-5, CG-8 (guide approved, H55),
CG-9, CG-13 (/groups page), CG-6a (Worker routes, NOT deployed), CG-6b (export and ingest), plus owner UI requests
AMB-NAV, AMB-CHOICE-CUES, AMB-FULLWIDTH. Every checkpoint passed the full gate in a clean worktree (latest 3,703
passed). Browser walks (mocked API, axe 0 at 1440/390) are scripts in scratch/ (ignored; e.g. scratch/trio_walk.py).

## In flight / next (in this order)
1. CG-6c: "Tag local groups" stream in the ambassador workspace (a new module like ambassador_knowledge.js): calls
   `GET /groups/batch?region=`, shows the leased groups (renew/release), the tagging form per docs/BFFP.md §5.4 and the
   approved guide docs/GROUPS_TAGGING_GUIDE.md (Tier 1 + evidence; activities 1-5; sector incl. joint_power_authority;
   no conflict-of-interest rule), posts `POST /submissions {stream: "knowledge", kind: "group_tag" | "group_suggest"}`.
   Validators: worker/src/groups.ts. Also apply QUESTIONS CG-NOT-ORG-REMOVAL (roster build drops not_an_organisation ids).
2. Then ask the owner for the Worker deploy (D1 migration 0007 group_leases + group routes):
   `cd worker && npx wrangler d1 migrations apply plastiverse-ambassadors --remote && npx wrangler deploy`.
3. CG-7 (review queue, double-tag sample, agreement stats), CG-10..CG-12b (tree, network, coverage/map/heat/comp,
   Sankey and others), CG-14, CG-15 pilot (owner), CG-16.
4. Owner-queued: AMB-PARENT-REGION (sub-region ambassadors also get country tasks; parent region + Worker deploy),
   AMB-MAIL-STYLE (styled emails; Worker deploy), ALERTS-GLOBAL (design first, owner review).
5. Roadmap: BQ-S9b, BQ-G3; rebuild site/data/global/denominators.json at the next global data refresh (owner).

## Open findings
- `tests/test_bq24_denominators.py::test_check_mode_on_committed_file_exits_zero` fails only on this machine's working
  tree (local ignored data); clean worktrees pass. Owner: rebuild at the next global refresh.
- BFFP data quirks (QUESTIONS BFFP-COUNTRY-ARTEFACTS): "eSwatini<" maps to no country; Afghanistan entries kept as
  listed. The member endpoint refuses scripted requests ("Origin not allowed"); `--fetch` uses one headless page view.
- A4-D24 binds code comments, docs, commit messages and CI logs: never write how many BFFP entries were dropped.
- Windows: write files with LF (`write_bytes(s.encode())`); `Path.write_text` writes CRLF (LESSONS 2026-11-26).
- Run pytest with `--basetemp` outside the repo when gating in a worktree (the AT-10 release test needs to be outside git).

## Owner actions (one line each)
- Try the live ambassador screens signed in (a knowledge item, a setting, the worldwide "Invite your co-authors" list).
- Accept or change the defaults in `.agent/QUESTIONS.md`: BFFP-COUNTRY-ARTEFACTS, CG-NOT-ORG-REMOVAL, A4-Q2..Q6, A4-Q8.
- H39 global gold labels; H28 OPC mapping; H42 PubMed misses; H2 low-confidence relevance (see HUMAN_TASKS).
- When CG-6c is ready: say "deploy the Worker" (migration 0007 + group routes).
