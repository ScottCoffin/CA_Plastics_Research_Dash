# Human Labeling Guide: A3 Addendum (`guide_v3`)

**Status:** Approved by the owner on 2026-11-18 (pre-approval QUESTIONS A3-Q5; "BQ-G0 approved" the same
day), including the `plastics_centrality` wording and the P4 target (section 9). The tier tie-break in
section 2 and the scope list in section 3 were added after that approval, from the independent review;
they restate rules already in `guide_v1` and the A3 spec and are marked **[review addition]**.

**Applied 2026-11-25:** the owner's taxonomy decisions (BQ-S5) are stated for labellers in
[LABELING_GUIDE_TAXONOMY_2026-11.md](LABELING_GUIDE_TAXONOMY_2026-11.md); where it is more specific, it applies.

`guide_v3` = `guide_v2` ([LABELING_GUIDE.md](LABELING_GUIDE.md) `guide_v1`, unchanged, plus
[LABELING_GUIDE_A2_ADDENDUM.md](LABELING_GUIDE_A2_ADDENDUM.md)) plus this addendum. `guide_v1` and
`guide_v2` stay frozen. The California evaluation sheet keeps `guide_version = guide_v2`; works labelled
under `guide_v3` (the global block, BQ-G3/G4) record `guide_v3`.

**Source:** [add_on_spec_3.md](add_on_spec_3.md) §1 (scope gate), §4.2-§4.6, §5.2 and §5.4; decisions
A3-D12 to A3-D20 in `.agent/DECISIONS.md`. Machine IDs below are exact; do not rename or translate them.

## 1. Candidate sets (the pipeline flags them; labellers do not decide membership)

- **Lifecycle-and-society candidate set:** works the pipeline matches with a lifecycle-and-society theme
  term (the vocabulary register, `config/search_vocabulary_v1.yml` from BQ-S1, built from A3 §5.5)
  together with a strong plastic anchor (section 1.1). Only these works get a `plastics_centrality`
  value; every other work gets `not_assessed`.
- **Lens-candidate set:** works matching a lens phrase (A3 §4.2 P6, its own stratum). Only these works
  get an `analytic_lens` decision; every other work gets `not_assessed`.

The labelling app shows both flags on each work.

### 1.1 Plastic-anchor rule (A3 §5.2)

A theme term makes a work a candidate only together with a strong anchor phrase in the same title or
abstract:

> plastic waste, plastic pollution, plastic debris, plastic litter, plastic bag(s), plastic bottle(s),
> plastic packaging, plastic products, plastic production, plastic recycling, single-use plastic(s),
> microplastic(s), bioplastic(s), biodegradable plastic(s), compostable plastic(s), plastics industry;
> polymer names count as anchors for LCA and recycling works only.

- Bare "plastic"/"plastics" is not an anchor (OpenAlex stems it to "plasticity").
- "Petrochemical" is not an anchor: petrochemical-pollution works are in only when plastics are
  `primary` or `substantial` (section 5).
- Policy, safe-and-sustainable-by-design, trash and framing terms are high risk and also use title-only
  patterns before promotion.
- The anchor rule only selects candidates. **`plastics_centrality` decides labelled scope.**

## 2. New tier `plastic_tier = lifecycle_and_society` (A3-D13, A3-D16)

Works whose primary subject is plastics as a material, product, waste stream or policy object, and how
these are produced, used, governed, managed, perceived or distributed across societies, rather than
plastics' occurrence or effects as pollutants (`core`) or their chemistry (`chemicals-in-plastics`).

**This changes `guide_v1` section 1, step 1.** Under `guide_v1`, a work that is neither core nor
chemicals-in-plastics gets no tier and `plastic_related = false`. Under `guide_v3`, such a work in the
lifecycle-and-society candidate set is checked for this tier before it is marked false.

Order of decision:
1. Apply `guide_v1` section 2. If the work is `core` or `chemicals-in-plastics`, keep that tier.
2. **Tie-break [review addition]:** `guide_v1` core already includes plastic-pollution policy and
   mitigation. Keep `core` when plastic pollution (occurrence, effects, litter, debris, or a policy aimed at
   them) is the problem the work studies. Use `lifecycle_and_society` when plastics are studied as a
   material, product, waste stream or policy object without pollution as the framed problem (for example
   LCA, recycling systems, bioplastics, consumer behaviour, waste trade, SSbD).
3. Otherwise, decide `plastics_centrality` (section 5):
   - `primary` or `substantial`: `plastic_related = true`, `plastic_tier = lifecycle_and_society`.
   - `incidental` or `none`: `plastic_related = false`, `plastic_tier` blank.
   - Evidence insufficient or genuinely conflicting: hold the item for adjudication, as `guide_v1`
     section 2 requires; never force `incidental` to complete a row.

Boundary defaults (A3-D12, accepted): bioplastics and biodegradable/compostable plastics, plastic
packaging, and safe-and-sustainable-by-design for plastics are in scope under this tier when the
centrality gate passes. A work that only uses a polymer as a fabrication material (a composite, a device)
is "an unrelated material/mechanical use" under `guide_v1` section 2 and stays `false`.

