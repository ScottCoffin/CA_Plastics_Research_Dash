# Human Labeling Guide — `guide_v1` (draft for owner approval)

**Status:** pending owner approval; not frozen and not authorized for gold-set annotation.
**Scope:** work-level labels for the S4 gold set.
**Approval record:** complete `docs/LABELING_GUIDE_REVIEW.md`; after approval, record the date and freeze this exact content as `guide_v1` before assigning any annotation.  A substantive change after approval requires a new guide version and review.

This guide turns the project definitions in `spec.md` A2 and C3–C4 into repeatable human decisions. It does not approve or promote the provisional `plastic-v2-candidate` query or `plastic-taxonomy-v1-candidate` taxonomy. Current rules and taxonomy seed concepts are candidate screening aids; annotators decide from the work evidence under this guide.

## 1. Unit, evidence, and order of decisions

The unit is one bibliographic work (`work_id`). Read its title and abstract first. Use the same record fields for each work; do not infer missing study facts from author affiliations, institution names, journal, OpenAlex topics, or a keyword hit alone. If authorized, accessible full text may resolve a case; record whether evidence came from abstract or full text.

Apply decisions in this order:

1. **Plastic relevance:** Is plastic debris/particles, a defined core subject, or a chemicals-in-plastics subject (including a tire-derived chemical when that is the primary research focus) the primary research subject? If no, do not assign a plastic tier or plastic-domain tags. If evidence is insufficient or genuinely conflicting, hold the item for adjudication rather than forcing a negative.
2. **Plastic tier:** For a relevant work, assign `core` or `chemicals-in-plastics` (Section 2).
3. **California sampling:** Independently decide whether field collection or deployed monitoring for this work occurred in California land or state waters; California mentions and affiliations alone do not establish sampling (Section 3).
4. **Domain tags:** Assign every supported domain in Section 4. These are multi-label, not mutually exclusive.
5. **Evidence:** Save the shortest exact excerpt that supports each non-obvious decision, with its source level. Do not paraphrase inside a quotation.

The project’s CA-plastic-centric flag is derived later: `plastic_related=true` and (`ca_led=true` or `ca_sampled` is `yes` or `partial`). `ca_led` is based on the first author’s California affiliation. Keep it distinct from `ca_sampled`; this guide does not create a new field in the current gold-work CSV.

G-5’s all-years works horizon (with the last 10 years emphasized) affects downstream sampling and display, not whether an individual work is plastic-related or CA-sampled. Do not use publication year as a label criterion.

## 2. Plastic relevance and tier

### Core (`plastic_tier=core`)

Label `plastic_related=true` when plastics/debris/particles are the primary subject, including macro-, meso-, micro-, or nanoplastics; plastic pollution, litter, debris, or fragments; plastic ingestion; environmental plastic pellets; plastic-pollution policy; and environmentally relevant synthetic textile microfibers or tire-wear particles. The work may study sources, occurrence, methods, fate, ecological effects, mitigation, or human exposure.

Apply context to collision-prone terms. “Microfiber” alone does not establish plastic relevance: environmental or synthetic/textile/plastic context must show that fibers are synthetic plastic. A textile study of natural fibers, an optical microfiber, or a fiber-optic sensor is not core. “Tire wear” alone does not establish particle relevance: require tire-wear particles or environmental particle/runoff/pollution context. Tire-derived chemicals such as 6PPD or 6PPD-quinone without a particle/debris focus belong in the tier below, not core. Mechanical “plastic deformation” or microplasticity in materials science is not environmental plastic relevance.

### Tier 2 (`plastic_tier=chemicals-in-plastics`)

Include work primarily about additives or chemicals in, from, or associated with plastics, including bisphenols, phthalates, and tire-derived chemicals when the study does not primarily concern tire-wear particles. Preserve this separate tier even when the chemical is measured in people, food, water, or the environment. A passing mention of BPA, phthalates, 6PPD, or another chemical in a plastic-related work does not by itself create a tier-2 label.

For a work whose primary subject is both plastic particles and their associated chemicals, use `core` when particle/debris behavior is central; use `chemicals-in-plastics` when chemical identity/exposure is central. If neither can be determined from the evidence, flag for adjudication. Do not assign both values to the single-valued `plastic_tier` field.

### Negative and unresolved relevance

