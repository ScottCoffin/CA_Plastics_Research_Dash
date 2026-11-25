# Labelling guide addendum: taxonomy changes (2026-11-25)

**Status:** Approved by the owner on 2026-11-25 (BQ-S5 items D1 to D10, each taking the lead's default; see
[TAXONOMY_PROPOSAL.md](TAXONOMY_PROPOSAL.md)). This is a dated addendum for labellers. `guide_v1`
([LABELING_GUIDE.md](LABELING_GUIDE.md)), `guide_v2` ([LABELING_GUIDE_A2_ADDENDUM.md](LABELING_GUIDE_A2_ADDENDUM.md))
and `guide_v3` ([LABELING_GUIDE_A3_ADDENDUM.md](LABELING_GUIDE_A3_ADDENDUM.md)) stay as approved records. Where
this page is more specific, it applies. Machine IDs are exact.

This addendum does not change any existing label. Works already labelled keep their values. Relabelling is a
separate owner decision.

## 1. What changed

| Item | Change |
|---|---|
| Topic tags (D1, D2) | One list of 21 tags. The 8-tag list in older guides is replaced by this list. |
| Lifecycle tags (D3) | Nine new tags, including the sub-tag `waste_trade_and_global_flows`. |
| Tier (D4) | New tier `lifecycle_and_society`, with the tie-break and boundary rules in section 3. |
| Lens (D5, D6) | `analytic_lens` with eight values. Quoted evidence is required. |
| Centrality (D7) | `plastics_centrality`, set only for the lifecycle tier. |
| Origin (D8) | `origin`, optional, only when the work states it. |
| Review facets (D9) | Registered for later use only. You do not label them yet. |
| Experimental topic (D10) | `culture_media_and_discourse`, optional and marked experimental (section 6). |

## 2. Topic tags: one list

Assign zero or more tags. A tag needs its subject to be a main subject of the work, not a background mention.
The `seed_concepts` in `config/taxonomy.yml` are discovery cues only. Tags do not depend on tier: a `core` work
can carry a lifecycle tag, and vice versa.

Original tags (definitions from `guide_v1` section 4 and the taxonomy notes):

| Tag | Assign when the work substantively studies ... |
|---|---|
| `occurrence_and_monitoring` | presence, abundance, distribution, accumulation, trends or field monitoring of plastic |
| `analytical_methods` | detection, identification, quantification, characterization or validation of methods |
| `fate_transport_and_sorption` | transport, weathering or degradation, transformation, sorption, movement through media |
| `wastewater_and_treatment` | wastewater, treatment processes, removal, effluent or treatment-plant performance |
| `ecotoxicology_and_trophic_transfer` | effects on organisms or ecosystems, ingestion, transfer through food webs |
| `soil_and_agriculture` | terrestrial soil, crops, agriculture or plant systems as a setting or endpoint |
| `human_exposure_and_health_risk` | human exposure, intake, inhalation or dermal pathways, dose or health risk |
| `air` | atmospheric or airborne plastic particles, aerosol transport or deposition |
| `risk_assessment` | ecological or human risk assessment, risk characterization, thresholds derived from risk (added on owner request, 2026-11-11) |
| `plastisphere` | life living on plastic: microbes or animals colonizing, fouling or rafting on plastic. Microbial-community effects in soil, and works only on microbes or insects that biodegrade plastic, do not count. "Biofilm" counts only in the title |
| `plastic_associated_chemicals` | chemicals-in-plastics works (for example BPA, phthalates, 6PPD, plastic additives). Assigned by the label rule, not by hand; coverage is incomplete (REL-TIER2) |

