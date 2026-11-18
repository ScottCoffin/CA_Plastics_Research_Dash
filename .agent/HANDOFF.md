# Handoff — 2026-11-17 (late) — landing design approved; build PLAT-1, PLAT-2a, PLAT-2

## State in one paragraph
The owner approved the global landing design: a scroll story branded "Plastiverse Live", recoloured
by the owner's logo (ADR-PLAT2-SPECTRAL-STORY-2026-11-17). The approved prototype is
`.impeccable/sketches/spectral_story.html`; its sources and rebuild commands are in
`.impeccable/sketches/src/README.md`. The build spec for the next agent is
`docs/PLAT_2_LANDING_SPEC.md`, and the Impeccable direction contract (version 2) is
`.impeccable/surfaces/framework-src-index-md.md`. No production code changed this session.
The repo now carries all agent state for cross-machine work: the Claude auto-memory mirror is in
`.claude/memory/` (see the CLAUDE.md "Cross-machine handoff" section). CI is red on one
pre-existing test (see Open findings); Pages deploys are green.

## Done this session
- Landing design iterated with the owner to approval: picnic that shatters item by item (Voronoi
  shards, crumbs), particle cloud, CC BY paper stack, Barker-like ordered mandala, bulb that fills
  with the particles and bursts into light, real OpenAlex chart with arrow annotations, evidence
  grid, springy network, world map, California zoom, local-ambassador button.
- Assets: generated blanket and item sheet (gpt-image-2.6-sunburst, prompts in sidecars), 15
  CC BY paper first pages (licence verified on the page, CalEPA download stamps redacted).
- Brand: the logo and its generation prompt are in `src/`; the palette is recorded in MEMORY.
- Commits `1ed81e31` (agent state, tooling and prototype tracked; ruff skips `.impeccable`;
  vendored skills exempt from whitespace checks) and `2e53fb02` (slower bulb-to-chart transition).

## In flight / next (in this order)
1. **MAIL-1 fix, then enable.** Unchanged from the previous handoff: the digest selects "new this
   week" by `works_detail.first_seen`, which the 2026-11-11 re-ingest reset (1,565 works in one
   week). Fix the selection (require `pub_date` in the last ~60 days too, or keep a first-seen
   ledger). Also fix `tests/test_weekly_digest.py::test_workflow_schedules_monday_and_sends_only_with_the_secret`,
   which fails because the cron is disabled (make it pass in the disabled state, or re-enable the
   cron once the owner says "Buttondown ready", H29). Send the owner a test first.
2. **PLAT-1 move California to /california (clean break).** As in `docs/PLATFORM_ARCHITECTURE.md`:
   move `framework/src/*.md` into `framework/src/california/`, fix imports and data paths,
   nav/footer, SEO pages, sitemap, robots, llms, feed, search index, ntfy and digest URLs; remove the
   redirect stubs in `scripts/assemble_site.py`; root `index.md` is a placeholder until PLAT-2.
   Cross-cutting: the lead or an Opus worker implements, sonnet-reviewer reviews.
3. **PLAT-2a global data**: `scripts/build_world_map.py` (Natural Earth 110m, public domain, Equal
   Earth raster as in `.impeccable/sketches/src/build_geo.py` and `story.py`) and
   `scripts/build_global_counts.py` to `site/data/global/global_counts.json` (group_by
   `authorships.countries`; at most 60 credits; never paid filters).
4. **PLAT-2 build the landing** to `docs/PLAT_2_LANDING_SPEC.md`: tokens and self-hosted fonts,
   `scripts/build_landing_assets.py`, `framework/src/components/landing_story.{js,css}`, the
   sections after the story, reduced-motion stills, `scripts/check_plat2.py`, then the Impeccable
   finish reviewer and documenter (DESIGN.md). Haiku may take the bounded parts (font files, asset
   script, check script, tests); the engine port and integration stay with the lead or Opus.
5. Then PLAT-2c (`/ambassadors` placeholder), PLAT-2b (gated on H30), VD-SM (carry the brand into
   the California pages), PLAT-3, PLAT-4, NOR-1..5.

## Open findings
- CI fails on the MAIL-1 digest schedule test (pre-existing since `0a5d35cd`; see step 1).
- Daily-ingest plan refusals returned as HTTP 429 still defer without an alert.
- `.agent/MEMORY.md` is about 285 lines (target 200); compact it at a quiet checkpoint.
- Unused prototype images (old flying picnic, dinner scene, earlier item set, full-size paper
  renders) are untracked in `.impeccable/sketches/`; they are not needed for the build.

## Owner actions (one line each)
- H31: revoke the OpenAI key pasted into the chat, then say "OpenAI key rotated".
- H30: approve or edit the evidence-map cells (spec section 4.6), reply "cells OK".
- H29: create the Buttondown account and secret, then say "Buttondown ready".
- H28: review the 22 OPC mapping rows (`py -3.14 -m streamlit run scripts/review_opc_mapping_app.py`).
- Answer or accept the defaults for QUESTIONS rows PLAT2-RESEARCH-LINE, PLAT2-FONTS, PLAT2-NETWORK, PLAT2-AMBASSADORS.
- After PLAT-1 deploys: resubmit `https://plastiverse.live/sitemap.xml` in Google Search Console.
