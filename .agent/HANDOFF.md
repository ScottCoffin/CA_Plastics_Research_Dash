# Handoff — 2026-11-18 (night, late) — BQ-0/S8/R1/G0/G1/1.2/1.6/3.1, PLAT-2b v2, LIC-1/LIC-2 done; next BQ-S1, BQ-S9, BQ-G2

## State in one paragraph
This session sealed PLAT-2b (live landing evidence counts; v2 matches topic terms in titles only, owner
"stricter"), BQ-0 (A3 recon), BQ-S8 (operator-limit test), BQ-3.1 (network doc), BQ-G1 (gold 38/150),
BQ-1.2 (failure taxonomy), BQ-1.6 (count reconciliation), BQ-R1 ("Authors": `/california/authors` live,
redirect stub, terminology lint) and BQ-G0 (`guide_v3`, owner approved), plus LIC-1: code licence is now
PolyForm Noncommercial 1.0.0 (ADR-LICENSE-PFNC-2026-11-18; earlier releases stay MIT), and LIC-2: Atlas-made
data is CC BY-NC 4.0 (ADR-LICENSE-DATA-NC-2026-11-18; earlier data stays CC BY 4.0).
All owner A3 questions are answered. Every spawned agent runs on `model: haiku`; `[E]` tasks get a Haiku
read-only review (both reviews this session found real defects).

## In flight / next (in this order)
1. PLAT-2b v2 (`798fee8d`), LIC-1 (`4cd8db57`) and LIC-2 are pushed; confirm their CI and deploys.
2. Agent-only BQ tasks now eligible: **BQ-S1** (vocabulary register; feeds the guide_v3 candidate sets),
   **BQ-S9** stage 1 (PubMed coverage; NCBI key and email are in `.env` and CI secrets), **BQ-G2** (design
   freeze), **BQ-V.0** (Sigma benchmark), **BQ-S6** after BQ-S1, **BQ-G7** (quote-check Ashworth/Foellmer
   in Zotero PBHFXCHZ/ZE57F89A; labels already confirmed `incidental`).
3. **PLAT-4a** (raw global fetch, unpublished; cost estimate first), **VD-SM**, **PLAT-3**, **PLAT-4**.
4. Small follow-ups filed: CNT-1, CNT-2 (BQ-1.6 possible bugs), OA-2 (`run_at1_audit.py` bypasses the
   throttled client), NET-2 (`select_nodes` docstring vs code).
5. Refresh `docs/A3_SOURCES.md` for the other sources the owner added (only Ashworth and Peryman updated).

## Open findings
- `test_opc_actions_em17.py::test_committed_json_is_not_stale` fails locally only (owner's H28 CSV).
- `/usage` output never pasted. `.agent/MEMORY.md` is over 200 lines; compact at a quiet checkout.
- Ports 8833 and friends may have stale listeners; previews use 127.0.0.1 and a fresh port.
- Lesson: never chain `git push` after a gate; read the gate output first (LESSONS 2026-11-18).

## Owner actions (one line each)
- H28: review the 22 OPC mapping rows (`py -3.14 -m streamlit run scripts/review_opc_mapping_app.py`).
- Optional: re-open any of the five `review_optional` CA works in `curation/a3_lens_backfill.csv`.
- Paste the `/usage` output if you still want those fixes.
