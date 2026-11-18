# Handoff — 2026-11-17 (night) — MAIL-1 selection fixed; next PLAT-1, PLAT-2a, PLAT-2

## State in one paragraph
The global landing design is approved (ADR-PLAT2-SPECTRAL-STORY-2026-11-17); build spec
`docs/PLAT_2_LANDING_SPEC.md`, prototype `.impeccable/sketches/spectral_story.html` (sources and
rebuild in `.impeccable/sketches/src/README.md`). The owner accepted the PLAT2 defaults on
2026-11-17 (QUESTIONS rows PLAT2-RESEARCH-LINE, -FONTS, -NETWORK, -AMBASSADORS); the ambassador
placeholder must also describe the role: QC local institutions and experts, identify local
community groups and networks, populate local monitoring datasets, identify local policy goals.
MAIL-1's selection is fixed and its Monday cron is back on, so CI is green again.

## Done this checkpoint
- MAIL-1: `select_new_works(..., max_age_days=)` also requires `pub_date` within
  `digest.max_age_days` (config, default 60) of the week's end; the 9-15 Nov dry run lists 19
  works instead of 1,565. The workflow schedule (Monday 14:00 UTC) is enabled; without the
  `BUTTONDOWN_API_KEY` secret it is a no-op. 40 digest tests; full gate 2143 passed, 10 skipped.

## In flight / next (in this order)
1. **PLAT-1 move California to /california (clean break).** As in `docs/PLATFORM_ARCHITECTURE.md`:
   move `framework/src/*.md` into `framework/src/california/`, fix imports and data paths,
   nav/footer, SEO pages, sitemap, robots, llms, feed, search index, ntfy and digest URLs; remove the
   redirect stubs in `scripts/assemble_site.py`; root `index.md` is a placeholder until PLAT-2.
   Cross-cutting: the lead or an Opus worker implements, sonnet-reviewer reviews.
2. **PLAT-2a global data**: `scripts/build_world_map.py` and `scripts/build_global_counts.py`
   (spec section 6; at most 60 credits; never paid filters).
3. **PLAT-2 build the landing** to `docs/PLAT_2_LANDING_SPEC.md`.
4. Then PLAT-2c (`/ambassadors`, with the role list above), PLAT-2b (gated on H30), VD-SM,
   PLAT-3, PLAT-4, NOR-1..5.

## Open findings
- Daily-ingest plan refusals returned as HTTP 429 still defer without an alert.
- `.agent/MEMORY.md` is about 280 lines (target 200); compact it at a quiet checkpoint.
- Unused prototype images are untracked in `.impeccable/sketches/`; not needed for the build.

## Owner actions (one line each)
- H31: revoke the OpenAI key pasted into the chat, then say "OpenAI key rotated".
- H30: approve or edit the evidence-map cells (spec section 4.6), reply "cells OK".
- H29: create the Buttondown account and secret, then say "Buttondown ready" (first Monday send reaches only you).
- H28: review the 22 OPC mapping rows (`py -3.14 -m streamlit run scripts/review_opc_mapping_app.py`).
- After PLAT-1 deploys: resubmit `https://plastiverse.live/sitemap.xml` in Google Search Console.
