# Handoff — 2026-11-18 (evening) — GA-3 phone layout + landing link done; GX assessment written

## State in one paragraph
`/explore` is live (GA-2). This checkpoint answers the owner's three asks: on phones the views moved into the side
Menu drawer and the map now fills about 75-82% of the screen (world as two stacked panes; a scoped map is a 3:5
portrait at about 70%); the landing links "Explore the data" from the header and under the regions map, and the
network beat's "illustrative" label is gone (PLAT-2d); and `docs/GLOBAL_EXPERTS_ASSESSMENT.md` says global expert
profiles can stay at $0 with PLAT-4 first, batch `/authors` metrics, sharded R2 files and top-N SEO pages (tasks
GX-1..GX-7). Pending outside the checkpoint: a proposed `.claude/agents/Explore.md` override on `model: haiku`
(shown to the owner, not created; waiting for "add Explore"); the owner's "fix what /usage flagged" needs the
`/usage` output, which was not in the session.

## Done this checkpoint
- GA-3a (Haiku): phone Menu drawer and two-pane map in `components/explore.{js,css}`, `explore.md`; lead: 3:5 portrait,
  `maptip` rename (Framework `.tip` collision), DESIGN.md app sections.
- GA-3b + PLAT-2d (Haiku): landing links, label removal, `/explore` in sitemap pages and `llms.txt`, tests; lead: spec lines.
- Lead: `docs/GLOBAL_EXPERTS_ASSESSMENT.md` (free-tier limits checked against provider pages 2026-11-18).

## In flight / next (in this order)
1. Owner: "add Explore" (agent override) and the `/usage` items (paste the output).
2. H34 owner look; H35 GX decisions.
3. PLAT-2b live evidence counts; VD-SM; PLAT-3; PLAT-4 (unblocks GX-1).

## Open findings
- `tests/test_opc_actions_em17.py::test_committed_json_is_not_stale` fails locally only from the owner's
  uncommitted `curation/opc_mapping_review.csv` (H28); a clean worktree passes.
- Global author counts in the assessment are estimates until PLAT-4 measures them.
- `.agent/MEMORY.md` is about 285 lines (target 200); compact at a quiet checkpoint.

## Owner actions (one line each)
- Reply "add Explore" (or edit the proposed text) and paste the `/usage` output.
- H34: check /explore on a phone; H35: GX decisions (or "defaults OK").
- H28: review the 22 OPC mapping rows (`py -3.14 -m streamlit run scripts/review_opc_mapping_app.py`).