Use `plastic_related=false` when the title/abstract provides enough evidence that plastics are incidental, a collision term has a non-plastic meaning, or the work concerns an unrelated material/mechanical use. Do not treat absence of a keyword as a negative if the supplied title/abstract is incomplete or unusable; hold that item for review. In gold-set output, unresolved items must remain unannotated/excluded until an adjudicator resolves them; never encode uncertainty as `false` merely to complete a row.

## 3. California sampling, mentions, and leadership

Use the C3 values `ca_sampled=yes | partial | no | unclear`.

- **`yes`:** Explicit evidence ties a field sample, environmental/biological/product collection, or deployed monitoring site to California land or California state waters. A named site is not required when the text clearly says sampling occurred in California.
- **`partial`:** The sampled footprint straddles the California boundary or includes a California-offshore/federal-water study area beyond the project’s three-nautical-mile state-waters limit. This follows owner answer G-4 and is filterable separately; do not silently upgrade beyond-3-nm sampling to `yes`.
- **`no`:** Evidence shows no qualifying field collection/deployed monitoring for this work, or shows sampling only outside the qualifying California geography. Lab analysis, modeling, a review, and a location mention alone are not sampling.
- **`unclear`:** Sampling is indicated but the site or sampling role cannot be determined from permitted evidence, or the geographic statement is too vague to resolve. Do not convert this to `no` solely because the abstract omits a site.

California geography for this decision is California land plus the CDFW state-waters polygon representing the three-nautical-mile zone. The polygon’s boundary is a project operational rule and is not a legal depiction of maritime limits; the Methods page carries that caveat. Do not invent coordinates or sites from a regional phrase.

### Required distinctions and edge cases

| Evidence pattern | Decision rule |
|---|---|
| California institution or first author, but samples are elsewhere / no samples | Does not establish `ca_sampled=yes`. Record `ca_led` separately from affiliation data. A CA-led human-health study without CA sampling can qualify through `ca_led`, consistent with G-3. |
| “California” / a California place appears as background, comparison, coauthor address, or literature context | Mention only; not sampling. Look for a statement linking field collection or deployed monitoring to the place. |
| Offshore sampling beyond 3 nm off California | `partial` under G-4, even if the study calls the region “off California”; do not classify as state-waters sampling. |
| Study includes both in-boundary and beyond-3-nm sites | `partial` because the sampled footprint crosses the project boundary. |
| Organisms or samples analyzed in a laboratory | The laboratory location is not the sample location. Label from the collection site: `yes` if collection in qualifying CA geography is explicit; `no` if another site is explicit; `unclear` if source location is absent. |
| Modeling using previously collected California data | The current modeling work did not itself sample; label `no` for `ca_sampled`. Preserve California-data use as context/evidence if the workflow supports it; do not turn data provenance into field collection by this work. |
| Review or synthesis of California studies | `no` for sampling by this work, even when it discusses California studies. |
| “Bay Area” with no explicit sampling site or unambiguous sampling statement | Do not infer a sampled site from the regional phrase alone. Use `unclear` if sampling is asserted but site is not resolvable; use `no` if it is only a mention/background. If the text explicitly says field samples were collected in the Bay Area, treat that as California land only when the wording unambiguously ties the collection to the region; otherwise adjudicate. |
| Wastewater-treatment plant | A plant’s California location qualifies only when the work explicitly reports field collection or deployed monitoring there. A plant used as a lab process, named as a facility, or discussed generically is not sampling evidence. |

### State-water boundary

Count marine sampling as `yes` only when the described site is in California state waters (the project’s three-nautical-mile zone) or the text clearly identifies a California land site. Named bays/estuaries must be assessed by the stated collection site or the project’s curated region geometry; do not use a bay centroid to infer that every sample lies inside the boundary. If a study spans both sides, use `partial`. For explicit California offshore sampling beyond the zone, use `partial` per G-4.

## 4. Domain tags (multi-label)

Use the current IDs from `config/taxonomy.yml`; assign zero or more supported tags. The YAML’s `seed_concepts` are discovery cues, not sufficient evidence by themselves. A concept must describe a substantive research aim, method, or result, rather than appear only in background. More than one tag may be correct. Do not manufacture labels outside this set in `guide_v1`.

