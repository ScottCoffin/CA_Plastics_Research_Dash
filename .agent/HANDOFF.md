# Handoff — 2026-11-15 — task NET-1

## Done
- NET-1 (owner request): the UC Davis Land to Sea Microplastics Consortium is linked from the Atlas. Registry `config/research_networks.yml` -> `scripts/build_research_networks_json.py [--check]` -> `site/data/research_networks.json` (`atlas.networks`).
- Surfaces: host card with the self-hosted logo on `/institution#inst=I84218800`; one-line pointer on OEHHA, CDPH, Oregon State, UC Berkeley and GAIA; badge on `expert.html` for the 6 listed contributors with Atlas profiles; link-out LO-13 on Resources and the Evidence Map strip (health, ecotoxicology, methods); static SEO institution pages with link, disclosure and JSON-LD `subOrganization`. Link-out disclosures are now published (fixes LO-8's unpublished disclosure).
- Facts come from the owner-supplied saved page (the live page returns 403 to bots): 14 contributors, 8 without Atlas profiles; roster not copied.
- Gate: links, A1/A2 scaffolds, Ruff, compileall, both JSON checks, public-text check; 1,702 passed / 9 expected skips; Framework build + assembled preview in headless Edge at 1280/375 px (no console errors, no overflow, axe clean on new markup). Evidence: `docs/NET_1_VERIFICATION.md`.
- Previous checkpoint (UX-28 follow-up, commit f1805a21, by a concurrent session): Funding Sankey click drill-down restored; Sankey-local by default (does not set the page filters).

## State of the repo
- Concurrent owner edits were preserved and left out of this commit (`framework/src/**` VD-7/VD-8 work, `tests/test_vd*.py`, `docs/VD_7A/7C/8_VERIFICATION.md`, `scripts/ux_tasks.py`, `tests/test_ux_tasks_script.py`, and the owner's formatting edits to `.agent/QUESTIONS.md`; only the three NET-1 rows were staged on top of HEAD).
- `.rs-disclosure` has no rule in the owner-dirty `resources.css`; it renders as a plain paragraph.

## Next tasks (suggested)
- Later idea (not in TODO): highlight consortium contributors on `/network`.
- From S2.6: add `fetch_orcid_author_ids.py` to `ingest_works.yml` before normalization; compute expert metrics for repaired authors from corpus authorships.

## Gotchas the next agent must know
- `serve_framework_preview.py` serves under `/CA_Plastics_Research_Dash/`; browser scripts must include the prefix.
- Add a consortium contributor only by Atlas author_id after a name check, then rebuild the JSON with the script.

## Needs owner input
- H26: consortium logo permission; QUESTIONS NET-1-NAME and NET-1-SURFACES.
- H25 (VD-12 design review). Optional: Sankey-local vs global drill-down (UX-28).
