# Handoff — 2026-11-26 — Reviews applied, favicon, roster QC in tagging, enrichment approved

## Done this session

- H59: D1 0008 and Worker 5a5f52e9 (CG-7b sampling, reviews, export); CG-7c review screen live; CG-7 closed. GRP-REVIEW-APPLY (08fcc839): complete reviewer checks publish edited values, status `reviewed`, `reviewed_at`.
- FAVICON-MAIN (cf7cb43b, 21699abf): `scripts/build_favicons.py [--check]` (pixel-tolerant: Linux and Windows Pillow encode differently); sun crop at small sizes, full mark at 180/512; root favicon.ico and apple-touch-icon.png.
- GRP-ENRICH spike: `docs/GROUP_ENRICHMENT_OPTIONS.md`; owner H61 "suggestions OK" (ADR-GRP-ENRICH-2026-11-26).
- AMB-ROSTER-QC (this commit and 5039bc3d, f03f1422): `roster_qc.json` (213 pairs, 31 suspect names; ids and reason codes only); Worker b2e7b4b5 accepts `same_as` and exports per-pair rater tokens (H60); the tagging form asks up to 3 optional duplicate questions and opens the name correction for suspect names; the export records answers in `curation/group_dupe_answers.csv` and appends `group_merges.csv` rows (newest lead/owner answer decides, else two distinct agreeing raters with no dissent; existing rows never change).
- H62: the owner's 5 review-app merge decisions are committed.

## State of the repo

- Strict clean-worktree gates green for every checkpoint; hosted CI green through f6772b1c. Worker 241 tests. Production: Worker b2e7b4b5, D1 0008.

## Next task

1. GRP-ENRICH slice 1: `scripts/build_group_suggestions.py [--check]` (Wikidata SPARQL, ≤1 req/s, UA `PlastiverseLive/<ver> (https://plastiverse.live)`, cache under ignored `data/interim/group_enrichment/`; website-domain match first, then English label with a country check, AF = unknown; no any-language search) -> public `site/data/global/groups/suggestions.json` (qid, website, inception year, type). Reuse `scratch/group_enrichment/wikidata_spike.py` (measured 42/47 domain matches correct).
2. Slice 2: form "Suggestions to check" plus per-country register search links; methods attribution line. Slice 3: IRS NTEE sector suggestions (US); verify BE/NO/IN/Charity Commission licences live first.
3. Then the remaining CG views (CG-12, CG-12b) and the owner-priority Norway/Belgium work.

## Gotchas

- With a local raw cache, `build_groups_roster.py --check` needs `--incremental`. A hand commit of `curation/group_merges.csv` needs `scripts/build_roster_qc.py` rerun (CI checks it).
- Byte-exact checks of generated images or CRLF-prone text break in clean checkouts or on Linux: compare pixels, write single-line SVG.
- Never pipe a gate check through tail in an && chain (LESSONS).

## Needs owner input

- None new. Open reviews: H39, H28, H42, H2, H9; H58 optional.