| Current tag ID | Apply when the work substantively studies… |
|---|---|
| `occurrence_and_monitoring` | Presence, abundance, distribution, accumulation, trends, or field monitoring of plastic material. |
| `analytical_methods` | Detection, identification, quantification, characterization, or validation of analytical measurement methods. |
| `fate_transport_and_sorption` | Transport, weathering/degradation, transformation, adsorption/sorption, or movement through media. |
| `wastewater_and_treatment` | Wastewater, treatment processes, removal, effluent, or treatment-plant performance. |
| `ecotoxicology_and_trophic_transfer` | Effects on organisms/ecosystems, ingestion, transfer through food webs, or biological response. |
| `soil_and_agriculture` | Terrestrial soil, crops, agriculture, or plant systems as a substantive setting or endpoint. |
| `human_exposure_and_health_risk` | Human exposure, intake, inhalation/dermal pathways, dose, or health risk. |
| `air` | Atmospheric/airborne plastic particles, aerosol transport, or deposition. |

Assign all clearly supported tags (for example, a wastewater occurrence study may receive both `occurrence_and_monitoring` and `wastewater_and_treatment`). Do not assign `air` solely because “inhalation” appears in a health paper; assign it when air/atmospheric material is studied. These IDs are the owner-supplied candidate taxonomy in the current configuration; schema expansion or new tags require a new guide version.

## 5. Evidence and source constraints

For every non-obvious positive, negative, sampling, or domain decision, preserve a short, exact excerpt from the title, abstract, or permitted full text. Include enough words to identify the proposition (e.g., the sample collection sentence), not a broad paragraph. Retain source provenance in the annotation interface or evidence record so a reviewer can locate the quote. Distinguish direct collection evidence from mere place-name hits.

Use public bibliographic metadata and lawful, accessible text only. OA full text may be cached only in the project’s gitignored cache under the owner’s G-8 answer. Do not copy or commit full text, copyrighted article sections, paywalled text, or text whose license/terms do not permit the intended use. Publish only short excerpts consistent with the source license/terms and G-8; when rights or permitted snippet length are uncertain, quote the title/abstract if sufficient or record a locator/decision note without reproducing full-text prose. Never include personal emails, phone numbers, or social accounts in annotation notes.

## 6. Adjudication and consistency

The owner plus one or two colleagues may annotate; the owner adjudicates, per G-10. Independently annotate assigned records before discussion. Escalate unresolved scope, ambiguous geography, conflicting evidence, or tier/domain disagreement to the owner; retain the competing short evidence and the reason for uncertainty. Record the adjudicated value and rationale in the gold annotation record. Do not resolve by majority vote or by allowing a rule/model suggestion to overrule source evidence.

At least 20% of works are to be double-annotated under S4.3. Report agreement per label; the proposed F1/G-9 target for core-label Cohen’s κ is ≥0.7 before training. This is an evaluation target, not a pass claim for this guide or any current labels. Do not use held-out test items for model development, threshold tuning, or error analysis (F3); test suggestions must not be shown to annotators during development.

## 7. Worked decision examples (illustrative, not corpus labels)

| Hypothetical evidence | Plastic decision | `ca_sampled` | Why |
|---|---|---|---|
| Abstract reports microplastic abundance in sediment collected at a named California beach | `true`, `core` | `yes` | Plastic subject and CA field collection are explicit. |
| CA first author studies human exposure to plastic particles using a non-CA cohort; no California field collection | `true`, `core` | `no` | Leadership may qualify the derived CA-plastic-centric flag; it does not change sampling. |
| California-affiliated lab analyzes fish collected off California beyond 3 nm | Depends on plastic focus | `partial` | Collection provenance is offshore beyond project state waters; lab address is irrelevant. |
| Model estimates transport from a published San Francisco Bay dataset, with no new field work | Depends on plastic focus | `no` | The work models existing data rather than collecting samples. |
| Review says “Bay Area studies report microplastics” | `true`, `core` if plastics are its subject | `no` | Review/synthesis is not sampling by this work; the regional mention is not a collection. |
| Abstract says “samples from Bay Area sites” without identifying whether samples were actually collected there or where | Depends on plastic focus | `unclear` | Do not infer a site or role from an underspecified phrase. |
| Study measures microplastic removal in a California wastewater plant using influent/effluent collected at that facility | `true`, `core` | `yes` | Explicit plant field samples; likely both occurrence and wastewater tags if aims support them. |
| Work measures 6PPD-quinone exposure in runoff but not tire particles | `true`, `chemicals-in-plastics` | Based on actual field collection; otherwise `no`/`unclear` | Tire-derived chemical is tier 2 absent a particle focus. |
| “Microfiber” describes an optical waveguide | `false` | Usually `no` | Collision term is unrelated to environmental synthetic fibers. |

