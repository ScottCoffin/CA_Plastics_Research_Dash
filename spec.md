CA Plastics Research Atlas — Agent Build Specification
Working title: CA Plastics Research Atlas (ca-plastics-atlas)Owner / product lead: Scott CoffinAudience: autonomous or semi-autonomous IDE coding agents (one session at a time) and the human product ownerSpec status: v1.0. Written 2026-11-05. Every external-API detail not marked (verified in research) must be smoke-tested by the agent before it is relied on and recorded in docs/api_notes/.
How to read this spec. Part A is the product. Part B is the operating protocol every agent session must follow (memory, handoff, tool requests). Part C is the architecture and data model. Part D is the source and reuse registry. Part E is the staged roadmap, where each stage is split into session-sized tasks. Part F covers quality, evaluation and ethics. Part G lists open decisions that need the human owner.Epistemic labels used throughout: [V] = verified in the research phase, with citation; [GK] = general knowledge, not verified for this project; [INF] = inference or design choice; [VERIFY] = the agent must test it before use.

PART A — PRODUCT
A1. Purpose
A free, auto-updating, public dashboard that answers three questions about plastic-related science in California:
1.	Who is doing plastic-related research in California, at which institutions, and in which domains? (Expert finding.)
2.	What monitoring data exist for plastics in California, including data collected by out-of-state researchers?
3.	What research is being funded in California, federally and by the state?
A2. Scope definitions (defaults; the owner may change them in Part G)

Term	Default definition
Plastic-related work	A work whose title or abstract is primarily about plastic debris or particles: macro-, meso-, micro-, nanoplastics; plastic litter and marine debris; microfibers; tire-wear particles; plastic pollution policy. Tier 2, flagged separately: chemicals-in-plastics (additives, plastic-associated chemicals).
CA-led	The first author's affiliation on the work resolves to a California institution. (Corresponding author and last author are recorded as secondary flags.)
CA-sampled	Field sampling, collection of environmental, biological or product samples, or deployed monitoring, took place in California land or California state waters.
CA-plastic-centric work	plastic_related = true AND (ca_led = true OR ca_sampled ∈ {yes, partial}). The ca_basis field records which condition(s) qualified it.
California institution	An institution whose registry location (state) is California.
State waters	California's 3-nautical-mile maritime zone. Use the CDFW polygon. That dataset was generated from NOAA's 3 nautical mile offshore maritime limit line clipped to California state waters, with a polygon version recommended for any area calculations or analysis 1, and its boundaries do NOT represent the legal depiction of maritime limits 2. Cite that caveat in the Methods page.

Owner assumption to honour: nearly all California-focused projects have at least one author at a California institution. The candidate pool for the CA-sampling classifier is therefore works with a California-affiliated author in any position. This does not imply that most pool members are CA-sampled. Many are lab, modeling, review, or out-of-state or global sampling studies. The classifier must be multi-class (see C4). A leak test (Stage 5) quantifies what the assumption misses.
A3. Primary user questions and required UX
A3.1 Tab "Experts & Institutions" (Question 1)
•	Filters (all combinable, with URL-hash state so a filtered view is shareable):
◦	topic and domain tags: environment/matrix (marine, estuarine, freshwater, stormwater, wastewater/biosolids, drinking water, air, soil/agriculture, biota, human exposure, consumer/indoor) × discipline (occurrence/monitoring, analytical methods, fate and transport/modeling, ecotoxicology, human health, sources and pathways, mitigation/engineering, policy/social science, materials/polymers, chemicals-in-plastics);
◦	institution type: UC, CSU, other public university, private university, community college, nonprofit/NGO, state agency, federal lab, local agency, JPA/research authority (e.g., a coastal water research authority), company;
◦	specific institution;
◦	years;
◦	ca_basis (CA-led, CA-sampled, both);
◦	OA availability.
•	Researcher list. Each row shows name, current CA affiliation, top domain tags, number of CA-plastic-centric works (all time and last 5 years), most recent year, and an ORCID link when OpenAlex has one.
•	Click-through researcher drawer or page showing:
◦	their CA-plastic-centric works (title, year, journal, DOI link, OA link, ca_basis, tags, evidence level);
◦	an affiliation history as recorded on those works;
◦	co-author institutions;
◦	a "report an error" link (see F4).
•	Institutions view. A leaderboard by tagged-work count (all time, 5-year) with sparklines, plus a map (institution markers sized by tagged works, clustered, colored by institution type). Institution coordinates are available in OpenAlex because the institution object has a geo object containing city, region, country_code, latitude and longitude 3.
•	Prominence. Institutions and labs with high counts are visually prominent by default. Researchers are sorted by "tagged works", labelled as volume, not quality. Do not default-rank individuals by citations (F4).
A3.2 Tab "Monitoring Data" (Question 2)
•	A dataset registry of plastics monitoring and occurrence data that cover California, with columns: name, steward, matrix, plastic size class (micro/macro), years, approximate N samples, spatial extent, methods (e.g., mesh size, spectroscopy), access tier, license, format, contact/URL, contributor_in_CA (so out-of-state contributors are visible), and linked papers.
•	A map of ingestible sample-level points (clustered), filterable by matrix, year, source, method and contributor.
•	A "data gaps" view (matrix × region × year) so users can see what is not monitored.
•	Access tiers:
◦	A = harmonized and ingested into the atlas;
◦	B = downloadable but not harmonized;
◦	C = exists, but request-only;
◦	D = in a paper or supplement only.
A3.3 Tab "Funding" (Question 3)
•	A table and charts of awards, filterable by funder (federal vs. state vs. other), program, year, amount, recipient institution type, topic tags, and ca_led (PI organization in California).
•	A pass-through chain field (e.g., OPC → California Sea Grant → a CSU campus), de-duplicated on the lowest-level project ID.
•	A separate "open funding calls" panel from the California Grants Portal. That portal lists grants offered, as a CSV updated daily with a public-domain license 4, so it is not an awards source.
•	Link awards to resulting papers and datasets where evidence exists (Stage 9).
A3.4 Tab "About / Methods / Data quality"
Definitions, source list with last-refresh timestamps, classifier performance (precision/recall on the held-out gold set), known limitations, how to submit corrections, citation and license info, and a disclaimer. Scott's personal site states that his views do not represent the State of California or its agencies, per the page (disclaimer on scottcoff.in 5). The dashboard must carry an explicit disclaimer that it is an independent project and not an official OEHHA or State product, unless the owner decides otherwise (G-12).
A4. Non-goals (v1)
•	No hosting of full-text papers. Store derived features and short evidence snippets only (F5).
•	No per-person quality rankings.
•	No paid LLM API calls in the pipeline. An optional, human-triggered, local-model assist for the review queue is allowed later.
•	No scraping behind logins.

PART B — AGENT OPERATING PROTOCOL (MANDATORY)
The project is built piece-wise by many short agent sessions. Context overload and compaction are the main failure modes. The rules below keep each session small and every handoff lossless.
B1. Core rules
1.	One task per session. Take the first unchecked task in .agent/TODO.md whose dependencies are met. Finish it to its Definition of Done (DoD), run its acceptance check, update memory, commit, and end the session. Do not start the next task, even if context remains.
2.	Smallest context that works. Never cat large data files. Use head, wc -l, DuckDB DESCRIBE/LIMIT, or schema printouts. Redirect verbose tool or API output to scratch/ (gitignored) and write only a ≤20-line summary into memory or docs.
3.	No silent assumptions. If a decision isn't in DECISIONS.md or this spec, record it as a question in .agent/QUESTIONS.md and use the stated default. Do not block unless the item is marked 🔴 BLOCKING.
4.	Verify before relying. Anything tagged [VERIFY] needs a smoke test script in scripts/smoke/ and a dated note in docs/api_notes/<source>.md (endpoint, parameters used, sample response shape, rate limits, license or terms observed). If reality contradicts this spec, the note wins. Add a lesson to LESSONS.md and update the spec-derived tasks.
5.	Reproducibility. Every pipeline step is a script with explicit inputs and outputs, runnable locally and in CI. No notebook-only logic.
6.	Idempotent, incremental, resumable. Re-running a step must not duplicate data. Ingesters record a high-water mark.
7.	Cost and rate discipline. Log API usage per run to data/logs/api_usage.jsonl. Budget alarms are described in Stage 2.
8.	Tests. Each stage ships unit tests plus a small fixture dataset (≤200 records) in tests/fixtures/ so later agents can develop without hitting live APIs.
9.	Never commit secrets. Use GitHub Actions secrets and .env (gitignored).
10.	Attribution and licenses. Before copying code from another repository, record its license in docs/REUSE.md. If a license is missing or incompatible, do not copy; reimplement from the described approach and note it.
B2. Persistent memory layout (create in Stage 0)
.agent/
  README.md            # this protocol, short form + pointers to the spec
  TODO.md              # roadmap as checkboxes: stage → task IDs, status, owner-needed flag
  MEMORY.md            # durable facts: architecture, conventions, IDs, file locations, "how to run X"
  DECISIONS.md         # ADR-style log: id, date, decision, alternatives, rationale, who decided
  LESSONS.md           # gotchas, API quirks, failed approaches (append-only, newest on top)
  HANDOFF.md           # ONLY the latest session's handoff note (overwritten each session)
  QUESTIONS.md         # open questions for the human owner, with defaults in use
  TOOL_REQUESTS.md     # requests for tools/skills/MCPs (see B5)
  SESSION_LOG.md       # one line per session: date, task ID, outcome, commit hash
docs/
  api_notes/           # one file per external source (verified behaviours)
  REUSE.md             # table of reused repos: URL, license, what was reused, adaptation notes
  SOURCES.md           # registry of data sources with status
