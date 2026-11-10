# Human Labeling Guide: A2 Addendum (draft for `guide_v2`)

**Status:** Draft addendum for guide_v2. Not approved. `guide_v1` remains the
frozen, approved guide; do not annotate A2 fields for the gold set until the
owner approves this addendum (QUESTIONS.md EM-1-A).

**Scope:** New A2 label fields only. It extends, and does not replace,
[LABELING_GUIDE.md](LABELING_GUIDE.md) (`guide_v1`). Sections 1 to 7 of
`guide_v1` still apply to plastic relevance, tier, California sampling and
evidence rules. The A2 vocabulary is specified in
[add_on_spec_2.md](add_on_spec_2.md) (§3 and §4).

**Machine IDs:** Every value in this draft is the exact ID stored in
`config/taxonomy.yml` under `add_on_a2`. Do not rename or translate IDs.

## 1. study_type (design of the work)

Assign one primary `study_type` per work. Decide from the title and abstract
first. Use full text only where it is authorized and it resolves a case, and
record the evidence source as `guide_v1` Section 1 requires.

- `study_type` answers "what design did the authors use?". It is single-valued.
- `discipline` (the topic, such as tire wear or drinking water) is multi-label.
  A2-C1 keeps the two apart: one work can have several disciplines and exactly
  one study_type.
- An optional hidden `study_type_secondary` may hold additional designs when
  the work is genuinely mixed (A2-D1). It is not shown in the primary labelling
  view and it is never required.
- `unclear_other` is always routed to `needs_review`. It is not a default.

### 1.1 Values

Definitions and disambiguation notes are copied from A2 §3.

| Value | Definition | Disambiguation |
|---|---|---|
| field_occurrence | Field sampling measuring levels or characteristics (environmental, biological, food, drinking water, dust, indoor air); monitoring, surveys, citizen science | New method validated on field samples → method_development |
| source_emission | Release from a product, material or activity | Post-release transport → pathway_load |
| pathway_load | Concentration, flux or loading through stormwater, wastewater, agricultural runoff, air | Evaluating a control → mitigation_eval |
| fate_transport | Degradation, weathering, sorption, settling, advection, burial | Lab and field both |
| exposure_lab_toxicity | Controlled lab exposure of organisms, tissues or cells (optional test_system ∈ in_vivo, in_vitro, other) | Cross-checked against ToMEx aquatic DOIs (EM-15) |
| mesocosm_semifield | Microcosm, mesocosm, enclosure | |
| human_exposure_health | Human subjects or samples: biomonitoring, tissue detection, epidemiology | Intake estimates from literature values → modelling_risk |
| method_development | Sampling, extraction, identification, quantification, QA/QC, interlaboratory studies | |
| modelling_risk | Transport, exposure or load models; risk assessment; threshold derivation | Meta-analysis → review_synthesis |
| mitigation_eval | Empirical evaluation of controls: treatment, BMPs, LID, filters, alternatives, policy effectiveness | |
| policy_social | Policy analysis, economics, behaviour, equity, tribal engagement, education | |
| review_synthesis | Narrative, systematic or scoping review; meta-analysis; evidence map; bibliometric | OpenAlex type = 'review' is a prior only (§4) |
| data_resource | Dataset, database, software or tool | |
| perspective_guidance | Commentary, editorial, guidance, strategy or report with no primary data | |
| unclear_other | Not assignable | Always needs_review |

`exposure_lab_toxicity` takes an optional `test_system` with the values
`in_vivo`, `in_vitro` or `other`. Record it only for that study_type.

### 1.2 Rules for study_type

- OpenAlex `type = 'review'` is a prior for `review_synthesis`. It is never the
  label. A work tagged as a review by OpenAlex still needs the abstract to
  show a review design.
- [INF] Before any model is trained, aim for at least 40 gold examples per
  study_type value (about 600 works in total).
- [INF] A study_type value whose inter-annotator κ is below 0.7, or whose
  per-tag F1 is below 0.70, ships as "experimental" and is labelled as such in
  any output.

## 2. Facets (multi-label)

Facets are optional-per-work lists. Assign every supported value. Do not force
a value for a work that gives no evidence for it.

