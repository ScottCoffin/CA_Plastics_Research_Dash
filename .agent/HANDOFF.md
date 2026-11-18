# Handoff — 2026-11-18 (night) — PLAT-2b live evidence counts; owner A3 answers recorded; next BQ-0 seal, BQ-S8, BQ-R1

## State in one paragraph
The landing evidence grid now shows live OpenAlex counts (PLAT-2b, `docs/PLAT_2B_VERIFICATION.md`): 30
one-query-per-cell counts a day (300 credits) from `config/evidence_cells.yml`, written to
`site/data/global/evidence_cells.json` by the daily ingest. The owner answered all A3 questions
(QUESTIONS A3-Q1..Q15): ADR-GOLD-GLOBAL accepted, person-level features kept, review-derived facets adopted
with a benchmark + caveat rule (A3-D21), no Module 5, standing approval for new dependencies (A3-D9),
NCBI key and email in `.env` and CI secrets, PLAT-4 split into PLAT-4a (early raw global fetch, unpublished)
and PLAT-4 (= PLAT-4b, after PLAT-3). H34 and H36 are done. Every spawned agent runs on `model: haiku`.

## Done this session
- A3-ANSWERS (`9236d710`) and the follow-up answers (in the PLAT-2b commit).
- PLAT-2b (this commit). "regulation" dropped from the solutions row (gene-regulation stem collision).

## In flight / next (in this order)
1. BQ-0 sealed (`docs/BQ_0_RECON.md`; licence string MIT; optional owner H41 NCBI registration).
2. **BQ-S8**, **BQ-R1** `[E]`, then the agent-only BQ tasks (BQ-G0 draft, BQ-G1, BQ-G2, BQ-S1, BQ-S9 stage 1,
   BQ-V.0, BQ-3.1, BQ-S6, BQ-1.2, BQ-1.6), **PLAT-4a** once BQ-0 is sealed, VD-SM, PLAT-3, PLAT-4.
3. Refresh `docs/A3_SOURCES.md` Zotero keys: the owner added the A3 sources they could obtain.

## Open findings
- PLAT2B-GAP (QUESTIONS): grid counts are title/abstract mentions; "policy"/"mitigation" in closing
  sentences inflate the solutions row. Default in use; owner may want stricter row terms.
- `test_opc_actions_em17.py::test_committed_json_is_not_stale` fails locally only (owner's H28 CSV).
- `/usage` output never pasted. `.agent/MEMORY.md` is over 200 lines; compact at a quiet checkpoint.
- Port 8833 on this machine has a stale listener; previews use 127.0.0.1 and a fresh port.

## Owner actions (one line each)
- H28: review the 22 OPC mapping rows (`py -3.14 -m streamlit run scripts/review_opc_mapping_app.py`).
- PLAT2B-GAP: reply "grid OK" or ask for stricter solutions/effects terms.
- Paste the `/usage` output if you still want those fixes.
