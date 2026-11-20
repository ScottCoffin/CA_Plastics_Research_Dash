# Handoff — 2026-11-19 — LAND-1..4 sealed (owner landing fixes); next BQ-S1, BQ-S9, BQ-G2

## State in one paragraph
Owner asked for three landing fixes (2026-11-19); all are done. LAND-1 (deployed, `63726b95`): the story
stage is full bleed at every width (Framework `layout.css` capped `body` at 1440 px), the header Regions
control has no box and keeps its caret, and an evidence-table contrast bug (white numerals on 60-88%
slate) is fixed by capping the ramp at 70% slate with ink text. LAND-2: the landing opens with the logo
MP4 centred at 50% of the view height on black, plays once and holds on the logo (it stops at 5.6 s
because the MP4 fades to black at the end), with a 2x scroll cue and animated arrow bottom-left and a 2x
skip link; poster only under reduced motion. LAND-3 (owner follow-up): the logo is 2x (box `min(100vh, 105vw)`), LAND-4 (owner follow-ups): the intro plays once at 1.2x, holds on the full logo (pauses at 5.6 s media time, before the clip's fade to black), has no pause control (~4.7 s of motion), and clips the "plastiverse.live" tagline.

## In flight / next (in this order)
1. Confirm CI and the deploy for LAND-4 (LAND-1..3 deployed and verified live).
2. Agent-only BQ tasks: BQ-S1, BQ-S9 stage 1, BQ-G2, BQ-V.0, BQ-S6 after BQ-S1, BQ-G7.
3. PLAT-4a, VD-SM, PLAT-3, PLAT-4. Follow-ups CNT-1, CNT-2, OA-2, NET-2.

## Open findings
- The footer logo MP4 loops through the clip's ~1.2 s fade to black (pre-existing, LOGO-1). Options: hold
  the footer the same way as the intro, or regenerate the MP4 to end on the logo (owner's
  `src/create_plastiverse_animation.py`).
- The footer and intro logo toggles differ: the footer still sets `aria-pressed` and changes its label.
- The Framework build warns that two links to `/feed.xml` (from /explore and /index) are broken; the feed
  is copied at assembly, so this is likely a build-time-only warning. Not checked against the baseline.
- `test_opc_actions_em17.py::test_committed_json_is_not_stale` fails locally only (owner's H28 CSV).
- `.agent/MEMORY.md` is over 200 lines; compact at a quiet checkout.
- Previews: 127.0.0.1 and a fresh port (stale listeners on 8781/8791/8794/8833/8871).

## Owner actions (one line each)
- H28: review the 22 OPC mapping rows (`py -3.14 -m streamlit run scripts/review_opc_mapping_app.py`).
- H2: 277 low-confidence work-relevance decisions (`scripts/review_work_relevance_app.py`).
- Optional: should the footer logo also drop the tagline, play once, or skip the clip's fade to black?
