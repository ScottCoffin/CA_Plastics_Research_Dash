# Candidate plastic-v3.2 (BQ-S2)

Status: **candidate, not promoted**. `config/queries.yml` (plastic-v3.1, active) is unchanged. Config: `config/queries_v32_candidate.yml`. Renderer: `src/atlas/query_v32.py`. Count script: `scripts/count_query_v32_candidate.py`. Register: `config/search_vocabulary_v1.yml` (BQ-S1). Source rules: A3 section 5.1 (additions), 5.2 (plastic-anchor rule), 5.8 (BQ-S2), 5.9 (operator throttle); owner rule A3-C1.

## Rules applied

- Base: every v3.1 core term, qualified term and exclusion is copied unchanged; tier_2_terms are copied and, as in v3.1, not rendered.
- Scope: English rows only, tier A or B, handling `qualified`, `co_term` or `title_only`, `in_v31` false. Groups: pollution, particle_descriptors, lifecycle_and_society, pollution_health_toxicology, and lens_evidence rows whose handling is `co_term` (18 rows, theme waste_colonialism_lens).
- Excluded by handling: `lens_evidence` (evidence only), tier C, tier D, never_standalone, handling `exclude`.
- Anchor rule (A3 5.2): added terms are qualified by the 23 anchor phrases, singular and plural as the spec spells them. Bare `plastic`, `plastics` and `petrochemical` are never anchors (tested). The one exception is microfibre (see review items).
- Title-only rows (`title_only`) are rendered only on `title.search`, with the anchor context, in a separate per-theme request. They never enter the title_and_abstract expression (tested).
- Factoring (render time, `factored_expression` in src/atlas/query_v32.py; not in the YAML or atlas.query): within one expression, qualified terms with an identical any_context list become `((t1 OR t2 ...) AND (ctx ...))`. This is logically identical to the per-term form; a truth-table test checks it. The v3.1 baseline keeps the v3.1 render.
- Expressions are wrapped once more so that the whole expression is one group. Every expression is fully parenthesised (checked by a tokenizer, `is_fully_parenthesised`).
- Exclusions: the 14 v3.1 exclusions plus the two A3 5.1 exclusions (`perpendicular anisotropy`, `microplastic kinetics`).
- Splitting: the combined request is sent as one request when its URL is at most 8,000 characters (it is, after factoring). If it were not, the v3.1 base and each theme would be sent separately; their OR equals the combined expression, but their counts cannot be summed (overlaps are not removed).
- Count requests are never OR-split. Operator counts above 5 are throttled, not refused (owner A3-C1), so they are reported and not capped.
- Incremental yield (`theme AND NOT v3.1`) is built only where the URL fits 8,000 characters.
- Promotion: not promoted. Promotion only by the existing precision rule (A3-D10; rule text copied from `config/queries.yml`), after BQ-S3.

## Per-theme added terms

| theme | added terms |
|---|---:|
| particles_and_fibres | 10 |
| tyre_pellets_and_debris | 5 |
| polymer_and_abbreviation_forms | 4 |
| trade_and_policy | 6 |
| justice_and_labour | 8 |
| circularity_and_greenwashing | 5 |
| exposure_matrix | 4 |
| waste_colonialism_lens | 18 |
| indigenous_title | 4 |
| total | 64 |

## Term table

