# Handoff — 2026-11-18 — GA-1 Global data app design done; next H33 owner look, then GA-2

## State in one paragraph
The owner asked for the Global site's interactive app (non-region data) designed with Impeccable on the
landing's post-story look; the landing stays untouched and California's redesign is deferred. GA-1 is done:
the owner chose the "Scope ladder" structure with a steer (no desktop sidebar, local-atlas indicator inside the
map and the table, bigger world map). The working prototype `.impeccable/sketches/global_app.html` uses real
OpenAlex data (ADR-GA-LAYOUT-2026-11-18). Finish review: fix (8 items) then ship on all 8; axe 0 on 6 views
at 1440 and 390; DESIGN.md merged (owner choice) with the app shell, type steps and components.

## Done this checkpoint
- GA-1: decision round (3 dealt structures), direction contract `.impeccable/surfaces/impeccable-sketches-global-app-html.md`,
  prototype + data module (`.impeccable/sketches/src/build_global_app_data.py`, `fetch_global_app_sample.py`:
  35 requests, 350 credits, raw in ignored `data/raw/global_app_sample/`), finish review, DESIGN.md + design.json.
- Owner answers recorded: H29 Buttondown done, H32 sitemap resubmitted, H30 cells approved (PLAT-2b eligible),
  PLAT2-NETWORK "remove the illustrative label" (queued as PLAT-2d; landing edit held).
- Owner rule (memory): every spawned agent runs on Haiku (`model: haiku`), Impeccable agents included.

## In flight / next (in this order)
1. H33: owner looks at the prototype; on "global app OK", GA-2 writes the build spec and builds the Framework pages.
2. PLAT-2b (eligible now: live evidence-map counts), PLAT-2d when landing edits are allowed again.
3. VD-SM (reuse the GA-1 shell for California), PLAT-3, PLAT-4, NOR-1..5.

## Open findings
- `tests/test_opc_actions_em17.py::test_committed_json_is_not_stale` fails locally only because of the owner's
  uncommitted edit in `curation/opc_mapping_review.csv` (H28 in progress); rebuild `opc_actions.json` after H28.
- Global query precision: recent-works samples include off-topic titles (for example "viral plasticity"); the
  prototype hides titles without "plastic". Country institution lists include foreign co-author institutions.
- DESIGN.md vs prototype: header sticky vs recorded fixed; mint text on the dark tooltip (Mint After Dark wording).
- `.agent/MEMORY.md` is about 280 lines (target 200); compact it at a quiet checkpoint.

## Owner actions (one line each)
- H33: open the prototype (steps in HUMAN_TASKS) and reply "global app OK" or list changes.
- H28: review the 22 OPC mapping rows (`py -3.14 -m streamlit run scripts/review_opc_mapping_app.py`).
