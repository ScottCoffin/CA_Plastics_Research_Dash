# Taxonomy reconciliation proposal (BQ-S5)

This document asks you to decide ten taxonomy items: the new lifecycle-and-society tier, its topic tags and facets, and the mismatched tag lists. Nothing ships until you approve it (A3-D7), so no label, export, site page or `config/taxonomy.yml` behaviour changes now. For each item the table gives the change, the reason and the lead's default; please write your decision in the last column.

## How to reply

1. Read each row of the table below.
2. In the "Owner decision" column, write approve, change or reject, with a short note.
3. Reply to the lead with the completed table. The lead applies only approved rows, in a later checkpoint.

The machine-readable record is `config/taxonomy_crosswalk.yml`. Every entry there is marked `pending`.

## Decision items

| # | Decision item | What changes | Why (source) | Lead's default | Owner decision |
|---|---|---|---|---|---|
| D1 | 8-vs-11 tag mismatch | Three tag lists disagree. The labelling guide and labelling app use 8 tags. The rule engine and the site use 11. The 3 extra tags are `risk_assessment`, `plastisphere` and `plastic_associated_chemicals`. The `disciplines` block in `taxonomy.yml` lists a third set of 8. | Labelling guide section 4 and `src/atlas/nlp/annotation.py` (8 tags) against `taxonomy.yml` `domain_tags` and `site/assets/topics.js` (11). | Treat the 11 tags in `taxonomy.yml` as the one list. In one later approved change, update the guide, the labelling app and the `disciplines` block to match. No change now. | |
| D2 | `risk_assessment` as a topic | Keep the topic. Add it to the guide's tag list. Keep it apart from the study-type value `modelling_risk`, which describes design, not subject. | Added on owner request 2026-11-11 (comment in `taxonomy.yml`). Missing from the 8-tag guide list. | Keep it. Write its rule into the guide together with D1. | |
| D3 | New lifecycle-and-society topic tags | Add 8 tags: `lca_and_sustainability`, `waste_management_and_recycling`, `policy_law_and_governance`, `behaviour_and_perception`, `justice_colonialism_and_power`, `litter_and_trash`, `bioplastics_and_alternatives`, `safe_and_sustainable_by_design`. Add one sub-tag: `waste_trade_and_global_flows`. | A3 section 5.4 candidate list (guide_v3 section 4). Search probes returned many off-topic hits, so seed words are still to be written. | Add all as proposed, with no renames. Tags do not depend on tier, so a core work can carry them. | |
| D4 | New tier `lifecycle_and_society` | A third plastic tier for works about plastics as a material, product, waste stream or policy object, not as a pollutant. | A3 section 5.4 and guide_v3 section 2. The name is confirmed (A3-D16). Code currently allows only two tiers (`_TIERS` in `annotation.py`). | Adopt, with the tie-break and boundary rules in guide_v3 section 2. Code change only after approval. | |
| D5 | Lens facet `analytic_lens[]` and its six original values | An optional, multi-value framing tag that can go with any topic. Six values: `waste_colonialism` (with two sub-fields), `environmental_justice_and_racism`, `indigenous_and_community_governance`, `community_and_participatory_methods`, `labour_and_informal_economy`, `circularity_critique_and_greenwashing`. | A3 section 5.4 item 2 (A3-D14); guide_v3 section 6. A lens is used only when the work itself uses the frame, with a quoted excerpt. | Adopt. Keep the rule: never infer a lens from the topic alone. | |
| D6 | A3-D20 reconciliation of lens values | Add two values: `political_economy_centre_periphery` and `responsibility_shifting`. Fold three addendum candidates into existing values: `spatial_injustice` into `environmental_justice_and_racism`, `decolonial_and_indigenous_research` into `indigenous_and_community_governance`, and `behavioural_and_psychosocial` into `behaviour_and_perception`. | A3-D20 (owner decision 2026-11-18, A3-Q7): implement and test now; public release waits for approval. | Accept all five changes. Public text waits for your approval. | |
| D7 | `plastics_centrality` field | One value per work, set only for lifecycle-and-society works: `primary`, `substantial`, `incidental`, `none`, `not_assessed`. It is the scope gate: works with only incidental plastics are out. | A3-D18; guide_v3 section 5. Without it the new tier has no scope gate. The wording is open as A3-Q5. | Adopt the five values. Confirm the wording (A3-Q5). | |
| D8 | `origin` facet | Optional facet. `primary` means plastic made as small particles on purpose. `secondary` means plastic broken from larger items. Add `not_stated` for works that do not say. | A3 section 5.6 (Hartmann et al. 2019; "origin facet candidate"). The California DTSC document also splits primary and secondary microplastics (A2 addendum, section 3). | Add as an optional facet. Apply it only when a work states the origin. | |
| D9 | Review-derived facets (A3 section 5.10.3) | 18 facets taken from recent reviews: exposure pathway, exposure source, human sample matrix, organ system, study design, experimental system, model organism, endpoint domain, endpoint technique, polymer type, particle shape and condition, analytical method, food-contact article, size-definition scheme, review type, environment setting, particle colour. Evidence-quality scores are not adopted. | A3-D21 (owner decision 2026-11-18, A3-Q8): adopt the facets. Each is benchmarked against the reviews' included-study lists. A facet ships with an on-site accuracy caveat, or not at all. | Adopt in small batches, one facet at a time. Merge `exposure_source` into exposure pathway, and `review_type` into the study-type value `review_synthesis`. Defer `study_design` (reconcile with study type first) and `particle_colour` (its source advises against it). Keep evidence-quality scores out. | |
| D10 | `culture_media_and_discourse` topic | Add an optional, experimental topic for art, media, material culture and heritage studies of plastics. Excluded from P1–P6 reporting. | A3-D17 and A3 section 5.4: low weight. Experimental until it has 40 gold examples and good scores (kappa 0.7, F1 0.70). | Propose only. Do not edit `taxonomy.yml` yet: the schema has no experimental flag that code reads, so a flag would do nothing. Register it after approval, with no seed words. | |