| term | theme | tier | handling | register source | rendering |
|---|---|---|---|---|---|
| large microplastic | particles_and_fibres | A | qualified | EN ISO 24187:2023 (A3 §5.1) | qualified: anchor context (23 phrases) |
| microbead | particles_and_fibres | B | qualified | Hampton et al. 2025 (ToMEx); Tran et al. 2026 (A3 §5.1) | qualified: anchor context (23 phrases) |
| microfibre | particles_and_fibres | B | qualified | Lin et al. 2026; Wu and Tong 2013 (A3 §5.1) | qualified: v3.1 microfiber any_context (A3 5.1 'existing context list'), not the anchor list |
| microparticles plastics | particles_and_fibres | A | qualified | Zuanazzi et al. 2026 (A3 §5.1) | qualified: anchor context (23 phrases) |
| nanoparticles plastics | particles_and_fibres | A | qualified | Zuanazzi et al. 2026 (A3 §5.1) | qualified: anchor context (23 phrases) |
| plastic microbead | particles_and_fibres | A | qualified | Tran et al. 2026 (A3 §5.1) | qualified: anchor context (23 phrases) |
| plastic microfiber | particles_and_fibres | A | qualified | Zuanazzi et al. 2026 (A3 §5.1) | qualified: anchor context (23 phrases) |
| plastic microparticle | particles_and_fibres | A | qualified | A3 §5.1 (Tran et al. 2026; Zuanazzi et al. 2026) | qualified: anchor context (23 phrases) |
| plastic nanoparticle | particles_and_fibres | A | qualified | A3 §5.1 (Tran et al. 2026; Zuanazzi et al. 2026) | qualified: anchor context (23 phrases) |
| synthetic polymer microparticle | particles_and_fibres | A | qualified | Regulation (EU) 2023/2055 (A3 §5.1) | qualified: anchor context (23 phrases) |
| garbage patch | tyre_pellets_and_debris | A | co_term | Discard Studies Compendium (A3 §5.1) | qualified: anchor context (23 phrases) |
| nurdle | tyre_pellets_and_debris | A | qualified | Lin et al. 2026 (A3 §5.1) | qualified: anchor context (23 phrases) |
| pre-production pellet | tyre_pellets_and_debris | A | qualified | Lin et al. 2026 (A3 §5.1) | qualified: anchor context (23 phrases) |
| tyre wear | tyre_pellets_and_debris | A | qualified | Lin et al. 2026 (A3 §5.1) | qualified: anchor context (23 phrases) |
| waste plastics | tyre_pellets_and_debris | B | qualified | Zuanazzi et al. 2026 (A3 §5.1) | qualified: anchor context (23 phrases) |
| MNP | polymer_and_abbreviation_forms | B | co_term | Zimmermann et al. 2025; Tran et al. 2026 (A3 §5.1) | qualified: anchor context (23 phrases) |
| MNPs | polymer_and_abbreviation_forms | B | co_term | Zimmermann et al. 2025 (A3 §5.1) | qualified: anchor context (23 phrases) |
| plastic polymer | polymer_and_abbreviation_forms | B | co_term | Ortiz-Balsero et al. 2026, S1 (A3 §5.1) | qualified: anchor context (23 phrases) |
| thermoplastic | polymer_and_abbreviation_forms | B | co_term | Ortiz-Balsero et al. 2026, S1 (A3 §5.1) | qualified: anchor context (23 phrases) |
| Bamako Convention | trade_and_policy | A | co_term | A3 §5.5 (Tier A additions) | qualified: anchor context (23 phrases) |
| Basel Convention | trade_and_policy | A | co_term | A3 §5.5 (Tier A additions) | qualified: anchor context (23 phrases) |
| Basel Convention plastic-waste amendments | trade_and_policy | A | co_term | Farrelly and Chitaka 2023 (A3 §5.5) | qualified: anchor context (23 phrases) |
| National Sword | trade_and_policy | A | co_term | A3 §5.5 (transboundary trade row) | qualified: anchor context (23 phrases) |
| plastic waste trade | trade_and_policy | A | co_term | Farrelly and Chitaka 2023; Gündoğdu et al. 2025 (A3 §5.5) | qualified: anchor context (23 phrases) |
| waste import ban | trade_and_policy | A | co_term | A3 §5.5 (transboundary trade row) | qualified: anchor context (23 phrases) |
| Cancer Alley | justice_and_labour | B | co_term | A3 §5.5 (justice row) | qualified: anchor context (23 phrases) |
| environmental justice | justice_and_labour | B | co_term | A3 §5.5 (justice and exposure-disparities rows) | qualified: anchor context (23 phrases) |
| fenceline | justice_and_labour | B | co_term | A3 §5.5 (justice row) | qualified: anchor context (23 phrases) |
| informal recycling | justice_and_labour | A | co_term | A3 §5.5 (labour row; Velis and Cook 2021; Nøklebye et al. 2023) | qualified: anchor context (23 phrases) |
| informal sector | justice_and_labour | B | co_term | A3 §5.5 (labour row, broader query) | qualified: anchor context (23 phrases) |
| Small Island Developing States | justice_and_labour | B | co_term | A3 §5.5 (regional terms; Fuller et al. 2022 keywords) | qualified: anchor context (23 phrases) |
| urban recoverer | justice_and_labour | B | co_term | Foellmer et al. 2022 (WHO HEN 75 keyword map) (A3 §5.5) | qualified: anchor context (23 phrases) |
| waste pickers | justice_and_labour | A | co_term | A3 §5.5 (labour row; Velis and Cook 2021; Nøklebye et al. 2023) | qualified: anchor context (23 phrases) |
| greenwashing | circularity_and_greenwashing | B | co_term | A3 §5.5 (greenwashing row) | qualified: anchor context (23 phrases) |
| plastic credits | circularity_and_greenwashing | A | co_term | A3 §5.5 (greenwashing row; Nandakumar et al. 2021) | qualified: anchor context (23 phrases) |
| plastic offsets | circularity_and_greenwashing | A | co_term | A3 §5.5 (greenwashing row; Nandakumar et al. 2021) | qualified: anchor context (23 phrases) |
| recycling contamination | circularity_and_greenwashing | B | co_term | A3 §5.5 (wishcycling row) | qualified: anchor context (23 phrases) |
| wishcycling | circularity_and_greenwashing | B | co_term | A3 §5.5 (wishcycling row) | qualified: anchor context (23 phrases) |
| atmospheric deposition | exposure_matrix | B | co_term | A3 §5.8 BQ-S3(d) | qualified: anchor context (23 phrases) |
| breast milk | exposure_matrix | B | co_term | A3 §5.8 BQ-S3(d) | qualified: anchor context (23 phrases) |
| indoor dust | exposure_matrix | B | co_term | Barchiesi et al. 2026, Table SI3 (A3 §5.10.3); A3 §5.8 BQ-S3(d) | qualified: anchor context (23 phrases) |
| infant formula | exposure_matrix | B | co_term | A3 §5.8 BQ-S3(d) | qualified: anchor context (23 phrases) |
| anticolonial approaches to plastic pollution science | waste_colonialism_lens | A | co_term | A3 §5.5 (Tier A additions) | qualified: anchor context (23 phrases) |
| assimilative capacity | waste_colonialism_lens | B | co_term | A3 §5.5 (Tier B additions) | qualified: anchor context (23 phrases) |
| centre–periphery | waste_colonialism_lens | B | co_term | A3 §5.5 (Tier B additions) | qualified: anchor context (23 phrases) |
| corporate imperialism | waste_colonialism_lens | A | co_term | Peryman et al. 2024 (keywords) (A3 §5.5) | qualified: anchor context (23 phrases) |
| discard well | waste_colonialism_lens | B | co_term | A3 §5.5 (Tier B additions) | qualified: anchor context (23 phrases) |
| dumping rights | waste_colonialism_lens | B | co_term | A3 §5.5 (Tier B additions) | qualified: anchor context (23 phrases) |
| Indigenous political ecology | waste_colonialism_lens | A | co_term | Fuller et al. 2022 (keywords) (A3 §5.5) | qualified: anchor context (23 phrases) |
| myth of purity | waste_colonialism_lens | B | co_term | A3 §5.5 (Tier B additions; Sharma et al. 2017) | qualified: anchor context (23 phrases) |
| plastic colonialism | waste_colonialism_lens | A | co_term | Discard Studies 2018 (A3 §5.5) | qualified: anchor context (23 phrases) |
| plastic waste colonialism | waste_colonialism_lens | A | co_term | A3 §5.5 (waste-colonialism family) | qualified: anchor context (23 phrases) |
| plastic wastescape | waste_colonialism_lens | A | co_term | Lewis-Sing et al. 2019 (A3 §5.5) | qualified: anchor context (23 phrases) |
| sacrifice zone | waste_colonialism_lens | B | co_term | A3 §5.5 (Tier B additions) | qualified: anchor context (23 phrases) |
| technique of power | waste_colonialism_lens | B | co_term | A3 §5.5 (Tier B additions) | qualified: anchor context (23 phrases) |
| waste chains | waste_colonialism_lens | B | co_term | A3 §5.5 (Tier B additions) | qualified: anchor context (23 phrases) |
| waste colonialism | waste_colonialism_lens | A | co_term | Discard Studies 2018 (A3 §5.5) | qualified: anchor context (23 phrases) |
| waste regime | waste_colonialism_lens | B | co_term | A3 §5.5 (Tier B additions) | qualified: anchor context (23 phrases) |
| waste well | waste_colonialism_lens | B | co_term | A3 §5.5 (Tier B additions) | qualified: anchor context (23 phrases) |
| wastescape | waste_colonialism_lens | B | co_term | A3 §5.5 (Tier B additions) | qualified: anchor context (23 phrases) |
| Indigenous communities | indigenous_title | B | title_only | A3 §5.5 (Indigenous and community row) | title_only: anchor context on title.search, separate request |
| Indigenous knowledge | indigenous_title | B | title_only | A3 §5.5 (Indigenous and community row) | title_only: anchor context on title.search, separate request |
| Indigenous peoples | indigenous_title | B | title_only | A3 §5.5 (Indigenous and community row) | title_only: anchor context on title.search, separate request |
| Indigenous-led | indigenous_title | B | title_only | A3 §5.5 (Indigenous and community row) | title_only: anchor context on title.search, separate request |

