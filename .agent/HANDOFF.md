# Handoff — 2026-11-17 (night) — MAIL-1, PLAT-1, PLAT-2a, PLAT-2c, PLAT-2 done; next VD-SM

## State in one paragraph
The global landing design is approved (ADR-PLAT2-SPECTRAL-STORY-2026-11-17); build spec
`docs/PLAT_2_LANDING_SPEC.md`, prototype `.impeccable/sketches/spectral_story.html` (sources and
rebuild in `.impeccable/sketches/src/README.md`). The owner accepted the PLAT2 defaults on
2026-11-17 (QUESTIONS rows PLAT2-RESEARCH-LINE, -FONTS, -NETWORK, -AMBASSADORS); the ambassador
placeholder must also describe the role: QC local institutions and experts, identify local
community groups and networks, populate local monitoring datasets, identify local policy goals.
MAIL-1's selection is fixed and its Monday cron is back on, so CI is green again.

## Done this checkpoint
- MAIL-1 (`2ba73047`): digest selection requires a recent `pub_date` (19 works, not 1,565); Monday
  cron on (no-op without the secret).
- PLAT-1: California moved to `/california/` with a clean break (ADR-PLAT1-LAYOUT-2026-11-17,
  `docs/PLAT_1_VERIFICATION.md`). Root `framework/src/index.md` is a placeholder until PLAT-2.
  Local assembled deploy: 6/6 UX tasks, axe 0 and no console errors on 14 routes. Owner: H32.
- PLAT-2a (`880973c1`), PLAT-2c (`a9e3a837`, live), release `design-plane-poster-2026-11-17` (pre-move site).
- PLAT-2: the landing (`docs/PLAT_2_VERIFICATION.md`, ADR-PLAT2-BUILD). check_plat2 0 failures; finish
  review: story matches the prototype, 6 fixes applied; DESIGN.md written.

## In flight / next (in this order)
1. Confirm the landing on the live site: `py -3.14 scripts/check_plat2.py --base https://plastiverse.live/`
   and Lighthouse mobile (spec target 90; local same-machine run was 85 vs California overview 84).
2. VD-SM: carry the Plastiverse Live system into the California pages. `DESIGN.md` (repo root, sidecar
   `.impeccable/design.json`) lists what is platform-wide; move the landing's font faces into
   `observablehq.config.js` then. Restyle `/ambassadors` in the new system.
3. PLAT-2b (gated on H30), PLAT-3, PLAT-4, NOR-1..5.

## Open findings
- Daily-ingest plan refusals returned as HTTP 429 still defer without an alert.
- `.agent/MEMORY.md` is about 280 lines (target 200); compact it at a quiet checkpoint.
- Unused prototype images are untracked in `.impeccable/sketches/`; not needed for the build.
- Landing follow-ups: two canvas hex literals in `landing_story.js` (California zoom cells); `papers.json`
  licence sentences truncated at source (`credits.json`); p00 has no title in `credits.json`.

## Owner actions (one line each)
- H30: approve or edit the evidence-map cells (spec section 4.6), reply "cells OK".
- H29: create the Buttondown account and secret, then say "Buttondown ready" (first Monday send reaches only you).
- H28: review the 22 OPC mapping rows (`py -3.14 -m streamlit run scripts/review_opc_mapping_app.py`).
- H32: after the PLAT-1 deploy, resubmit `https://plastiverse.live/sitemap.xml` in Search Console.
