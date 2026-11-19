# Handoff — 2026-11-19 — LAND-1 sealed; LAND-2 (landing logo intro) next

## State in one paragraph
Owner asked for three landing fixes (2026-11-19). LAND-1 is sealed: the story stage is full bleed at
every width (Framework `layout.css` capped `body` at 1440 px), the header Regions control has no box and
keeps its caret, and the gate exposed a PLAT-2b contrast bug in the evidence table (white numerals on
60-88% slate), fixed by capping the ramp at 70% slate with ink text. LAND-2 (logo MP4 intro before the
picnic story, 2x scroll cue with animated arrow, 2x skip link) is next.

## In flight / next (in this order)
1. LAND-2 (TODO). Then confirm CI and the deploy for LAND-1 and LAND-2.
2. Agent-only BQ tasks: BQ-S1, BQ-S9 stage 1, BQ-G2, BQ-V.0, BQ-S6 after BQ-S1, BQ-G7.
3. PLAT-4a, VD-SM, PLAT-3, PLAT-4. Follow-ups CNT-1, CNT-2, OA-2, NET-2.

## Open findings
- `test_opc_actions_em17.py::test_committed_json_is_not_stale` fails locally only (owner's H28 CSV).
- `.agent/MEMORY.md` is over 200 lines; compact at a quiet checkout.
- Previews: 127.0.0.1 and a fresh port (stale listeners on 8781/8791/8794/8833).

## Owner actions (one line each)
- H28: review the 22 OPC mapping rows (`py -3.14 -m streamlit run scripts/review_opc_mapping_app.py`).
- H2: 277 low-confidence work-relevance decisions (`scripts/review_work_relevance_app.py`).
