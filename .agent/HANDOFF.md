# Handoff — 2026-11-26 (late) — Groups views, enrichment, parity plan and California contract

## Done this session (all pushed, CI green unless noted)

- CG-7b/7c live (H59: D1 0008, Worker 5a5f52e9); GRP-REVIEW-APPLY; FAVICON-MAIN; AMB-ROSTER-QC (H60: Worker b2e7b4b5); H62 owner merges committed.
- GRP-ENRICH (H61 suggestions OK, ADR-GRP-ENRICH): slice 1 `suggestions.json` (Wikidata, 319 groups), slice 2 form hints + register links + methods attribution, slice 3 `register_suggestions.json` (IRS EO BMF, 190 US groups, NTEE hints). Register licences: IRS and CRA usable; UK and ACNC need a manual wording check; BE, NO, IN not used.
- CG-12 and CG-12b: /groups coverage + map, heatmaps, two-level treemap, evidence panel, flows, participation, combinations, languages (browser-verified with a fixture, axe 0 at 1440/390).
- GP-0 `docs/GLOBAL_PARITY.md` (21 rows, slices GP-2..GP-10); GP-1 `scripts/check_gp1_contract.py` + `config/gp1_california_contract.json` (17 routes, 257,265 links, 0 broken).
- Owner direction recorded as GP-GROUPS (ADR-GP-GROUPS-2026-11-26): groups map first, /explore-style drill-down, scoped views, shared look.

## State

- Production: Worker b2e7b4b5, D1 0008. Strict clean-worktree gate 4,013 passed at 60b69558.

## Next tasks (eligible, in order)

1. GRP-ENRICH slice 3b: show `register_suggestions.json` hints (registered name, EIN link to IRS, ruling year, NTEE-derived sector/activity hints labelled as hints) in the form's suggestions box, like slice 2.
2. GP-2 (author list + profile per region, L) per docs/GLOBAL_PARITY.md section 4; run `scripts/check_gp1_contract.py --site <assembled>` before and after.
3. GP-GROUPS after GP-2 or alongside, reusing explore.js shell patterns.

## Gotchas

- Tests run on Linux CI: use `sys.executable`, never `py` (LESSONS). Chart views: verify in Chromium with a populated fixture (`scratch/cg12_smoke.py`), node stubs miss Plot/d3 issues (LESSONS).
- `build_groups_roster.py --check` needs `--incremental` locally; a hand commit of group_merges.csv needs `build_roster_qc.py` rerun.

## Needs owner input

- None new. Open: H39, H28, H42, H2, H9; H58 optional. Manual check of the UK Charity Commission and ACNC licence wording (pages returned 403 to the agent).
