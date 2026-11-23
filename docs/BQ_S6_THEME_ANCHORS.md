# BQ-S6 theme anchors

**What this is.** A3 section 5.8 names 42 works as known-relevant. They are recall anchors: later
checks ask whether the search finds them. This page records which of the 42 are confirmed
plastics-primary, what was missing, and what it cost. The anchor sets are fixed reference
points, not an estimate of anything.

**Output.** `tests/fixtures/theme_anchors.json` (schema `theme-anchors-v1`). Builder:
`scripts/build_theme_anchors.py`. Tests: `tests/test_theme_anchors.py` (17 pass).

## Counts by theme

| Theme | Spec DOIs | Found in OpenAlex | Anchors | Excluded | Not found |
|---|---:|---:|---:|---:|---:|
| waste_recycling | 6 | 6 | 6 | 0 | 0 |
| policy | 5 | 5 | 5 | 0 | 0 |
| behaviour | 3 | 3 | 3 | 0 | 0 |
| lca_bioplastics | 3 | 3 | 3 | 0 | 0 |
| litter | 2 | 2 | 2 | 0 | 0 |
| ssbd | 1 | 1 | 1 | 0 | 0 |
| chemicals | 2 | 2 | 2 | 0 | 0 |
| waste_colonialism_justice | 6 | 6 | 6 | 0 | 0 |
| labour_critique | 4 | 4 | 4 | 0 | 0 |
| book | 1 | 1 | 1 | 0 | 0 |
| pollution_exposure_health | 4 | 4 | 4 | 0 | 0 |
| reviews_2025_2026 | 5 | 5 | 5 | 0 | 0 |
| **Total** | **42** | **42** | **42** | **0** | **0** |

Each DOI appears once in the fixture. The test checks this.

## Venue distribution (anchors only)

- 29 distinct venues across the 42 anchors.
- Largest venues: Marine Pollution Bulletin (3) and Cambridge Prisms Plastics (3). Max share is
  3/42 = 0.071, well under the 0.5 limit.
- Eleven venues hold two or three anchors each, and 18 hold one. No venue dominates.

## Misses

There were none. All 42 DOIs returned in one call, with no duplicates. The 2025 and 2026 items were
all found, so no indexing lag showed up in this call. One 2026 item,
`10.1016/j.jhazmat.2026.144102`, is indexed but has no abstract in OpenAlex. Its plastics call rests
on the title.

## Plastics-primary judgements

- Made from the cached OpenAlex title and abstract. No PDFs were opened.
- 16 anchors have no abstract in OpenAlex, so their call rests on the title alone. Every one of
  those titles is about plastics (bioplastics, microplastics or plastic waste included).
- Every anchor's evidence is a verbatim quote of 30 words or fewer. The build checks each quote
  against the cached title or abstract and stops if one does not match.
- **Lead override (2026-11-22, decided_by `lead`):** `10.1038/s41893-025-01672-z` (ssbd) is an
  anchor. The builder had marked it unclear, because its abstract is about BPA-analogue chemistry
  for a polyester. The lead reads it as a safer plastic polymer designed to replace BPA-based
  plastics, so it is plastics-primary under the chemicals-in-plastics tier. Evidence is its title.
- Judgement calls the lead asked to keep for review: `10.1016/j.resconrec.2022.106219` (title lacks
  "plastic"; abstract frames it as alternatives to plastic packaging), `10.1515/9781478021445`
  (abstract: "Focusing on plastic pollution"), and `10.1093/etojnl/vgag148` (scientometric umbrella
  review).

## Corpus overlap

Four of the 42 DOIs are in the atlas works table: three waste-recycling works and the Southern
California litter paper (`10.5894/rgci194`). This is a fact about the corpus, not a measure of
recall.

## Cost and calls

- One OpenAlex DOI list call, through the shared client and budget guard. Cost 1 credit
  (USD 0.0001). The budget guard was checked before the call.
- No other network calls. The raw response is cached in `data/interim/theme_anchors_raw.json`
  (ignored). The builder refuses a second `--live` run unless `--force` is given.
- The lead override and the fixture regeneration were done offline from that cache.
- Offline rebuild: `py -3.14 scripts/build_theme_anchors.py`.
