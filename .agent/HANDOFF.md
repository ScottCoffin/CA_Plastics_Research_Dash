# Handoff — 2026-11-18 (end of session) — GA-1..GA-3, PLAT-2d, LOGO-1 done; next PLAT-2b, VD-SM, PLAT-3/4

## State in one paragraph
The Global data app is live at https://plastiverse.live/explore (GA-1 design, GA-2 Framework build, GA-3 phone
menu and bigger phone map) and the landing links to it (PLAT-2d). The landing footer now shows the owner's logo
animation (LOGO-1). `docs/GLOBAL_EXPERTS_ASSESSMENT.md` is the $0 plan for global expert profiles; the owner
answered its decisions (QUESTIONS GX-*: threshold 3+ works, top-20,000 SEO pages, licensed Wikidata photos shown
automatically, OpenAlex author records as they are, R2 token reminder at GX-3). GX-1 waits on PLAT-4. Owner rule:
every spawned agent runs on Haiku (`model: haiku`); the project `Explore` agent override now runs on Haiku too.

## Done this session (commits on main)
- GA-1 `d2c01acf` design (Scope ladder), GA-2 `776c6aa3` /explore + explore data in the daily ingest,
  GA-3 `355cbbb9` phone menu/map + landing link + label removal + assessment, LOGO-1 (this commit).

## In flight / next (in this order)
1. PLAT-2b: live global evidence-map counts (cells approved, H30).
2. VD-SM: carry the Plastiverse Live system (reuse the /explore shell: header, scope ladder, tabs) into California.
3. PLAT-3 region abstraction, then PLAT-4 global ingest (unblocks GX-1..GX-7; remind the owner about the R2 token at GX-3).

## Open findings
- `/usage` items: the owner asked to fix what `/usage` flagged, showing each change first; the output was never
  pasted into the session. Ask for it.
- `tests/test_opc_actions_em17.py::test_committed_json_is_not_stale` fails locally only from the owner's
  uncommitted `curation/opc_mapping_review.csv` (H28 in progress); a clean worktree passes.
- `explore.json --check` goes stale when `build_metadata.json` counts change without a rebuild (daily ingest rebuilds both).
- `.agent/MEMORY.md` is about 290 lines (target 200); compact it at a quiet checkpoint.
- Untracked prototype images under `.impeccable/sketches/{brand,items,papers,scene}` are the owner's; leave them.

## Owner actions (one line each)
- Paste the `/usage` output (each fix is shown before it is made).
- H34: check /explore on a phone and the landing footer animation; reply "explore OK" or list changes.
- H28: review the 22 OPC mapping rows (`py -3.14 -m streamlit run scripts/review_opc_mapping_app.py`).