| Facet | Values | How to decide |
|---|---|---|
| compartment[] | surface_water, sediment, biota, air, indoor_air, indoor_dust, soil, wastewater_stream, stormwater_stream, drinking_water, food, human_tissue | Monitoring scope: surface waters (rivers, streams, estuaries, lakes, reservoirs and nearshore marine waters), associated sediments, surface water discharges (stormwater, wastewater) and aquatic biota. `indoor_air` and `indoor_dust` are atlas additions, supported by DTSC's 2023 proposal, which reports microplastics in household dust and indoor air. |
| waterbody_type[] | coastal_subembayment, estuary, nearshore, offshore, river_stream, lake_reservoir, groundwater | Marine environments (coastal subembayments, estuaries, nearshore and offshore waters) and freshwater systems (lakes, creeks and rivers). Use `groundwater` only when the work sampled or modelled groundwater. |
| pathway[] | urban_runoff_stormwater, wastewater, agricultural_runoff, atmospheric_deposition, direct_discharge_litter, indoor_release | The environmental route through which plastic moves from source to receptor. Use this for the route the work studies, not for every route it mentions. |
| source_category[] (coarse) | vehicle_tires, textiles, single_use_foodware_packaging, agriculture, fisheries_aquaculture, preproduction_pellets, consumer_product_other | Coarse source groups following the Ocean Plastics Council categories (vehicle tires, textiles, single-use foodware and packaging, agriculture, fisheries and aquaculture). `preproduction_pellets` covers nurdles and other pellets. |
| product_type[] (fine) | See 2.1 | Keyword rules with spot-check validation, not a trained classifier. |
| size_class[] | macro, micro, nano, unspecified | Macroplastics are debris larger than 5 mm. Nanoplastics are particles smaller than 1 µm. Every `micro` rule includes `nano` (see 2.2). |
| size_subclass[] (optional) | nano_1_100nm, submicron_100nm_1um, small_micro_1_100um, large_micro_100um_5mm | Assign only when the work reports its own size range (A2-D9). See 2.2. |
| rwqcb_region[] | 1 to 9 (North Coast to San Diego), offshore_state_waters, offshore_or_unassigned, statewide_unspecified | Derived from sampled coordinates, not hand-labelled. See 2.3. |

### 2.1 product_type and the parent/subtype rule

Product types follow DTSC Table 1, Table A1 and footnote 1. The full list is in
`config/taxonomy.yml`. Parent values are:

- `laundry_dish_detergents`, with subtypes `detergent_insoluble_polymers`,
  `detergent_fragrance_microcapsules` and `detergent_water_soluble_polymers`.
- `food_contact_articles`, with subtypes `food_contact_baby_bottles`,
  `food_contact_beverage_bottles`, `food_contact_films`,
  `food_contact_wrappers`, `food_contact_ps_foam` and `food_contact_tea_bags`.

