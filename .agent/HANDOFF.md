# Handoff — 2026-11-23 — BQ batch: S1, S4, S6, S9, G2, G7, V.0, 2.1, 2.2, 3.2 + NET-2, CNT-1, CNT-2, OA-2 sealed

## State in one paragraph
Owner asked the lead to work through all available tasks with Haiku workers, committing and pushing each step.
Sealed and pushed on 2026-11-22/23: NET-2 (network nodes need another Atlas expert; network.json rebuilt),
CNT-2 (California Now line has a "works of other types" remainder), OA-2 (AT-1 audit uses the shared OpenAlex
client), BQ-G7 (boundary cases recorded with checked quotes), BQ-S1 (163-term vocabulary register), BQ-S9
(PubMed coverage stage 1: R1 163/178, R2 313/352 in the published Atlas; `pmid` on normalized works; 43-miss
triage app, H42), BQ-V.0 (sigma benchmark: 20k desktop / 5k phone meet targets; owner's 60k kept, phone cap
default A3-Q10b), BQ-S6 (42 theme anchors), CNT-1 (unmatched exclusions classified; 2 carried to duplicate
keepers), BQ-G2 (label-blind gold design freeze with Horvitz-Thompson weights, ADR-GOLD-DESIGN-HT), BQ-S4
(language probe, USD 0.064), BQ-2.1 and BQ-2.2 (denominator series A/B/C/D; B and PubMed R2 use A3 §5.3
pollution-core v0, `config/pollution_core_v0.yml`), BQ-3.2 (network_metrics.json). CI green at 28bde730.

## In flight / next (in this order)
1. Workers running at handoff time: BQ-S10 (review-string replay), BQ-1.5 (anchor overlap), BQ-2.3 (trend metrics).
   Their files are uncommitted; rerun or finish them before anything else.
2. Then: BQ-2.4 (Trend tab + `site/data/denominators.json`; replace the EM-7 share line with C/A), BQ-3.4
   (collaboration panel, no person rankings), BQ-R2 (glossary; verify citations and the HEN 75 ISBN live),
   BQ-S5 (taxonomy proposal for owner H40), BQ-S2 `[E]` (lead implements), PLAT-4a (global raw fetch).
3. Wire into the daily ingest when the owner agrees: `fetch_denominator_series.py --allow-stale`,
   `build_network_metrics.py`, `build_pubmed_coverage_json.py --check` (needs interim data; skips in CI).

## Open findings
- `test_opc_actions_em17.py::test_committed_json_is_not_stale` fails locally only (owner's H28 CSV in progress).
- Keep pytest `--basetemp` outside the repo; inside, `test_release_at10` finds git and fails.
- The Evidence page's California share line divides all published works by series A (not like-for-like); BQ-2.4.
- 2 published works drop at the next daily export (CNT-1 carried exclusions).
- `.agent/MEMORY.md` is over 200 lines; compact at a quiet checkout.

## Owner actions (one line each)
- H28: review the 22 OPC mapping rows (`py -3.14 -m streamlit run scripts/review_opc_mapping_app.py`).
- H42: triage 43 PubMed misses (`py -3.14 -m streamlit run scripts/review_pubmed_misses_app.py`).
- H2: 277 low-confidence work-relevance decisions (`scripts/review_work_relevance_app.py`).
- A3-Q10b: cap the author graph at 5,000 nodes on phones (default) or not?
- BQ-G2-OWN: keep the 17 owner-decided pool works in the CA evaluation (default: yes, report both ways)?
- BQ-2.2-QUAL: add qualified microfiber / tire wear / litter terms to pollution-core (default: not in v0)?
- BQ-S10: supply Ortiz-Balsero et al. (2026) Supplementary Text S1 if you want its PubMed blocks replayed.
