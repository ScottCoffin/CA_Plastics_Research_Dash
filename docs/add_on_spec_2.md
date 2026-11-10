ADD-ON SPEC A2 — Evidence Map, study_type, Need Ledger (V-9), Related Resources, Policy Panel
Base specification: [spec.md](../spec.md). Integration status: tasks EM-1..EM-18 are scheduled in `.agent/TODO.md`; conflicts and defaults are in `.agent/DECISIONS.md` and `.agent/QUESTIONS.md`.
Status: integration add-on to the base spec (CA Plastics Research Atlas) and Add-on A1. Markers: [INF] proposed or inferred, [VERIFY] unresolved, [OWNER] owner statement not independently verified. Open decisions are in §10.Audience: orchestrator and worker agents, plus the owner. Ledger row text lives in the companion data file docs\opc_needs_csv_Need_Ledger_Data_File_companion_to_Add_on_Spec_A2.xlsx (document "docs\opc_needs_csv_Need_Ledger_Data_File_companion_to_Add_on_Spec_A2.xlsx", version 3 or later; 70 rows, 20 columns; contract in §6.3). Workers do not re-verify quoted source items. They run the regression test in EM-1 and flag wording drift. Source verification status is in §12.
Owner determinations recorded 2026-11-09 (log in docs/DECISIONS.md)
•	ToMEx DOI list comes from the PSSDplusplus R package dataset tomex2; the column DOI exists in that dataset [OWNER]. Scope is the aquatic-organisms database. ToMEx 3.0 output (a separate in-progress project) will be added once available [OWNER].
•	The Minderoo Plastic Health Map is not included anywhere in the tool.
•	Regional Water Board boundaries come from the hosted feature service (§4). The layer is treated as openly licensed, with a mandatory accuracy disclaimer and source links [OWNER].
•	Plastic Pollution Coalition / Global Plastic Laws is link-only. California-specific laws appear on the owner's California search page [OWNER]. No integration and no outreach.
•	The Solutions-track policy panel and the DTSC regulatory timeline (EM-18) are included.
•	The link-out launch set is accepted.
•	Block D covers DTSC's narrowed categories plus the broader initial list. The ten additional ledger rows (N1.9–N1.11, N2.8–N2.10, N4.5, N4.6, M4, M5) are included.
•	The August 2026 SFEI report is the canonical Monitoring Strategy [OWNER].