## 3. Out of scope unless plastics are primary or substantial (A3 §1, §5.4) [review addition]

Generic waste, generic LCA, generic sustainability, generic consumer psychology, generic polymer
chemistry, and "waste colonialism" about non-plastic waste (e-waste, hazardous waste). Pollution-science,
exposure and health-effects work stays in `core` or `chemicals-in-plastics`. The India waste-import review
(Sridhar and Kumar 2019) is a known borderline case: decide it by gold labelling, not by rule.

## 4. Topic tags, group "Lifecycle and society" (candidate)

Multi-label, like `guide_v1` section 4. Assign a tag only when its subject is a main subject of the work.

| ID | Assign when the work's main subject is ... |
|---|---|
| `lca_and_sustainability` | life-cycle assessment, carbon footprint or sustainability assessment of plastics |
| `waste_management_and_recycling` | collection, landfill, incineration, recycling of plastic waste; sub-topic `waste_trade_and_global_flows` for plastic waste trade and import bans |
| `policy_law_and_governance` | policy instruments, treaties, bans, levies, extended producer responsibility, regulation of plastics |
| `behaviour_and_perception` | individual and consumer behaviour, attitudes and psychology; extended (A3-D20): social norms (descriptive vs prescriptive), attitude-behaviour gaps, risk perception, disposal behaviour, stigma, psychosocial and wellbeing outcomes, where plastics are primary or substantial |
| `justice_colonialism_and_power` | justice, racism, colonialism, labour or power in relation to plastics as the primary analytic subject |
| `litter_and_trash` | plastic litter, trash, clean-ups, littering behaviour ("trash" never qualifies alone) |
| `bioplastics_and_alternatives` | bioplastics, compostable and biodegradable plastics, alternatives to conventional plastics |
| `safe_and_sustainable_by_design` | SSbD of plastics or polymers (a design stage plus a safety and sustainability assessment) |
| `culture_media_and_discourse` | humanities, material culture, art, media and discourse analyses of plastics. Optional, low weight, outside P1-P6, assigned opportunistically (A3-D17). Experimental while it has fewer than 40 gold examples, or kappa < 0.7 / F1 < 0.70 (A2 rule) |

Keep `behaviour_and_perception` for individuals and consumers. Systems-level and power analyses go under
`justice_colonialism_and_power` or another tag, never under behaviour.

## 5. `plastics_centrality` (single-valued scope gate, A3-D18)

Assigned only to works in the lifecycle-and-society candidate set (section 1).

| Value | Definition | In corpus? |
|---|---|---|
| `primary` | Plastics, polymers, plastic products or a named plastic stream are the main object of the work. | Yes |
| `substantial` | Plastics are not the sole object but are a named, analysed object with plastics-specific evidence, a case, a dataset, a policy instrument, or an argument occupying a distinct section, and plastics appear in the title, abstract or keywords. | Yes |
| `incidental` | Plastics appear as one example in a list of waste or pollutant types, or in a passing sentence. | No (may appear in Related Resources) |
| `none` | No meaningful plastics content. | No |
| `not_assessed` | The work was not in the candidate set, or was labelled before `guide_v3`. | n/a |

## 6. `analytic_lens[]` and `lens_evidence` (multi-valued, optional, A3-D14, A3-D20)

A cross-cutting facet usable with any topic tag (a monitoring study using Indigenous-led methods keeps its
scientific tag and may add a lens). Decided only for works in the lens-candidate set (section 1).

**Assignment rule (explicit framing only).** Assign a lens only when the work itself adopts or analyses
the frame, and paste the shortest exact excerpt that shows it into `lens_evidence` (as `guide_v1`
section 1 step 5 requires for evidence). Never infer a frame from the topic: a plastic waste trade study
that does not use the frame gets `waste_management_and_recycling` / `waste_trade_and_global_flows` and no
lens.

| ID | The work explicitly frames plastics through ... |
|---|---|
| `waste_colonialism` | waste or pollution as domination of one group's homeland by another; optional sub-fields in their own columns: `colonialism_framing` = `transboundary_disposal` \| `land_and_dispossession`; `waste_colonialism_type` = `classical` \| `neocolonial_export` \| `incidental_accumulation` \| `criminal_trade` |
| `environmental_justice_and_racism` | environmental justice or racism, including fenceline, sacrifice-zone, wastescape and spatial-injustice framings and slow violence (A3-D20 fold-in of `spatial_injustice`) |
| `indigenous_and_community_governance` | Indigenous participation or governance, including anticolonial or decolonial approaches to plastics science and governance (A3-D20 fold-in of `decolonial_and_indigenous_research`) |
| `community_and_participatory_methods` | community science or participatory research methods |
| `labour_and_informal_economy` | waste pickers, informal recycling, labour in plastic supply chains |
| `circularity_critique_and_greenwashing` | critique of circular-economy or biodegradability claims, greenwashing |
| `political_economy_centre_periphery` | waste flows, trade, dumping rights and import bans as power relations, including corporate imperialism |
| `responsibility_shifting` | critique of individual-responsibility framing, scalar mismatch, extended producer responsibility design |

