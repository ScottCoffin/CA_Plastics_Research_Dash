# Handoff — 2026-11-26 — CG-11, group form redesign, roster QC

## Done

- H56: D1 migration 0007 was applied and Worker `cb95ec35` deployed (commit `94b46e36`). CG-6 is closed.
- CG-11: the Network section on `/groups`. A build-time layout lives in `groups_graph.json`. It shows an empty state until groups are tagged.
- AMB-GROUPS-UX (owner feedback): tagging a group now takes 4 clicks, 3 selects and one quote.
  - Tooltips on lease actions.
  - Compact activity chips and plain labels (`group_labels.js`).
  - Place and language pickers by name, with prefills.
  - One evidence block, and "Their pages do not mention plastics" for incidental or none.
  - Auto-advance to the next group.
  - Suggest a missing group has its own card (stream E).
- GRP-NAME-CLEAN and GRP-ROSTER-QC: display-name cleaning, HTML decode, placeholder quarantine, and same-country legal-form and punctuation merges. The roster went from 2,708 to 2,673 records; ids of kept records are unchanged. `scripts/review_group_roster_app.py` writes `curation/group_merges.csv` and `curation/group_name_corrections.csv`.
- GRP-NAME-FIX backend: `name_correction` on group_tag (Worker validator, export CSV, applied by the roster and group builds). **The Worker is not deployed and the form has no name field yet.**

## Verification

- Gate in the main checkout: ruff lint and format, design tokens, public text, `build_groups.py --check`, `build_groups_roster.py --check`, links, A1-A4 scaffolds, `git diff --check`, Worker `tsc` and 206 tests.
- Clean-worktree pytest result: see SESSION_LOG.
- Browser walks (mocked, offline): CG-11 54/54 and form 130/130. Axe was 0 at 1440 and 390 px. The lead read the screenshots and fixed two CSS specificity bugs that the walks missed.

## Next task

1. When the owner answers H57 ("deploy the Worker"): run `npx wrangler deploy` in `worker/`, check `/groups/*` 401s live, then add the optional "Correct the name" field to `ambassador_groups.js` (payload `name_correction`).
2. When the owner answers H58: run `py -3.14 scripts/build_groups_roster.py` (offline), then `py -3.14 scripts/build_groups.py`, `--check`, and commit the curation CSVs and rebuilt files.
3. Otherwise CG-7 (now eligible), then CG-12, CG-12b, CG-14, CG-16; then AMB-PARENT-REGION, AMB-MAIL-STYLE, ALERTS-GLOBAL, BQ-S9b, BQ-G3.

## Claude Code entry

Start with [CLAUDE.md](../CLAUDE.md). The owner wants Haiku workers for every bounded task (memory: delegate-to-haiku-first). Tell browser-check workers to read their screenshots. See [resume prompt](RESUME_PROMPT.md).

## Gotchas and owner input

- Harnesses (ignored): `scratch/cg11_walk.py` and `scratch/ambux_walk.py` (build `framework/dist-ambux` first). `scratch/cg6c_walk.py` is outdated.
- `groups.js` keeps its own centrality wording, so the public card and the form differ slightly. A small follow-up could switch it to `groupLabel`.
- Open owner items: H57, H58, H39, H28, H42 and H2 in [human tasks](HUMAN_TASKS.md).