Register source is the `source` field in `config/search_vocabulary_v1.yml`. Plural forms are not added separately: the register lists singular rows, and OpenAlex stems plurals.

## Excluded register rows

73 of 137 English rows are excluded; the rest are in the term table. Reasons are assigned in this order: in v3.1; exclusion phrase; abbreviation; template form; tier C; handling lens_evidence; tier D; never_standalone; handling exclude.

| reason | rows | terms |
|---|---:|---|
| stem collision (lead review 2026-11-25): OpenAlex stems "recycler" to "recycl", so it matches every anchored recycling work (23,264 hits alone vs about 500 for the other eight justice terms combined) | 1 | recycler |
| tier C (never queried) | 13 | tire particles; tire and road wear particles; discard studies; waste studies; social studies of waste; Empire of Waste; Empire of Plenty; Capitalocene; Plantationocene; Chthulucene; Pyrocene; Great Acceleration; waypoints |
| never_standalone | 22 | nanoparticles; PS; PE; PC; PA; PU; waste flows; solid waste management; legal issues in waste; waste-to-energy; recycling cooperatives; wastelands; wasting; lead; mulch; community; behaviour; discard; export; Indigenous; trash; petrochemical |
| already in v3.1 (in_v31) | 8 | mesoplastic; polystyrene; polyethylene; polypropylene; polylactic acid; PET; PLA; plastic particles |
| template form, polymer list not registered | 1 | [polymer] particle* |
| abbreviation not added (MP: Hossain 2026; NP: ambiguous) | 2 | MP; NP |
| exclusion phrase (A3 5.1) added to exclusions | 2 | perpendicular anisotropy; microplastic kinetics |
| handling lens_evidence (evidence only) | 7 | pollution is colonialism; waste neocolonialism; toxic colonialism; garbage imperialism; waste imperialism; environmental racism; dispossession by contamination |
| tier D (probe only; BQ-S3) | 17 | social norms; theory of planned behaviour; intention–behaviour gap; risk perception; disposal behaviour; littering; stigma; disgust; sense of place; psychosocial wellbeing; social life cycle assessment; environmental health equity; unequal exposure; decolonizing research; two-eyed seeing; community science; community-based participatory research |

