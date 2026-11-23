# Search vocabulary register (v1)

## Purpose

This register lists the search terms that A3 §§5.1, 5.5, 5.7 and 5.10 propose, test or rule out. It is a register, not a query: adding a row changes no search. BQ-S3 tests each candidate before any query uses it.

The data is in `config/search_vocabulary_v1.yml`. The checks are in `tests/test_search_vocabulary.py`.

## Columns

Each row has the 11 fields that A3 §5.8 names.

| Column | Meaning |
|---|---|
| term | The search string. A "(s)" in the spec gives one row for the singular and plural. |
| language | ISO 639-1 code, such as `en`, `zh` or `de`. |
| concept | The concept family the term belongs to. |
| group | One of the six groups below. |
| tier | One of the five tiers below. |
| source | The citation the spec gives for the row, as text. No DOI is given unless the spec prints it. |
| anchor_required | `true` when the term needs a plastic anchor (A3 §5.2) before it can count. |
| handling | One of the six handling values below. |
| in_v31 | `true` when the exact string is a core term, a qualified term, a context word or an exclusion in `config/queries.yml`. |
| probe_count_and_date | The probe count the spec states, with its date when the spec gives one. `null` if none. |
| risk | Polysemy, stemming or noise that the spec names. `null` if the spec names none. |

## Tiers

- A: plastic-anchored, high-precision candidates.
- B: query only with a plastic anchor. Never standalone.
- C: glossary or theory terms. Never queried.
- D: behaviour, psychosocial and health-equity terms. Anchored probes only.
- never_standalone: never a standalone query term.

## Groups

- pollution: sources, objects, abbreviations and exclusions.
- particle_descriptors: particle types, sizes, shapes and polymer names.
- pollution_health_toxicology: exposure matrices and health-exposure terms.
- lifecycle_and_society: trade, labour, justice, behaviour and place terms.
- lens_evidence: critical waste-studies framing, theory and glossary terms.
- analytical_methods: reserved. No term in this version belongs here.

## Handling

- core: a v3.1 core term. Only terms already in the v3.1 core list use it.
- qualified: query only with a context list.
- title_only: query only in the title.
- co_term: query only when a plastic anchor appears in the same title or abstract.
- lens_evidence: Atlas framing evidence. Not a search term.
- exclude: not a query term. Covers exclusion phrases and never-standalone words.

## Counts by tier

| Tier | Rows |
|---|---:|
| A | 53 |
| B | 50 |
| C | 13 |
| D | 17 |
| never_standalone | 30 |
| Total | 163 |

## Counts by group

| Group | Rows |
|---|---:|
| pollution | 43 |
| particle_descriptors | 23 |
| pollution_health_toxicology | 8 |
| lifecycle_and_society | 49 |
| lens_evidence | 40 |
| analytical_methods | 0 |
| Total | 163 |

## Rules

1. One row per term. Split concept families into single-term rows.
2. A term with no tier, handling or source is not allowed.
3. Tier C rows are never queried. They use `lens_evidence` or `exclude`.
4. Tier D rows are probes only. They use `qualified`.
5. `never_standalone` rows use `exclude` or `co_term`. They never use `core`.
6. `core` is only for v3.1 terms (`in_v31` is `true`).
7. `anchor_required` is `true` for every row except core terms, tier C rows and `exclude` rows.
8. Registering a term changes no query. Only BQ-S3 and the owner can promote a term.

## Judgment calls

The spec does not give a tier for the §5.1 rows, so BQ-S1 set them from the handling the spec proposes. These calls are open to review.

- New pollution terms (`nurdle`, `pre-production pellet`) are `qualified`, not `core`. The spec says "add" but names no handling, and a new core term needs owner approval.
- Review phrases with no stated handling (`microparticles plastics`, `nanoparticles plastics`, `plastic microfiber`) are `qualified`.
- `basura marina` and `marint søppel` are tier B. They mean "marine litter" and need a plastic anchor.
- `waste regime` is tier B. The Discard Studies entries list it as never stand-alone, but the Tier B rule applies.
- `in_v31` counts context words. `PET`, `PLA`, `polystyrene`, `polyethylene`, `polypropylene` and `polylactic acid` appear only as context words in v3.1, not as standalone query terms.
- The four exposure-matrix phrases (`indoor dust`, `atmospheric deposition`, `breast milk`, `infant formula`) come from the BQ-S1 brief. Their source is cited as A3 §5.8 BQ-S3(d). That section was not read for this register.

## Not registered

- A3 §5.10.3 facet values (analytical methods, digestion reagents, organ systems, polymer types, particle shapes and similar). These are owner-gated facet values, not search terms.
- A3 §5.10.1 model-system terms (Caco-2, HT-29). The spec calls them co-term candidates for a facet, not vocabulary additions.
- A3 §5.7 Italian (85). The spec gives no term string.
- A3 §5.1 size schemes (small microplastic, micro, meso). These are size definitions, not search terms.
- A3 §5.2 probe-only phrases (decolonial, settler colonialism, community methods, zero waste).
- `MPs` (excluded by Hossain et al. 2026) and `microplasticity of metal materials` (not proposed for addition).

## Probe notes

- Counts are the spec's own probe numbers. BQ-S1 did not run any probe.
- Many spec probes give no date. The register records "date not stated" in those rows.
- The §5.7 probes are dated 2026-11-18 in the spec.
- Counts marked "combined" cover more than one term. Do not read them as one term's count.
