# Handoff — 2026-11-18 (late) — Add-on A3 integrated (52 BQ tasks); next PLAT-2b, then BQ-0/BQ-S8/BQ-R1, VD-SM, PLAT-3/4

## State in one paragraph
The owner's Add-on A3 spec (`docs/add_on_spec_3.md`: corpus quality, global-denominator trends,
collaboration structure, topic evolution, evidence-gap heatmap, Sigma.js views, search vocabulary and
taxonomy, "Authors" terminology, precision-goal-driven labelling, PubMed coverage QC) is now in the plan:
TODO section "BQ" (52 tasks, dependency-ordered), DECISIONS ADR-A3-INTEGRATION + registers A3-D0..D24 and
A3-C1..C14 + ADR-GOLD-GLOBAL (proposed) + ADR-A3-PUBMED, QUESTIONS A3-Q1..Q15 (defaults in use),
HUMAN_TASKS H36-H40, REUSE "Add-on A3" ledger, `docs/A3_SOURCES.md` (Zotero keys for quote checks), and the
CI scaffold `scripts/check_a3_scaffold.py`. No product code changed. Owner rule (2026-11-18): for OpenAlex,
the repo's verified facts override the spec (A3-C1). Every spawned agent runs on `model: haiku`.

## Done this session
- A3 integration (this commit). Premises pre-checked: no `pmid` stored anywhere; the shared OpenAlex client
  already throttles >5-operator searches and retries their 429; `requests` is not a dependency (PubMed port
  uses `urllib`); code is MIT and data CC BY (only the `pyproject.toml` string is stale; BQ-0 fixes it).

## In flight / next (in this order; A3-Q1 default)
1. **PLAT-2b** live global evidence-map counts (cells approved, H30). Each of the 30 cells is ONE fully
   parenthesised count query `(v3.1) AND (row) AND (column)` on the verified throttled path (>5 operators =
   5 req/s, retry on "wait 1s"; about 10 credits each, about USD 0.03/day); never split OR lists (split counts
   cannot be summed, A3-C1); never paid filters (`from_updated_date` is paid); budget guard stops at USD 0.95.
   Reuse the A2 compartment vocabulary for columns; build the fetch so BQ-2.2 can share it. Wire into the daily
   ingest; replace the landing's "illustrative" labels only when real counts exist.
2. **BQ-0** recon (verify every A3 `[VERIFY]`, record the test baseline, fix the pyproject licence string).
3. **BQ-S8** operator-limit verify/test/document (scope reduced by A3-C9).
4. **BQ-R1** "Authors" rename, `[E]`, before VD-SM (A3-C3, A3-C4).
5. Agent-only BQ work that needs no owner input, in TODO order as each becomes eligible: BQ-G0 draft (then
   owner H37), BQ-G1, BQ-G2, BQ-S1, BQ-S9 stage 1 (free live NCBI calls authorized), BQ-V.0, BQ-3.1, BQ-S6,
   BQ-1.2, BQ-1.6.
6. **VD-SM** (reuse the /explore shell for California).
7. **PLAT-3** then **PLAT-4** (= BQ-V.2; carries its acceptance, A3-C2; estimate cost first: the global
   corpus is about 135k works, so a full backfill is several thousand credits and must be spread across
   days under the USD 0.95 guard), then GX-1 and BQ-S4/G3/G4 (H39 labelling after H37).

## Open findings
- `/usage` items: the owner asked to fix what `/usage` flagged, showing each change first; the output was never
  pasted into the session. Ask for it.
- `tests/test_opc_actions_em17.py::test_committed_json_is_not_stale` fails locally only from the owner's
  uncommitted `curation/opc_mapping_review.csv` (H28 in progress); a clean worktree passes.
- `explore.json --check` goes stale when `build_metadata.json` counts change without a rebuild.
- `.agent/MEMORY.md` is about 290 lines (target 200); compact it at a quiet checkpoint.
- Untracked prototype images under `.impeccable/sketches/{brand,items,papers,scene}` are the owner's; leave them.

## Owner actions (one line each)
- Paste the `/usage` output (each fix is shown before it is made).
- H34: check /explore on a phone and the landing footer animation; reply "explore OK" or list changes.
- H28: review the 22 OPC mapping rows (`py -3.14 -m streamlit run scripts/review_opc_mapping_app.py`).
- H36: answer A3-Q1..Q15 in one line each, or reply "A3 defaults OK" (none blocks the next tasks).