0. Operating rules (inherit base spec and A1 §0, plus)
1.	Complementarity. Do not duplicate existing plastic evidence resources. ToMEx is an open access database and open source R Shiny web application that enables users to upload, search, visualize, and analyze microplastic toxicity data 1. The atlas shows counts of California works and links out. It builds no dose-response, effect-direction, forest-plot, SSD or health-outcome views.
2.	Volume, not strength. Evidence maps do not synthesise existing evidence 2. Every view carries the caption "Volume of California-relevant research (distinct works). Not a measure of quality, effect or sufficiency."
3.	Absence is not a gap. Empty cells can reflect pipeline recall, the California-institution candidate filter, or classifier error. Every cell shows its needs_review share.
4.	Counts come only from DuckDB tables (A1 C4). No per-entity pages (A1 C13). No frontier-LLM classifiers.
5.	Attribution and non-endorsement. Paraphrase, short quotes, links. The atlas is not an official OPC, SFEI, DTSC, OEHHA, Water Board or partner product. Do not commit source PDFs or full-text extracts.
6.	Source identity.
◦	2022 Statewide Microplastics Strategy: OPC, February 2022.
◦	Statewide Plastics Monitoring Strategy and Planning Framework: the August 2026 SFEI report (#1289) prepared with the Moore Institute and funded by OPC (sfei publication #1289 august 2026 3; Funded by California Ocean Protection Council 3). The suggested citation lists Lin, D.; Hale, T.; Paterson, K.; Miller, E.; Moore, S. 2026 4, while the title page lists four preparers (no Miller). Use the suggested citation verbatim. OPC also hosts an earlier Public Review February 2026 5 version; page numbers in this spec refer to the August 2026 file.
◦	DTSC Safer Consumer Products (SCP) documents: the Three-Year Priority Product Work Plan (2024–2026); the microplastics Candidate Chemicals listing and research page; the Proposal to Add Microplastics to the Candidate Chemicals List (Virtual Public Workshop: June 27, 2023 6; a proposal; 9 pages; no tables or appendices); and the Background Document on DTSC's Microplastics in Consumer Products Research (November 2025 Prepared by Department of Toxic Substances Control Safer Consumer Products Program California Environmental Protection Agency 7; printed "Page N of 24" = PDF N+1; calls itself preliminary screening research results 7).
7.	Disclosure. The owner is named under OEHHA in the Monitoring Strategy's State Advisory Group (Office of Environmental Health Hazard Assessment — Scott Coffin, Wesley Smith 3), as a consultant on the 2022 Strategy (Dr. Scott Coffin (State Water Resources Control Board) 4), and in the DTSC 2023 proposal's acknowledgement (DTSC would like to extend its sincere appreciation to Dr. Scott Coffin with the California State Water Resources Control Board 4). The owner is also an author of ToMEx 2.0 and a co-founder of Plastiverse (project notes). The About/Methods tab states these relationships (A2-D8).
8.	Listing is not regulation. DTSC's listing does not create new regulatory requirements 8 and At this time, DTSC has not proposed to regulate any Priority Products containing or generating microplastics. 9 The atlas never implies a status beyond what DTSC states.
9.	Link-out only. Related resources are never ingested, mirrored or scraped (§8).

1. What A2 adds
•	A defined study_type. The base spec's work_labels lists study_type 10, but an extraction of the spec found no controlled vocabulary for it.
•	Evidence-map views. The base spec has a monitoring "data gaps" view (matrix × region × year) 10 and an optional evidence-map view: matrix × discipline heatmap of works (EviAtlas-style) 10. A1 offers PRISMA-style flow numbers 11 in the release card only.
•	A policy-anchored gap view (V-9) with four drivers (OPC-2022, MON-2026, DTSC-SCP, LEG), a policy panel and a Related Resources tab.
Tabs: Experts & Institutions · Monitoring Data · Funding · Evidence Map (V-1..V-5, V-9, policy panel) · Related Resources · About/Methods.

Level	Contents	Rollback
E0 Vocabularies	EM-1..EM-4	Base domain_tags
E1 Evidence Map core	EM-5..EM-8	Base S11.2
E2 Geography, reviews, cross-links	EM-9, EM-10, EM-15, EM-16	Omit
E3 Ledger and policy	EM-11..EM-14, EM-17, EM-18	Omit


2. Conflict register

ID	Issue	Resolution
C1	discipline overlaps study_type = method_development	discipline = topic (multi-label); study_type = design (single). Report collinearity.
C2	Base matrix ≠ framework compartments	Add compartment[], waterbody_type[]; map matrix in taxonomy.yml.
C3	Base size_class is on samples only	Add works-level size_class[] (§4).
C4	Base S7.5 gaps heatmap overlaps V-9, V-2	Keep S7.5; share one heatmap component.
C5	Base S11.2	Replaced by EM-8.
C6	A1 C12: iframes cannot share facet state	Client-side bit-set facets (AT-4).
C7	Gold-set load (κ ≥ 0.7)	Extend existing gold works (EM-3); weak fields ship "experimental".
C8	Source text reuse	Paraphrase, short quotes, links. The Monitoring Strategy states image permission only (one-time use in this publication only 4); no text licence was found.
C9	Monitoring Strategy excludes drinking water	Block X extension rows.
C10	Regional layer has no licence text in its metadata	Owner-determined open use plus disclaimer (§4).
C11	ToMEx loads in R (A1 allows R only if gated)	EM-15 is a one-off owner-run export; R is not added to CI.
C12	source_category explodes with DTSC products	Coarse source_category plus rule-based product_type[] (§4).
C13	Several microplastic and nanoplastic definitions in play	Definitions crosswalk in METHODS (§4).
C14	DTSC sub-rows vs works tagged only at parent level	group_id column and parent product_type values (§6.3).
C15	Many keyword flags with unknown precision	Each flag gets a spot-check in EM-4; rows relying on weak flags stay low rule confidence.


3. study_type vocabulary (EM-1)
A single primary label for research design. It is a synthesis, not an adopted standard, drawing on design distinctions in a scoping review (primary literature (n=638) as the dominant study type, followed by review papers (n=185) 12), a groundwater review that excluded laboratory and column experiments, review papers, soil-only studies, and modeling-only analyses 13, a USGS vision of environmental sources, pathways, and fate; human and wildlife exposure routes; ecotoxicology; sampling protocols; analytical methods 14, a bibliometric review (most of the studies were carried out under laboratory simulation conditions 15), ToMEx's in vitro versus in vivo 1 coding, and a critical review of methods of sampling, isolating, purifying and identifying microplastics 16.

Value	Definition	Disambiguation
field_occurrence	Field sampling measuring levels or characteristics (environmental, biological, food, drinking water, dust, indoor air); monitoring, surveys, citizen science	New method validated on field samples → method_development
source_emission	Release from a product, material or activity	Post-release transport → pathway_load
pathway_load	Concentration, flux or loading through stormwater, wastewater, agricultural runoff, air	Evaluating a control → mitigation_eval
fate_transport	Degradation, weathering, sorption, settling, advection, burial	Lab and field both
exposure_lab_toxicity	Controlled lab exposure of organisms, tissues or cells (optional test_system ∈ in_vivo, in_vitro, other)	Cross-checked against ToMEx aquatic DOIs (EM-15)
mesocosm_semifield	Microcosm, mesocosm, enclosure	
human_exposure_health	Human subjects or samples: biomonitoring, tissue detection, epidemiology	Intake estimates from literature values → modelling_risk
method_development	Sampling, extraction, identification, quantification, QA/QC, interlaboratory studies	
modelling_risk	Transport, exposure or load models; risk assessment; threshold derivation	Meta-analysis → review_synthesis
mitigation_eval	Empirical evaluation of controls: treatment, BMPs, LID, filters, alternatives, policy effectiveness	
policy_social	Policy analysis, economics, behaviour, equity, tribal engagement, education	
review_synthesis	Narrative, systematic or scoping review; meta-analysis; evidence map; bibliometric	OpenAlex type = 'review' is a prior only (§4)
data_resource	Dataset, database, software or tool	
perspective_guidance	Commentary, editorial, guidance, strategy or report with no primary data	
unclear_other	Not assignable	Always needs_review

Rules: one primary label (optional hidden study_type_secondary[], A2-D1). Abstract-level first. [INF] ≥ 40 gold examples per value (about 600 works) before training. Values below κ 0.7 or per-tag F1 0.70 are "experimental". EM-1 first step: check the repo for an existing study_type vocabulary; if one exists, diff it, map old → new, and do not overwrite human labels.

4. Facets, definitions, regional layer and verified tooling (EM-1, EM-2)

Facet	Values (draft)	Basis
compartment[]	surface_water, sediment, biota, air, indoor_air, indoor_dust, soil, wastewater_stream, stormwater_stream, drinking_water, food, human_tissue	Monitoring scope: surface waters (rivers, streams, estuaries, lakes, reservoirs, and nearshore marine waters), associated sediments, surface water discharges (stormwater, wastewater) and aquatic biota 3. indoor_air and indoor_dust are atlas additions: DTSC's 2023 proposal states MPs have been reported in drinking water, household dust, and indoor air 4 (analyst-transcribed), and its paint row notes MPs shed from dried paint can contaminate indoor air and household dust. 4

waterbody_type[]	coastal_subembayment, estuary, nearshore, offshore, river_stream, lake_reservoir, groundwater	marine environments (e.g., coastal subembayments, estuaries, nearshore, and offshore waters) and freshwater systems (e.g., lakes, creeks, and rivers) 3

pathway[]	urban_runoff_stormwater, wastewater, agricultural_runoff, atmospheric_deposition, direct_discharge_litter, indoor_release	Glossary: Pathway: The environmental compartment through which microplastics and macroplastics are transported from sources. 4

source_category[] (coarse)	vehicle_tires, textiles, single_use_foodware_packaging, agriculture, fisheries_aquaculture, preproduction_pellets, consumer_product_other	OPC: (1) vehicle tires, (2) textiles, (3) single-use foodware and packaging, (4) agriculture, and (5) fisheries & aquaculture 17; nurdles also named.
product_type[] (fine, keyword-rule based)	DTSC Table 1: artificial_turf_infill; paints_coatings; laundry_dish_detergents (parent) with detergent_insoluble_polymers, detergent_fragrance_microcapsules, detergent_water_soluble_polymers; plastic_film_mulch; cigarette_filters; food_contact_articles (parent) with food_contact_baby_bottles, food_contact_beverage_bottles, food_contact_films, food_contact_wrappers, food_contact_ps_foam, food_contact_tea_bags; childrens_toys. DTSC Table A1: agricultural_other, aquaculture_gear, artificial_turf_blades, personal_care_leave_on, personal_care_wipes, building_materials, cleaning_other, furniture_foams, glitter, motor_vehicle_foams, ppe_masks, floral_foam, geotextiles, balloons_toys. DTSC footnote 1: plastic_bags, silicone_cookware.	Works naming only a parent (e.g. "detergents") get the parent value. Keyword rules with spot-check validation, not a trained classifier.
size_class[]	macro (>5 mm), micro (<5 mm), nano (<1 µm), unspecified	Macroplastics Any plastic debris greater than 5 mm in size. 3Nanoplastics: Plastic particles smaller than 1 μm. Included within this report's definition of microplastics. 4 Every "micro" rule includes nano.
size_subclass[] (optional, [INF])	nano_1_100nm, submicron_100nm_1um, small_micro_1_100um, large_micro_100um_5mm	DTSC 2023 proposal nomenclature (analyst-transcribed): 'nanoplastics' (1 nm to <100 nm); 'sub-micron plastics' (100 nm to <1 μm); 'small microplastics' (1 μm to < 100 μm); 'large microplastics' (100 μm to <5 mm) 4. Assign only when a work reports its size range.
rwqcb_region[]	1 North Coast, 2 San Francisco Bay, 3 Central Coast, 4 Los Angeles, 5 Central Valley, 6 Lahontan, 7 Colorado River, 8 Santa Ana, 9 San Diego, plus offshore_state_waters, offshore_or_unassigned, statewide_unspecified	Codes and names from the feature service (below).
policy_driver[] (ledger rows)	OPC-2022, MON-2026, DTSC-SCP, LEG	Filter by who is asking.

Derived keyword flags (booleans produced by rules in EM-4; used in cell_rule): kw_particle_characterization, kw_food_seafood, kw_equity_ej_tribal, kw_seasonal, kw_temporal, kw_small_particles, kw_fibers, kw_tire_wear, kw_cost_accreditation, kw_persistence_degradation, kw_mobility_transport, kw_water_column, kw_realistic_particles, kw_hydrodynamic_transport, kw_landfill_recycling, kw_ballast_water, kw_source_identification, kw_data_standards, kw_pmc_trash_composition, kw_trash_monitoring_methods.
Definitions crosswalk (METHODS; shown wherever size classes appear)

Source	Definition
Monitoring Strategy (adopts State Water Board Resolution 2020-0021)	particles which have at least three dimensions that are greater than 1 nm and less than 5 mm 3; unmodified natural polymers excluded. "Nanoplastics" = <1 µm, within microplastics.
DTSC 2023 proposal (superseded)	solid polymeric materials to which chemical additives or other substances may have been added, which are particles having at least three dimensions that are less than 5,000 micrometers (μm). Polymers derived in nature that have not been chemically modified (other than by hydrolysis) are excluded. 6 It states it is consistent with the State Water Resources Control Board's Definition of Microplastics in Drinking Water (SWRCB Resolution No. 2020-0021) 6. Its "nanoplastics" = 1 nm to <100 nm. This wording is also printed in the 2024–2026 Work Plan.
DTSC final listing (June 2026)	plastics that are less than 5 millimeters (mm) in their longest dimension... This definition does not have a lower size limit nor distinguish polymer types. 8

DTSC Background Document (Nov 2025)	Microplastics are generally plastics that are less than 5 millimeters (mm) in their longest dimension , and can be classified as: primary microplastics that are manufactured and intentionally added to products ... or secondary microplastics that arise from the degradation of plastic products 7


Nomenclature conflict: the Monitoring Strategy's "nanoplastics" (<1 µm) is not DTSC 2023's "nanoplastics" (1 nm to <100 nm). The atlas size_class = nano follows the Monitoring Strategy; size_subclass preserves DTSC's finer bins.
Regional boundary layer (verified 2026-11-09)
•	Source: the California Water Boards hosted feature service "Regional Board Boundary Features", layer 1 (named in its JSON "Regional_Board_Boundaries" 18): https://gispublic.waterboards.ca.gov/portalserver/rest/services/Hosted/Regional_Board_Boundary_Features/FeatureServer/1. California State Geoportal listing: https://gis.data.ca.gov/datasets/waterboards::regional-board-boundaries. The geoportal shows Records: 9 19, published 10 December 2019, info and data updated 9 March 2026. This replaces the 2018 shapefile item used in earlier spec versions.
•	Schema: geometry esriGeometryPolygon 18; fields objectid, rb (values 1–9), rb_name, SHAPE__Length, SHAPE__Area, globalid 18; spatial reference wkid 102100 (latestWkid 3857) 18; supported exports include geojson. Nine features, all returned in one query. Codes and names (rb, rb_name): Lahontan 6, Central Valley 5, Santa Ana 8, San Francisco Bay 2, Los Angeles 4, North Coast 1, Colorado River 7, San Diego 9, Central Coast 3 18. Note "Colorado River" (feature service) versus "Colorado River Basin" (prose descriptions and the Monitoring Strategy's gap sentence).
•	Query checks: a Sacramento point returned Central Valley (rb 5) 18; a San Francisco Bay point returned San Francisco Bay (rb 2) 18. Two offshore points returned nothing (an empty features array 18 at about 60 km out; no Regional Board boundary feature 18 at about 15–20 km out). Only two offshore points were tested, so offshore coverage is inferred from those tests, not proven.
•	Offshore rule: no polygon hit → offshore_or_unassigned. If a state-waters polygon is available and the point falls inside it → offshore_state_waters. The state-waters polygon source is [VERIFY] and is selected in EM-2; V-2 and V-9a show these two values as separate columns with an explanatory note.
•	Licence: the geoportal shows a "Custom License" 19 whose text I could not retrieve, and the service JSON has no licence field. The owner has determined California State GIS files are open [OWNER]; log in REUSE.md. Polygons may be committed, simplified if needed.
•	Mandatory disclaimer (V-2, V-9a, About; link both URLs above): "Regional Water Board boundaries come from the California Water Boards' 'Regional Board Boundary Features' feature service and are only as accurate as that source. The Water Boards describe the boundaries as generally based on watersheds, with official legal definitions in Water Code Section 13200. Region assignments for studies are derived from sampled coordinates and may be wrong near boundaries; points offshore are not assigned to a Regional Board by this layer. Geometry shown may be simplified for web display." (Delete the last clause if not simplified.) Source for the "official legal definitions" statement: The official legal definitions are in Section 13200 of the California Water Code. 19
•	EM-2 acceptance: fetch the layer as GeoJSON; assert exactly 9 features with codes 1–9; run the four point checks above as unit tests; apply the offshore rule; record the state-waters source.
Verified tooling facts
•	DuckDB documents all functions used by cell_rule: list_has_any(list1, list2), list_contains(list, element), and len(list) (alias for length) 20. Rules are evaluated at build time (Python DuckDB), not in the browser; the DuckDB version pinned in the build environment is [VERIFY] in EM-11 by running the unit tests.
•	OpenAlex: each work has exactly one type (Every work has exactly one type, exposed as its type field 21), including review (A journal article that summarizes and evaluates the existing research on a topic without reporting new findings, such as a literature review, systematic review, or meta-analysis 22). The retraction field is is_retracted: True if this work has been retracted (from Retraction Watch database) 23. Use type = 'review' as a prior for review_synthesis, never as the label.
•	ToMEx package: PSSDplusplus version 0.4.1, MIT + file LICENSE 24, loaded with data("tomex2", package = "PSSDplusplus") (The bundled ToMEx 2.0 ecotoxicity dataset is available as PSSDplusplus::tomex2 24). The dataset documentation says it is built from SCCWRP/ToMEx_AquaticOrganisms, release v2.0.1 of 2026-06-30 24 and is identical to the source RDS 24, so it is the aquatic-organisms database only.

5. Evidence Map tab (V-1..V-5)
One tab, shared URL-hash filter state, A1 bit-set facets (AT-4). Distinct works only. Every cell opens a drawer. A contextual related-resources strip follows the filters.

ID	View	Spec
V-3	Pipeline flow diagram	Built each run from AT-10 counts, following ROSES templates for searching, screening, coding/meta-data extraction, data extraction, critical appraisal and synthesis 25, provided under Creative Commons Attribution 4.0 International (CC BY 4.0) 26. ROSES commenced the update process as of July 2026 27; use the current published template. Stages not performed are shown as "not performed".
V-4	Trend panel	Works per year by tag, plus CA share of global output under the same query version (A1 SPK-7 cost). Last 12 months drawn lighter.
V-1	Evidence matrix	compartment × discipline, compartment × study_type, waterbody_type × study_type. the matrix design (33.5%) and bubble plot design (28%) are the two largest groups, and 67% of interactive maps used a matrix design 28. EviAtlas offers Heat Maps that cross-tabulate two or more variables 29. Cells are not additive; colour by count bin only.
V-2	Sampled-location atlas	Points and polygons from geo_mentions with role_pred = sampled, plus a region × compartment grid and the regional disclaimer.
V-5	Review overlay	Mark cells with many primary studies and no recent review, following where there is a concentration of impact evaluations but no recent high-quality systematic review 30. N and "many" are owner parameters (A2-D4).

Not built: study-quality grading. Where other maps use traffic lights it applies to the confidence level of systematic reviews 31, and the base spec has No per-person quality rankings 10.

6. V-9 Need Ledger
6.1 Concept and drivers
Rows are California management, monitoring and product-sector questions. In evidence-gap-map practice the matrix into which the evidence is plotted is generated a priori 2. Four drivers feed the ledger:
•	OPC-2022: the 2022 Strategy (Solutions (Chapter 2A) 17 and Science to Inform Future Action).
•	MON-2026: the Monitoring Strategy, whose purpose includes to assess and understand the current baseline of plastic contamination in state surface waters and identify temporal trends 3. It also contains a table titled Summary of Critical Science Gaps Important for Informing Management Questions and Monitoring Strategy 3 (Table G.1), which several rows draw on.
•	DTSC-SCP: DTSC product-sector information requests, listing-criteria context, and screening notes.
•	LEG: legislative drivers (SB 1422, SB-1147) used for extension rows.
DTSC states its product evaluations align with the Statewide Microplastics Strategy 7. The ledger is a transparency and prioritisation aid, not an assessment of any agency.
6.2 Verified count discrepancy (do not "fix")
The 2022 Strategy's Executive Summary states the 22 recommended early actions and 13 research priorities outlined in the two tracks of this Strategy 17 (PDF 5). It has exactly 22 distinct early-action codes (PDF 22–24; two Objective 2 entries are cross-references). Chapter 2B has 14 distinct research-priority codes (Total unique codes 14 4; first listing PDF 30, repeated in the timeline table PDF 33–34). Record "13" as a documented discrepancy, hard-code neither total in UI text, and do not speculate about the reason. Cite by PDF page index with printed label in parentheses.
6.3 Data file contract: docs\opc_needs_csv_Need_Ledger_Data_File_companion_to_Add_on_Spec_A2.xlsx (companion document)
One row per need. UTF-8 CSV with a header row; list fields use | as separator. Columns (20): need_id, block, policy_driver, title, paraphrase, source_doc, source_item, pdf_page, printed_label, quote, quote_verification, statement_type, cell_rule, evidence_cols, rule_confidence, dtsc_tier, aliases, link_out_ids, notes, group_id.

Column	Content
need_id	Stable ID (roster below); never reused
block	1, 2, 3, 4, M, X, D, DI, DC
policy_driver	OPC-2022, MON-2026, DTSC-SCP, LEG (list)
source_doc	OPC2022, MON2026, DTSC_WP, DTSC_BG2025, DTSC_2023, DTSC_LIST, DTSC_RES
pdf_page, printed_label	PDF page index and printed label. Monitoring Strategy: printed = PDF − 15 in the main body; Appendix F: PDF = F-n + 130; Appendix G: PDF = G-n + 147. Work Plan: printed = PDF − 2. DTSC Background Document: printed "Page N of 24" = PDF N+1. A ; separates multiple locations.
quote	Short verbatim quote (≤ 30 words) of the gap, question or request
quote_verification	direct_page_text or analyst_transcribed (a tool-transcribed quote with exact wording and page confirmed by a targeted query)
statement_type	management_question, stated_gap, recommended_activity, dtsc_information_request, dtsc_screening_statement, listing_criterion, extension_not_in_source
cell_rule	DuckDB SQL boolean expression over the works table (functions verified in §4)
evidence_cols	For Blocks D and DI: the three DTSC evidence-type rules, combined (AND) with cell_rule
rule_confidence	medium or low until EM-13 sets high
dtsc_tier	narrowed, initial_list, footnote_evaluated, or empty
group_id	D3 (detergents) or D6 (food contact); empty otherwise. The group header counts any work tagged with the parent or any subtype product_type.

Roster (70 rows; the data file must match exactly)

Block	IDs	Count	Driver
1 Levels and impacts	N1.1–N1.11	11	MON-2026 (N1.8 also OPC-2022)
2 Sources, pathways, loads	N2.1–N2.10	10	MON-2026 (N2.1, N2.4 also OPC-2022)
3 Trends and mitigation	N3.1–N3.3	3	MON-2026 (N3.3 also OPC-2022)
4 Enabling science	N4.1–N4.6	6	MON-2026
M Macroplastics	M1–M5	5	MON-2026
X Extension	X1–X2	2	LEG
D DTSC Table 1 rows	D1, D2, D3a–D3c, D4, D5, D6a–D6f, D7	14	DTSC-SCP
DI DTSC Table A1 and footnote	DI1–DI14 (Table A1), DI15–DI16 (footnote 1)	16	DTSC-SCP
DC Listing-criteria context	DC1–DC3	3	DTSC-SCP
Total		70	

Rows added in this version (10):
•	N1.9 small particles and fibers in field data. N1.10 toxicity data for environmentally realistic particles. N1.11 water-column (depth-resolved) concentrations.
•	N2.8 transport under different hydrodynamic conditions. N2.9 landfills and recycling centers as sources. N2.10 ship ballast water as a pathway.
•	N4.5 source-identification methods. N4.6 unified data standards and minimum data elements (Monitoring Strategy Section 6).
•	M4 the Plastic Material Coefficient (PMC) pilot. M5 harmonizing macroplastic and trash monitoring methods.
Block D (14 rows = every row of Table 1). Turf infill (D1); water-based interior wall paints (D2); detergents: insoluble polymers (D3a), fragrance microcapsules (D3b), water-soluble PVA polymers (D3c); film mulch (D4); cigarette filters (D5); food contact: baby bottles (D6a), beverage bottles and caps (D6b), cling wraps and films (D6c), snack and candy wrappers (D6d), polystyrene foam foodware (D6e), tea bags (D6f); children's toys with primary microplastics (D7). Table 1's columns are Product description, Type of MPs, Potential for exposure, Potential alternatives, Relevant regulations (List of products evaluated during DTSC's preliminary screening research that contain microplastics (MPs) or have the potential to release MPs. 7). Each row's quote is DTSC's request from its "Topics for Feedback" list; Table 1 exposure and regulation text goes in notes.
Block DI (16 rows). Table A1 has 14 category rows (Agricultural products ... Toys 4), displayed collapsed because DTSC says they may be considered for further research in the future 4. DI15 and DI16 come from footnote 1: a new regulation banned plastic grocery bag sales in California by 2026 27 4 and current research showed no evidence of microplastics shedding from silicone during cooking or baking 28 4; both are DTSC statements (dtsc_screening_statement), not atlas conclusions.
Block DC (3 rows). Listing-criteria context from the 2023 proposal: DC1 persistence/degradation (One study found that different types of MP materials persist in the environment up to 11 years 6); DC2 mobility; DC3 indoor and drinking-water occurrence.
Evidence-type columns for Blocks D and DI. The three DTSC-requested types (research page: exposure data ("How and when products shed microplastics" 9), adverse-impact data, mitigation strategies):
•	release_exposure = source_emission ∨ field_occurrence ∨ human_exposure_health for the product.
•	adverse_impact = exposure_lab_toxicity ∨ mesocosm_semifield ∨ human_exposure_health.
•	mitigation = mitigation_eval.
Cautions for Block D
•	DTSC's artificial-turf evaluation in the Work Plan concerns PFAS (The expanded category includes artificial turf, which we have since begun to evaluate 32), a separate workstream from turf-infill microplastics. Chemicals-in-plastics questions (chemical migration, leaching) remain base-spec Tier 2, outside the V-9 core.
•	Table 1 and the feedback lists are DTSC's information requests and screening statements, not research-gap statements. Label cells "DTSC information request".
•	Many Table 1 "Relevant regulations" cells name non-California regulations (EU, New York, France). Show them as DTSC-stated context with a caveat, never as a California status.
Block X note. The Monitoring Strategy states Drinking water sources, including distribution infrastructure, end use taps, and bottled water are not a focus of this Strategy 3, and the Introduction notes the legislature required the Office of Environmental Health Hazard Assessment (OEHHA) to develop guidelines for safe levels in drinking water and bottled water (SB-1147, 2024) 3. X2 draws on the OEHHA description at PDF 105 (OEHHA is particularly interested in environmental monitoring data to evaluate human health exposure, such as sportfish, air, drinking water, biomonitoring, shellfish. 3), under Appendix C: List of Potential Monitoring Program Partners 3. X1 and X2 are labelled "Added by the atlas; not from the source frameworks", with no link-out target.
6.4 Views
•	V-9a: need × rwqcb_region (with disclaimer; offshore values as separate columns). V-9b: need × study_type. V-9c: need × 5-year bins.
•	V-9d (layers): datasets in tiers A–B and matching awards. Tiers: A = harmonized and ingested into the atlas; B = downloadable but not harmonized; C = request-only; D = in a paper or supplement only 10. Awards layer after S8.
•	V-9e (ToMEx coverage): for N1.6, N1.10 and exposure_lab_toxicity cells, the count and share of works whose DOI is in the aquatic-organisms ToMEx 2.0 list, plus an unmatched list for ToMEx curators to screen. The UI states "aquatic-organisms database only; human-health ToMEx and ToMEx 3.0 not yet included". A non-match is not a claim of eligibility.
•	V-9f (Block D grid): product × the three DTSC evidence types, with a policy_driver filter and group headers for D3 and D6.
•	Cell content: distinct works (all years and 5-year), split by ca_basis, needs_review share, a marker where a source states a gap or information request, and the related-resources strip.
•	Concordance report (docs/needs_concordance.md): a stated gap with a low atlas count is consistent; a stated gap with a high count must be investigated; no stated gap with a zero count is flagged as a possible pipeline miss.
•	UI caveats: a cell rule is an operational proxy; each row shows its rule confidence [INF]; the ledger records the document versions used.

7. Policy panel (EM-17) and regulatory timeline (EM-18)
The panel is reference information with outbound links. It makes no statement about implementation, enforcement or effectiveness.
Part A — OPC Solutions track. For each of the 22 early actions it shows the code, a paraphrase, the Strategy's deadline, a link to the matching Global Plastic Laws topic and a "California search" link, plus a link to the matching atlas cell. The target's disclaimer is shown: The Global Plastic Laws Database is an educational and research resource and should not be regarded as fully comprehensive or completely up to date for legal purposes. 33 The nine topics are Design + Reuse; Extended Producer Responsibility; Maritime Sources; Microplastics; Production + Manufacturing; Reduction; Transparency + Traceability; Waste Management; Waste Trade 33.
Slug status. Topic pages whose titles resolved: design-reuse (Design and Reuse | Global Plastic Laws 34), microplastics (Microplastics | Global Plastic Laws 35), reduction (Reduction | Global Plastic Laws 36), maritime-sources (Maritime Sources | Global Plastic Laws 37), waste-management (Waste Management | Global Plastic Laws 38); product-manufacturing and transparency-traceability were observed on the homepage. extended-producer-responsibility returned a title but no confirming content (Extended Producer Responsibility | Global Plastic Laws 39), and waste-trade was not tested. The site renders its content client-side, so the link checker validates only HTTP status. The owner reports California-specific laws appear on the California search page (https://www.globalplasticlaws.org/search?search=california) [OWNER]; I could not retrieve it.
Draft mapping [INF], owner review in EM-17 (action wording from TOTAL DISTINCT NUMBERED CODES 22 4):

Codes	Theme	Candidate topic	Atlas cell
2A.1.1, 2A.1.3, 2A.1.4, 2A.1.6	Foodware on request; reduction goals; EPS prohibition; tobacco products	Reduction	single_use_foodware_packaging, cigarette_filters ∧ policy_social/mitigation_eval; D5, D6e
2A.1.2, 2A.1.9	State purchasing of reusables; industry alternatives	Design + Reuse	source_category (all)
2A.1.5, 2A.1.8	Microbead ban expansion; washing machine and dryer filtration	Microplastics	textiles ∧ mitigation_eval; consumer_product_other
2A.1.7	Extended producer responsibility	Extended Producer Responsibility	policy_social
2A.2.4	Pellet ("nurdle") discharge enforcement	Production + Manufacturing; Maritime Sources	preproduction_pellets; DI10
2A.2.5, 2A.2.6	Trash receptacles; Trash Provisions	Waste Management	Block M
2A.2.1–2A.2.3, 2A.2.7, 2A.2.8	LID and wastewater actions	No obvious topic	urban_runoff_stormwater, wastewater ∧ mitigation_eval
2A.3.1–2A.3.5	Outreach and education	No obvious topic	N1.8 ∧ policy_social

Part B — DTSC regulatory timeline (EM-18). Curated config/dtsc_timeline.yml (no scraping), shown as a timeline with source links, dates exactly as DTSC states them. DTSC's research-page timeline table is listed newest-first, so it is in consistent (reverse-chronological) order:
•	27 June 2023: workshop on the initial proposal (Public comment on a proposal; workshop held June 27, 2023 8).
•	20 June 2025: proposed regulation released (June 20, 2025 Release of Proposed Regulation for Public Comment 8).
•	November 2025: Background Document; December 2025 workshop; January 2026 comments (timeline rows 9). The Background Document says DTSC will hold a virtual public workshop on this background document 7, with engagement that will help inform additional research that may result in the proposal of one or more Priority Products 7.
•	18 June 2026: DTSC finalized a rulemaking that adds microplastics to the Candidate Chemicals 8 list (2 July 2026 DTSC release: DATE: July 2, 2026 40).
•	1 October 2026: Effective Date of Final Regulation 8.
•	Background: the Work Plan notes a draft-plan workshop on June 18, 2024 32 and a comment period from May 16, 2024 through July 15, 2024 32.
Always show: "Listing does not by itself create requirements; Priority Product designation is a separate rulemaking." DTSC states it may only designate a Priority Product if it falls within one of the categories described in the current Work Plan, with three exceptions 4.

8. Related Resources tab and link-out registry (EM-16)
Principles: link, don't mirror; deepest verified link only; static and contextual; no claims beyond what the steward says; terms recorded per entry; weekly HTTP status check only. Registry file config/linkouts.yml: id, name, steward, description_source, relation, update_model (as stated or "not stated"), terms_status, reuse_mode = link_only, root_url, deep_link_templates (with evidence_url), trigger_rules, last_checked.

ID	Resource	Steward and description (as stated)	Link pattern
LO-1	Global Plastic Laws	managed by Plastic Pollution Coalition, with key partners Break Free From Plastic Europe, Environmental Law Alliance Worldwide, and Surfrider Foundation U.S. 41; plastic legislation that has been passed around the world 33. "Global Plastic Laws. All rights reserved." 33
/search?search=, /map, /topic/{slug}, /law?lawId={id} 33

LO-2	ToMEx (Aquatic Organisms; Human Health)	SCCWRP; microplastics.sccwrp.org 42; a living resource, new studies can be added at any time 43
Root
LO-3	NOAA NCEI Marine Microplastics	a global database of microplastics observations in marine settings 44; Data Update Frequency Quarterly 45
Root
LO-4	Atlas of Ocean Microplastics (AOMI)	a global database of surface microplastics 46, Japan Ministry of the Environment	Root
LO-5	Global Plastics Hub (data hub)	GPML; datasets available on plastics across the lifecycle 47
Root
LO-6	Global Plastics Data Tracker	UNSW CSDR via Global Ocean Accounts Partnership; an interactive registry that maps plastics data across more than 193 countries 48
Root
LO-7	Global Plastics Policy Tool	Berkeley data-science center project; predicts the impact of potential interventions 49
Root
LO-8	Plastiverse tools directory	a curated and evolving directory of plastics research tools & resources 50
Root
LO-9	Moore Institute: One4All and Microplastics Open Data Portal	One4All is an open-source portal and toolkit designed to make microplastics data Findable, Accessible, Interoperable, and Reusable (FAIR) 51; the Monitoring Strategy notes the Microplastics Open Data Portal uses the California Open Data Portal as its actual authoritative destination for uploaded data 5
Root (URL confirmed at EM-16)
LO-10	DTSC: Microplastics in Consumer Products	DTSC SCP research page; invites exposure data, adverse impact data and mitigation strategies	Page URL
LO-11	DTSC: Addition to the Candidate Chemicals List: Microplastics	DTSC SCP listing page	Page URL
LO-12	DTSC: Priority Product Work Plan	DTSC SCP three-year plan page	Page URL

The Minderoo Plastic Health Map is intentionally not in the registry.

9. Tasks
Sizes S ≤ 1 session, M ≈ 2, L ≈ 3. [E] = higher-tier model.

ID	Task	Depends on	DoD	Size
EM-1	Vocabularies in taxonomy.yml (full product_type list and all 20 keyword flags in §4); LABELING_GUIDE; ingest docs\opc_needs_csv_Need_Ledger_Data_File_companion_to_Add_on_Spec_A2.xlsx and validate it against the §6.3 schema and the 70-row roster; keyword rules [E]; local-only regression test checking every quote against the owner's local PDFs (PDFs not committed)	S4.1	Existing study_type diffed if present; roster test passes; 13/14 discrepancy recorded	M
EM-2	Fetch the regional feature service as GeoJSON; run the §4 acceptance checks; implement the offshore rule; record the state-waters polygon source; derive rwqcb_region	S5 geo	Nine features, four point checks pass; disclaimer wired into V-2, V-9a, About; REUSE.md entry [OWNER]	S
EM-3	Extend gold set with the new labels; double-label 20%	EM-1	κ per field; weak fields "experimental"	L
EM-4	Rules and SetFit per field; keyword flags with spot-check precision; collinearity report	EM-3, S5	Per-field F1 in METHODS	M
EM-5	Evidence Map shell, shared drawer, related-resources strip	A1 AT-4	Payload budget met	M
EM-6	V-3 flow diagram	AT-10	Numbers match methods card	S
EM-7	V-4 trend panel	AT-3, SPK-7	Query-version-keyed cache	S
EM-8	V-1 matrix	EM-4, EM-5	Cells match DuckDB on fixture	M
EM-9	V-2 sampled-location atlas	EM-2	Only sampled points	M
EM-10	V-5 review overlay	EM-8	Parameters in config	S
EM-11	V-9 aggregator and UI (V-9a–c, V-9f incl. group headers); evaluate cell_rule expressions; concordance report [E]	EM-1, EM-4, EM-5	Per-row rule tests; DuckDB function check passes on the pinned version	L
EM-12	V-9d layers (datasets, awards)	S7, S8, EM-11	Counts match registry	M
EM-13	Validation: ≥ 20 need cells reviewed by owner or expert; precision spot-check; set rule_confidence	EM-11	Confidence set	M
EM-14	METHODS, definitions crosswalk, disclaimers, disclosures	all	Owner review	S
EM-15	ToMEx DOI crosswalk: owner-run R script: library(PSSDplusplus); data("tomex2", package = "PSSDplusplus"); read DOI [OWNER]; normalize DOIs; commit only a DOI list plus package-version and source-release stamps (v2.0.1, 2026-06-30); V-9e. Install per the repo README (remotes::install_github("ScottCoffin/ToMEx2.0_EcoToxRisk", subdir = "package", build_vignettes = FALSE) 52). Later: ToMEx 3.0 output when available	EM-1	Script prints nrow and names(); match rate reported; UI states aquatic-only	S
EM-16	Related Resources tab, registry, weekly link checker	EM-5	Registry validates; broken-link test passes	M
EM-17	Policy panel Part A	EM-16	Mapping owner-reviewed; disclaimers shown	S
EM-18	DTSC timeline panel (Part B), curated YAML, link-checked	EM-16	Dates as DTSC states them; non-regulation caveat shown	S

Acceptance tests: EAT-1 fixture cell counts correct and non-additive; EAT-2 every roster row has source, PDF page and rule, and unit tests pass; EAT-3 concordance lists all stated-gap needs; EAT-4 flow numbers match AT-10; EAT-5 no counts outside DuckDB; EAT-6 human labels override model labels; EAT-7 link checker flags a broken link; EAT-8 no Minderoo content or link anywhere (grep test); EAT-9 no repo content ingested from link-only resources; EAT-10 docs\opc_needs_csv_Need_Ledger_Data_File_companion_to_Add_on_Spec_A2.xlsx has exactly 70 rows with unique IDs matching the roster, 20 columns, and every product_type value and kw_ flag used in a cell_rule exists in taxonomy.yml; EAT-11 group headers D3 and D6 count a work once even if it carries several subtype tags; EAT-12 the regional feature service returns nine features and the four point checks behave as recorded in §4.

10. Open decisions (defaults)

ID	Decision	Default
A2-D1	Secondary study_type labels	Single primary; secondary hidden
A2-D2	Include Block M (macroplastics)	Yes, collapsed
A2-D3	Include Block X rows	Yes, labelled
A2-D4	V-5 parameters	N = 5 years; threshold from build-time distribution
A2-D5	V-9a region unit	Nine Regional Boards plus the two offshore values
A2-D6	Who validates need→rule mappings	Owner first, then an OPC, SCCWRP, SFEI or DTSC colleague
A2-D7	Funding layer at launch	No; after S8
A2-D8	Disclosure text	Include in About
A2-D9	Use size_subclass (DTSC 2023 bins)	Optional; empty unless a work reports its size range
A2-D10	Show non-California regulations from DTSC Table 1	Show as DTSC-stated context only, with caveat
A2-D11	State-waters polygon source for the offshore rule	Pick in EM-2; owner confirms


11. Known unknowns
•	Text of the regional layer's "Custom License"; offshore coverage beyond the two tested points; the state-waters polygon source.
•	Global Plastic Laws: Terms & Conditions; the waste-trade and extended-producer-responsibility slugs; the exact California result count (owner reports California laws appear).
•	The DOI column and row count of tomex2 (documentation does not list columns; owner confirms the column exists [OWNER]).
•	DuckDB version pinned in the build environment (function names are documented in the current docs).
•	Monitoring Strategy Appendices D and E and parts of Section 4 beyond the pages cited; the DTSC Background Document's reference list; the DTSC workshop page.
•	ROSES update outcome; text-reuse terms for OPC, SFEI and DTSC documents.
•	Achievable per-field κ for study_type, compartment, waterbody_type; precision of the many keyword rules.

12. Source verification ledger
Method: page-targeted reads. Direct page text is cited where returned; other quotes were transcribed by the document-analysis tool with exact wording and page confirmed by a targeted query. The tool's own PDF page numbers drift by one or two pages in some replies; direct page snippets are authoritative, and printed label plus 15 (Monitoring Strategy main body) is the cross-check. PDFs were not in the sandbox, so no byte-level diff was possible; EM-1's local test provides that. Where the tool's row counts disagreed with its verbatim transcription, the transcription count was used.

Source	Checked	Status
2022 Strategy	Title and date; "22 and 13" (PDF 5); "final" (PDF 8); 22 early-action codes (PDF 22–24); 14 research-priority codes (PDF 30, 33–34)	Confirmed; discrepancy is in the source; 2B.1.5 direct, 2B.2.3 and 2B.2.4 direct in the timeline table (PDF 34)
Monitoring Strategy (Aug 2026)	Cover and preparers; table of contents; definitions (PDF 6–9); scope (PDF 18); MQ1–3; Table 2.1 (PDF 31); Sections 3.5–3.7 (PDF 50–56); Sections 4.4, 5.2 (PDF 68–69, 76); Section 6 (PDF 83–85); Appendix C (PDF 103–106); Appendix F (PDF 131–137); Appendix G incl. Table G.1 (PDF 148–153); gap sentences (PDF 28, 30, 36–42, 133–134, 149, 152); Table 4.1 (PDF 61–62)	Confirmed; most quotes in the data file now direct page text
Monitoring Strategy	Appendices D and E; parts of Section 4	Not read
DTSC Work Plan	Identity, microplastics section (PDF 24–25), paints (PDF 22–23), tires (PDF 29), food contact (PDF 30), process	Confirmed; printed = PDF − 2; "final" status inferred from Appendix C
DTSC listing and research pages	Dates, definition, timeline, categories, information requests	Confirmed; research-page timeline is newest-first
DTSC 2023 proposal (two identical uploaded copies)	Identity, definition, persistence, mobility, exposure, product and California stormwater sentences	Confirmed; size nomenclature analyst-transcribed
DTSC Background Document (Nov 2025)	Overview; Introduction; footnote 1; Table 1 (14 rows, PDF 6–9); Topics for Feedback (PDF 10–13); Table A1 (14 rows, PDF 25)	Confirmed; several Table 1 cells and feedback quotes are direct page text, the rest analyst-transcribed with exact wording confirmed. Reference list not read.
Regional feature service	Schema, nine features, four point checks	Verified by REST queries; licence text not retrievable
ToMEx package	DESCRIPTION, README, dataset documentation	Verified; DOI column is [OWNER]
DuckDB, OpenAlex	Function names; type, review, is_retracted	Verified in current documentation
Global Plastic Laws	About, homepage patterns, disclaimer, topic-page titles	Confirmed; California search results [OWNER]


13. Change log vs base spec and A1
•	Replaces base S11.2 with EM-8. Extends base S4 and S5 with new fields.
•	Adds works-level size_class, size_subclass, compartment (including indoor_air and indoor_dust), waterbody_type, pathway, source_category, a full product_type vocabulary, rwqcb_region (nine codes plus two offshore values), a defined study_type, and 20 keyword flags.
•	Adds the Evidence Map tab (including the Need Ledger, policy panel and DTSC timeline) and the Related Resources tab.
•	Ledger row text lives in the companion data file docs\opc_needs_csv_Need_Ledger_Data_File_companion_to_Add_on_Spec_A2.xlsx (70-row roster, 20 columns, schema in §6.3).
•	Adds four policy drivers (OPC-2022, MON-2026, DTSC-SCP, LEG). Removes Minderoo from scope. Reuses A1 AT-3, AT-4 and AT-10 with no change to any A1 decision gate.
•	Closes A1 open items: OpenAlex retraction field is is_retracted; type = 'review' documented.
•	Corrections vs v7: the roster is 70 rows (v7 said 60); the regional layer is the hosted feature service with a measured offshore result and a defined offshore rule (v7 used the shapefile item, whose contents could not be parsed); ToMEx package name is PSSDplusplus and scope is aquatic-only; the spurious "DTSC timeline out of order" caution is removed; X2 is at PDF 105, C-3 (not PDF 122); the Moore portal entry (LO-9) is updated; Section 6 and Appendices F and G of the Monitoring Strategy are now read and reflected.
References
1.	Thornton Hampton LM, Lowman H, Coffin S, Darin E, De Frond H, Hermabessiere L, Miller E, de Ruijter VN, Faltynkova A, Kotar S, Monclús L, Siddiqui S, Völker J, Brander S, Koelmans AA, Rochman CM, Wagner M, Mehinto AC. A living tool for the continued exploration of microplastic toxicity. Micropl.&amp;Nanopl. 2022;2(1). doi:10.1186/s43591-022-00032-4.
2.	Campbell F, Wong R, Llewellyen JL, Stoniute A, Pearson F, Bond M. PROTOCOL: Methods used in the development, production and updating of evidence and gap maps: A scoping review. Campbell Syst Rev. 2024;20(2):e1402. doi:10.1002/cl2.1402. PMID: 38686100.
3.	OPC Statewide Plastics Monitoring Strategy and Planning Framework 508. Uploaded document.
4.	Analyst response (synthesis, not source text). Uploaded document.
5.	Statewide Plastics Monitoring Strategy and Planning Framework. Retrieved 2026-11-09, from https://opc.ca.gov/wp-content/uploads/2026/02/Plastic-Strategy-Report-Public-Review-February-2026-508.pdf
6.	Background Document Proposal to Add Microplastics to the Candidate Chemical List May272023. Uploaded document.
7.	Background Document on DTSCs Microplastics in Consumer Products Research (1). Uploaded document.
8.	Addition to the Candidate Chemicals List: Microplastics | Department of Toxic Substances Control. Retrieved 2026-11-09, from https://dtsc.ca.gov/scp/candidate-chemical-list_microplastics/
9.	Microplastics in Consumer Products | Department of Toxic Substances Control. Retrieved 2026-11-09, from https://dtsc.ca.gov/scp/microplastics-in-consumer-products
10.	spec.md. Uploaded document.
11.	add on spec.md. Uploaded document.
12.	A Scientific Perspective on Microplastics in Nature and Society. Retrieved 2026-11-09, from https://strathprints.strath.ac.uk/86044/1/SAPEA_2019_A_Scientific_Perspective_on_Micro_Plastics.pdf
13.	Sajid L, Alfio MR, Vasileiou E, Balacco G. Microplastics in groundwater: An updated systematic review of occurrence, hydrogeological controls, methodological challenges, and regulatory gaps. J Hazard Mater. 2026;516:143318. doi:10.1016/j.jhazmat.2026.143318. PMID: 42623875.
14.	Integrated science for the study of microplastics in the environment—A strategic science vision for the U.S. Geological Survey. Retrieved 2026-11-09, from https://pubs.usgs.gov/publication/cir1521/full
15.	Zhang et al 2020 Global trends and prospects in microplastics research. Uploaded document.
16.	Koelmans AA, Mohamed Nor NH, Hermsen E, Kooi M, Mintenig SM, De France J. Microplastics in freshwaters and drinking water: Critical review and assessment of data quality. Water Res. 2019;155:410-422. doi:10.1016/j.watres.2019.02.054. PMID: 30861380.
17.	Item 6 Exhibit A Statewide Microplastics Strategy (1). Uploaded document.
18.	Regional Board Boundary Features. Retrieved 2026-11-09, from https://gispublic.waterboards.ca.gov/portalserver/rest/services/Hosted/Regional_Board_Boundary_Features/FeatureServer/1?f=json
19.	Regional Board Boundaries | California State Geoportal. Retrieved 2026-11-09, from https://gis.data.ca.gov/datasets/waterboards::regional-board-boundaries
20.	List Functions. Retrieved 2026-11-09, from https://duckdb.org/docs/2.0/sql/functions/list.html
21.	OpenAlex. About. Retrieved 2026-11-09, from https://help.openalex.org/data/work-types/
22.	OpenAlex. Work Types Overview. Retrieved 2026-11-09, from https://developers.openalex.org/api-reference/work-types
23.	OpenAlex. List works. Retrieved 2026-11-09, from https://developers.openalex.org/api-reference/works/list-works
24.	Tomex2.0 Ecotoxrisk. Retrieved 2026-11-09, from https://raw.githubusercontent.com/ScottCoffin/ToMEx2.0_EcoToxRisk/main/package/DESCRIPTION
25.	ROSES flow diagram | ROSES. Retrieved 2026-11-09, from https://www.roses-reporting.com/flow-diagram
26.	ROSES for systematic map protocols | ROSES. Retrieved 2026-11-09, from https://www.roses-reporting.com/systematic-map-protocols
27.	Updates and extensions | ROSES. Retrieved 2026-11-09, from https://www.roses-reporting.com/updates-and-extensions
28.	Fredlund M, Rogers M, Orr N, Kneale D, Allen K, Thompson Coon J. What are the methodological characteristics of evidence and gap maps? A systematic review and evidence and gap map. Cochrane Evid Synth Methods. 2024;2(8):e12096. doi:10.1002/cesm.12096. PMID: 40475113.
29.	Haddaway NR, Feierman A, Grainger MJ, Gray CT, Tanriver-Ayder E, Dhaubanjar S, Westgate MJ. EviAtlas: a tool for visualising evidence synthesis databases. Environ Evid. 2019;8(1). doi:10.1186/s13750-019-0167-1.
30.	Evidence gap maps | 3ie. Retrieved 2026-11-09, from https://www.3ieimpact.org/evidence-hub/evidence-gap-maps
31.	Evidence Gap Maps as a Tool for Evidence-Informed Decision-Making. Retrieved 2026-11-09, from https://publications.iadb.org/publications/english/document/Evidence-Gap-Maps-as-a-Tool-for-Evidence-Informed-Decision-Making.pdf
32.	2024 2026 Priority Product Work Plan. Uploaded document.
33.	Global Plastic Laws | Global Plastic Laws. Retrieved 2026-11-09, from https://www.globalplasticlaws.org/
34.	Design and Reuse | Global Plastic Laws. Retrieved 2026-11-09, from https://www.globalplasticlaws.org/topic/design-reuse
35.	Microplastics | Global Plastic Laws. Retrieved 2026-11-09, from https://www.globalplasticlaws.org/topic/microplastics
36.	Reduction | Global Plastic Laws. Retrieved 2026-11-09, from https://www.globalplasticlaws.org/topic/reduction
37.	Maritime Sources | Global Plastic Laws. Retrieved 2026-11-09, from https://www.globalplasticlaws.org/topic/maritime-sources
38.	Waste Management | Global Plastic Laws. Retrieved 2026-11-09, from https://www.globalplasticlaws.org/topic/waste-management
39.	Extended Producer Responsibility | Global Plastic Laws. Retrieved 2026-11-09, from https://www.globalplasticlaws.org/topic/extended-producer-responsibility
40.	California Finalizes Regulation Adding Microplastics to Candidate Chemicals List | Department of Toxic Substances Control. Retrieved 2026-11-09, from https://dtsc.ca.gov/2026/07/02/california-finalizes-regulation-adding-microplastics-to-candidate-chemicals-list
41.	About the Project | Global Plastic Laws. Retrieved 2026-11-09, from https://www.globalplasticlaws.org/about
42.	Microplastics. Retrieved 2026-11-09, from https://microplastics.sccwrp.org/
43.	ToMEx — Microplastics Toxicity Database » Plastiverse. Retrieved 2026-11-09, from https://www.plastiverse.org/tools/tomex-microplastics-toxicity-database
44.	Marine Microplastics | National Centers for Environmental Information (NCEI). Retrieved 2026-11-09, from https://www.ncei.noaa.gov/products/microplastics
45.	Dataset Overview | National Centers for Environmental Information (NCEI). Retrieved 2026-11-09, from https://www.ncei.noaa.gov/metadata/geoportal/rest/metadata/item/gov.noaa.ncei:MicroplasticsDatabase/html
46.	ATLAS OF OCEAN MICROPLASTICS. Retrieved 2026-11-09, from https://aomi.env.go.jp/
47.	Data Sources | Global Plastics Hub. Retrieved 2026-11-09, from https://globalplasticshub.org/page/data-sources
48.	Global Plastic and Waste Data Tracker | Global Ocean Accounts Partnership. Retrieved 2026-11-09, from https://oceanaccounts.org/publications/global-plastic-data-tracker/
49.	Data, Interactive-Tools, and AI for Actionable Change in Ending Plastic Pollution | The Eric and Wendy Schmidt Center for Data Science & Environment at Berkeley. Retrieved 2026-11-09, from https://dse.berkeley.edu/news/data-interactive-tools-and-ai-actionable-change-ending-plastic-pollution
50.	Plastics Research Tools & Resources » Plastiverse. Retrieved 2026-11-09, from https://www.plastiverse.org/microplastics-tools-resources
51.	One4All: An Open Source Portal to Validate, Share, and Harmonize Microplastics Data » Plastiverse. Retrieved 2026-11-09, from https://www.plastiverse.org/tools/one4all-an-open-source-portal-to-validate-share-and-harmonize-microplastics-data
52.	GitHub - ScottCoffin/ToMEx2.0_EcoToxRisk: ToMEx 2.0 Ecological Risk Assessment (PSSD++) · GitHub. Retrieved 2026-11-09, from https://github.com/ScottCoffin/ToMEx2.0_EcoToxRisk