A lens candidate with no explicit frame gets an empty `analytic_lens` and an empty `lens_evidence`.

Public text says "works using this analytic frame" and links the lens definition; the Atlas makes no
statement about whether a frame is correct, and About and Glossary describe both senses of waste
colonialism with their sources (A3 §5.4 item 5). The A3-D20 reconciliation is implemented and tested now
and ships publicly only after owner approval (A3-Q7).

## 7. New template fields

`curation/gold_works.csv` gains six columns (the California evaluation sheet is unchanged; its backfill is
in `curation/a3_lens_backfill.csv`):

| Field | Values | Rule |
|---|---|---|
| `analytic_lens` | `;`-separated lens IDs, empty, or `not_assessed` | section 6 |
| `lens_evidence` | exact excerpt, or empty | required when `analytic_lens` is non-empty |
| `colonialism_framing` | empty, `transboundary_disposal`, `land_and_dispossession` | only with `waste_colonialism` |
| `waste_colonialism_type` | empty, `classical`, `neocolonial_export`, `incidental_accumulation`, `criminal_trade` | only with `waste_colonialism` |
| `plastics_centrality` | section 5 values | required for lifecycle-and-society candidates |
| `role` | `gold` \| `guide_example` | `guide_example` works never enter any frame or test set (A3 §4.3 item 8) |

## 8. The California works already labelled (A3-D15)

A3 (written on 2026-11-18) counted 13 labelled California works (H9 at the time); by the BQ-G1 status
note the same day the owner had labelled 38 of the 150 (`docs/BQ_G1_STATUS.md`). All 38 get
`plastics_centrality = not_assessed` and `analytic_lens = not_assessed` in
`curation/a3_lens_backfill.csv`. A work is re-opened only if A3 conflicts with its label; nothing was
re-opened. Five are flagged `review_optional` for the owner:

- `W1970066681`, `W1539877952`, `W3157208304` (labelled `true`, `core`): an LCA of biodegradable packaging,
  the plastics industry's role in bag laws, and a biodegradable polyester precursor; under section 2 their
  tier may be `lifecycle_and_society` instead of `core`. Relevance is unchanged.
- `W2037994813` (labelled `false`) and `W3084276090` (labelled `true`): composites that use HDPE or PP as a
  fabrication material; `guide_v1` section 2 treats an unrelated material use as `false`, so the two
  labels disagree with each other. The owner's labels stand until the owner decides.

## 9. Precision target for the new tier (P4)

P4 = share of `lifecycle_and_society` works with `plastics_centrality` in {`primary`, `substantial`},
estimated in its own stratum with the P1 half-width goal (95% CI half-width <= 0.05). Target (agent
proposal accepted with BQ-G0 on 2026-11-18; A3 §4.2 left the number to the owner): the tier is shown
publicly only when the P4 point estimate is at least 0.80; below 0.80, or while the half-width exceeds
0.05, results are labelled "indicative".

## 10. Calibration cases (`role = guide_example`)

These five works teach the gate. They are listed with OpenAlex IDs and DOIs in
`curation/a3_guide_examples.csv` and are excluded from every frame, test and audit sample. The labels
were approved with this guide; the lens values for the three `primary` cases are agent proposals (A3
§5.4 gives no lens for them) and rest on the quoted text shown.

| Work | Label | Evidence |
|---|---|---|
| Ashworth (2026), "Empires of Waste. Seeing and Confronting the Global Politics of Throwing Things Away", Millennium (DOI 10.1177/03058298261464283) | `incidental` (A3-Q6) | A theory piece on the global politics of waste; plastics are one example among several waste streams (A3 §5.4). Boundary case: the abstract names plastics. Quoted evidence is checked in BQ-G7 against Zotero PBHFXCHZ. |
| Foellmer et al. (2022), "How do the cultural contexts of waste practices affect health and well-being?", WHO/Europe Health Evidence Network synthesis report 75 | `incidental` (A3-Q6) | Scope is municipal solid waste; litter is not necessarily plastic (A3 §5.4). Quoted evidence is checked in BQ-G7 against Zotero ZE57F89A. |
| Peryman et al. (2024), "Plastic pollution as waste colonialism in Aotearoa (New Zealand)", Marine Policy 163:106078 (DOI 10.1016/j.marpol.2024.106078) | `primary`; lens `waste_colonialism` | Abstract (Zotero FVXB5LJV, read 2026-11-18): "Taking a full life-cycle approach to understanding plastic pollution, this study explores the interconnections between plastics, power, and people"; "Plastic pollution as waste colonialism also perpetuates significant inequities for Aotearoa’s most disenfranchised communities". |
| Stoett (2024), "Plastic Waste Colonialism: A Typology of Global Toxicity" (book chapter, DOI 10.1007/978-3-031-51358-9_1) | `primary` (title level); lens `waste_colonialism` | Title (OpenAlex W4392308148). |
| Gutberlet (2023), "Global Plastic Pollution and Informal Waste Pickers", Cambridge Prisms: Plastics (DOI 10.1017/plc.2023.10) | `primary` (title level); lens `labour_and_informal_economy` | Title (OpenAlex W4381512825). |