## Items for lead review

- Microfibre uses the v3.1 `microfiber` any_context list (textile, textiles, laundry, washing, shedding, wastewater, microplastic), as A3 5.1 says ('with the existing context list'), not the anchor list. Marked `context_source` in the YAML.
- Waste-colonialism lens rows (18, handling co_term, tiers A and B) are included in theme waste_colonialism_lens and anchored. Rationale: A3 5.2 item 4 shows the anchored waste-colonialism phrases were 20 of 20 on-topic; BQ-1.3 (docs/BQ_1_3_RECALL_PROBES.md) found v3.1 missing 2 of 6 waste-colonialism anchors. Rows with handling lens_evidence stay excluded (evidence only).
- MP and NP are not added (MP: Hossain et al. 2026 excluded it; NP is ambiguous with nanoparticle). MNP and MNPs are added as co-term, as the register says.
- The `[polymer] particle*` template is not added: it needs a polymer-name list that the register does not give.
- Thermoplastic and plastic polymer are added as co-term (generic polymer chemistry under A3-D18 scope). They are the weakest rows; BQ-S3 should test them.
- Urban recoverer is a local-language term marked 'to test' in the register; it is added as co-term and needs a precision probe (0 anchored hits on 2026-11-25). Recycler was removed after the live counts (stem collision; see the excluded rows).
- Breast milk, infant formula, indoor dust and atmospheric deposition are added as co-term (BQ-S3(d) probes); the anchor list limits them to plastic works.
- Policy, trade and justice terms stay co_term, as the register says. A3 5.2 wants title-only patterns for highest-risk themes (policy, SSbD, trash, framing); this candidate does not change that rendering. BQ-S3's isolated probes decide whether any of them is demoted to title-only.
- The anchor list includes 'plastic products' and 'plastic production', which the v3.1 scope note records as noise when used as standalone terms. They are used here only as anchors, next to a theme term.