Lifecycle and society tags (guide_v3 section 4, with the owner's D3 approval):

| Tag | Assign when the work's main subject is ... |
|---|---|
| `lca_and_sustainability` | life-cycle assessment, carbon footprint or sustainability assessment of plastics |
| `waste_management_and_recycling` | collection, landfill, incineration or recycling of plastic waste |
| `waste_trade_and_global_flows` | plastic waste trade and import bans (sub-tag of `waste_management_and_recycling`) |
| `policy_law_and_governance` | policy instruments, treaties, bans, levies, extended producer responsibility, regulation of plastics |
| `behaviour_and_perception` | individual and consumer behaviour, attitudes and psychology, including social norms, risk perception, disposal and stigma, where plastics are primary or substantial. Systems-level and power analyses go under `justice_colonialism_and_power` |
| `justice_colonialism_and_power` | justice, racism, colonialism, labour or power in relation to plastics as the primary analytic subject |
| `litter_and_trash` | plastic litter, trash, clean-ups, littering behaviour. "Trash" never qualifies alone |
| `bioplastics_and_alternatives` | bioplastics, compostable and biodegradable plastics, alternatives to conventional plastics |
| `safe_and_sustainable_by_design` | safe and sustainable by design (SSbD) for plastics or polymers: a design stage plus a safety and sustainability assessment |

Experimental (section 6): `culture_media_and_discourse`.

## 3. Tier: `lifecycle_and_society`

Use this tier for works whose primary subject is plastics as a material, product, waste stream or policy
object, and how they are made, used, governed, managed, perceived or distributed, rather than plastics as a
pollutant (`core`) or their chemistry (`chemicals-in-plastics`).

Order of decision:

1. Apply `guide_v1` section 2. If the work is `core` or `chemicals-in-plastics`, keep that tier.
2. Tie-break: keep `core` when plastic pollution (occurrence, effects, litter, debris, or a policy aimed at
   them) is the problem the work studies. Use `lifecycle_and_society` when plastics are studied as a material,
   product, waste stream or policy object without pollution as the framed problem (for example LCA, recycling
   systems, bioplastics, consumer behaviour, waste trade, SSbD).
3. Otherwise, set `plastics_centrality` (section 4):
   - `primary` or `substantial`: `plastic_related = yes`, tier `lifecycle_and_society`.
   - `incidental` or `none`: `plastic_related = no`. Nothing else is recorded for that work.
   - Evidence insufficient or genuinely conflicting: needs adjudication. Never force `incidental` to complete a row.

Boundary defaults: bioplastics and biodegradable or compostable plastics, plastic packaging, and SSbD for plastics
are in scope under this tier when the centrality test passes. A work that uses a polymer only as a fabrication
material (a composite, a device) is an unrelated material use under `guide_v1` section 2 and stays `no`.

Out of scope unless plastics are primary or substantial: generic waste (for example e-waste or hazardous waste),
generic LCA, generic sustainability, generic consumer psychology, generic polymer chemistry, and "waste
colonialism" about non-plastic waste. Pollution science, exposure and health-effects work stays in `core` or
`chemicals-in-plastics`. Borderline works are decided by gold labelling, not by a rule.

## 4. `plastics_centrality` (one value per work)

Set it only when the tier is `lifecycle_and_society`. Leave the default `not_assessed` for every other tier.

| Value | Set it when |
|---|---|
| `primary` | plastics, polymers, plastic products or a named plastic stream are the main object of the work |
| `substantial` | plastics are not the sole object, but a named, analysed object with plastics-specific evidence (a case, a dataset, a policy instrument, or a distinct section), and plastics appear in the title, abstract or keywords |
| `incidental` | plastics appear as one example in a list of waste or pollutant types, or in a passing sentence. Mark the work `plastic_related = no` |
| `none` | no meaningful plastics content. Mark the work `plastic_related = no` |
| `not_assessed` | default. Works not in the lifecycle candidate set, or labelled before this addendum |

The sheet stores centrality only for works you keep as plastic-related, so `incidental` and `none` are recorded
by the `no` answer. The wording of the four values is still open (A3-Q5).

## 5. `analytic_lens` and `lens_evidence`

A lens is a framing, optional, and can go with any topic tag. Multiple lenses are allowed.

**The rule: only when the work itself uses the frame, with the shortest exact excerpt that shows it in
`lens_evidence`. Never inferred from the topic.** A plastic waste trade study that does not use a frame gets
`waste_management_and_recycling` or `waste_trade_and_global_flows`, and no lens. A lens with no excerpt is not
saved; the app refuses it.

| Lens ID | The work explicitly frames plastics through ... |
|---|---|
| `waste_colonialism` | waste or pollution as domination of one group's homeland by another |
| `environmental_justice_and_racism` | environmental justice or racism, including fenceline, sacrifice-zone, spatial-injustice framings and slow violence |
| `indigenous_and_community_governance` | Indigenous participation or governance, including anticolonial or decolonial approaches |
| `community_and_participatory_methods` | community science or participatory research methods |
| `labour_and_informal_economy` | waste pickers, informal recycling, labour in plastic supply chains |
| `circularity_critique_and_greenwashing` | critique of circular-economy or biodegradability claims, greenwashing |
| `political_economy_centre_periphery` | waste flows, trade, dumping rights and import bans as power relations, including corporate imperialism |
| `responsibility_shifting` | critique of individual-responsibility framing, scalar mismatch, or extended producer responsibility design |

Not in the sheet yet: the `waste_colonialism` sub-fields in `guide_v3` section 6 (`colonialism_framing`,
`waste_colonialism_type`). Do not record them.

## 6. `origin` and the experimental topic

`origin` (optional): `primary` means plastic made as small particles on purpose; `secondary` means plastic
broken down from larger items; `not_stated` means the work does not say. Set it only when the work states the
origin. Leave it blank otherwise.

`culture_media_and_discourse` (optional, low weight): humanities, material culture, art, media and discourse
analyses of plastics. It is experimental until it has 40 gold examples and kappa 0.7 and F1 0.70. It is
excluded from per-tag metrics and from the P1 to P6 reporting. Assign it only when it clearly applies.

## 7. Study type

`study_type` stays a single design label. The taxonomy keeps 15 values, including `unclear_other`, which the
sheet does not offer: a work you cannot place goes to "Needs adjudication". The 15-value list is an open
question for the owner, and no value was added or removed by this addendum.

## 8. Where the labels go

The annotation sheet has four new columns: `analytic_lens`, `lens_evidence`, `plastics_centrality` and `origin`.
Sheets created before this addendum have the older header and still load; the new columns read as blank.
A blank `plastics_centrality` means `not_assessed`. The first save widens the header.

The review-derived facets of D9 (for example `human_exposure_pathway`, `polymer_type`) are registered in
`config/taxonomy.yml` and are not labelled yet. Each will be adopted one at a time with a benchmark.

## 9. Open items

- A3-Q5: the wording of the `plastics_centrality` values.
- The `study_type` count (section 7).
- D6: the public text for the lens values waits for owner approval before it is published.
