# Handoff — 2026-11-18 (later) — GA-2 /explore built; next owner look (H34) and the landing link

## State in one paragraph
The owner approved the GA-1 Global data app prototype ("global app OK"). GA-2 ported it into Framework as the
global page `/explore` (spec `docs/GA_2_BUILD_SPEC.md`), with committed data from two new pipeline scripts
that also run in the daily ingest. Acceptance on the assembled deploy: axe 0 on 10 views at 1440/390/375 and the
1024 world view, no console errors, no horizontal overflow. Haiku finish review: fix (5) then ship on all 5
(seed verified; footer and map box were capture artifacts; table margin reset; phone tab-row fade cue).
The page is not linked from the landing yet (QUESTIONS GA-LANDING-LINK; landing edits held).

## Done this checkpoint
- GA-2a (Haiku): `scripts/fetch_global_explore_sample.py`, `scripts/build_global_explore.py [--check]`,
  `site/data/global/explore{,_sample}.json`, `tests/test_global_explore_data.py`, `docs/api_notes/global_explore.md`.
  Lead fixes: California works read from `build_metadata.json`; a country's last map cell is never taken (Israel).
- GA-2b (Haiku): `framework/src/explore.md`, `components/explore.{js,css}`, `tests/test_ga2_explore.py`,
  `check_at5.py` GLOBAL_PAGES. Lead fixes: js fence blank line (page never mounted), footer link underline,
  table header text, Framework table/link overrides, phone tab fade.
- Daily ingest refreshes and commits both explore files (`.github/workflows/ingest_works.yml`).

## In flight / next (in this order)
1. H34: owner checks https://plastiverse.live/explore after the deploy; answer GA-LANDING-LINK.
2. PLAT-2d + landing link (when landing edits are allowed), PLAT-2b live evidence counts.
3. VD-SM (reuse the /explore shell for California), PLAT-3, PLAT-4 (fills every country profile), NOR-1..5.

## Open findings
- `tests/test_opc_actions_em17.py::test_committed_json_is_not_stale` fails locally only from the owner's
  uncommitted `curation/opc_mapping_review.csv` edit (H28); clean worktree passes.
- `explore.json --check` goes stale whenever `build_metadata.json` counts change without a rebuild (the daily
  ingest rebuilds both).
- `/explore` is not in the sitemap or `llms.txt` yet; add with the landing link.
- Global query precision: off-topic newest-works titles are hidden in the preview.
- `.agent/MEMORY.md` is about 280 lines (target 200); compact at a quiet checkpoint.

## Owner actions (one line each)
- H34: open https://plastiverse.live/explore after this deploy and reply "explore OK" or list changes.
- GA-LANDING-LINK: reply "link it" to add "Explore the data" to the landing header and regions band (a landing edit).
- H28: review the 22 OPC mapping rows (`py -3.14 -m streamlit run scripts/review_opc_mapping_app.py`).