## Per-request dry-run lengths

Limit: 8000 characters per URL. Combined expression: 5175 characters.

| request | field | URL characters | operators |
|---|---|---:|---:|
| v31 | title_and_abstract.search | 3415 | 169 |
| combined | title_and_abstract.search | 5175 | 225 |
| theme:particles_and_fibres | title_and_abstract.search | 1583 | 55 |
| theme:tyre_pellets_and_debris | title_and_abstract.search | 1313 | 43 |
| theme:polymer_and_abbreviation_forms | title_and_abstract.search | 1263 | 42 |
| theme:trade_and_policy | title_and_abstract.search | 1389 | 44 |
| theme:justice_and_labour | title_and_abstract.search | 1425 | 47 |
| theme:circularity_and_greenwashing | title_and_abstract.search | 1320 | 43 |
| theme:exposure_matrix | title_and_abstract.search | 1304 | 42 |
| theme:waste_colonialism_lens | title_and_abstract.search | 1721 | 56 |
| title:indigenous_title | title.search | 1307 | 42 |
| incremental:particles_and_fibres | title_and_abstract.search | 4844 | 225 |
| incremental:tyre_pellets_and_debris | title_and_abstract.search | 4574 | 213 |
| incremental:polymer_and_abbreviation_forms | title_and_abstract.search | 4524 | 212 |
| incremental:trade_and_policy | title_and_abstract.search | 4650 | 214 |
| incremental:justice_and_labour | title_and_abstract.search | 4686 | 217 |
| incremental:circularity_and_greenwashing | title_and_abstract.search | 4581 | 213 |
| incremental:exposure_matrix | title_and_abstract.search | 4565 | 212 |
| incremental:waste_colonialism_lens | title_and_abstract.search | 4982 | 226 |


## Counts

Live count run on 2026-11-25 (UTC), title_and_abstract, v3.1 type exclusions on every request, one request
each (never OR-split; A3-C1). Output `docs/api_notes/query_v32_counts.json`; cache `data/interim/query_v32/`.
Credits: 350 for the first run, 170 for the lead's per-term probe of justice_and_labour, 40 for the rerun
after removing "recycler". These are OpenAlex record counts, not precision: none of these works is labelled yet.

| request | count | new vs v3.1 (theme AND NOT v3.1) |
|---|---:|---:|
| v3.1 baseline | 136,323 | - |
| v3.2 candidate, combined (one request) | 138,146 | +1,823 (+1.3%) |
| particles_and_fibres | 1,497 | 195 |
| tyre_pellets_and_debris | 2,291 | 570 |
| polymer_and_abbreviation_forms | 3,727 | 833 |
| trade_and_policy | 198 | 55 |
| justice_and_labour | 470 | 112 |
| circularity_and_greenwashing | 152 | 25 |
| exposure_matrix | 924 | 52 |
| waste_colonialism_lens | 43 | 11 |
| indigenous_title (title.search) | 4 | not requested |

Theme rows overlap, so they do not sum to the combined count.

Per-term probe, justice_and_labour (each term alone with the anchor context, 2026-11-25): environmental
justice 122, fenceline 3, Cancer Alley 0, waste pickers 140, informal recycling 59, informal sector 130,
recycler 23,264 (removed: stem collision), urban recoverer 0, Small Island Developing States 49.

Reading the counts:

- The candidate adds about 1,800 records (1.3%) to v3.1. Most of the gain is in polymer and abbreviation
  forms (833; the weak co-terms thermoplastic and plastic polymer are the first suspects) and in tyre,
  pellet and debris terms (570).
- The lifecycle-and-society and lens themes add few records (25 to 112 each). That fits BQ-1.3: v3.1
  already retrieves most anchored lifecycle works because its core list holds recycling and LCA terms.
- Zero-hit terms (Cancer Alley, urban recoverer) cost nothing in recall but add operators; BQ-S3 decides.
- Precision is unmeasured. Promotion follows only the existing precision rule after BQ-S3's labelled probes.
