# Handoff — 2026-11-25 (late) — California data moved to site/data/california; global backfill complete; new machine onboarded; BQ-1.3, BQ-2.4, BQ-S2, BQ-3.3, PLAT-3 slices 1-3, PLAT-4 slices 1-2, PLAT-4a backfill day 1

## State in one paragraph
New Windows machine set up (CLAUDE.md "Cross-machine handoff" lists the toolchain; owner added both OpenAlex keys
and logged in `gh`, H43 done). Every bounded task went to Haiku workers; the lead reviewed, gated each commit in a
clean worktree and pushed. Sealed and pushed, CI green: BQ-1.3 (recall probes), BQ-2.4 (`denominators.json`; V-4
share is now C/A), BQ-S2 (candidate plastic-v3.2, ADR-BQS2-REVIEW; "recycler" removed as a stem collision),
BQ-3.3 (null model; `--check` skips the 17-minute null recompute), PLAT-3 slices 1-3 (region registry,
`--region`, per-region data folder; slice 3b moved California to site/data/california per owner), PLAT-4a (global raw
fetch + budget guard 401/403 reserve + 0.6 s spacing + network-error deferral), PLAT-4 slices 1-2 (local
partition with institution-registry join), UX-13 part a (Monitoring filters in the URL). Last commit 1ecf1053.

## In flight / next (in this order)
1. Done: global backfill (136,086 works, all 77 slices) and partition (`data/processed/global/`, 37,925 with pmid, 1,972 california). California data moved to `site/data/california/` (owner; docs/DATA_LAYOUT.md), live and smoke-tested (0 failed data requests on 15 routes).
2. Then PLAT-4 remaining: Tier B outputs per region from `data/processed/global/`; check BQ-V.2's acceptance
   (estimate, unscreened label, pmid, guard, no paid filters) and tick BQ-V.2 with PLAT-4.
3. Unblocked by BQ-V.2: BQ-S9b (PubMed stage 2 on global works), BQ-V.1 (graph builder; check
   `docs/PRIVACY_REVIEW.md` before any global author-level output), then BQ-G3.
4. Design-led, wait for owner review (H25): VD-SM, UX-13 part b (expert.html into the shell; collides with
   `site/california/expert.html` at the same assembled path).

## Open findings
- `scripts/check_s2_2.py` and `scripts/check_s3_1.py` fail on this machine's local data at HEAD too (assert on a
  fixture work id W9000000103); not caused by this session; likely the checks read live data with fixture asserts.
- OpenAlex free keys: >5-operator searches are limited to 2 req/s (was 5); MEMORY updated.
- `network_metrics.json` goes stale when `index.json` changes; a full rebuild takes about 17 minutes (R=100).
- The Evidence page filter list has one axe colour-contrast hit (`.ev-zero > .ev-option-name`), pre-existing.


- Global builds (raw top-up, partition, countries.json, region pages, global graphs) run only on this machine: the raw store is too large for git. QUESTIONS GLOBAL-RAW-HOME asks whether to keep weekly local runs (default) or move the raw store to R2 so CI can run them.

## Owner actions (one line each)
- H28: review the 22 OPC mapping rows (`py -3.14 -m streamlit run scripts/review_opc_mapping_app.py`).
- H40: taxonomy decisions D1-D10 in `docs/TAXONOMY_PROPOSAL.md`.
- H42: triage 43 PubMed misses (`py -3.14 -m streamlit run scripts/review_pubmed_misses_app.py`).
- H2: 277 low-confidence work-relevance decisions (`scripts/review_work_relevance_app.py`).