Keep each memory file short (target ≤200 lines; split or archive older entries into .agent/archive/ when longer). MEMORY.md is the only file every session must read in full.
B3. Session start checklist (≤5 minutes of reading)
1.	Read .agent/README.md (30 lines), then MEMORY.md, HANDOFF.md, TODO.md.
2.	Skim QUESTIONS.md for answers from the owner since the last session.
3.	git log --oneline -15 and git status.
4.	Read only the spec sections for your task: Part B, the stage entry in Part E, and any source rows in Part D that the task names.
5.	Confirm the task, its dependencies, and its DoD in TODO.md. If a dependency is unmet, pick the next eligible task or record the block.
B4. Session end checklist
1.	Run the task's acceptance check and the full unit test suite (make test).
2.	Update, in this order: TODO.md (check off), MEMORY.md (new durable facts only), DECISIONS.md, LESSONS.md, QUESTIONS.md, docs/api_notes/*, docs/REUSE.md.
3.	Overwrite HANDOFF.md using the template below.
4.	Append one line to SESSION_LOG.md.
5.	Commit with message S<stage>.<task>: <summary>. Push if configured.
6.	Stop. Final message to the user: what was done, what is next, what the owner must do (if anything).
HANDOFF.md template
# Handoff — <date> — task <ID>
## Done
- bullets, with file paths
## State of the repo
- how to run it / what currently works (commands)
- known failing tests or warnings
## Next task (suggested)
- ID, one-sentence goal, first 3 steps
## Gotchas the next agent must know
- bullets (also copied to LESSONS.md if durable)
## Needs owner input
- links to QUESTIONS.md items
## Files that are large or unsafe to read whole
- path → how to inspect (command)
B5. Tool, skill and MCP requests
Agents should ask for capabilities rather than grinding through tasks inefficiently. Append to .agent/TOOL_REQUESTS.md, and also tell the user in the session-end message:
## <date> — <short name>
- Task/stage where it would help:
- What I'm doing the slow way now:
- Proposed capability (tool / skill / MCP / CLI / service):
- Expected benefit (time, accuracy, context saved):
- Risk/cost/privacy notes:
- Fallback if declined:
Candidate requests to consider (do not assume they exist; ask):

Capability	Where it helps
GitHub MCP / gh CLI with Actions scope	Triggering and inspecting workflow runs, reading logs, managing secrets and variables (Stages 0, 2, 10)
DuckDB CLI or MCP	Inspecting Parquet without loading it into context (all data stages)
Browser automation MCP (e.g., Playwright-style)	JavaScript-rendered pages that block simple fetches: Sea Grant listings, funder pages, NCEI portal (Stages 7–8)
Web fetch / search MCP	Verifying API docs and funder pages (all)
Library-docs MCP	Up-to-date docs for pyalex, SetFit, DuckDB-Wasm, MapLibre/Leaflet
Annotation tool (Label Studio or Argilla via Docker)	Gold-set labelling with agreement stats (Stage 4)
Docker	GROBID service, optional Elasticsearch/GeoNames for geoparser evaluation (Stages 5–6)
GPU or self-hosted runner	Only if SciBERT fine-tuning or a local LLM becomes necessary
PDF skills (text and layout extraction)	Stage 6 fallback when GROBID is unavailable
Spreadsheet or XLSX reader skill	CA open-data XLSX sources, Delta Science Tracker export
Playwright or screenshot skill for UI regression	Stage 3 and later front-end checks


PART C — ARCHITECTURE
C1. High-level design
 ┌───────────────┐  ┌───────────────┐  ┌───────────────┐
 │ Works sources │  │ Grants sources│  │ Monitoring    │
 │ OpenAlex,     │  │ NIH, NSF,     │  │ sources: NCEI,│
 │ EuropePMC,    │  │ USAspending,  │  │ CA Open Data, │
 │ DataCite…     │  │ Sea Grant,OPC…│  │ CEDEN, MDMAP… │
 └──────┬────────┘  └──────┬────────┘  └──────┬────────┘
        ▼ ingest (cron, incremental, idempotent) ▼
   data/raw/*  →  data/interim/*  (normalized, Parquet)
        ▼ enrich + classify (CPU inference, frozen models)
   data/processed/*.parquet  (works, authorships, authors, institutions,
                              labels, grants, datasets, links)
        ▼ build (aggregate, precompute JSON for UI)
   site/data/*.json (small)  + site/data/*.parquet (optional DuckDB-Wasm)
        ▼ static front end (single-file HTML/JS; stlite fallback)
   GitHub Pages
This follows the pattern of the owner's Job_Scraper repo. That repo is a set of GitHub Actions pipelines that scrape sources on a schedule, commit results to the repo, and show them in a filterable triage.html dashboard hosted on GitHub Pages 6. Its dashboard is a single-file static page that fetches the JSON files from the same repo at view time, so it reflects the latest commit 6. Adopt that pattern, but fix its sluggishness on big datasets (C5).
C2. Repository layout (target)
ca-plastics-atlas/
  .agent/                     # memory (B2)
  .github/workflows/
    ingest_works.yml          # daily
    ingest_grants.yml         # weekly
    ingest_monitoring.yml     # weekly
    classify.yml              # after ingest (workflow_run) or inside ingest jobs
    build_deploy.yml          # builds site, deploys Pages
    watchdog.yml              # re-dispatches missed runs (pattern from Job_Scraper)
    keepalive.yml             # prevents 60-day auto-disable
  config/
    queries.yml               # plastic-related queries, versioned
    taxonomy.yml              # domain/matrix/discipline vocabularies (human-editable)
    institution_overrides.csv # manual institution type/region fixes
    author_overrides.csv      # merge/split/exclude researchers
    gazetteer_ca.csv          # curated CA place names + water bodies + aliases
    sources.yml               # source registry (mirrors Part D)
  curation/
    gold_works.parquet|csv    # human-labelled gold set (versioned)
    gold_grants.csv
    overrides_works.csv       # human-confirmed labels; NEVER overwritten by cron
    review_queue.csv          # low-confidence items for humans
  data/                       # (see C6 on size/branching)
    raw/ interim/ processed/ logs/
  src/atlas/
    ingest/ (openalex.py, europepmc.py, datacite.py, grants/*.py, monitoring/*.py)
    geo/ (gazetteer.py, geocode.py, ca_polygons.py)
    nlp/ (rules.py, features.py, setfit_train.py, infer.py, eval.py)
    fulltext/ (fetch.py, grobid_client.py, sections.py)
    build/ (aggregate.py, export_site.py)
    util/ (io.py, ids.py, logging.py, cost.py)
  scripts/ smoke/             # smoke tests for external APIs
  site/
    index.html                # single-file app (or small bundle)
    assets/ data/
    stlite/                   # fallback app (Stage 11)
  tests/ fixtures/
  docs/ (api_notes/, REUSE.md, SOURCES.md, METHODS.md, LABELING_GUIDE.md)
  Makefile  pyproject.toml  README.md  LICENSE
C3. Data model (processed layer; Parquet, snake_case)
•	works: work_id (OpenAlex ID), doi, title, abstract, year, pub_date, type, journal, is_oa, oa_status, oa_url, license, openalex_topics[], primary_topic, cited_by_count, first_seen, last_updated.
•	authorships: work_id, author_id, author_name, position (first/middle/last), is_corresponding, institution_ids[], raw_affiliation.
•	authors: author_id, name, orcid, ca_works_count, first_year, last_year, domain_tags[] (aggregated), override_flags.
•	institutions: inst_id, ror, name, city, region, lat, lon, ror_types[], atlas_type (UC, CSU, other-public, private, community-college, nonprofit/NGO, state-agency, federal, local-agency, JPA, company, other), parent_system, ca_flag.
•	work_labels: work_id, plastic_related (+score), plastic_tier (core | chemicals-in-plastics), ca_sampled (yes|partial|no|unclear), ca_setting[], study_type, domain_tags[], evidence_level (abstract|fulltext), evidence_snippets[], model_version, label_source (rule|model|human), confidence, needs_review.
•	geo_mentions: work_id, toponym, geonames_id, lat, lon, in_ca_land, in_ca_state_waters, section, sentence_id, role_pred (sampled|mention|other).
•	datasets: registry rows (A3.2) + access_tier, contributor_orgs[], contributor_in_ca, linked_work_ids[].
•	samples (tier-A sources only): sample_id, dataset_id, lat, lon, date, matrix, size_class, method, mesh_um, concentration_value, concentration_unit, in_ca_land, in_ca_state_waters, contributor, citation.
•	grants: grant_key, source, source_award_id, title, abstract, pi_names[], org, org_ror, org_state, start, end, amount, currency, funder, program, funder_chain[], url, plastic_related, domain_tags[], ca_led, ca_sampling_flag.
•	links: work_grant_links, work_dataset_links (evidence: acknowledgement-match | DataCite-relation | DAS-match | manual).
Keys: OpenAlex IDs for works, authors and institutions; ROR for institutions where available; DOI as a cross-source work key; grant_key = hash of (source, source_award_id) with a de-dup pass across pass-through sources.
C4. Classification design (no frontier-LLM calls)
The task is decomposed so that most of it is deterministic.
Layer 0 — Candidate pool (metadata, no ML).OpenAlex query for plastic-related terms (config/queries.yml), restricted to works with ≥1 authorship whose institution is in the California institution registry (C7). Also collect ca_led from first authorship. OpenAlex has the building blocks:
•	institutions can be filtered and grouped by geo.region, which holds the state, province or region 3; the docs give no California example, so test geo.region:California [VERIFY];
•	works can be filtered by authorships.institutions.id, .ror, .country_code, .type and .lineage 7.A direct geo.region filter on the works endpoint was not confirmed; build the California institution ID list first and batch it into works filters [VERIFY URL length limits].
Layer 1 — Plastic relevance (works and grants). Rules (term lists with word boundaries and exclusions) for high-precision includes, then a small classifier for the ambiguous middle. Decision-tree ordering of rules and "keywords for obvious cases, model for ambiguous ones" mirror the approach described in the grant-classification repo, which uses hybrid keyword + LLM and a decision tree with strict ordering 8; reuse the pattern, not the LLM.
Layer 2 — CA-sampling classifier (the hard part). Staged:
1.	Gazetteer gate (recall-tuned). Match "California", "CA, USA", counties, cities, named waters (bays, estuaries, rivers, lakes, beaches, marine sanctuaries, offshore regions), and coordinate patterns inside a California bounding box. Gazetteer-based lookup is a standard approach (toponym recognition in scientific articles has mainly relied on rule-based and gazetteer-based approaches 9), and GeoNames is the most widely used gazetteer 10.
2.	NER/toponym extraction, restricted to the right text. One published approach pairs a pre-trained NER tool with rules, targeting specific article portions, to output the relevant locations (study sites, sample locations) 9. Choose the NER tool by measurement on the gold set. A cross-domain comparison found Flair with F1 0.89 but spaCy with recall of only 0.5 11, which is a reason not to trust a default spaCy model unvalidated. Do not extrapolate those numbers to this corpus.
3.	Sampling-vs-mention classifier on sentences containing a California toponym: labels sampled_here | mentioned | other. First baseline: SetFit, which is prompt-free, does not require large models, and is typically an order of magnitude or more faster to train and run 12. Comparator: fine-tuned SciBERT, since SciBERT consistently outperformed BERT, BioBERT and BlueBERT on abstract- and keyword-based scientific text classification 13 (benchmarks are topic classification, not location role; they do not predict performance here).
4.	Geocode and polygon test. Resolve toponyms to GeoNames coordinates; test against (California land polygon) ∪ (CDFW 3-nm state-waters polygon). Named regions (e.g., a bight or a bay) are matched via a curated region→polygon table, not a single centroid [INF]. Papers that straddle the 3-nm limit get partial.
5.	Aggregation to ca_sampled with confidence; low confidence or conflicting signals → needs_review.
Heavier alternatives (Mordecai3 and similar) are evaluation comparators only in v1. Mordecai3 uses spaCy to identify place names, retrieves candidate locations from the GeoNames gazetteer in a local Elasticsearch index, and ranks candidates with a neural model 14. The Elasticsearch requirement makes it heavy for scheduled CI, so default to a lightweight GeoNames subset in SQLite or DuckDB [INF].
Layer 3 — Domain tagging (multi-label). Input features: OpenAlex topics, text embeddings, rule hits from taxonomy.yml. OpenAlex's hierarchy is 4 domains → 26 fields → 252 subfields → 4,516 topics (with up to three topics per work assigned automatically from title, abstract and source name 3), and a work lands in a subfield because a machine-learning model inferred its topic 15. Use these as features and a sanity check, not as the final domain tags: OpenAlex topics are too coarse for "air monitoring vs. aquatic toxicology" [INF]. Train a multi-label SetFit head on the gold set. Reuse the regex facet vocabularies from the Trendspotter app as a seed (EXP_*, MECH_*, ORGAN_*, MODEL_* columns, per its README) (the regex labels are generated by pattern matching 16), and note its own caveat that regex could not tell studying a mechanism from merely mentioning it 16. The same weakness will affect California mentions.
Layer 4 — Researcher-level tags. Aggregate work-level domain tags to authors, weighting first/last/corresponding positions higher [INF]; show top-N tags with counts. Researcher profiles inherit OpenAlex's disambiguation errors (C8).
Training policy.
•	Training happens offline (a local machine or a manually triggered workflow).
•	The cron job only runs inference with a frozen, versioned model (committed small, or hosted on a model hub).
•	Human overrides in curation/overrides_works.csv always beat model output.
C5. Front-end performance design
The owner reports that the single-file dashboard pattern can be sluggish on large datasets. Apply this ladder, in order, and measure before escalating:
1.	Never render all rows. Virtualize or paginate tables, and render at most a few hundred DOM rows.
2.	Pre-aggregate in the build. Counts by year, institution, tag, and map clusters are computed in Python and shipped as small JSON.
3.	Split data. index.json (slim fields for filtering and lists) plus per-entity detail JSON loaded on click. Filter in a Web Worker, not the main thread [GK].
4.	Text search index built at build time (a small client-side search library) [GK].
5.	DuckDB-Wasm + Parquet only if needed. It runs a full DuckDB engine inside the browser and reads only the bytes a query needs from Parquet 17, but WebAssembly limits memory to 4 GB and browsers may impose stricter limits 18.
6.	Fallback: stlite (Stage 11), a serverless Streamlit running entirely in the browser via Pyodide, Apache-2.0, hostable as static files 19. Known limits: packages with binary extensions not built for Pyodide cannot be installed, runtime files are lost on reload, and it runs single-threaded 19. Because ML runs in CI, the app only reads data files. Streamlit Community Cloud is not recommended for embedding: apps without traffic for 12 hours go to sleep 20.
Performance budget (targets; confirm in Stage 3): first meaningful render < 2 s on a mid-range laptop; filter response < 150 ms; initial payload < 3 MB gzip [INF].
C6. Data size and branch strategy
•	Keep committed site/data/ small (JSON and a slim Parquet).
•	Large intermediates (data/raw, embeddings, extracted text) are gitignored and cached in Actions artifacts or stored on a data branch or release assets [VERIFY GitHub file-size and repo-size limits at implementation time].
•	Job_Scraper-style commits require read-and-write workflow permissions plus a repo variable ENABLE_DATA_COMMITS=true; without it scrapers run but nothing is saved 6. Reuse that guard.
C7. California institution registry
1.	Pull OpenAlex institutions with geo.region = California [VERIFY exact value and edge cases such as "CA" or missing region].
2.	Join to ROR. ROR schema v2.1 gives country_subdivision_code and country_subdivision_name in locations.geonames_details 21, and organization types from a controlled list: education, funder, healthcare, company, archive, nonprofit, government, facility, other 22.
3.	Map into atlas_type (UC, CSU, other-public, private, community-college, nonprofit/NGO, state-agency, federal, local-agency, JPA, company) via lineage and name rules plus config/institution_overrides.csv. UC/CSU campuses are children of a system; use lineage. Estuary institutes, research authorities and federal labs are likely to need manual typing [INF].
4.	Manually review the top ~150 institutions by plastic-work count (human check, ~1 hour).
5.	Publish institutions.parquet and keep an audit of institutions with missing region (these cause false negatives for CA-led).
C8. Researcher identity
•	Use OpenAlex author IDs and ORCIDs when present. The system has known limits: the two failure modes are splitting (one person's works across profiles) and merging (different people collapsed into one) 23; about one author profile in ten has an ORCID 24, and ORCID attachments can be wrong upstream.
•	Therefore: provide config/author_overrides.csv (merge, split, exclude), a "report an error" link, and a QC report listing authors with unusually many topics or institutions across the corpus [INF].
•	Never infer or publish personal contact details (F4).

PART D — SOURCE AND REUSE REGISTRY
D1. Works and metadata sources

Source	Verified facts	Use
OpenAlex API	Free account → API key with $1/day free usage and no payment method 25; exhausted budgets return rate-limit errors until midnight UTC 25. Cost note: a group_by costs what its query costs: 1 credit on a list, 10 on a search 26. Filtering supports negation (!) and AND via commas 27. Authorship filter/group fields include authorships.countries, authorships.institutions.country_code, authorships.institutions.id, authorships.institutions.lineage 28
Primary works, authorships, institutions, topics, OA links. Build a cost logger first (Stage 2.1); the credit-to-dollar conversion must be read from the "Example costs" docs [VERIFY]
OpenAlex OA fields	is_oa, oa_status, oa_url 29; best_oa_location is the best freely readable copy or null 30; locations include pdf_url, license, version 31
Full-text discovery and license gating
pyalex	Python library for OpenAlex with cursor and offset paging; paginate() takes per_page and n_max 32
Client; license [VERIFY] before vendoring. Prefer it as a pip dependency
Europe PMC	fullTextXML endpoint returns full text in XML for the Open Access subset 33; OA XML directory updated weekly 34; downloads include a preprints subset 35
Structured OA full text (best source for Methods sections)
pyEuropePMC	FullTextClient retrieves full text by PMC ID as XML, PDF or HTML with a file cache and rate-limit delay 36
Possible reuse; license and maintenance [VERIFY]
GROBID	Header extraction, full-text structuring, and models for section titles, data availability statements, figures and tables 37; output is TEI XML	PDF→sections when XML is unavailable; run as a Docker service in CI or locally
DataCite REST API	/dois endpoint queries DOI metadata and relationships; citation and reference events use relation types such as IsCitedBy/IsReferencedBy/IsSupplementTo 38; relatedIdentifier connects objects 39
Find datasets linked to papers (Stage 7/9)
ROR API v2	Schema/types/locations as in C7	Institution typing and region
CDFW 3-nm limit dataset	Creative Commons Attribution license; line and polygon versions 1; GeoJSON download offered	State-waters polygon

D2. Monitoring-data sources (Question 2)

Source	Verified facts	Plan
NOAA NCEI Marine Microplastics DB	Contains only in-situ measured marine microplastic concentrations; downloadable in CSV, JSON, GeoJSON; updated quarterly; minimum required fields include sampling date, coordinates, mesh size and concentration 40. 29,076 samples between 1972 and 2026 41 (global). Portal supports export of filtered data and whole-database download 42
Tier A. Download (or API [VERIFY]), clip to CA land + state waters with polygon tests, preserve contributor and citation fields, set contributor_in_ca by affiliation matching [VERIFY field names]
SFEI / 5 Gyres SF Bay Microplastics Project (CA Open Data)	Sampling in stormwater, treated wastewater, surface water, sediment and prey fish 43; XLSX particle data linked to particle-specific data by a SampleID field 44; license Creative Commons Attribution 45
Tier A after schema mapping
SFEI RMP (CD3)	≈2 million records since 1993 via the CD3 tool; also uploaded to CEDEN 46
Tier B unless microplastics subset is separable [VERIFY]
CEDEN	Query tool plus Open Data Portal flat files and APIs; larger datasets may have problems 47. CEDEN 2.0: microplastics and other data types will be added over time 48
Watch item. Check for microplastics data at implementation; likely Tier B or C now [VERIFY]
Drinking-water microplastics (SB 1422)	Law requires a standard methodology and four years of testing and reporting with public disclosure 49; Phase One for large untreated community water systems began in Fall 2023 and continues through 2025 50; three laboratories are accredited 51. A reporting workflow exists: upload data to the Microplastic Data Portal (One4ALL), correct errors, input a key, and data is sent to data.ca.gov 52
Tier A if a data.ca.gov dataset is published; else registry-only. Discover dataset IDs at implementation [VERIFY]
Moore Institute "Microplastics in Drinking Water" (CA Open Data)	Alpha dataset created by reviewing peer-reviewed studies on microplastics in drinking water for bottled and tap water; raw data also on GitHub 53
Literature-derived data; flag as secondary; useful to cross-check paper links
NOAA MDMAP	Flagship initiative to measure amount and types of marine debris on shorelines; data explorable and exportable 54; documentation and an API are accessible via 'About MDMAP' 54; exports ship with a readme and a suggested citation format 55
Tier A (macrodebris). Clip to CA; keep protocol-version notes (methods changed over time, described in the export readme 55)

Debris Tracker / MDMAP link	MDMAP data collected with the Debris Tracker app will be imported into the MDMAP database 54
Registry note
OPC / SFEI Statewide Plastics Monitoring Strategy	Strategy and planning framework for a statewide plastics program; separate micro- and macroplastics strategies 56; OPC intends to support SWAMP to implement pilot monitoring, with a pilot program in 2027 57; data will be shared through the Open Data Portal or another public database 58
Seed the registry with existing efforts named in the strategy; add the 2027 pilot as a tracked future source
SCCWRP standardized collection methods	Harmonized collection methods for surface sediments, aquatic biota, ambient water and stormwater flows 59
Method-harmonization metadata for method fields
Paper-linked data	DataCite relations (D1); GROBID data-availability parsing (D1)	Stage 7.4: harvest data DOIs (Dryad, Zenodo and similar) tied to CA works [VERIFY coverage]

D3. Funding sources (Question 3)

Source	Verified facts	Plan
NIH RePORTER	org_states filter (no wildcard) and fiscal_years 60; advanced_text_search over title, abstract and mined terms 61
API; org_states=["CA"] + term queries; also run non-CA-org queries for CA-sampling terms
NSF Award Search API	(Secondary guide) boolean keyword search, awardee and performance location, dates and amounts 62
API; confirm exact state parameter in NSF docs [VERIFY]
USAspending	spending_by_award accepts keywords, time_period, recipient_locations, place_of_performance_locations, agencies; award_type_codes required 63; bulk endpoints generate zip files of award data in CSV 64
Covers EPA/NOAA/DOE-type assistance awards [VERIFY agency coverage and key requirements]; short descriptions → noisy keyword relevance
NOAA Marine Debris Program	Award announcements list grantees, state and amount (e.g., California Department of Parks and Recreation, $2,633,100 for removal in the Delta 65)
Scrape or hand-curated CSV; check for a structured awards listing
California Sea Grant projects	Project pages show project number, date range, funding agency, focus area, PI and institution 66. Sea Grant leads grant administration for the five OPC microplastics projects 67 and administers Delta Research Awards with the Delta Science Program 68
Primary structured state source. Scrape the research-projects listing [VERIFY listing structure/pagination]
OPC	Plastic pollution approvals totaled $4,002,797 in the 2023 annual report table 69; June 2026: up to $2,500,000 approved for a pilot statewide microplastics monitoring program 70
Parse Council staff recommendations and annual reports to catch approvals before projects appear on Sea Grant pages
OPC Microplastics Strategy legislative report (June 2026)	Track 2 describes science conducted or funded by state agencies 57
Seed list, hand-curate and cross-check coverage
Delta Science Tracker	Holds fund sources and amounts, geographic areas and products 71; all activities can be exported to an Excel spreadsheet 72
Scheduled export if terms allow [VERIFY automation]
CSU COAST	Grant Development Program awards $5,000–$20,000 73; awardees must acknowledge COAST by a specified name in publications 74; State Coastal Conservancy proposed up to $1,000,000 to COAST for State Science Information Needs research 75
No machine-readable awardee list found; scrape or curate; use Conservancy PDFs for pass-through; use acknowledgement string to link papers
State Water Board	FAAST public proposals search allows viewing and downloading proposals 76; programs are mostly construction, wastewater, recycling and similar financial assistance 77
Expect few research awards. Ask the owner where Water Board research contracts are published (G-6)
CA Grants Portal	Grants offered; CSV updated daily; public-domain license 4
"Open calls" panel only

D4. Reuse registry (code and patterns)

Repository	What to reuse	Verified notes	License check
ScottCoffin/Job_Scraper (owner's)	Cron workflows (hourly/daily), watchdog re-dispatch, ENABLE_DATA_COMMITS guard, dedupe-against-previous-output, workflow_runs.jsonl audit log, per-run deltas/, single-file triage.html (filters, localStorage state, CSV export, charts)	linkedin_watch_backup.yml is a watchdog that re-dispatches missed slots; workflow_runs.jsonl is a CI audit log; dashboard offers CSV export and localStorage-persisted states 6
Owner's repo; ask owner for license preference
SIDaniels/Microplastics_chem_exp_explorer (Trendspotter)	Streamlit UI layout, facet definitions, scripts/ structure, regex label vocabularies (EXP/MECH/ORGAN/MODEL), CSV schema ideas	MIT licensed; Streamlit; README says to replace data files and update classification definitions in app.py; no scheduled refresh documented 16. A vercel-explorer folder and explorer.html exist and are unexplained [VERIFY: read them; they may already be a static front end]	MIT [V]; keep notice
SIDaniels/grant-classification-workflows	Two-pass classification and strict-ordering ideas, and error-review practice	Uses Claude Sonnet; reports no accuracy metrics; license not shown 8
Do not copy code until the license is confirmed; reimplement ideas without LLM calls
Moore-Institute…/Microplastic_Data_Portal	Controlled vocabularies, validator logic and data schema for microplastic sample data; data-submission structure	Open-source R project, CC-BY-4.0, with California Water Boards, supporting SB 1422 78; hosts validator, visualization tool and image explorer web apps	CC-BY-4.0 [V]; attribution required. R→Python port or schema reuse only
whitphx/stlite	Fallback in-browser Streamlit	Apache-2.0; @stlite/browser mounts apps in a page via <streamlit-app> 19
Apache-2.0 [V]
Observable Framework deploy.yml	Reference Pages workflow with push + daily cron + manual dispatch	Workflow uses schedule: [{ cron: "15 10 * * *" }], actions/configure-pages, upload-pages-artifact, deploy-pages 79
Copy the pattern
huggingface/setfit	Few-shot classifier training	Prompt-free few-shot fine-tuning of Sentence Transformers; fast to train 12
Check license/dependencies [VERIFY]
ahalterman/mordecai3	Evaluation comparator	Needs spaCy plus a local Elasticsearch GeoNames index 14
Check license [VERIFY]
grobidOrg/grobid	PDF→TEI service	Full-text extraction including data availability statements and affiliation parsing 80
Check license [VERIFY]
EviAtlas (design reference)	Evidence-map UI concepts	Spatial maps, data tables, descriptive plots and heatmaps 81
Design inspiration only

Note on GitHub Actions: scheduled workflows only run on the default branch, and in public repositories are automatically disabled after 60 days of no repository activity 82. They use UTC by default and can run as often as every 5 minutes 83. Implement keepalive.yml and the watchdog, and document the failure mode in LESSONS.md.

PART E — STAGED ROADMAP
Legend. Session = one agent working session ending in a discrete handoff. IDs are S<stage>.<task>. 🧑 = owner action required. Every task's final step is B4. Approximate effort: S (<1 h), M (1–3 h), L (3–6 h) of agent time.
Dependency overview
S0 ─ S1 ─ S2 ─ S3 (MVP live, OpenAlex topics only)
              ├─ S4 (gold set) ─ S5 (classifiers) ─ S9 (linking)
              ├─ S6 (full text) ───────────────────┘
              ├─ S7 (monitoring)  ─────────────────┘
              └─ S8 (grants)      ─────────────────┘
S10 (hardening) after S5+S7+S8;  S11 (fallback/extras) last
Why this order: S3 ships a usable expert finder early from metadata alone, so the owner and colleagues can react to real output while the harder classification work proceeds.

STAGE 0 — Bootstrap and agent memory (≈2 sessions)
Goal. Repo skeleton, tooling, CI scaffolding, and the memory system from Part B.

ID	Task	DoD / acceptance	Size
S0.1	Create repo skeleton per C2; pyproject.toml, Makefile targets (setup, test, lint, build), pre-commit, .gitignore, LICENSE placeholder 🧑 license choice, README stub. Create .agent/* and docs/* files with the templates in B2/B4	make test passes on an empty test; all .agent files exist; TODO.md contains this roadmap as checkboxes	M
S0.2	CI scaffold: lint+test workflow; Pages deploy workflow cloned from the Observable pattern with a placeholder site/index.html; keepalive.yml; watchdog.yml modeled on Job_Scraper; ENABLE_DATA_COMMITS guard	A push deploys the placeholder page; a manual dispatch runs; secrets documented in docs/SECRETS.md (names only) 🧑 add OPENALEX_API_KEY	M

Handoff: MEMORY.md has repo conventions and commands. Request tools: GitHub CLI/MCP (B5).

STAGE 1 — Reference data (≈4 sessions)
Goal. California institution registry, geography, gazetteer, and the plastics query config. Everything downstream depends on these.

ID	Task	DoD / acceptance	Size
S1.1	API smoke tests for OpenAlex (institutions with geo.region, works filters by institution ID, cost accounting), ROR v2. Write docs/api_notes/openalex.md and ror.md. Build util/cost.py that logs requests and credit cost per run	Notes include: exact working geo.region value for California, URL-length limit for institution-ID batches, observed per-request cost, pagination method used	M
S1.2	CA institution registry: pull, join ROR, derive atlas_type (rules + institution_overrides.csv), produce data/processed/institutions.parquet and docs/institutions_qc.md (counts per type, institutions with missing region)	Registry covers UC (all campuses), CSU (all campuses), major private universities, and at least the top 100 institutions by plastic-work count are manually reviewed 🧑 (30–60 min review of a generated CSV)	L
S1.3	Geography assets: California land polygon (a public boundary dataset [VERIFY source and license]), CDFW 3-nm state-waters polygon (see A2), geo/ca_polygons.py with in_ca(lat, lon) → {land, state_waters, none}, unit tests with known points (e.g., inland CA, a point 1 nm offshore, a point 10 nm offshore, a point in Oregon)	Tests pass; polygons stored simplified for the browser (<1 MB) and full-resolution for the pipeline	M
S1.4	Gazetteer v0: GeoNames California subset (load into SQLite/DuckDB) + config/gazetteer_ca.csv of curated aliases (water bodies, regions, local nicknames) and blacklist of ambiguous names (e.g., place names that are also common words)	geo/gazetteer.py lookup API with tests; documented blacklist rationale	M
S1.5	Query config v1: config/queries.yml (core terms, tier-2 terms, exclusions), documented in docs/METHODS.md with a versioning rule. Run a count-only OpenAlex query to estimate corpus size	Estimated counts logged in MEMORY.md; owner decision G-1/G-2 recorded 🧑	S


STAGE 2 — Works ingestion (≈4 sessions)
Goal. Incremental, idempotent OpenAlex ingestion for the CA candidate pool.

ID	Task	DoD / acceptance	Size
S2.1	Ingester v1 (ingest/openalex.py): backfill by year windows, then incremental by date or updated-since. [VERIFY which OpenAlex filters support incremental pulls]. Store raw JSON snapshots (gitignored) → interim/works_raw.parquet	Re-running yields no duplicates; high-water mark file; api_usage.jsonl written; fixture of ≤200 works committed	L
S2.2	Normalization: works, authorships, authors, institution linking, ca_led (first author) + ca_any_author flags; QC report (missing affiliations, null-author IDs, works with CA authors but no resolved institution)	Output tables conform to C3; QC report generated by make qc	M
S2.3	Provisional tags from OpenAlex topics and rule-based facets (matrix/discipline) seeded from config/taxonomy.yml and the Trendspotter regex vocabularies. Mark label_source=rule	work_labels populated with plastic_related (rule-based) and provisional domain_tags; coverage stats logged	M
S2.4	Workflow ingest_works.yml (daily cron) committing outputs under the ENABLE_DATA_COMMITS guard; budget guard that aborts gracefully on a 429 and resumes next run	A scheduled run succeeds in CI; failure mode tested (simulate rate limit)	M

Handoff note must include: the actual measured daily credit use and the largest backfill window that fits the free budget.

STAGE 3 — MVP front end: Experts & Institutions (≈6 sessions)
Goal. A live, performant dashboard answering Question 1 from metadata-level labels.

ID	Task	DoD / acceptance	Size
S3.1	Build exporter build/export_site.py: produce site/data/index.json (slim), institutions.json, per-author detail JSON, aggregates (by year, type, tag), map layer GeoJSON	Payload sizes logged; schema documented in docs/SITE_DATA.md; payload under budget (C5) or a documented reason	M
S3.2	App shell: single-file HTML/JS (reuse structure and CSS from Job_Scraper's triage.html: filters, state in URL hash, CSV export). Tabs: Experts, Institutions, Monitoring (stub), Funding (stub), About	Loads the fixture and the real data; keyboard-accessible; mobile-friendly	L
S3.3	Experts tab: filters (tags, institution type, institution, years, ca_basis), virtualized list, researcher drawer with works list and "report an error" link	Perf budget met on the full dataset (measure and record); screenshot test	L
S3.4	Institutions tab + map: leaderboard, sparkline, institution-type filter chips, clustered map (a client-side mapping library [GK]; check the tile provider's usage terms [VERIFY])	Map renders ≥ all CA institutions with tagged works; popups link into the Experts view	L
S3.5	About/Methods page from docs/METHODS.md + auto-generated data freshness and counts; disclaimer (G-12)	Page shows last refresh time from build metadata	S
S3.6	Deploy + perf pass: Pages deploy from CI; run the performance ladder (C5) if the budget is missed	Lighthouse-style metrics recorded in MEMORY.md; escalate to DuckDB-Wasm only if needed (decision logged)	M

Milestone M1 (end of Stage 3): public MVP; the owner reviews real outputs and refines taxonomy (feeds Stage 4).

STAGE 4 — Gold set, annotation, and evaluation harness (≈4 sessions; heavy 🧑)
Goal. A versioned labelled set for training and testing; the main bottleneck for quality.

ID	Task	DoD / acceptance	Size
S4.1	Labeling guide docs/LABELING_GUIDE.md: definitions (A2), positive/negative examples, edge cases (offshore, partial, lab with field-collected organisms, modeling using CA data, reviews, "Bay Area" without explicit sites, wastewater plants, tire-wear), state-waters rule, evidence quoting rule	Owner approves 🧑; version tag guide_v1 frozen before labelling	M
S4.2	Sampling plan: stratified sample of ~400–600 pool works (by year, journal type, matrix, OA vs not, institution type) plus a leak-test sample from works with no CA-affiliated author but a gazetteer hit; split into train / dev / test (held out, time- or lab-grouped to limit leakage). Persist IDs in curation/splits_v1.csv	Split files committed; a test set that models never see during development	M
S4.3	Annotation tooling: either (a) a spreadsheet template + importer or (b) a locally-run annotation app [request tool, B5]; double-annotate ≥20% of items; compute Cohen's κ per label	Importer round-trips; agreement report script nlp/eval_agreement.py	M
S4.4	Eval harness nlp/eval.py: precision/recall/F1 per label and per class, calibration plot, error-analysis table written to docs/EVAL_<version>.md. Define target thresholds with the owner 🧑 (G-9)	Harness runs on a dummy predictor; metrics reproducible	M

Owner effort: roughly 6–12 hours of labelling spread over weeks; the agent should provide pre-annotated suggestions (rules output) to speed review, clearly marked as suggestions, to reduce effort without biasing the held-out test set (suggestions are not shown for test items) [INF].

STAGE 5 — Classifiers (≈6 sessions)
Goal. Replace provisional rule-only labels with validated labels.

ID	Task	DoD / acceptance	Size
S5.1	Plastic-relevance classifier: rules + SetFit on dev set; evaluate; threshold selection; document failure cases	Meets thresholds in G-9 on test set, or documents the gap and proposes more labels	M
S5.2	Gazetteer gate + toponym extraction (nlp/rules.py, geo/*): evaluate recall of the gate on the labelled set and on the leak-test sample; compare 2–3 NER options offline	Gate recall reported with CI; chosen NER tool justified in DECISIONS.md	L
S5.3	Sampling-vs-mention classifier (SetFit baseline; SciBERT comparator if baseline misses thresholds) trained on sentence-level labels derived from gold evidence snippets	Per-class metrics on test; model_version registered; model artifacts small enough to commit or host [VERIFY]	L
S5.4	Aggregation + geocoding + polygon logic: produce ca_sampled, ca_setting, confidence, needs_review, evidence_snippets	End-to-end run on test set; confusion matrix for ca_sampled documented	M
S5.5	Domain tagging multi-label (SetFit) over the taxonomy; author-level aggregation	Per-tag F1 reported; tags with insufficient data are merged or flagged "experimental" in UI	L
S5.6	Inference in CI (classify.yml): CPU-only, uses frozen models; writes work_labels and review_queue.csv; merges overrides_works.csv last	CI run completes within a stated time budget; override precedence unit-tested	M
S5.7	Leak-test report: how many CA-sampled papers have no CA-affiliated author? Decide whether to widen the candidate pool 🧑	Report in docs/EVAL_leak_test.md; decision in DECISIONS.md	S

Milestone M2: dashboard shows validated ca_basis, ca_sampled, domain tags; the About page lists precision/recall.

STAGE 6 — Open-access full-text enrichment (≈4 sessions)
Goal. Raise recall of CA-sampling and data-availability detection by reading Methods, not just abstracts, and only for OA papers.

ID	Task	DoD / acceptance	Size
S6.1	Full-text locator: for each candidate work, pick the best OA source: Europe PMC XML when a PMCID exists, otherwise best_oa_location.pdf_url; record license and decide storability (G-8)	Coverage report: share of candidate works with XML, PDF-only, or none	M
S6.2	XML section parser (Europe PMC JATS) → Methods/Study Area/Sampling/Data Availability text; use the cache pattern from pyEuropePMC if license allows	Unit tests on 10 fixture articles	M
S6.3	PDF path via GROBID (Docker); TEI → same section schema; fallback when GROBID fails; throttle and cache in data/raw (gitignored)	Section extraction accuracy spot-checked on 30 PDFs; failure rate logged	L
S6.4	Integrate into Layer 2: run toponym extraction on Methods sections; set evidence_level; re-evaluate on the OA subset of the test set	Report abstract-only vs. full-text performance delta	M

Constraints: store only derived features and short snippets. Respect rate limits, robots rules and licenses (F5). Preprint servers vary; use whatever OpenAlex locations or Europe PMC expose rather than assuming arXiv coverage [GK].

STAGE 7 — Monitoring-data catalogue (≈6 sessions)
Goal. Answer Question 2.

ID	Task	DoD / acceptance	Size
S7.1	Registry schema + seed config/datasets.yml from D2 (NCEI, SF Bay/5 Gyres, RMP/CD3, CEDEN, drinking water, Moore literature dataset, MDMAP, OPC strategy-listed efforts). Include access tier and provenance links	≥15 entries with verified URLs and a last_checked date	M
S7.2	API/portal smoke tests per source; docs/api_notes/* entries; decide Tier A vs B per source	Each source has: access method, format, license, update frequency, field map	M
S7.3	Tier-A ingesters (one session per 1–2 sources): NCEI (clip to CA; contributor fields), SF Bay XLSX (SampleID join), MDMAP (API), drinking-water dataset if public. Normalize to samples schema, unit harmonization (concentration units, size classes), method fields informed by SCCWRP standards	Samples table with polygon flags; QC report (units, missing coords, duplicates); fixtures + tests	L×2–3
S7.4	Paper-linked data discovery: DataCite /dois relationship queries from CA works' DOIs; GROBID/XML data-availability extraction → datasets rows with tier D/B	Precision spot-check on 50 links	M
S7.5	Monitoring tab: registry table, map of samples (clustered, filters), data-gaps heatmap (matrix × region × year), "contributor in CA?" filter	Perf budget met; links to source and citation text displayed	L
S7.6	Watch list: statewide pilot monitoring (planned 2027) and CEDEN 2.0 microplastics module as tracked future sources with a check script	A weekly "has anything changed?" check writes to docs/SOURCES.md	S

Cautions: NCEI is global and heterogeneous. Preserve the data-quality tier and contributor/citation fields rather than blending silently. Sample-level numbers from different methods are not directly comparable; show the method fields next to values. Never present registry inclusion as an endorsement of data quality.

STAGE 8 — Grants (≈7 sessions)
Goal. Answer Question 3.

ID	Task	DoD / acceptance	Size
S8.1	Grant schema + normalization lib; shared plastic-relevance classifier (reuse S5.1 model, retrain on grant text if needed)	Schema in C3; unit tests	M
S8.2	NIH RePORTER ingester (org_states=["CA"] + term sets; also term-only sweep to catch out-of-state projects sampling in CA)	Backfill + incremental; fixtures; usage notes	M
S8.3	NSF ingester; confirm API parameters from NSF docs	Same	M
S8.4	USAspending ingester (spending_by_award, agencies of interest; bulk download for backfill)	Handles pagination (page, hasNext); notes on noisy keywords	L
S8.5	California Sea Grant projects scraper (listing → project pages; parse project number, dates, funder, PI, institution)	≥ all OPC microplastics projects captured, cross-checked against the OPC/Sea Grant announcements	L
S8.6	OPC + Coastal Conservancy + Delta Science Program + COAST curated or scraped sources: Council items, annual reports, Delta Tracker export, COAST pages; pass-through de-dup via funder_chain	Overlap/dedupe report; manual-curation CSV for gaps (curation/gold_grants.csv)	L
S8.7	NOAA Marine Debris Program awards (announcement parsing or curated CSV)	CA awards captured for the last N years; owner confirms N	M
S8.8	State Water Board research funding: investigate what exists, document, implement if feasible 🧑 owner guidance (G-6)	Decision logged: ingest, curate manually, or defer	M
S8.9	California Grants Portal open-calls panel (CSV)	Panel shows open plastic-related calls with deadlines	S
S8.10	Funding tab UI: filters, charts (by funder type/year/institution type), pass-through chain display, links to sources	Perf budget met; amounts clearly labelled with fiscal-year/obligation caveats per source	L

Cautions: definitions of "amount" differ by source (obligated vs. total award); label them. Pass-through awards must not be double-counted in totals.

STAGE 9 — Linking and profile polish (≈3 sessions)

ID	Task	DoD / acceptance	Size
S9.1	Work↔grant links: match award IDs in OA full-text acknowledgements and funding statements (GROBID parses acknowledgement and funding statements per its output spec); match fixed strings such as COAST's required acknowledgement name; match OpenAlex funder/award fields where present [VERIFY availability]	Precision spot-check on 50 links; unmatched left unlinked	M
S9.2	Work↔dataset links surfaced in researcher drawers and dataset rows	Links display with evidence type	S
S9.3	Expert profile polish: "active funding" badges (from grants), "data stewardship" badges (from datasets), co-author institution network summary; optional "expertise statement" built from top tags (no free-text generation by external LLMs)	Owner review of 10 sample profiles 🧑	M


STAGE 10 — Hardening, governance, release (≈4 sessions)

ID	Task	DoD / acceptance	Size
S10.1	Observability: run summary page (site/status.html) reading workflow_runs.jsonl-style logs: last success, rows added, API spend, classifier drift stats (label rates over time)	Drift alarm if label rates or counts shift beyond a threshold	M
S10.2	Data governance: privacy review (F4), license audit (docs/REUSE.md), takedown/correction process page, data dictionary, citation file (CITATION.cff)	Checklist signed off by the owner 🧑	M
S10.3	Reproducibility package: make all from scratch on fixtures; documented full rebuild; archived release (versioned snapshot of processed data and gold set)	Tagged release; archived outside GitHub if the owner wants a DOI 🧑	M
S10.4	Security & robustness: pin dependencies, dependabot, failure-notification channel, secret rotation notes	CI passes; docs updated	S


STAGE 11 — Fallback and extras (as needed)

ID	Task	Notes
S11.1	stlite fallback app reading the same JSON/Parquet; port facets and tables from the Trendspotter layout where license allows (MIT [V])	Must run as static files; test Pyodide package compatibility early (e.g., plotly/altair version issues documented for stlite)
S11.2	Evidence-map views: matrix × discipline heatmap of works (EviAtlas-style)	Optional
S11.3	Optional local-model reviewer assist for the review queue (open-weight model run locally, never in CI)	Only if label throughput becomes a bottleneck
S11.4	RSS/email digest of new CA-plastic-centric papers and new awards	Optional, via a scheduled workflow
S11.5	Cross-listing with Plastiverse and ToMEx-style resources	Owner-led


PART F — QUALITY, EVALUATION, ETHICS
F1. Targets (proposed; owner to confirm, G-9)

Metric	Proposed target
Gazetteer gate recall for ca_sampled ∈ {yes, partial} (on test set and leak sample)	≥ 0.95 (the gate must not lose true positives)
Final ca_sampled=yes precision	≥ 0.85
Final ca_sampled=yes recall	≥ 0.80
Plastic-relevance F1	≥ 0.90
Domain tag F1	per-tag; tags < 0.70 are flagged "experimental"
ca_led correctness (manual spot check of 200 works)	≥ 0.95
Inter-annotator agreement (κ)	≥ 0.7 on core labels before training

These are targets to be negotiated, not claims about achievable performance. If they cannot be met with non-LLM methods, document the gap and escalate options (more labels, SciBERT, local LLM) via DECISIONS.md.
F2. Error handling and uncertainty in the UI
Display confidence and evidence_level on each work. Show "abstract-only" badges. Make the limitations page prominent. Provide counts with ranges where classifier error materially changes them, e.g., "N works (estimated precision p)" [INF].
F3. Evaluation hygiene
Test set is frozen after S4.2; never used for threshold tuning or error analysis during development (use dev). Split by time or by author-group where feasible to limit leakage [INF]. Record model version and data snapshot for every published metric.
F4. Ethics and privacy for the expert directory
•	Public bibliographic metadata only; no scraping of personal emails, phone numbers or social accounts.
•	Researchers can request correction or removal; process documented on the About page; overrides applied within the next build.
•	Present author prominence as "number of tagged works," not performance rankings; avoid default citation-based rankings of individuals.
•	OpenAlex disambiguation errors (C8) mean some profiles will be wrong; provide an "Is this you? Report an issue" link.
•	Respect the owner's affiliation context: include the independence disclaimer (A3.4/G-12).
F5. Licensing and text-mining hygiene
Only process full text where the license or access terms permit [VERIFY per source]; store derived features and ≤ a few short quoted snippets per work [INF]; respect robots rules, rate limits and terms of service for scraped sources; attribute sources on each tab (dataset citation text where provided, e.g., MDMAP's suggested citation format given on its About page 55).

PART G — OPEN DECISIONS FOR THE OWNER
Defaults are used until answered. Record answers in .agent/DECISIONS.md.

ID	Question	Default
G-1	Should "plastic-related" include chemicals-in-plastics (additives, bisphenols, phthalates) and tire-chemical studies, or only particles/debris/litter?	Particles/debris/litter in core; chemicals-in-plastics as flagged tier 2
G-2	Include tire-wear particles and textile microfibers in core?	Yes
G-3	Include human-health studies in which no sampling occurred in California but a CA-based first author leads?	Yes via ca_led, labelled separately from ca_sampled
G-4	Offshore sampling beyond 3 nm (e.g., federal waters off CA)?	partial/not CA-sampled; visible via a filter
G-5	Time horizon for works and grants?	Works: all years with an emphasis on the last 10; grants: last 15 fiscal years
G-6	Where are State Water Board research contracts and grants published, and should they be included?	Investigate; defer if no machine-readable source
G-7	Repo name, hosting (separate repo vs. subfolder of scottcoffin.github.io), license?	Separate repo, linked/iframed from the personal site; MIT for code, CC-BY for derived data (pending upstream license check)
G-8	May we store OA full text locally (gitignored cache only) and which snippets may be published?	Cache only; publish short snippets
G-9	Acceptance thresholds in F1	As proposed
G-10	Who labels the gold set, how many hours, and who adjudicates?	Owner + 1–2 colleagues; adjudication by the owner
G-11	Should the Monitoring tab include literature-derived datasets (e.g., Moore drinking-water dataset) alongside primary monitoring data?	Yes, clearly flagged as secondary
G-12	Dashboard disclaimer wording and affiliation statement	Independent project; not an official OEHHA/State product
G-13	Should federal awards include out-of-state recipients that sample in California?	Yes, flagged; ca_led=false
G-14	Acceptable GitHub repo size/branch strategy for data (C6)?	Slim data in the main branch; large intermediates outside git


APPENDIX 1 — Starter TODO.md (agents paste this in S0.1)
# TODO (roadmap) — check off only when DoD + acceptance are met
## S0 Bootstrap
- [ ] S0.1 skeleton + memory files
- [ ] S0.2 CI scaffold (deploy, keepalive, watchdog)
## S1 Reference data
- [ ] S1.1 API smoke tests + cost logger
- [ ] S1.2 CA institution registry
- [ ] S1.3 CA polygons (land + 3 nm waters)
- [ ] S1.4 Gazetteer v0
- [ ] S1.5 Query config v1
## S2 Works ingestion
- [ ] S2.1 OpenAlex ingester v1
- [ ] S2.2 Normalization + QC
- [ ] S2.3 Provisional tags
- [ ] S2.4 Daily workflow
## S3 MVP front end
- [ ] S3.1 Build exporter
- [ ] S3.2 App shell
- [ ] S3.3 Experts tab
- [ ] S3.4 Institutions tab + map
- [ ] S3.5 About/Methods
- [ ] S3.6 Deploy + perf pass
## S4 Gold set (owner-heavy)
- [ ] S4.1 Labeling guide
- [ ] S4.2 Sampling plan + splits
- [ ] S4.3 Annotation tooling
- [ ] S4.4 Eval harness
## S5 Classifiers
- [ ] S5.1 .. S5.7
## S6 Full text
- [ ] S6.1 .. S6.4
## S7 Monitoring data
- [ ] S7.1 .. S7.6
## S8 Grants
- [ ] S8.1 .. S8.10
## S9 Linking
- [ ] S9.1 .. S9.3
## S10 Hardening
- [ ] S10.1 .. S10.4
## S11 Fallback/extras
- [ ] S11.1 .. S11.5
APPENDIX 2 — Starter MEMORY.md skeleton
# MEMORY (durable facts only; ≤200 lines)
## Project in one paragraph
## How to run (commands)
## Conventions (naming, IDs, paths, timezones: store UTC; CI cron is UTC)
## Key decisions (links to DECISIONS.md IDs)
## Verified API facts (one line each; details in docs/api_notes/)
## Data locations and sizes (what's committed vs. gitignored; how to inspect)
## Known pitfalls (top 10; details in LESSONS.md)
## Current model versions and metrics (one line per model)
APPENDIX 3 — Session prompt template for the human to paste
You are a build agent for the CA Plastics Research Atlas. Follow Part B of SPEC.md.
1) Read .agent/README.md, MEMORY.md, HANDOFF.md, TODO.md.
2) Do exactly ONE task: the first unchecked, dependency-satisfied task.
3) Verify [VERIFY] items by smoke test and write docs/api_notes/.
4) Keep context small: never cat large files; inspect with head/duckdb.
5) Update memory files, write HANDOFF.md, commit, and STOP.
6) If a tool/skill/MCP would materially speed this up, add it to .agent/TOOL_REQUESTS.md and tell me.
Task: <paste ID, e.g., S1.2>
References
1.	Three Nautical Mile State Maritime Limit - R7 - CDFW [ds3158] – Data.CA.gov. Retrieved 2026-11-05, from https://data.ca.gov/dataset/three-nautical-mile-state-maritime-limit-r7-cdfw-ds31581
2.	Three Nautical Mile State Maritime Limit - R7 - CDFW [ds3158] | California State Geoportal. Retrieved 2026-11-05, from https://gis-california.opendata.arcgis.com/datasets/CDFW::three-nautical-mile-state-maritime-limit-r7-cdfw-ds3158/about
3.	OpenAlex. About. Retrieved 2026-11-05, from https://help.openalex.org/data/institutions
4.	California Grants Portal- Grants Offered - CA Open Data Publishing. Retrieved 2026-11-05, from https://publish.data.ca.gov/dataset/california-grants-portal
5.	Scott Coffin, PhD — Environmental Toxicologist | Scott Coffin, PhD. Retrieved 2026-11-05, from https://scottcoff.in/
6.	GitHub - ScottCoffin/Job_Scraper: A 100%-free personalizable job-scraper / dashboard that requires zero installation/software/coding. Get a job! · GitHub. Retrieved 2026-11-05, from https://github.com/ScottCoffin/Job_Scraper
7.	OpenAlex. Authorships – Component | OpenAlex Help Center. Retrieved 2026-11-05, from https://help.openalex.org/data/authorships
8.	GitHub - SIDaniels/grant-classification-workflows · GitHub. Retrieved 2026-11-05, from https://github.com/SIDaniels/grant-classification-workflows
9.	Acheson E, Purves RS. Extracting and modeling geographic information from scientific articles. PLoS One. 2021;16(1):e0244918. doi:10.1371/journal.pone.0244918. PMID: 33406109.
10.	Hu X, Zhou Z, Li H, Hu Y, Gu F, Kersten J, Fan H, Klan F. Location Reference Recognition from Texts: A Survey and Comparison. ACM Comput. Surv. 2023;56(5):1-37. doi:10.1145/3625819.
11.	Yu T, Zhang X, Yin J. Utilizing Geoparsing for Mapping Natural Hazards in Europe. Water. 2025;17(24):3520. doi:10.3390/w17243520.
12.	SetFit · Hugging Face. Retrieved 2026-11-05, from https://huggingface.co/docs/setfit/index
13.	Fine-Tuning Large Language Models for Scientific Text Classification: A Comparative Study. Retrieved 2026-11-05, from https://arxiv.org/html/2412.00098v2
14.	GitHub - ahalterman/mordecai3: Full text geoparsing/toponym resolution with event geolocation. Retrieved 2026-11-05, from https://github.com/ahalterman/mordecai3
15.	OpenAlex. Subfields – Aboutness | OpenAlex Help Center. Retrieved 2026-11-05, from https://help.openalex.org/data/subfields
16.	GitHub - SIDaniels/Microplastics_chem_exp_explorer: Explore the latest microplastics research through NIH grants, recent papers, conference proceedings, and ARPA-H STOMP teaming profiles. · GitHub. Retrieved 2026-11-05, from https://github.com/SIDaniels/Microplastics_chem_exp_explorer
17.	DuckDB Wasm Client. Retrieved 2026-11-05, from https://duckdb.org/docs/current/clients/wasm/overview
18.	Troubleshoot. Retrieved 2026-11-05, from https://duckdb.org/docs/current/clients/wasm/troubleshoot.html
19.	GitHub - whitphx/stlite: Streamlit-Lite; In-browser Streamlit 🎈🚀 · GitHub. Retrieved 2026-11-05, from https://github.com/whitphx/stlite
20.	Manage your app - Streamlit Docs. Retrieved 2026-11-05, from https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app
21.	2024-12-12 Schema v2.1. Retrieved 2026-11-05, from https://ror.readme.io/changelog/2024-12-12-schema-v2-1
22.	Data structure. Retrieved 2026-11-05, from https://ror.readme.io/docs/ror-data-structure
23.	OpenAlex. Disambiguation – Authors | OpenAlex Help Center. Retrieved 2026-11-05, from https://help.openalex.org/hc/en-us/articles/24347048891543-Author-disambiguation
24.	OpenAlex. ORCID – Authors | OpenAlex Help Center. Retrieved 2026-11-05, from https://help.openalex.org/data/authors/orcid/
25.	OpenAlex. Buying & renewing – Pricing | OpenAlex Help Center. Retrieved 2026-11-05, from https://developers.openalex.org/access/buying-and-renewing
26.	OpenAlex. Group properties. Retrieved 2026-11-05, from https://help.openalex.org/api/grouping/
27.	OpenAlex. Examples. Retrieved 2026-11-05, from https://help.openalex.org/api/filtering/
28.	OpenAlex. Works Overview. Retrieved 2026-11-05, from https://developers.openalex.org/api-reference/works
29.	OpenAlex. Open access – Works | OpenAlex Help Center. Retrieved 2026-11-05, from https://help.openalex.org/data/works/open-access
30.	OpenAlex. Locations – Component | OpenAlex Help Center. Retrieved 2026-11-05, from https://help.openalex.org/data/locations
31.	OpenAlex. List works. Retrieved 2026-11-05, from https://developers.openalex.org/api-reference/works/list-works
32.	GitHub - J535D165/pyalex: A Python library for OpenAlex (openalex.org) · GitHub. Retrieved 2026-11-05, from https://github.com/J535D165/pyalex
33.	Europe PMC. Europe PMC. Retrieved 2026-11-05, from https://europepmc.org/RestfulWebService
34.	Europe PMC. Open access subset - Developers. Retrieved 2026-11-05, from https://europepmc.org/downloads/openaccess
35.	Europe PMC. Downloads - Developers. Retrieved 2026-11-05, from https://europepmc.org/downloads
36.	FullTextClient | pyEuropePMC. Retrieved 2026-11-05, from https://jonasheinickebio.github.io/pyEuropePMC/api/fulltext-client.html
37.	Introduction. Retrieved 2026-11-05, from https://grobid.readthedocs.io/en/latest/Introduction
38.	Consuming Citations and References. Retrieved 2026-11-05, from https://support.datacite.org/docs/consuming-citations-and-references
39.	Connecting Research Outputs. Retrieved 2026-11-05, from https://support.datacite.org/docs/connecting-research-outputs
40.	Nyadjro ES, Webster JAB, Boyer TP, Cebrian J, Collazo L, Kaltenberger G, Larsen K, Lau YH, Mickle P, Toft T, Wang Z. The NOAA NCEI marine microplastics database. Sci Data. 2023;10(1). doi:10.1038/s41597-023-02632-y.
41.	Marine Microplastics. Retrieved 2026-11-05, from https://marinemicroplastics-noaa.hub.arcgis.com/
42.	Marine Microplastics Map Tutorial | National Centers for Environmental Information (NCEI). Retrieved 2026-11-05, from https://www.ncei.noaa.gov/products/microplastics/help
43.	Microplastic and Microparticle Data from Surface Water: San Francisco Bay and Adjacent Sanctuaries - Dataset - California Open Data. Retrieved 2026-11-05, from https://data.ca.gov/dataset/microplastic-and-microparticle-data-from-surface-water-san-francisco-bay-and-adjacent-sanctuari
44.	Particle Data for Surface Water, Sediment, Effluent, Storm water, and Fish – Microplastic and Microparticle Data from Surface Water: San Francisco Bay and Adjacent Sanctuaries – Data.CA.gov. Retrieved 2026-11-05, from https://data.ca.gov/@california-ocean-protection-council/microplastic-and-microparticle-data-from-surface-water-san-francisco-bay-and-adjacent-sanctuari/r/6a2434e2-16b8-4072-813a-5522e922e23d
45.	Microplastic and Microparticle Data from Surface Water: San Francisco Bay and Adjacent Sanctuaries - CA Open Data Publishing. Retrieved 2026-11-05, from https://publish.data.ca.gov/dataset/microplastic-and-microparticle-data-from-surface-water-san-francisco-bay-and-adjacent-sanctuari
46.	Accessing RMP Data | San Francisco Estuary Institute. Retrieved 2026-11-05, from https://www.sfei.org/programs/rmp/data
47.	Find Data | CEDEN. Retrieved 2026-11-05, from https://ceden.waterboards.ca.gov/find-data.html
48.	Monitoring Council Minutes. Retrieved 2026-11-05, from https://mywaterquality.ca.gov/meetings/docs/2026/feb/cwqmc-meeting-draft-minutes-2026-02-26.pdf
49.	Microplastics Drinking Water | California State Water Resources Control Board. Retrieved 2026-11-05, from https://www.waterboards.ca.gov/drinking_water/certlic/drinkingwater/microplastics.html
50.	California Becomes First State to Adopt Statewide Testing Requirement for Microplastics in Drinking Water | King & Spalding. Retrieved 2026-11-05, from https://www.kslaw.com/insights/articles/california-becomes-first-state-to-adopt-statewide-testing-requirement-for-microplastics-in-drinking-water
51.	2025 Safe Drinking Water Plan. Retrieved 2026-11-05, from https://www.waterboards.ca.gov/drinking_water/safedrinkingwaterplan/docs/final-2025-sdwp.pdf
52.	U.S. Environmental Protection Agency (EPA). Microplastics Monitoring in Drinking Water. Retrieved 2026-11-05, from https://www.epa.gov/system/files/documents/2024-05/2023_11_29_epa-trash-free-water_coffin-for-erg-508.pdf
53.	Microplastics in Drinking Water - California Open Data. Retrieved 2026-11-05, from https://data.ca.gov/nb_NO/dataset/microplastics-in-drinking-water
54.	Marine Debris Monitoring and Assessment Project | Marine Debris Program. Retrieved 2026-11-05, from https://marinedebris.noaa.gov/our-work/monitoring/marine-debris-monitoring-and-assessment-project
55.	About MDMAP. Retrieved 2026-11-05, from https://mdmap.orr.noaa.gov/about
56.	Statewide Plastics Monitoring Strategy and Planning Framework | San Francisco Estuary Institute. Retrieved 2026-11-05, from https://www.sfei.org/documents/plastics-monitoring-strategy
57.	Statewide Microplastics Strategy Report to the Legislature. Retrieved 2026-11-05, from https://opc.ca.gov/wp-content/uploads/2026/06/Item-6b-Exhibit-A-OPC-Microplastics-Legislative-Report-508.pdf
58.	Plastics Monitoring Strategy and Framework. Retrieved 2026-11-05, from https://opc.ca.gov/wp-content/uploads/2026/06/Item-6c-Exhibit-A-Statewide-Plastics-Monitoring-Strategy-508.pdf
59.	Standardization of Operating Procedures for the Collection of Samples for Microplastics Analysis Part 2: Ambient Water. Retrieved 2026-11-05, from https://ftp.sccwrp.org/pub/download/DOCUMENTS/TechnicalReports/1410B_MicroplasticsSampleCollectionAmbientWater.pdf
60.	National Institutes of Health (NIH). NIH RePORTER API. Retrieved 2026-11-05, from https://api.reporter.nih.gov/
61.	National Institutes of Health (NIH). Data Elements for RePORTER Project API Contents. Retrieved 2026-11-05, from https://api.reporter.nih.gov/documents/Data%20Elements%20for%20RePORTER%20Project%20API_V2.pdf
62.	How to Use NSF Award Search: Step-by-Step — CASRAI. Retrieved 2026-11-05, from https://casrai.org/guides/nsf-award-search
63.	usaspending-api/usaspending_api/api_contracts/contracts/v2/search/spending_by_award.md at master · fedspendingtransparency/usaspending-api · GitHub. Retrieved 2026-11-05, from https://github.com/fedspendingtransparency/usaspending-api/blob/master/usaspending_api/api_contracts/contracts/v2/search/spending_by_award.md
64.	USAspending API. Retrieved 2026-11-05, from https://api.usaspending.gov/docs/endpoints
65.	The NOAA Marine Debris Program Awards 13 New Projects for Funding to Remove Marine Debris | Marine Debris Program. Retrieved 2026-11-05, from https://marinedebris.noaa.gov/funding-opportunities/noaa-marine-debris-program-awards-13-new-projects-funding-remove-marine-debris
66.	Field monitoring of microplastics loading and accumulation in low impact development-best management practices | California Sea Grant. Retrieved 2026-11-05, from https://caseagrant.ucsd.edu/our-work/research-projects/field-monitoring-microplastics-loading-and-accumulation-low-impact
67.	California Sea Grant and Ocean Protection Council administer $2 million in funding to improve microplastic understanding and management | California Sea Grant. Retrieved 2026-11-05, from https://caseagrant.ucsd.edu/news/california-sea-grant-and-ocean-protection-council-administer-2-million-funding-improve
68.	$6 Million Awarded for Research to Build a More Resilient Sacramento-San Joaquin Delta | California Sea Grant. Retrieved 2026-11-05, from https://caseagrant.ucsd.edu/news/6-million-awarded-research-build-more-resilient-sacramento-san-joaquin-delta
69.	State of California Coast and Ocean Annual Report. Retrieved 2026-11-05, from https://opc.ca.gov/wp-content/uploads/2024/02/Annual-California-Coast-and-Ocean-Report-2023-508.pdf
70.	Updates from the June 16, 2026 Council Meeting - California Ocean Protection Council. Retrieved 2026-11-05, from https://opc.ca.gov/2026/06/june-16-2026-council-meeting-summary
71.	121522 Delta Science Tracker. Retrieved 2026-11-05, from https://deltacouncil.ca.gov/pdf/council-meeting/meeting-materials/2022-12-15-item-8-delta-science-tracker.pdf
72.	Get Started with the Delta Science Tracker! | Science Tracker. Retrieved 2026-11-05, from https://sciencetracker.deltacouncil.ca.gov/get-started-delta-science-tracker
73.	2026-27 Grant Development Program | CSU. Retrieved 2026-11-05, from https://www.calstate.edu/impact-of-the-csu/research/coast/funding/Pages/GDP.aspx
74.	Funding | CSU. Retrieved 2026-11-05, from https://www.calstate.edu/impact-of-the-csu/research/coast/funding
75.	PROJECT NAME. Retrieved 2026-11-05, from http://scc.ca.gov/webmaster/ftp/pdf/sccbb/2026/0618/20260618Board06_COAST_SSINP_SR.pdf
76.	Data and Databases | California State Water Resources Control Board. Retrieved 2026-11-05, from https://waterboards.ca.gov/resources/data_databases
77.	Financial Assistance Funding - Grants and Loans | California State Water Resources Control Board. Retrieved 2026-11-05, from https://water.waterboards.ca.gov/water_issues/programs/grants_loans
78.	GitHub - Moore-Institute-4-Plastic-Pollution-Res/Microplastic_Data_Portal: The Microplastics Data Portal is an Open Source project to increase access to microplastics data. · GitHub. Retrieved 2026-11-05, from https://github.com/Moore-Institute-4-Plastic-Pollution-Res/Microplastic_Data_Portal
79.	Deploying | Observable Framework. Retrieved 2026-11-05, from https://observablehq.com/framework/deploying
80.	GitHub - grobidOrg/grobid: A machine learning software for extracting information from scholarly documents · GitHub. Retrieved 2026-11-05, from https://github.com/grobidOrg/grobid
81.	Haddaway NR, Feierman A, Grainger MJ, Gray CT, Tanriver-Ayder E, Dhaubanjar S, Westgate MJ. EviAtlas: a tool for visualising evidence synthesis databases. Environ Evid. 2019;8(1). doi:10.1186/s13750-019-0167-1.
82.	Events that trigger workflows. Retrieved 2026-11-05, from https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows
83.	Workflow syntax for GitHub Actions - GitHub Docs. Retrieved 2026-11-05, from https://docs.github.com/actions/reference/workflow-syntax-for-github-actions