## Points to check before you decide

- The spec list names nine items. D5 and D6 split the lens item in two, so the list has ten rows. Merge them if you prefer nine.
- A3 says study type has 16 values. The labelling guide (A2 addendum, section 1.1) and `taxonomy.yml` list 15. Please confirm the correct count before the D9 reconciliation.
- The labelling app and the evaluation use the 8-tag list in `annotation.py`. So `risk_assessment`, `plastisphere` and `plastic_associated_chemicals` have no gold labels and no accuracy scores yet (D1).
- Denominator series B2 (`config/denominator_series.yml`) needs `plastics_centrality`. It is marked "not built" and waits for D7.
- `config/taxonomy.yml` is unchanged in this proposal.

## Glossary

- A2, A3: the two add-on specifications (`docs/add_on_spec_2.md`, `docs/add_on_spec_3.md`).
- A3-Dxx, A3-Qx: decision and question IDs in the project decision log (`.agent/DECISIONS.md`).
- A3-D7: the rule that only owner-approved tags may appear in topic series.
- Tag: a topic label on a work, for example `occurrence_and_monitoring`.
- Tier: the top-level class of plastic relevance: `core`, `chemicals-in-plastics`, or the new `lifecycle_and_society`.
- Facet: an extra descriptor for a work, for example polymer type.
- Lens: a framing that a work itself uses, for example environmental justice. It needs a quoted excerpt.
- `plastics_centrality`: how central plastics are to a work (primary, substantial, incidental or none).
- Study type (`study_type`): the design of a work, for example a review or field sampling (A2 guide).
- P1–P6: the six precision goals in A3. Culture is excluded from them.
- Experimental: shown with a caveat because its accuracy is not yet proven.
- Seed words: search cue words. They are not evidence on their own.
- Co-term: an extra term recorded next to a tag, not a tag itself.
- Gold labels: hand-checked examples used to measure accuracy.
- F1: a score that combines precision (how many hits are right) and recall (how many right ones are found).
- Kappa: a score of agreement between two labellers.
- Scope gate: a rule that keeps out works that are not about plastics enough.