Rule: a work that names only a parent (for example "detergents" or "food
contact materials") gets the parent value only. Add a subtype only when the
work names that subtype or its specific product. Do not infer a subtype from
the parent.

Other values, such as `artificial_turf_infill`, `paints_coatings`,
`plastic_film_mulch`, `cigarette_filters`, `childrens_toys`, `plastic_bags` and
`silicone_cookware`, stand alone.

### 2.2 Size: nano, micro and subclasses

- The Monitoring Strategy adopts the State Water Board definition: particles
  with at least three dimensions greater than 1 nm and less than 5 mm. Natural
  polymers that have not been chemically modified are excluded.
- Nanoplastics (below 1 µm) fall within microplastics. A work on nanoplastics
  gets `nano` and also `micro`, unless it is clearly outside the micro scope.
  The rule "every `micro` rule includes `nano`" applies in every rule.
- `size_subclass` is optional. It uses DTSC 2023 proposal ranges
  (nano 1 to <100 nm; submicron 100 nm to <1 µm; small micro 1 to <100 µm;
  large micro 100 µm to <5 mm). Assign a subclass only when the work reports a
  size range that falls within it. Do not convert a reported range from a
  different scale.

### 2.3 rwqcb_region (derived, not hand-labelled)

`rwqcb_region` is computed from the sampling coordinates in the sampling
record. Annotators do not type it. Its values are:

- Regions 1 to 9 (North Coast, San Francisco Bay, Central Coast, Los Angeles,
  Central Valley, Lahontan, Colorado River, Santa Ana, San Diego).
- `offshore_state_waters`: sampling points inside California state waters
  that fall outside every regional polygon. These are the offshore points the
  `guide_v1` boundary rules place inside state waters.
- `offshore_or_unassigned`: sampling points outside state waters, or points
  that cannot be assigned to a region. Offshore sampling beyond 3 nm keeps
  `ca_sampled = partial` under `guide_v1` Section 3 (G-4); the region value
  does not change that label.
- `statewide_unspecified`: the work covers California but gives no site or
  coordinates. It is not assigned to a region.

## 3. Definitions crosswalk and nomenclature conflict

Several sources define "microplastic" or the size classes differently. The
atlas uses the Monitoring Strategy definition for `size_class`. The table
shows where the other sources differ.

| Source | Definition (short quote) | Size note |
|---|---|---|
| Monitoring Strategy (adopts State Water Board Resolution 2020-0021) | "particles which have at least three dimensions that are greater than 1 nm and less than 5 mm" | "Nanoplastics" are below 1 µm and sit within microplastics. |
| DTSC 2023 proposal (superseded) | "solid polymeric materials to which chemical additives or other substances may have been added" | Its "nanoplastics" are 1 nm to below 100 nm. |
| DTSC final listing (June 2026) | "plastics that are less than 5 millimeters (mm) in their longest dimension" | No lower size limit and no polymer-type distinction. |
| DTSC Background Document (Nov 2025) | "generally plastics that are less than 5 millimeters (mm) in their longest dimension" | Splits primary and secondary microplastics. |

Nomenclature conflict: the DTSC 2023 proposal calls 1 nm to below 100 nm
"nanoplastics" and 100 nm to below 1 µm "sub-micron plastics", while the
Monitoring Strategy calls everything below 1 µm "nanoplastics". Annotators
do not choose between these. They record the size the work reports, set
`size_class` by the Monitoring Strategy rule, and use `size_subclass` only
when the work reports its own size range.

[INF] Where a source's definition is quoted in a work, record that quote as
evidence. It does not change the label.

## 4. Worked edge cases

Each case below is written for this addendum. It is marked [INF] because the
decision is an inference from the A2 disambiguation notes and `guide_v1`, and
the owner has not yet reviewed it.

1. [INF] **New method validated on field samples.** A paper proposes a
   polymer-identification protocol and tests it on river sediment. Label
   `study_type = method_development`. The field samples are the validation
   material, not the design. Do not label `field_occurrence` unless the paper
   also reports occurrence results as a main aim.

2. [INF] **Intake estimate from literature values.** A paper estimates human
   microplastic intake by combining published concentrations in food and
   drinking water with consumption rates. No new human samples are analysed.
   Label `study_type = modelling_risk`, not `human_exposure_health`.

3. [INF] **Meta-analysis.** A paper pools effect sizes from published
   exposure studies. Label `study_type = review_synthesis`. If the same paper
   fits a new dose-response model to the pooled data as its main output, record
   the secondary design in `study_type_secondary` (A2-D1).

4. [INF] **Detergent paper that does not name a subtype.** A paper examines
   plastic microbeads and polymers in laundry detergent but does not say which
   polymer class or fragrance system is involved. Label
   `product_type = laundry_dish_detergents` only. Do not add a subtype.

5. [INF] **Tire-wear stormwater loading.** A paper measures tire-wear particle
   concentrations and loads in urban stormwater runoff. Label
   `study_type = pathway_load`, `source_category` includes `vehicle_tires`,
   and `pathway` includes `urban_runoff_stormwater`. Tire-wear particle
   relevance is decided under `guide_v1` Section 2, not here.

6. [INF] **Lab exposure of field-collected organisms.** A paper collects
   mussels from a California estuary and exposes them to microplastics in
   aquaria. Label `study_type = exposure_lab_toxicity` with
   `test_system = in_vivo`. Add `waterbody_type = estuary` only if the field
   collection site is named. The `guide_v1` edge case for this situation still
   applies to California sampling.

7. [INF] **Review that is also a bibliometric analysis.** A paper maps
   publication trends and reviews the findings of the selected studies.
   Label `study_type = review_synthesis`. OpenAlex may also tag it as a
   review. That tag supports the label but does not set it.

8. [INF] **Policy paper with a mock dataset.** A guidance document presents
   an illustrative calculation with invented numbers and no measured data.
   Label `study_type = perspective_guidance`, not `modelling_risk`. A
   calculation that uses measured inputs is `modelling_risk`.

## 5. Approval checklist

Please review this addendum and confirm each item before it is merged into
`guide_v2`:

- [ ] Study_type vocabulary and disambiguation notes match A2 §3.
- [ ] One primary study_type per work, with `discipline` kept separate.
- [ ] `unclear_other` always routes to `needs_review`.
- [ ] `test_system` applies only to `exposure_lab_toxicity`.
- [ ] OpenAlex `review` is a prior, not a label.
- [ ] Facet definitions and the parent/subtype rule for `product_type` match
      A2 §4.
- [ ] Every micro rule includes nano; `size_subclass` is used only when the
      work reports a range (A2-D9).
- [ ] `rwqcb_region` is derived from coordinates, and offshore values are
      explained as stated.
- [ ] Definitions crosswalk quotes are short and match the sources.
- [ ] Worked edge cases agree with `guide_v1` Sections 2 and 3.
- [ ] The ≥ 40 examples per value rule and the κ 0.7 / F1 0.70 "experimental"
      threshold are accepted as planning targets.
- [ ] Owner approval is recorded, with the date and the approved file hash,
      in `docs/LABELING_GUIDE_REVIEW.md` before any A2 field is annotated.
