# Handoff — 2026-11-17 — VD-27 owner feedback round 3 and EM-17 OPC Solutions track

## Done this run
- VD-27: paper-California favicon and brand mark (also `site/assets/favicon.svg` on classic and SEO pages); notices/callouts full width; Policy text full width (timeline reservation re-measured); Funding tables full width, heatmap cells filter the awards table (Reset clears them); Experts More filters aligned, up-and-coming button and URL pill removed; Network slider and status padding; Overview "living evidence map" pipeline section with live output mix; About rewritten (OpenAlex and sources, six classification steps, living screening flow, larger headings, colour cards with hover).
- FLOW-1: export writes `build_metadata.json` `flow` (2,070 retrieved, 37 duplicates, 2,033 unique, 56 no CA author, 62 removed by curation, 1,915 published, 1,579 plastic-related, by_type). The committed file got the flow block from a real local export of the same snapshot.
- EM-17 (partial): `config/opc_early_actions.yml` (22 actions; deadlines verified verbatim against the 2022 Strategy PDF), validator, JSON export, Policy panel, review app `scripts/review_opc_mapping_app.py` + `curation/opc_mapping_review.csv`.
- Gate: links, scaffolds, triggers, ruff, format, compileall, tokens, public text, full pytest (after fixes: 4 stale tests updated), Framework build, check_at5, opc/methods flow --check, git diff --check; local screenshots at 1440/390 with no overflow.

## Open findings
- Owner mid-run request (next checkpoint VD-28): Network on mobile: name search should list matches only after typing; full-screen view should give space to expert details only when an expert is selected, with more economical text widths; "Exit full screen" label overflows its button.
- Impeccable hook findings on classic `site/sem.html`, `grants.html`, `expert.html` predate this run (UX-13/VD-26).
- `.agent/MEMORY.md` is 278 lines (target ≤ 200); compact it at a quiet checkpoint.

## Next eligible
- VD-28 (network mobile), then VD-26.

## Owner actions (one line each)
- H28: review the 22 OPC mapping rows in the Streamlit app, then say "OPC mapping reviewed".
- Look at the live site after this deploy (About, Overview, Funding heatmaps, Policy).
- H27: tick Enforce HTTPS once GitHub finishes the certificate.
