# Decisions

ADR-style decisions belong here with date, alternatives, rationale, and decision
owner. Unanswered items continue to use the defaults in `spec.md` Part G and
remain listed in `QUESTIONS.md`.

## ADR-012 - 2026-11-06 - Dependency-free S3.2 app shell

- **Decision:** Keep the MVP shell as one responsive `site/index.html` with
  native HTML controls and browser `fetch()` calls to the S3.1 JSON contract.
  Persist the Experts filter state in the URL hash, provide keyboard-operable
  tabs and CSV export, and reserve Monitoring and Funding as explicit stubs.
- **Alternatives:** Add a client framework/bundler; ship a Python runtime to
  the browser; omit filters until the Experts task.
- **Rationale:** The existing static Pages artifact can serve the fixture and
  future generated data without a build dependency, while native controls make
  the shell usable on keyboard and narrow screens. Detailed drawers,
  virtualization, maps, and domain-specific tabs remain scoped to S3.3-S3.5.
- **Decided by:** Build agent under the S3.2 contract; owner may revise the
  client design in later MVP tasks.

## ADR-011 - 2026-11-06 - Static site export contract

- **Decision:** Build compact, deterministic JSON from the normalized C3
  tables. Keep filter/list fields in `site/data/index.json`, split complete
  author records into `authors/<author_id>.json`, and publish separate
  institution, GeoJSON map, and year/type/tag aggregate payloads. Record raw
  and gzip byte sizes in `build_metadata.json`.
- **Alternatives:** Ship Parquet to the browser; put every abstract in the
  index; combine all details into one large JSON document; calculate
  aggregates in the client.
- **Rationale:** The split keeps the initial payload within the C5 budget and
  gives S3.2 stable filter/list data while preserving click-time detail.
  Deterministic ordering makes generated site data reviewable and reproducible.
- **Decided by:** Build agent under the S3.1 implementation contract; the
  owner may revise the client contract during S3.2.

## ADR-010 - 2026-11-06 - Guarded daily works refresh

- **Decision:** Schedule `.github/workflows/ingest_works.yml` daily and allow
  manual bounded dispatches. Treat OpenAlex HTTP 429 responses and optional
  per-run credit/USD ceilings as clean deferred outcomes; do not advance the
  high-water mark or generated outputs until a run completes. Commit generated
  outputs only when `ENABLE_DATA_COMMITS` is exactly `true`.
- **Alternatives:** Retry a daily-budget 429 until the job fails; advance state
  after partial pages; commit on every scheduled run; make the guard implicit.
- **Rationale:** OpenAlex's daily budget may be exhausted by the shared
  account/network, and inclusive publication-date rereads are idempotent. A
  visible clean defer preserves resumability while the exact repository guard
  prevents an unexpected write-capable workflow.
- **Decided by:** Build agent under the S2.4 implementation contract; owner may
  adjust the schedule or budget variables later.

## ADR-009 - 2026-11-06 - Deterministic provisional work labels

- **Decision:** Emit a separate sorted `work_labels` Parquet from normalized
  works joined to raw OpenAlex topic metadata. Apply exclusions before core,
  qualified, and tier-2 query rules; use taxonomy seeds and independent local
  matrix facets for provisional multi-label tags.
- **Alternatives:** Infer topic names from normalized IDs alone; drop works
  with missing raw/topic rows; promote the owner-supplied candidate as a
  validated classifier; copy Trendspotter source code.
- **Rationale:** Normalization intentionally retains topic IDs only, so raw
  records are required for display names. Retaining and counting missing joins
  makes coverage visible. The candidate is not validated, and the MIT
  Trendspotter approach was sufficient without copying code.
- **Decided by:** Build agent under the S2.3 implementation contract; owner
  promotion remains outside this task.

## ADR-008 - 2026-11-06 - Separate normalized institution output

- **Decision:** Normalize each S2.1 work object into C3-shaped works,
  authorships, authors, and institution tables under
  `data/processed/normalized/`. Use the reviewed California institution
  registry as the resolved-CA authority, keep unresolved raw institution rows
  with `ca_flag=false`, and derive `ca_led` from the first authorship plus
  `ca_any_author` from any resolved CA affiliation.
- **Alternatives:** Overwrite the owner-reviewed `institutions.parquet`; drop
  unresolved coauthor institutions; infer California membership from raw
  affiliation text alone.
- **Rationale:** The existing registry contains owner-reviewed classifications
  and must remain intact. Retaining unresolved links makes QC visible without
  turning an affiliation-text heuristic into a resolved CA flag. The separate
  output directory supports repeatable live normalization and fixture-based CI.
- **Decided by:** Build agent under the S2.2 implementation contract; owner
  review is not required for this deterministic schema/QC choice.

## ADR-007 - 2026-11-06 - Resumable OpenAlex works ingestion

- **Decision:** Implement S2.1 with year-window backfills and inclusive
  publication-date incrementals by default. Batch California institution IDs
  in groups of at most 100, follow cursor pagination, preserve each response
  as an ignored raw JSON snapshot, and atomically merge a deduplicated
  `data/interim/works_raw.parquet` before advancing the high-water mark. Keep
  `from_updated_date` available as an explicit mode for plans that support
  OpenAlex daily sync.
- **Alternatives:** Use offset paging; overwrite the raw table on each run;
  advance state before the output write; depend on updated-since for every
  account; store response bodies in Git.
- **Rationale:** OpenAlex accepted the bounded publication-date smoke request
  but returned HTTP 429 Plan upgrade required for `from_updated_date` on the
  available free access level. Inclusive date rereads are safe because stable
  OpenAlex IDs are merged idempotently, and atomic output/state writes make a
  failed run resumable.
- **Decided by:** Build agent under the S2.1 implementation contract; the
  owner may enable updated-since after confirming an eligible OpenAlex plan.

## ADR-006 - 2026-11-05 - Lightweight California GeoNames gazetteer

- **Decision:** Build a committed SQLite lookup database from the official
  GeoNames `US.zip` extract, retaining records where `country_code=US` and
  `admin1_code=CA`. Normalize exact names and alternates for lookup, layer a
  small reviewed alias CSV ahead of GeoNames results, and reject an explicit
  common-word ambiguity blacklist before either lookup.
- **Alternatives:** Run GeoNames web-service calls during classification; ship
  a worldwide or U.S.-wide gazetteer; use a full Elasticsearch/Mordecai stack;
  allow all exact place-name matches and solve ambiguity only downstream.
- **Rationale:** The static CC BY 4.0 source is reproducible and avoids an API
  credential/rate dependency in CI. The California subset is adequate for the
  first gate while curated water and regional aliases cover high-value local
  names. Exact blacklisting prevents obvious false-positive geographic gates;
  it remains intentionally narrow so later context-aware work can recover
  legitimate places.
- **Decided by:** Build agent from S1.4 source/license smoke verification and
  acceptance tests. GeoNames attribution remains required for derived data.

## ADR-005 - 2026-11-05 - California land and state-waters geometry

- **Decision:** Use the Natural Earth 1:10m Admin 1 `US-CA` feature as the
  land-only polygon and the official CDFW ds3158 `ds3158_poly` feature as the
  three-nautical-mile state-waters polygon. Store unsimplified geometry as
  GeoParquet for the pipeline and publish a topology-preserving, 0.002-degree
  simplified combined GeoJSON for the browser. Classify land before water at
  shared shoreline boundaries.
- **Alternatives:** Use a Census legal state boundary as the land polygon;
  derive water by buffering a coastline; use CDFW's line-only ArcGIS layer;
  keep the 22 MB full-resolution water geometry as text GeoJSON.
- **Rationale:** A legal state boundary included offshore jurisdiction and
  mislabeled the known one-mile point as land. Natural Earth is public domain
  and follows the coastline, while CDFW's CC BY 4.0 distribution includes the
  polygon it recommends for analysis. GeoParquet retains all 565,997 source
  coordinates compactly; the 306,997-byte browser asset is below the 1 MB cap.
- **Decided by:** Build agent from live source/license verification and S1.3
  known-point acceptance tests.

## ADR-004 - 2026-11-05 - California institution registry and review queue

- **Decision:** Seed institutions with exact OpenAlex
  `geo.region:California`, then explicitly verify and supplement the official
  10 UC campuses, 23 CSU campus records (22 integrated universities), and an
  11-institution major-private default set. Join every known ROR ID to the
  checksum-verified versioned ROR dump. Apply deterministic name/lineage/type
  rules, then `config/institution_overrides.csv`. Rank the owner review queue
  with 10-target OpenAlex `search=plastic` grouped counts; preserve owner review columns on
  reruns and do not treat this heuristic as the later corpus query.
- **Alternatives:** Trust the geographic seed without explicit coverage;
  exhaustively page the mutable ROR API; hand-type all 4,000+ rows; use total
  works rather than a plastics-specific review priority; overwrite the owner
  queue on every build.
- **Rationale:** Live retrieval required 23 supplements to satisfy system
  coverage. ROR v2.15 matched every known ID reproducibly, and the generated
  top-100 queue concentrated human review on the largest broad-query counts.
  The owner reviewed all 100 rows and supplied 22 type corrections. Institution
  types also indicate that `search=plastic` captures non-pollution meanings, so
  its counts remain review heuristics and must not become leaderboard values.
- **Decided by:** Build agent under S1.2; owner completed the top-100 review on
  2026-11-05. Query retuning remains assigned to S1.5.

## ADR-004 — 2026-11-06 — Versioned plastics query rendering and cache identity

- **Decision:** Render the S1.5 OpenAlex Boolean expression from
  `config/queries.yml` structured term lists, percent-encode the complete
  `title_and_abstract.search` filter, and accept a count cache only when both
  `query_version` and `rendered_query` match. Keep the owner-supplied query in
  candidate status until promotion review.
- **Alternatives:** Reuse a flat count cache; duplicate the terms in Python;
  promote the candidate automatically after the first count.
- **Rationale:** Query identity must travel with every estimate so a changed
  term, qualifier, exclusion, or field scope cannot silently reuse old counts.
  The bounded audit found 20/22 sampled matches relevant by title/abstract and
  4/4 literature-informed anchors included, but this is not the later gold-set
  review.
- **Decided by:** Build agent from the S1.5 acceptance run; owner promotion is
  still required.

## ADR-003 — 2026-11-05 — Institution API retrieval and usage accounting

- **Decision:** Use OpenAlex `geo.region:California` to seed California
  institutions and canonical `institutions.id` works filters in batches of at
  most 100 IDs. Use cursor paging for large works pulls. Use ROR v2 single-ID
  lookups to enrich known ROR IDs; use the ROR data dump, not exhaustive API
  paging, if a complete registry is needed. Record every API request and each
  run's aggregate credits and USD cost in the ignored JSONL usage log.
- **Alternatives:** Use the longer OpenAlex filter alias; send larger ID lists;
  use basic paging for large works pulls; build a complete ROR registry by
  paging the API; omit zero-cost ROR calls from usage accounting.
- **Rationale:** Live S1.1 tests found equivalent OpenAlex filter results, a
  hard 100-value OR cap, cursor metadata for works, and ROR's documented
  10,000-result retrieval ceiling and paging consistency warning. One shared
  log makes per-run request volume and paid/zero-cost usage auditable.
- **Decided by:** Build agent from verified API behavior under S1.1.

## ADR-002 — 2026-11-05 — Public GitHub Pages hosting and repository configuration

- **Decision:** Keep `ScottCoffin/CA_Plastics_Research_Dash` public and host it
  with GitHub Actions Pages. Permit guarded automation commits through
  `ENABLE_DATA_COMMITS=true`. Use MIT for source code and CC BY for derived data
  when upstream source licenses allow it.
- **Alternatives:** Keep the repository private and upgrade the GitHub plan;
  use alternate hosting; keep automation commits disabled.
- **Rationale:** Public visibility resolves the Pages plan restriction and is
  the owner's chosen G-7 hosting model. The existing guard keeps write-capable
  automation explicit. Per-source license review remains required before
  publishing derived data.
- **Decided by:** Owner answers in `QUESTIONS.md`, verified 2026-11-05.

## ADR-001 — 2026-11-05 — Bootstrap automation cadence and guards

- **Decision:** Deploy the static `site/` directory with official GitHub Pages
  actions after every main-branch push, by manual dispatch, and daily at 10:15
  UTC. Check for a missed run daily at 11:47 UTC and redispatch when the latest
  run is at least 25 hours old. Make the monthly keepalive commit only when
  `ENABLE_DATA_COMMITS` is exactly `true`.
- **Alternatives:** Deploy only on pushes; use an external watchdog; use a
  third-party keepalive action; allow unguarded automated commits.
- **Rationale:** This implements the Observable and Job_Scraper patterns named
  in the spec while using off-peak cron minutes, least-privilege permissions,
  and no new third-party workflow dependency.
- **Decided by:** Build agent under the S0.2 implementation contract; owner may
  revise the cadence later.

## ADR-013 -- 2026-11-06 -- Bounded client-side Experts rendering

- **Decision:** Keep the S3.3 Experts view dependency-free and virtualize the
  fixed-height list with a 174px row slot and four-row overscan. Load researcher
  detail JSON only after an explicit selection.
- **Alternatives:** Render every author card eagerly; add a client-side query
  dependency; or defer the drawer to a later stage.
- **Rationale:** The S3.1 export already provides deterministic per-author
  documents, so bounded DOM work and lazy fetches meet the MVP performance
  contract without adding bundle or license cost.
- **Decided by:** Build agent under the S3.3 task contract; revisit if the
  full-data performance ladder in S3.6 shows the static export exceeds budget.

## ADR-014 -- 2026-11-06 -- Dependency-free Institutions map and leaderboard

- **Decision:** Derive institution metrics from the shared slim work index,
  counting only `plastic_related === true` works. Render all qualifying
  institutions in a type-filterable leaderboard with all-time and latest-five-
  year counts, and draw a small SVG sparkline from the indexed work years.
  Render California institutions with coordinates in a client-side grid-
  clustered map; marker and leaderboard actions write the existing Experts
  institution hash filter.
- **Alternatives:** Publish a second institution metrics payload; rank by the
  broad S1.2 `search=plastic` heuristic; add a third-party tile/map runtime.
- **Rationale:** The S3.1 index already contains deterministic work and
  institution joins, so deriving metrics avoids duplicated state and preserves
  the warning that provisional labels describe volume, not quality. A
  dependency-free schematic avoids tile-provider terms and network failures in
  the static MVP while retaining a clear path to a richer map in S3.6.
- **Decided by:** Build agent under the S3.4 task contract.

## ADR-015 -- 2026-11-06 -- Continuous execution through atomic checkpoints

- **Decision:** Replace the mandatory fresh-session boundary with an atomic
  roadmap checkpoint. A continuous chat or Goal-mode run may complete multiple
  tasks sequentially, but every task retains its own acceptance, B4 updates,
  narrow commit, and push before the next task begins.
- **Alternatives:** Require a human to start a fresh chat after every task; or
  allow one long unstructured implementation spanning multiple roadmap items.
- **Rationale:** Durable checkpoint files and automatic context compaction make
  repeated human restarts unnecessary, while task-scoped verification and Git
  boundaries retain the protections that motivated the original protocol.
- **Decided by:** Owner authorization to establish continuous orchestration.

## ADR-016 -- 2026-11-06 -- Luna-first bounded task-agent delegation

- **Decision:** When a selected route or explicit instruction authorizes task
  agents, use Luna roles by default and send a file-scoped context capsule.
  Escalate to a higher-intelligence executor only for a documented exceptional
  difficulty or risk.
- **Alternatives:** Delegate every task at the main agent's intelligence level;
  or give each worker the repository's full documentation and history.
- **Rationale:** Bounded Luna assignments minimize repeated context ingestion
  and token use while retaining an explicit escalation path for rare work that
  needs stronger reasoning.
- **Decided by:** Owner instruction during continuous-goal setup.

## ADR-017 -- 2026-11-07 -- Defer browser database escalation until representative performance evidence

- **Decision:** Keep the static JSON implementation and do not add DuckDB-Wasm
  based on the four-work fixture. Keep S3.6 unchecked until C5 is measured on a
  representative export.
- **Alternatives:** Add DuckDB-Wasm based on the remote count estimate, or treat
  fixture timing as full-corpus evidence.
- **Rationale:** Fixture payload and response times pass C5, but the fixture is
  not representative and the 98,118 S1.5 count is not downloaded data. An
  authorized export requires owner query review first.
- **Decided by:** Build agent under the S3.6 partial evidence checkpoint.

## Add-on A1 open conflicts (L3 register)

### Add-on A1 C1

- **Conflict:** Base S3.2 single-file vs. Framework
- **Rule text (copied verbatim from docs/add_on_spec.md §6):** Decided by SPK-3. If Framework is chosen, S3.2 is implemented in it (guardrails in AT-5); the single-file app is the documented fallback
- **Status:** Open
- **Affected base tasks:** S3.2–S3.5

### Add-on A1 C2

- **Conflict:** R vs. Python runtimes
- **Rule text (copied verbatim from docs/add_on_spec.md §6):** R is confined to one monthly job (AT-7); interface is CSV/Parquet. Bibliometrix has 34 imports including igraph, shiny, plotly and tidytext 3, so cache packages (setup-r-dependencies caches the library 4). Drop R if gate G-R fails
- **Status:** Open
- **Affected base tasks:** S11.2

### Add-on A1 C3

- **Conflict:** Schema mismatch
- **Rule text (copied verbatim from docs/add_on_spec.md §6):** Bibliometrix expects WoS-style tags. Its README says convert2df can take OpenAlex JSON/XML objects via openalexR 5, but its vignette lists no OpenAlex source 6. Build an adapter from our Parquet; skip analyses needing parsed cited references
- **Status:** Open
- **Affected base tasks:** S11.2

### Add-on A1 C4

- **Conflict:** Two sets of counts
- **Rule text (copied verbatim from docs/add_on_spec.md §6):** Counts come only from DuckDB (AT-3). R may output structure (clusters, curves), never counts shown to users
- **Status:** Open
- **Affected base tasks:** S3.1, S11.2

### Add-on A1 C5

- **Conflict:** Licences vs. base G-7 (MIT)
- **Rule text (copied verbatim from docs/add_on_spec.md §6):** Bibliometrix is GPL-3 per CRAN 7 and DESCRIPTION 3 though its README says MIT 5. Treat as GPL-3: separate process, no code copied. Others are permissive: openalexR MIT 3, Mosaic BSD-3 3, VOSviewer Online MIT 8, Framework ISC 9, ASReview Apache-2.0 10
- **Status:** Open
- **Affected base tasks:** S3.2–S3.5, S11.2

### Add-on A1 C6

- **Conflict:** DESTINY code
- **Rule text (copied verbatim from docs/add_on_spec.md §6):** Excluded: its UI is AGPL-3.0, Keycloak-gated and API-backed 11; its updater is FastAPI, PostgreSQL and Azure Blob Storage 12. Ideas only (bit-masks, compact payloads, human-over-model precedence)
- **Status:** Open
- **Affected base tasks:** S3.6

### Add-on A1 C7

- **Conflict:** Two DuckDB-Wasm builds on a page
- **Rule text (copied verbatim from docs/add_on_spec.md §6):** Framework's SQL blocks use DuckDB-Wasm 1.29.0, aligned with DuckDB 1.1.1, not changeable for SQL blocks 13. One DuckDB stack per page; CI Parquet must be readable by it (SPK-2)
- **Status:** Open
- **Affected base tasks:** S3.2-S3.6

### Add-on A1 C8

- **Conflict:** ASReview vs. S4.2 test set
- **Rule text (copied verbatim from docs/add_on_spec.md §6):** Active-learning ranking biases a labelled set. Use ASReview (active-learning screening with a Simulate mode 14) for training-pool labelling only; the frozen test set is drawn separately at random, stratified, and never ranked
- **Status:** Open
- **Affected base tasks:** S4.2, S4.3

### Add-on A1 C9

- **Conflict:** Base C5 "Explore only if needed" vs. add-on Explore page
- **Rule text (copied verbatim from docs/add_on_spec.md §6):** Explore (AT-6) is optional and lazy-loaded; the main page never loads WASM
- **Status:** Open
- **Affected base tasks:** S3.6

### Add-on A1 C10

- **Conflict:** API budget
- **Rule text (copied verbatim from docs/add_on_spec.md §6):** Only ingestion calls OpenAlex. Institution rankings in steady state are computed from local tables, not group_by calls
- **Status:** Open
- **Affected base tasks:** S1.1, S1.2, S2.1–S2.4

### Add-on A1 C11

- **Conflict:** OpenAlex changes under you
- **Rule text (copied verbatim from docs/add_on_spec.md §6):** Archive own releases: each quarterly public snapshot "replaces the bucket contents in place" 15
- **Status:** Open
- **Affected base tasks:** S10.3

### Add-on A1 C12

- **Conflict:** Maps vs. facets
- **Rule text (copied verbatim from docs/add_on_spec.md §6):** A VOSviewer iframe cannot share state with facets; pre-render maps per tag × year slice
- **Status:** Open
- **Affected base tasks:** S3.6, S11.2

### Add-on A1 C13

- **Conflict:** Per-entity pages
- **Rule text (copied verbatim from docs/add_on_spec.md §6):** Framework parameterized routes create one file per parameter value 16. Don't generate per-researcher pages: Pages has a 10-minute deploy timeout 17 and Cloudflare Pages a 20,000-file limit 18. Use JSON shards + a detail drawer
- **Status:** Open
- **Affected base tasks:** S3.1, S3.2–S3.5

### Add-on A1 C14

- **Conflict:** Heavy work in the site build
- **Rule text (copied verbatim from docs/add_on_spec.md §6):** Framework loaders run at build time, only if the output is referenced and not cached 19. Pipelines run outside the build; loaders only read artifacts
- **Status:** Open
- **Affected base tasks:** S3.1, S3.2–S3.5

### Add-on A1 C15

- **Conflict:** Nondeterminism
- **Rule text (copied verbatim from docs/add_on_spec.md §6):** UMAP/BERTopic: fix random_state (BERTopic's example sets one 20), store coordinates per release, recompute quarterly
- **Status:** Open
- **Affected base tasks:** S10.3, S11.2

## ADR-A2-OWNER: Add-on A2 owner determinations (2026-11-09)

- **Context:** `docs/add_on_spec_2.md` (Add-on A2) records owner determinations
  dated 2026-11-09 and says they are logged in `docs/DECISIONS.md`. This repo's
  decision log is `.agent/DECISIONS.md`; this entry is that log.
- **Decision (copied from the A2 preamble, [OWNER] where marked):**
  - ToMEx DOI list comes from PSSDplusplus dataset `tomex2` (column `DOI`
    [OWNER]); scope is the aquatic-organisms database; ToMEx 3.0 is added later.
  - The Minderoo Plastic Health Map is not included anywhere (EAT-8).
  - Regional Water Board boundaries come from the hosted feature service (A2 §4),
    treated as openly licensed with a mandatory accuracy disclaimer [OWNER].
  - Plastic Pollution Coalition / Global Plastic Laws is link-only; no
    integration and no outreach [OWNER].
  - The Solutions-track policy panel (EM-17) and DTSC timeline (EM-18) are included.
  - The link-out launch set (A2 §8, LO-1..LO-12) is accepted.
  - Block D covers DTSC's narrowed categories plus the broader initial list; the
    ten added ledger rows (N1.9–N1.11, N2.8–N2.10, N4.5, N4.6, M4, M5) are included.
  - The August 2026 SFEI report (#1289) is the canonical Monitoring Strategy [OWNER].
- **Consequence:** A2 replaces base S11.2 with EM-8 and extends S4/S5 with new
  label fields. It reuses A1 AT-3, AT-4 and AT-10 without changing any A1 gate.
- **Decided by:** Owner (Scott Coffin), recorded at A2 integration.

## Add-on A2 open conflicts (register)

Resolution text is copied verbatim from `docs/add_on_spec_2.md` §2. Each entry is
an adopted rule that downstream EM tasks must implement; status stays Open until
the implementing task's acceptance passes.

| ID | Issue | Resolution (verbatim) | Implementing / affected tasks | Status |
|---|---|---|---|---|
| A2-C1 | discipline overlaps study_type = method_development | discipline = topic (multi-label); study_type = design (single). Report collinearity. | EM-1, EM-4; S5.5 | Open |
| A2-C2 | Base matrix ≠ framework compartments | Add compartment[], waterbody_type[]; map matrix in taxonomy.yml. | EM-1; S7.3 matrix field | Open |
| A2-C3 | Base size_class is on samples only | Add works-level size_class[] (§4). | EM-1, EM-4 | Open |
| A2-C4 | Base S7.5 gaps heatmap overlaps V-9, V-2 | Keep S7.5; share one heatmap component. | S7.5, EM-8, EM-9, EM-11 | Open |
| A2-C5 | Base S11.2 | Replaced by EM-8. | S11.2 → EM-8 | Open |
| A2-C6 | A1 C12: iframes cannot share facet state | Client-side bit-set facets (AT-4). | AT-4, EM-5 | Open |
| A2-C7 | Gold-set load (κ ≥ 0.7) | Extend existing gold works (EM-3); weak fields ship "experimental". | EM-3; S4.2, S4.3 | Open |
| A2-C8 | Source text reuse | Paraphrase, short quotes, links. The Monitoring Strategy states image permission only (one-time use in this publication only 4); no text licence was found. | EM-1, EM-11, EM-14 | Open |
| A2-C9 | Monitoring Strategy excludes drinking water | Block X extension rows. | EM-1, EM-11 | Open |
| A2-C10 | Regional layer has no licence text in its metadata | Owner-determined open use plus disclaimer (§4). | EM-2, EM-9, EM-14; REUSE.md | Open |
| A2-C11 | ToMEx loads in R (A1 allows R only if gated) | EM-15 is a one-off owner-run export; R is not added to CI. | EM-15; A1 C2/SPK-5 unaffected | Open |
| A2-C12 | source_category explodes with DTSC products | Coarse source_category plus rule-based product_type[] (§4). | EM-1, EM-4 | Open |
| A2-C13 | Several microplastic and nanoplastic definitions in play | Definitions crosswalk in METHODS (§4). | EM-14; docs/METHODS.md | Open |
| A2-C14 | DTSC sub-rows vs works tagged only at parent level | group_id column and parent product_type values (§6.3). | EM-1, EM-11 (EAT-11) | Open |
| A2-C15 | Many keyword flags with unknown precision | Each flag gets a spot-check in EM-4; rows relying on weak flags stay low rule confidence. | EM-4, EM-13 | Open |

## ADR-DEFAULTS-2026-11-09: Owner accepts all pending defaults

- **Decision:** The owner accepted the stated default for every open question
  with a pending answer: S1.5-A, S7.3-A, A1-D1..D7, A2-D1..D11 and A2-INT-1..3
  (`.agent/QUESTIONS.md`). G-6 keeps its existing owner pointer.
- **Consequences:** A1-D1 ("L0 + L1 now; L2 after spikes; L3 optional") makes
  SPK-1..SPK-4 eligible now; AT-4, AT-5, AT-6 and AT-11 follow their spike gates
  (G-HOST, G-PARQ, G-SHELL, G-FACET). L3 tasks (SPK-5, SPK-6, AT-7..AT-10) stay
  optional and gated. S1.5-A and S7.3-A defaults keep the query candidate inactive
  and SF Bay / 5 Gyres data unpublished. A2 levels E0-E3 are adopted (A2-INT-3).
- **Decided by:** Owner instruction, 2026-11-09.

## ADR-SPK-AUTH-2026-11-09: Owner authorizes the L2 spikes

- **Decision:** The owner authorized SPK-1..SPK-4 to add spike dependencies
  (DuckDB-Wasm, Mosaic, Observable Framework and Node tooling) and to run live
  hosting tests (Pages deploy of synthetic Parquet, Cloudflare R2), 2026-11-09.
- **Guardrails:** Spike dependencies stay isolated (a `spikes/` workspace or dev
  extras), not runtime dependencies of `site/` until the gate decision lands.
  Synthetic test files above 25 MB are generated at deploy time, never committed.
  R2 needs owner-side Cloudflare account steps (bucket, custom domain, CORS);
  the agent never handles Cloudflare credentials.
- **Also recorded:** EM-1-A approved (`guide_v2`); A2-D11 confirmed (CDFW ds3158).

## ADR-AT1-V31-2026-11-11: Promote query v3.1; CA-only experts; reviewed grant relevance
- Context: owner labels showed v3's additions were 53.1% precise (overall ~77.5%, below v2's
  82.8%). Clause attribution located the noise (trash, bioplastic, LCA, litter, single-use).
- Decision: promote the tightened `plastic-v3.1` (est. ~83.8%, no v2-relevant loss) by the
  rule "precision >= v2 and no relevant v2-labelled work lost". The Experts list holds
  authors with at least one CA-affiliated authorship (spec A3.1). Grants count as plastic-related
  on a short-title match or a reviewed label; abstract-only mentions default to false.
- Consequences: a full backfill replaces v2 rows; grant labels from the Haiku review await
  an owner spot-check (QUESTIONS GRANT-REL).


## ADR-S21B-2026-11-11: OpenAlex daily budget, owner labels in the pipeline, assisted work relevance
- **Context:** The v3.1 backfill as written would have fetched only 1950 (end year defaulted to the start year) and replaced the table with it, and its per-year windows multiplied 10-credit boolean searches (~3,800 calls, ~3.8 USD). Owner audit labels never reached the export, so 62 owner-rejected works were live. The owner set a standing rule: OpenAlex may run up to the free USD 1.00/day limit.
- **Decision:** (1) `config/budget.yml` abort threshold 0.95 USD / 9,500 credits (daily ceiling stays 1.00 / 10,000). (2) Backfills page one publication-date window per institution batch, 1950..next year. (3) `scripts/build_audit_overrides.py` generates `curation/overrides_works.csv` from the AT-1 audit CSVs: `not_relevant` becomes the new `exclude` override (work removed like a suppression, counted as `works_excluded_listed`), `relevant` becomes `plastic_related=true`. (4) `curation/work_relevance.csv` holds Claude Haiku relevance calls for works the owner has not labelled; the export applies them to `plastic_related` before owner overrides. They never exclude a work. (5) The export recounts `ca_works_count` from curated authorships and redacts email addresses inside abstracts.
- **Consequence:** CA experts drop from 2,121 to 1,982 (authors whose only works were owner-rejected). A full v3.1 backfill costs about 0.05 USD, so no resumable backfill is needed. Abstract publication remains an open question (ABSTRACT-PUB).

## ADR-GRANT-STRONG-2026-11-11: Strong abstract terms decide grant relevance
- **Context:** Reviewing the Haiku grant calls, the owner found most abstract-only grants are relevant: mentions of "plastic pollution", "microplastics"/"micro-plastics" and usually "anthropogenic debris" indicate a plastic-related grant.
- **Decision:** `grant_plastic_decision` precedence: owner decision (`owner_review` confirmed/changed) > core-term title match > strong abstract term (`STRONG_ABSTRACT_RE`; nanoplastics, plastic debris, marine debris, plastic particles and tire wear particles added by the owner the same day) > Haiku call > false. The review app's default view lists only pending grants the rules do not settle.
- **Evidence:** 41/41 strong-term grants already reviewed by the owner were relevant; the rule flips 93 grants to plastic-related and leaves 40 pending grants for the owner.

## ADR-GRANT-SECTORS-2026-11-11: Recipient sectors and funder agencies for the funding visualizations
- **Context:** The owner asked for a Sankey of funders, recipient institutions grouped by sector (academia, nonprofit, JPA, government, industry) and topics. `institution_type` was unknown for 484/524 grants and funder names were inconsistent (NSF vs National Science Foundation; NOAA under Department of Commerce).
- **Decision:** `config/grant_sectors.yml` + `atlas.build.grant_sectors` add `sector`, `sector_detail` and `funder_agency` at export (names > ordered regex rules > registry type). Current split: academia 405, nonprofit 52, industry 35, government 20, individual 6, JPA 4, unknown 2. Visualizations default to award counts because amounts are not comparable across sources.

## ADR-OA-FALLBACK-2026-11-11: Fallback OpenAlex key; whole-record plastics citations
- **Fallback key (owner rule):** when the primary free account returns a non-burst HTTP 429 (daily allowance exhausted), `_request_json` switches to `OPENALEX_API_KEY_ALT` (local `.env` alias `OPEN_ALEX_API_KEY_ALT`) for the rest of the process; the budget guard scales its per-account ceilings by the number of keys. CI needs the repository secret `OPENALEX_API_KEY_ALT` (owner action).
- **Plastics citations:** the Experts share compared corpus-only plastics citations with career citations and understated specialists (Rochman 42% vs 98.7% whole-record). `scripts/fetch_author_metrics.py` now counts each author's plastics works and citations across their whole OpenAlex record with the active query (incremental, 25 authors per batch; full pass 952 credits). Export field `plastic_basis` says which basis applies.

## ADR-GATES-2026-11-11: Owner clears the A1 L3 gates, defers AT-5/AT-6, sets gold-set labelling
- **AT-5/AT-6 (Observable Framework shell, Explore page):** deferred; the static site is kept. AT-4 targets the existing pages.
- **L3 tasks approved:** SPK-5/AT-7 (bibliometrix, R outside CI), SPK-6/AT-8 (maps), AT-9 (embedding map and taxonomy QA, after S5), AT-10 (release pipeline).
- **Gold set (G-10 revised):** the owner labels the S4.2 sample; a Claude reviewer independently double-labels 20%. Reported kappa is owner-vs-model agreement, disclosed in METHODS; the owner adjudicates disagreements.
- **Abstracts:** kept in public per-author JSON (emails redacted); AT-4 public Parquet stays abstract-free as A1 specifies.

## ADR-FRAMEWORK-REVISIT-2026-11-11: Observable Framework migration deferred, with automatic revisit triggers
- **Context:** SPK-3 (2026-11-10) chose Observable Framework 1.13.4 as G-SHELL when the site was a fixture shell. By 2026-11-11 the hand-built static site covers Experts, Institutions (interactive map), Monitoring, the institution evidence map (`site/sem.html`) and the grants Sankey suite (`site/grants.html`), within C5 budgets (initial payload ~465 KB gzip, expert filtering ~5.5 ms). The owner deferred AT-5/AT-6.
- **What Framework would buy:** (1) build-time data loaders, so Python/R/SQL (AT-3 DuckDB, AT-7 bibliometrix) feed pages directly; (2) Observable Plot + reactive Inputs instead of hand-written SVG charts and wiring; (3) one small Markdown page per view instead of one large `index.html`, which matters for the many Add-on A2 views (EM-5..EM-12); (4) DuckDB-Wasm/Parquet integration for client-side SQL when JSON payloads get too large (AT-4 facets); (5) per-page code splitting, theming/dark mode and search.
- **Costs:** a Node build step in CI; rewriting five working, tested pages; regression risk; no current performance need.
- **Revisit triggers (checked on every CI run by `scripts/check_framework_triggers.py`, which emits a GitHub `::warning::`):** T1 exported works > 10,000; T2 initial payload > 1.5 MB gzip (half the C5 budget); T3 any of EM-5..EM-12 started or done (A2 visual build-out); T4 `site/index.html` > 300 KB or more than 6 hand-built pages.
- **Added 2026-11-11:** SEO (S3.8) needs pre-rendered static pages per expert and institution; when S3.8 starts, weigh building those routes in Framework, since static page generation is one of its strengths.
- **When a trigger fires:** reopen AT-5/AT-6 with the owner. Preferred path: build the new A2 pages in Framework alongside the existing pages (incremental), not a big-bang rewrite.

## ADR-CA-INFERENCE-2026-11-11: California inference beyond linked institutions; CA-only public works
- **Context:** Owner forensics on Aleksandra Karapetrova: a 2022 Zenodo poster had no OpenAlex affiliation, and 35/40 sampled Europe PMC CA papers missing from the corpus had a California raw affiliation but no linked institution.
- **Decision:** authorships carry `ca_basis` = registry | raw_affiliation (strict matcher; excludes Baja California and California, PA) | author_carry_forward (no institution and empty/placeholder affiliation, author has a CA authorship within 2 years). Ingest adds a `raw_affiliation_strings.search:California` scope and author-anchored units (25 CA experts per call, kept only when the anchored authorship is unaffiliated or CA). The public export keeps only works with a CA authorship on any basis; other fetched works stay in the corpus.
- **Result:** corpus 1,486 -> 1,896 works; site 1,774 works, 2,422 experts; authorships by basis: registry 3,648, raw_affiliation 917, carry_forward 230. Karapetrova's alpine poster is in.
- **Risk:** carry-forward can misattribute when OpenAlex merges same-name authors; ORCID dated employments (TODO S2.5c) are the planned confirmation.

## ADR-AL-RELEVANCE-2026-11-11: Active learning for work relevance (owner request)
- **Context:** Reviewing >1,000 Haiku relevance calls one by one is too much for the owner, who asked for an embedding/BERT model that recalibrates with their annotations.
- **Decision:** Owner authorizes local sentence-transformers (already installed) and one small open embedding model download, as an optional `ml` extra that CI never installs. Calibrated logistic regression on embeddings is trained on human labels only (AT-1 owner labels + owner app decisions); Haiku calls are only used to find disagreements. Queue = uncertain + disagreements + random audit of confident labels; auto-labels are accepted only when the audit accuracy's Wilson lower bound reaches the target (default 95%, ≥30 audits). Owner confirmed the 95% target (2026-11-11) and asked for a prominent accuracy indicator (audit accuracy + CI vs target, audits needed, CV fit, errors remaining, trend per retrain) to decide when to stop tagging. The S4.2 test split is excluded from training and the queue. Precedence at export: owner > AT-1 overrides > accepted model labels > Haiku. This is the S5.1 relevance classifier's first iteration (SetFit remains the spec's later option).

## ADR-STATE-AGENCIES-2026-11-11: California state agencies differentiated; owner top-100 review restored
- **Context:** Owner: state institutions did not separate CDPH, OEHHA, State Water Board, OPC. 40 CA government institutions were missing from the registry and government defaulted to local-agency; OEHHA/SWRCB/RWQCBs/State Lands have no OpenAlex record (filed under CalEPA or "State of California").
- **Decision:** registry supplement (`scripts/build_institutions.py --supplement-government --reuse-ror-dump`), state/local/federal/county-health name rules, and `config/ca_state_agencies.yml` resolving sub-agencies from raw affiliations into `CAAG-*` institutions (umbrella replaced, no double count). OEHHA 37 and SWRCB 35 works now appear; "State of California" falls 41 -> 5.
- **Recovered loss:** the owner's 2026-11-05 top-100 review (100/100, commit 0cec765) had been overwritten by a blank regenerated file on 2026-11-06 (44166c7). Restored; `write_outputs` now never rewrites a review file that holds owner reviews. AT-2 regenerated from it: owner_reviewed 56, new entrants 47 (SCCWRP and SFEI among them, as A1 expected).
- **Owner confirmed 2026-11-11:** overrides I4210161945 "Department of Health Services" and I4405283712 (CDPH injury-control branch) typed state-agency.

## ADR-OUTREACH-2026-11-11: Expert outreach by owner-sent email
- **Decision (owner):** collect expert emails only from published corresponding-author data and public ORCID records; store them in `data/private/` (gitignored) only; the owner sends mail-merge invitations from their own account; experts submit bio/photo/licence/consent through an owner-owned Google/Microsoft Form; only owner-approved public fields are imported. No automated sending, no robots-disallowed crawling, no guessed addresses; opt-outs honoured permanently. Spec `docs/OUTREACH.md`, TODO S9.6.

## ADR-DUCKDB-2-2026-11-11: DuckDB 2.0.0 as the pipeline engine and G-PARQ writer pin
- **Context:** AT-3 makes DuckDB a pipeline dependency (A1 C4: counts come only from DuckDB). The G-PARQ pin, DuckDB 1.1.1, has no wheel for the project interpreter (Python 3.14). SPK-2 found that DuckDB 2.0.0 + zstd Parquet passes 15/15 checks in both browser engines (wasm 1.29.0 / engine 1.1.1 and wasm 1.32.0 / engine 1.4.3) and is about 10% smaller.
- **Decision (owner, 2026-11-11):** `duckdb==2.0.0` goes in `pyproject.toml` dependencies and `requirements/lock.txt`. The G-PARQ writer pin moves to 2.0.0 with `COPY ... (FORMAT PARQUET, COMPRESSION zstd)` and default row groups.
- **Alternatives:** keep 1.1.1 in a separate Python 3.12 environment (second interpreter in CI, more fragile); pyarrow-only counts (contradicts C4).
- **Consequence:** AT-4 public Parquet uses the 2.0.0 writer. Re-run the SPK-2 browser checks if the wasm pin changes.

## ADR-RELEVANCE-RULES-2026-11-11: Plastisphere topic, always-relevant micro-nano plastics, shared abstracts ignored
- **Plastisphere (owner, 2026-11-11):** its own topic = life living on plastic. Owner decided microplastic effects on soil/other microbial communities and works only about microbes or insects biodegrading plastic do not count. Taxonomy entries may now carry `title_seed_concepts` (title-only matches; `biofilm`, `biofouled`, `rafting`) and `exclude_concepts` (veto). 29 works, 7 grants. Hatched ecotox pink; `topics.js` hatch patterns are per topic (`#atlas-hatch-<tag>`).
- **Micro-nano plastics (owner, 2026-11-11):** always plastic-related, any spelling (`always_relevant_patterns` in `config/queries.yml`, not part of the rendered OpenAlex query). Export precedence: owner review-app decision > curation/AT-1 overrides > always-relevant > accepted model > Haiku > keyword rule. Grant `STRONG_ABSTRACT_RE` and review-app highlighting include it.
- **Mis-attached abstracts (lead, revised after owner report):** OpenAlex attached one teaser-style micro-nano plastics abstract to 10 unrelated PNAS papers (no real abstract exists; Europe PMC has none). `atlas.ingest.abstract_qc.misattached_abstract_ids` flags an abstract shared by >= 3 works with >= 3 distinct DOI roots (version, chapter and `/supp-N` suffixes stripped) and >= 3 distinct title families; normalization blanks it (QC row), and labels, export and the works review app apply the same check. A plain 'shared by >= 3' rule wrongly caught PeerJ supplement records and book chapters. Effect: 1 false positive removed (W3124276284). Export now also prunes author files not written in the run (171 stale files removed). Upstream fix: owner reports the records to OpenAlex (HUMAN_TASKS).

## ADR-ESCHOLARSHIP-2026-11-12: eScholarship UC evidence as a California basis
- **Decision (owner, 2026-11-11):** leverage eScholarship's UC affiliation evidence. eScholarship's public GraphQL API (`item(id)`, no keyword search; the HTML/OAI site is behind a bot screen) gives each item's units, source and type. `scripts/fetch_escholarship_items.py` writes `data/processed/escholarship_items.parquet` with `ca_evidence`: `etd` (UC thesis), `uc_oa_policy` (UC open-access-policy deposit), `uc_unit` (campus/department series) or `journal_only` (UC-hosted journal: authors anywhere, no evidence), and campus ids via unit parents. Never requests emails.
- **Use:** normalization basis `escholarship`: every work with etd/uc_oa_policy/uc_unit evidence is California research (work level); author level for the sole author of a UC thesis, or a co-author already California-based elsewhere whose name matches an eScholarship author. `scripts/ingest_escholarship_works.py` adds query-matching eScholarship works with such evidence (19 on 2026-11-12). Candidates come from OpenAlex (source S4306400115) via `scripts/audit_escholarship_openalex.py` (20 credits).
- **Limits:** 2 s spacing drew a 403 block after ~120 requests on 2026-11-12; the fetcher now spaces 5 s, stops on 403/429 and resumes from cache (66 of 214 items fetched; 148 pending).

## ADR-GOLD-NEGATIVES-2026-11-11: Negative gold works need no further labels; open design labels
- **Decision (owner, 2026-11-11):** a gold work marked `plastic_related=false` needs no other input. The review app hides CA sampling, design and domain tags for it and saves them blank. `atlas.nlp.annotation` accepts blank `ca_sampled`/`study_type` on negative rows (still validated if given) and still requires both on positive rows.
- **Scoring:** `atlas.nlp.eval` scores `ca_sampled` and `study_type` only on gold rows with `plastic_related=true` (`POSITIVE_ONLY`); predictions on negative gold works are not checked or scored for those fields. The derived CA-plastic flag already requires `plastic_related=true`, so the G-9 `ca_sampled=yes` targets are now measured on plastic-relevant works.
- **New design labels (owner):** the app offers "+ Create a new design label"; a typed label is saved in snake_case and offered for later works (read back from the sheet). `study_type` was already open vocabulary in the importer and evaluator. Domain tags stay a closed list (`DOMAIN_TAGS`).
- **Display:** the app shows authors, journal, year and a DOI link (OpenAlex link when there is no DOI); `load_works` reads them from `works.parquet`, `authorships.parquet` and the raw OpenAlex fallback.

## ADR-GOLD-EVAL-SET-2026-11-11: Owner gold labelling limited to the 150-work evaluation set
- **Context:** the S4.2 sample is 580 works (dev 75, test 75 random + 80 leak-check, train 350). The owner was re-judging works already decided in the AT-1 audit (46 of the 150 dev/test pool works) and asked how many labels a Haiku test needs.
- **Decision (owner, 2026-11-11):** the owner labels only the evaluation set (split dev/test, role pool; 150). Haiku was not tuned on dev, so all 150 are held out for Haiku (95% CI half-width about 0.05 at p near 0.9, about 0.07 at 75); trained models report the final number on the 75 test works only (F3). Train works get no owner gold labels (S5.0 active learning supplies training labels). The 80 leak-check works are labelled for relevance and CA sampling when S5.7 runs.
- **Prior decisions:** AT-1 audit calls (`overrides_works.csv`: `plastic_related=true`, or `exclude=true` with reason `not_relevant`) are pre-selected in the app, never auto-saved: the one overlap labelled so far reversed an audit `not_relevant`. Works-review-app decisions (`work_relevance.csv` confirmed/changed) were made with Haiku's call visible, so they are not pre-selected and are relabelled blind.
- **Consequence:** rare design classes and domain tags will have small support; they are reported with CIs and stay experimental under the per-tag rule.

## ADR-EXPERT-METRICS-2026-11-12: Expert page, primary affiliation, citation histogram, m-quotient, rising score
- **Owner request (2026-11-12, after H7):** full-page expert views; primary affiliation(s) instead of co-authors' institutions; citations-per-year histogram with plastics citations coloured separately; sortable/filterable publications with clickable topic tags; Experts default sort by plastics citations; a way to find up-and-coming researchers; the m-quotient.
- **Data:** `scripts/fetch_author_metrics.py` also stores OpenAlex `counts_by_year`, `last_known_institutions`, `affiliations` (the author's own) from the existing `/authors` calls; plastics citations received per year (sum of the whole-record plastics works' `counts_by_year`); works per publication year by `group_by=publication_year` (1 credit per author, refreshed every 180 days).
- **Definitions** (`atlas.build.expert_metrics`): histogram = last 10 years (works' `counts_by_year` covers only ten years, so the plastics series is complete only there). m-quotient = h-index / max(1, build year − first publication year), first year = earliest year with ≥ 2 works in it and the next 5 years (skips isolated misattributed early works; single-work authors use their one year). Rising score = least-squares slope over the last 5 complete years of the expert's share (%) of all exported experts' plastics citations per year (normalizing by the yearly field total removes field growth); scored only with ≥ 10 plastics citations in the window; `rising_pct` = percentile among scored experts. Early career = first publication ≤ 10 years before the build year. "Find up-and-coming researchers" = early career + sort by rising score. Primary affiliation = OpenAlex last-known institutions, else the institution(s) the author used most in their latest Atlas year.
- **UI:** `site/expert.html#author=<id>` (full page; helpers in `site/assets/expert_page.js`, shared with the drawer histogram). Drawer affiliation history now lists only the author's own affiliations. Open question RISING-METRIC records the default.

## ADR-UNSURE-SEM-2026-11-12: Owner-unsure grants are not plastic-related
- Owner answer UNSURE-SEM: "Unsure" in the grant review app sets `plastic_related=false` (was: Haiku's value). No rows were unsure when applied.

## ADR-AT11-WINDOW-2026-11-12: Daily works pull capped at yesterday UTC
- Owner answer AT11-WINDOW: `run_daily_works.py` passes `publication_date_cap` = yesterday UTC; `ingest_live` adds `to_publication_date` to backfill and incremental windows. `--no-date-cap` overrides.

## ADR-CA-CARRY-ORCID-2026-11-12: ORCID contradiction drops a carry-forward
- Owner answer CA-CARRY-ORCID: normalization skips an `author_carry_forward` authorship when the author's ORCID record (committed `data/processed/orcid_profiles.parquet`) has dated employments and none in California covers the work year (±1, `atlas.ingest.orcid.classify_carry_forward`). QC reports the dropped count. Missing file = previous behaviour.

## ADR-EM5-FRAMEWORK-2026-11-12: Observable Framework before the evidence map
- Owner answer EM5-FRAMEWORK: migrate to Observable Framework (AT-5 shell, static routes; also serves S3.8 SEO) before EM-5. Supersedes the "incremental hand-built" preference in ADR-FRAMEWORK-REVISIT-2026-11-11. AT-5 is now eligible; installing `@observablehq/framework@1.13.4` (G-SHELL pin) needs the owner to approve the npm install (HUMAN_TASKS H14). New pages built meanwhile (`site/expert.html`) keep plain JS helpers in `site/assets/` so they port as Framework components.

## ADR-OUTREACH-EMAILS-2026-11-12: Emails allowed only in data/private/
- Owner answer OUTREACH-EMAILS: expert emails may be stored only in gitignored `data/private/`, only for owner-sent outreach (S9.6). Committed tables and public payloads stay email-free (normalization redaction unchanged).

## ADR-AT5-SHELL-2026-11-12: Framework app beside the classic site, lift-and-shift ports
- **Context:** owner chose the Framework migration (ADR-EM5-FRAMEWORK-2026-11-12) and asked to avoid regressions.
- **Decision:** `framework/` builds to `dist/`; the deploy copies it to `site/app/` (best-effort step, so a failed Framework build never blocks the classic deploy). The classic `site/` stays the live root until the owner approves the switch after a parity review (H16). Tabs are ported lift-and-shift (same markup, scoped CSS, same logic as ES modules, DOM-free helpers tested in Node), not rewritten in Plot/Inputs; Framework idioms are for new pages (EM-5+). Pages read the classic payloads at runtime from `../data/` (one copy of the data; every page is top-level in `src/`); shared helpers are copied from `site/assets/` at build. No external fonts/CDNs (`globalStylesheets: []`). `npm audit` findings are build-time only; keep the 1.13.4 pin.
- **Switch plan (after H16):** build Framework at the root, move classic-only pages (`grants.html`, `sem.html`, `expert.html`, `status.html`, `feed.xml`, `data/`, `assets/`) alongside, and make `index.html#<tab>?...` redirect to the matching page hash.

## ADR-EM5-SHELL-2026-11-12: Evidence Map shell in Framework; link-out strip rules in the registry
- EM-5 is the Framework page `/app/evidence`, not a classic tab. Filters are the AT-4 bit-set facets (counts = popcounts of build-time bit-sets; EAT-5), hash `#facet=a,b&year_from&year_to&q`. One shared works drawer (`openWorksDrawer`) for every later view. The related-resources strip reads `site/data/linkouts.json`, exported from `config/linkouts.yml`; display rules are `trigger_rules` strings `topic=<tag>` and `default` (other strings are ignored), defaults pending owner question EM5-STRIP. Link-only: names, stewards and descriptions as stated; nothing ingested (EAT-9).

## ADR-UX-SPEC-2026-11-12: Owner UX remediation spec integrated as UX-0..UX-25
- Owner spec `docs/EM_spec.md` (UX/UI remediation from a text walkthrough of the live site) becomes TODO section "UX". A browser audit (Playwright + axe-core 4.10.3 + Lighthouse 12.8.2, 2026-11-12) was added as its Section 1A: it confirmed the broken "Classic site" link and the internal vocabulary, refuted the broken expert-profile links and the stuck loading text, and added UX-21..UX-25 (template lang/viewport, contrast, headings, Monitoring CLS, mobile).
- The spec's branch-per-PR rule and `.agent/handoff.md` append are replaced by this repo's checkpoint protocol (commit on main as `UX-<n>: ...`, HANDOFF overwritten). Spec decisions UXD-1..8 plus UXD-9 (CI audit tooling) are QUESTIONS rows with defaults in use.
- Framework 1.13.4 template limits (no `<html lang>`, `maximum-scale=1`, header links outside the app root rewritten to `./`) are fixed by `framework/scripts/postbuild.mjs`, run by npm's postbuild hook; revisit when upgrading Framework.

## ADR-REL-1-2026-11-13: Public views use resolved plastic relevance; title-only rescue patterns; tier-2 survives low-confidence Haiku "false"
Context: a Neolithic pottery paper (OpenAlex matched a withheld abstract on "microfibers") showed on the Evidence map although the rule and Haiku labels said not plastic-related; the map ignored `plastic_related`. Decision: every Evidence map view uses only `plastic_related === true`; `title_relevant_patterns` (title-only, 100% precision on export titles) sit at the always-relevant precedence; `relevance_policy.tier2_survives_low_confidence_false` keeps rule chemicals-in-plastics hits against pending low-confidence Haiku calls; works ingested outside the OpenAlex query need a Haiku screen before export. Owner decisions still win. Evidence: `docs/RELEVANCE_AUDIT_2026-11-13.md`. Questions: REL-TIER2, REL-TITLE.

## ADR-S3.8-RENDER-2026-11-13: Crawlable entity pages are static Python output at deploy
Decision (lead default, QUESTIONS S3.8-RENDER): `scripts/build_seo_pages.py` writes `/experts/<id>/`, `/institutions/<id>/` and sitemaps into `site/` during `build_deploy.yml` (gitignored, ~10 MB), each linking into the interactive app. Independent of the classic-vs-Framework root switch, so pages are built once. robots.txt allows all crawlers (S3.8-AI default).

## ADR-S9.4-VIEW-2026-11-13: Network page without VOSviewer/sigma.js; networkx local-only for now
Owner asked to start S9.4 before SPK-6. The page is a hand-built SVG over a precomputed seeded spring layout (no new front-end dependency). networkx (spec-named) is not a declared dependency yet, so `site/data/network.json` is rebuilt locally with `scripts/build_network.py` and committed; CI export waits for S9.4-DEP. Revisit when SPK-6 runs.

## ADR-FUNDING-MERGE-2026-11-13: Funding visualizations live in the Framework Funding page
Owner prefers the Framework layout. The grants.html views are ported to `/app/funding` and follow its single filter form; grants.html stays for the classic root until the H16 switch, then becomes a redirect (UX-13).

## ADR-H16-ROOT-SWITCH-2026-11-14: Observable Framework app is the site root
Owner H16 answer (2026-11-13): "Switch to observable framework". Decision: `build_deploy.yml` builds the SEO pages into `site/`, builds the Framework app, then runs `scripts/assemble_site.py --out site` (`atlas.build.assemble`): the Framework build is copied over the classic site, so its `index.html` is the home page; `/app/<page>` (and `/app/`), `grants.html` and `sem.html` become noindex redirect stubs that keep the query and hash (to `/<page>`, `/funding`, `/institution`); the new home page carries the classic canonical, Open Graph and JSON-LD head plus a script that sends classic `#<tab>?<params>` links to `/<tab>#<params>`; `experts/index.html` and `institutions/index.html` stubs cover hosts that serve the SEO folders for `/experts`. `expert.html`, `status.html`, `feed.xml`, `data/`, `assets/` and the SEO pages stay. The best-effort contract is kept: if the Framework build or check fails, the classic site stays the root. `atlas.js` `siteRoot()` resolves `data/` from the root or, for the side-by-side preview, from `/app/`. The header "Classic site" link is removed; sitemap and llms.txt list the root routes. Supersedes the "classic stays the root" part of ADR-AT5-SHELL-2026-11-12; question H16-STUBS records the redirect map.

## ADR-S9.4-SIGMA-2026-11-14: Network page renders with sigma.js; networkx is a dependency
Owner asked for a more interactive network (ipysigma or pyvis; S9.4-DEP "do it"). ipysigma is a Jupyter widget around sigma.js and pyvis emits vis.js HTML; neither fits a static Framework page, so the page uses sigma.js 3.0.3 + graphology 0.26.0 + graphology-layout-forceatlas2 0.10.1 (MIT, Framework `npm:` imports self-hosted at build; the S9.4 spec's named fallback). Positions start from the seeded networkx spring layout in `network.json`; ForceAtlas2 runs only on request. networkx is a declared dependency (`networkx>=3.4`, BSD-3-Clause); the daily ingest rebuilds `network.json`. Supersedes ADR-S9.4-VIEW-2026-11-13.

## ADR-REL-2-2026-11-14: Chemicals-in-plastics works are an auxiliary topic
Owner REL-TIER2 answer (2026-11-13): keep BPA and phthalate studies, tag them as plastic-associated chemicals, and say they are auxiliary with less coverage than particle studies. Decision: the label rule adds domain tag `plastic_associated_chemicals` when the plastic decision tier is `chemicals-in-plastics` (no seed matching); `topics.js` marks it `auxiliary` (grey hatch, dashed italic chip, coverage tooltip); the glossary and the Evidence map carry the disclaimer. Relevance precedence is unchanged (ADR-REL-1).

## ADR-S9.3-BADGES-2026-11-14: Expert badges restate public records only
`site/data/expert_badges.json` (daily ingest): funding = plastic-related grants linked through an OpenAlex award ID on the expert's works, or whose PI name key (first given name + family name, accents folded) matches exactly one expert at a California organisation (question S9.3-NAMES); data stewardship = plastic-related DataCite datasets the expert authored via ORCID, versions collapsed. The page decides "active" from the grant end date. The expertise sentence is a fixed template over top topics and settings; no generated text.

## ADR-VD-SPEC-2026-11-14: Visual design refresh follows docs/VISUAL_DESIGN_SPEC.md ("Pacific Contour")
Owner request 2026-11-14: the Framework site "lacks any meaningful design elements" and should have colour and components that look modern and comfortable. Decision: the assessment and spec in `docs/VISUAL_DESIGN_SPEC.md` (TODO section VD, VD-1..VD-13) are the contract, with `docs/design/style_tile.html` as the binding visual reference for token and class names. Rules: presentation only (as ADR-UX-SPEC-2026-11-12), light theme only (UX-26), no runtime requests to font or CDN hosts (vendored fonts with licences recorded in `docs/REUSE.md`), no new dependencies, Framework stays 1.13.4. Topic colours in `site/assets/topics.js` are unchanged; other categorical sets must pass the dataviz palette validator. The direction extends the classic expert.html profile (deep-teal band, tiles on a mint page). The owner accepted VD-D1..VD-D8 on 2026-11-14.

## ADR-VD4-ICONS-2026-11-15: Complete the stated 24-icon sprite with an Atlas external-link icon
- **Context:** `docs/VISUAL_DESIGN_SPEC.md` and the style tile describe 24 Atlas-drawn symbols, but the binding sprite in `docs/design/style_tile.html` contains only 23 (`i-home` through `i-menu`). Section 8 also requires an external-link icon for Policy sources.
- **Decision (lead default):** preserve the 23 style-tile symbols byte-for-byte and add `i-external`, a matching 24 x 24 line icon, as symbol 24. The focused test locks both the original paths and the unique 24-name set. This resolves the internal count discrepancy without adopting a third-party icon set or delaying eligible visual-design work.

## ADR-NET-1-2026-11-15: Research networks are linked, not mirrored, with an owner disclosure
- **Context:** the owner asked that the UC Davis Land to Sea Microplastics Consortium be linked from the Atlas with its logo. The consortium lists 14 contributors (including the owner); 8 have no Atlas profile yet, and its page is all rights reserved.
- **Decision (lead default, QUESTIONS NET-1-NAME/LOGO/SURFACES):** a registry `config/research_networks.yml` drives a host card (UC Davis), member pointers (institutions of listed contributors), expert badges (only contributors with Atlas profiles, by author_id), link-out LO-13 and SEO `subOrganization`. The roster is not copied; the steward's aim and focus headings are quoted verbatim; the page-title name form is used; the logo is self-hosted (no hotlinking) pending permission; every surface carries the disclosure that the owner is a listed contributor (A2 section 0 rule 7 precedent, LO-8).
- **Consequences:** new contributors appear only when their author_id is added; declining the logo means deleting the `logo` block (the page falls back to text).

## ADR-VD9-PALETTE-2026-11-16: One Okabe-Ito secondary set; six colours where all pairs meet
- **Context:** VD-9 (spec Section 7) needs one secondary categorical set for non-topic categories, validated with the dataviz `validate_palette.js`. The 7- and 8-slot Okabe-Ito sets pass adjacent pairs but fail `--pairs all` (`#7A4E9B`/`#0072B2` deutan ΔE 3.8, normal 14.0), which maps and node-link views need; the first six pass all pairs (CVD warn 7.6, so legends/tables are required). The monitoring map has eight matrices.
- **Decision (lead default):** `framework/src/components/shared/palette.js` is the single JS source. Bars and lines use 7 slots (`SECONDARY`); maps and the network use the first 6 (`SECONDARY_ALL_PAIRS`); everything else folds into one `OTHER` grey `#8a969c`. Monitoring: atmospheric deposition and both snow matrices share one colour as a deposition group (the legend still names each matrix). Funding: the seven listed agencies take the slots in their existing order, the rest fold into Other; Sankey agencies and sectors stay neutral so topics carry colour. Heatmaps: zero = sunken fill, any non-zero count starts at seq-200 (`countFill`), because seq-100 is the deliberate near-zero step that fails the ordinal light-end contrast check (1.15:1).
- **Consequences:** network colours only the six largest communities. The classic `site/index.html` monitoring palette is unchanged (outside the Framework app); the drift test compares matrix keys only.

## ADR-VD25-PLANE-POSTER-2026-11-16: Replace the Pacific Contour look with the Plane Poster world
- **Context:** H25 round 2. The owner asked for an Impeccable-designed intro page as an option. Impeccable's direction round (seed d6d6c0290ca009e1) assigned "The Sorting Tray"; the owner chose the competitive challenger "Plane Poster" (Ikko Tanaka flat-plane posters): California drawn from four flat planes, one per task.
- **Decision (owner, 2026-11-16):** adopt the Plane Poster world site-wide (VD-25). The owner likes the four task colours. The current design is preserved first as git tag and GitHub release `design-pacific-contour-2026-11-16`.
- **Consequences:** `design/tokens.css` and the shell get a new palette and display face (Archivo, self-hosted; no CDN per C5). The colour law binds every page: researchers vermilion, monitoring indigo, funding gold, evidence ink. DESIGN.md is written from the built world at the end of VD-25.

## ADR-CREDIT-2026-11-17: A creator credit replaces the disclaimer and the About disclosure
- **Context:** the footer and About page carried the G-12 disclaimer ("Independent project; not an official OEHHA or State product.") and the EM-14 owner disclosure (Plastiverse co-founder, GOV-B 2026-11-10).
- **Decision (owner, 2026-11-17):** remove both statements everywhere they appeared (Framework footer, About, classic expert/status pages, redirect stubs and the old classic index) and show only "Created by Scott Coffin" linking to https://scottcoff.in (footer and the end of About). Link-out and research-network disclosures on Related resources, institution pages and SEO pages are separate statements and stay. Footer links are larger (1rem; 0.9375rem and may wrap on the narrowest phones).
- **Consequences:** `scripts/check_s3_5.py` now checks the credit; the classic pages' no-external-host tests allow the one outbound credit link; PRODUCT.md Brand Commitments updated. EM-14's disclosure item (A2-D8) is answered by this decision.

## ADR-VD30-MAP-INTRO-2026-11-17: Homepage map intro is a sampled spring, no animation library
- **Context:** the owner asked for the four map planes to start at the page edges and join, and chose the springy option (Motion was proposed). The Visual Design Spec 3.3 limits motion to short hover transitions.
- **Decision (owner request; lead implementation choice):** an owner-approved exception to spec 3.3 for the homepage map only. Motion 14.9.0 (MIT) was built and measured at about 64 KB gzip (motion-dom), which breaks the S3.7/C5 hero budget, so the spring (damping ratio 0.55, 10 rad/s, 1.1 s, 120 ms stagger, small tilt) is sampled in the page and played with the Web Animations API. Plays once per browser session; off under prefers-reduced-motion; any pointer or key input finishes it.
- **Consequences:** no dependency or REUSE entry; transforms only (no CLS); the hero clips horizontal overflow only while the intro runs (the site-search listbox lives in the hero).

## ADR-PLAT2-SPECTRAL-STORY-2026-11-17: Plastiverse Live brand and a scroll-story global landing
- **Context:** the platform pivot (PLAT-1..4) needs a global landing page and a platform-wide look. The owner iterated on Impeccable directions and prototypes during 2026-11-17 and approved the result ("love the concept, finalize it").
- **Decision (owner):** the site is "Plastiverse Live". The Spectral Match direction (seed 2c42143eccc874ce), recoloured by the owner's logo (`src/Plastiverse Live_ From Pollution to Progress.png`), replaces Plane Poster across the platform (ADR-VD25 is superseded once VD-SM ships). The landing is a scroll story after Hartmann, Mennekes and Wagner (2026): a picnic shatters into microplastics, particles become papers and knowledge, a bulb lights, then the real global record (works per year, evidence map, network, world map) and a closing local-knowledge beat with a local-ambassador invitation. Text never overlaps images. Paper first pages are CC BY only, with download stamps removed and credits in the footer.
- **Consequences:** build spec `docs/PLAT_2_LANDING_SPEC.md`; direction contract version 2 in `.impeccable/surfaces/framework-src-index-md.md`; prototype and sources in `.impeccable/sketches/`. New fonts (Schibsted Grotesk, Martian Mono, OFL) are self-hosted. Illustrative beats (evidence counts until PLAT-2b, the network) carry visible labels. Logo variants come only from `src/plastiverse_logo_gen_prompt.md`.

## ADR-PLAT1-LAYOUT-2026-11-17: California under /california/ with a clean break; site/ stays at the root
- **Context:** PLAT-1 frees the site root for the global Plastiverse Live page (PLAT-2). The landing spec reads `site/data/trend_global.json`, `site/data/global/` and `site/assets/landing/`, so the shared data and assets must stay at `/data/` and `/assets/`.
- **Decision:** Framework pages move to `framework/src/california/` and deploy to `/california/<page>`; `framework/src/index.md` is the global page. `site/` is unchanged at the root except the classic profile, now `site/california/expert.html`, and the deploy-built SEO pages, now `site/california/{experts,institutions}/<id>/`. Header, footer and top-nav links are written root-relative (`./california/...`) because Framework re-resolves them per page; `atlas.js` `siteRoot()` climbs one level from `/california/` pages and `pageUrl()` links files in the page's own folder; `postbuild.mjs` `nestAssets` rewrites the config head's `./assets/` to `../assets/` for nested pages (Framework leaves head text alone). Search-index hrefs carry the `california/` prefix. Clean break (owner, 2026-11-17): no redirect stubs; `assemble.py` removes `app/`, `grants.html`, `sem.html`, root `expert.html` and root `experts/`/`institutions/` from the output. The feed stays at `/feed.xml` (frozen ids); its links point at `/california/`.
- **Consequences:** old URLs 404; the owner resubmits the sitemap after deploy (H32). PLAT-3 can add regions as sibling folders (`check_at5.py` `REGIONS`). The sidebar home link is now the global page; "California overview" is the first sidebar entry.

## ADR-PLAT2-BUILD-2026-11-17: Landing build choices that differ from the spec
- **Context:** PLAT-2 ports the approved prototype to `framework/src/index.md` + `components/landing_story.{js,css}` (spec `docs/PLAT_2_LANDING_SPEC.md`). Acceptance (`scripts/check_plat2.py`) and Lighthouse forced a few deviations.
- **Decisions:** (1) `--pv-coral-ink` is #c53e39, not #D9443F (4.06:1 on `--pv-ground` fails AA for 14 px links; #c53e39 gives 4.6:1). (2) The opening shows the offline composed picnic (`picnic_first_paint{,_800}.webp`, `srcset`, `sizes="100vw"`) as the LCP element; the canvas engine loads after `load` + a painted frame + idle, cuts shards in yielded chunks, and takes over on the first scroll. The prototype's item-by-item fade-in on load is dropped. (3) Framework must find static `<img>` files under `src/`, so `framework/scripts/sync_shared.mjs` copies the landing's static images from `site/assets/landing/` into gitignored `framework/src/assets/landing/`; the engine fetches everything else at runtime from `site/`. (4) Bitmaps are decoded with `createImageBitmap` (fetch + blob) to keep decodes off the main thread. (5) The country counts and the world raster refresh in the daily ingest (`build_global_counts.py`, cached 7 days; `build_landing_assets.py --raster-only`). (6) Evidence-grid counts and the network stay labelled illustrative (PLAT-2b gated on H30).
- **Consequences:** same-machine Lighthouse (mobile): landing 85 vs California overview 84 locally; live numbers are checked after deploy. `window.__landingDebug` (visualRects, captionRects, timings) is the test hook for the no-overlap rule.

## ADR-GA-LAYOUT-2026-11-18: Global data app = one shell with a scope ladder
- **Context:** the owner asked for the Global site's interactive app (non-region data) designed with Impeccable on the landing's post-story light look, landing untouched, California deferred. Answers: countries first; views countries + profile, evidence map + trend, experts + institutions, network + works; one shell with a scope switch that regional atlases reuse.
- **Decision:** Impeccable surface round (seed:2fe7429ad86b7253) dealt three structures; the owner locked "Scope ladder" and steered it: the ladder is a sticky breadcrumb bar under the header on desktop (World > continent > country > regional atlas, each step a disclosure; "Find a country" on the right) and a left drawer only on phones; the live California atlas and the Norway atlas in preparation appear inside the map (callouts in open water, coral cells, dashed cell-traced outline) and inside the country table (a coral sub-row under the United States, a dashed badge on Norway) and as the last ladder step; the world map spans the content width. The seven view tabs stay fixed while every view re-scopes; the map's viewBox zooms (450 ms ease-out) on scope changes.
- **Consequences:** prototype `.impeccable/sketches/global_app.html` is the composition GA-2 builds in Framework; VD-SM should reuse this shell for California. Continent totals are sums of country counts (overlapping) and say so. Per-country profiles need PLAT-4 data; the prototype shows honest empty states outside the US, China and Norway.

## ADR-A3-INTEGRATION-2026-11-18: Add-on A3 (BQ tasks) integrated into the roadmap

- **Context:** the owner supplied `docs/add_on_spec_3.md` (Add-on A3: corpus quality, global-denominator trends, collaboration structure, topic evolution, evidence-gap heatmap, Sigma.js views, search vocabulary and taxonomy, terminology, precision-goal-driven labelling; task prefix BQ-). It cites repo facts read on 2026-11-18 and marks drift-prone ones `[VERIFY]`.
- **Decision:** 52 BQ tasks in `TODO.md` section "BQ" (A3 §10 order, with three dependency-driven changes: BQ-S2/S6/S3/S7 come before the BQ-1 module because BQ-1.3 and BQ-1.5 need the anchor sets; BQ-1.2 and BQ-1.6 depend only on BQ-0, so they become eligible early; PubMed stage 2 is the separate ID BQ-S9b). The A3 decision table is copied below as A3-D0..D24 with status; conflicts with repo facts or earlier ADRs are A3-C1..C14; open owner items are QUESTIONS A3-Q1..Q15; owner steps are HUMAN_TASKS H36-H40. `scripts/check_a3_scaffold.py` (CI) asserts every ID exists once and BQ dependencies are listed in order. Quote-verification sources are in `docs/A3_SOURCES.md` (Zotero item and attachment keys).
- **Owner rule (2026-11-18):** for OpenAlex, depend on the repo's verified facts, not on the spec's claims (A3-C1).
- **Pre-checked premises (2026-11-18):** `pmid` is not stored anywhere; the shared OpenAlex client already throttles >5-operator searches and retries their 429 (`atlas.ingest.openalex._throttle`); `requests` is not a dependency; code is MIT (`LICENSE`, ADR-002) and derived data CC BY (`LICENSE-DATA.md`), only the `pyproject.toml` string is stale.
- **Consequence:** the 2026-11-18 handoff queue (PLAT-2b, VD-SM, PLAT-3, PLAT-4) is interleaved with A3 (A3-Q1 default). A3 does not change any A1/A2 gate, the active query, the frozen guide or the gold files.
- **Decided by:** lead at integration; owner decisions marked in the register.

## Add-on A3 decisions (register)

Copied from `docs/add_on_spec_3.md` §3. "Owner" = decided by the owner per the spec; "Proposal" = awaiting owner approval (nothing ships on a proposal).

| ID | Decision | Status |
|---|---|---|
| A3-D0 | Terminology: "Authors", never "Experts" (BQ-R1) | Owner |
| A3-D1 | Engine: Sigma.js + graphology, precomputed layouts; stay on sigma 3.0.3 unless BQ-V.0 requires a change | Owner |
| A3-D2 | Views: Authors, Institutions, Works in the seven-tab shell | Owner |
| A3-D3 | Scope ladder Worldwide > Country > Region; generic subregion schema; California = RWQCB + offshore (A2); Norway subregions open (A3-Q12) | Owner (Norway open) |
| A3-D4 | Pollution-core = v3.1 pollution terms as the starting set (A3 §5.3) | Owner |
| A3-D5 | Label budget: 150 CA-eval + up to 350 global, precision-goal-driven, 350 is a ceiling; needs ADR-GOLD-GLOBAL | Owner (ADR proposed below, A3-Q3) |
| A3-D6 | Second reader: Claude 20% per ADR-GATES, reported as LLM-owner agreement; optional 40-work intra-rater retest stored separately | Owner |
| A3-D7 | Topic series use only owner-approved tags | Owner |
| A3-D8 | Person-level metrics aggregate only; node size = work count | Owner (scope vs existing features: A3-C5, A3-Q2) |
| A3-D9 | New dependencies need owner approval + a DECISIONS entry | Owner. Standing approval 2026-11-18 (A3-Q13): add any dependency a task needs unless it has a major workflow, reusability or security impact; still record each in DECISIONS with licence and pin |
| A3-D10 | Query changes go to candidate plastic-v3.2; promotion by the existing precision rule | Owner |
| A3-D11 | Gold publication: IDs, labels, short excerpts; licence open (A3-Q9) | Owner (licence open) |
| A3-D12 | Lifecycle-and-society scope included with the boundary defaults (bioplastics, packaging, SSbD) | Owner |
| A3-D13 | Tier name `lifecycle_and_society` | Owner |
| A3-D14 | Waste colonialism: topic tag + `analytic_lens[]` facet, explicit framing with quoted excerpt only | Owner |
| A3-D15 | The 13 labelled CA works are checked against A3; lens and centrality default `not_assessed` | Owner |
| A3-D16 | Tier name confirmed | Owner |
| A3-D17 | `culture_media_and_discourse` optional, low weight, outside P1-P6 | Owner |
| A3-D18 | Scope gate loosened via `plastics_centrality`; definition wording is a proposal | Owner (wording: A3-Q5) |
| A3-D19 | No new label budgets beyond the 350 ceiling and the >= 30 reserve | Owner |
| A3-D20 | Lens/tag reconciliation (two new lens values; other candidates folded) | Owner 2026-11-18 (A3-Q7): implement and test now to prevent regression; ship publicly only after approval |
| A3-D21 | Review-derived facets (A3 §5.10.3) are candidates; evidence-quality scores not adopted | Owner 2026-11-18 (A3-Q8): adopt the review-derived facets. Each facet is benchmarked against the reviews' included-study lists (abstract-level matching for now); a facet ships with a clear on-site precision/accuracy caveat, or does not ship if results are truly poor. Evidence-quality scores stay out |
| A3-D22 | BERT-based title classifier is precedent for certification arithmetic only | Owner |
| A3-D23 | PubMed coverage QC: Python port on NCBI E-utilities (ADR-A3-PUBMED) | Owner |
| A3-D24 | PubMed results are coverage against a reference set, never recall | Owner |

## Add-on A3 conflicts (register)

Each row is an adopted rule; status stays Open until the implementing task's acceptance passes.

| ID | Issue | Resolution | Tasks | Status |
|---|---|---|---|---|
| A3-C1 | A3 §0 rule 12 and §5.9 cap agent-written OpenAlex queries at 5 boolean operators, from a 429 seen in a research tool; the repo verified on 2026-11-11 that >5-operator searches are rate-limited to 5 req/s (429 "wait 1s"), cost 10 credits, and are throttled and retried by the shared client. Splitting OR lists breaks count queries (split counts cannot be summed). | Owner 2026-11-18: verified repo facts govern OpenAlex, not the spec. Count queries (PLAT-2b cells, trend, language probe, per-theme counts) stay one fully parenthesised query on the throttled path. Splitting is allowed only for ID retrieval with dedupe by work ID. Any new OpenAlex behaviour is smoke-tested and recorded in `docs/api_notes/` before it is relied on. | BQ-S8, BQ-S2, BQ-S4, BQ-S10, BQ-2.2, PLAT-2b | Open |
| A3-C2 | BQ-V.2 (global ingest) duplicates PLAT-4 | One implementation: PLAT-4 carries BQ-V.2's acceptance (cost estimate first, "unscreened query hits", `ids.pmid`, budget guard USD 0.95/day, no paid filters); BQ-V.2 is checked when PLAT-4 passes. PLAT-4 keeps its PLAT-3 dependency (A3-Q15). | PLAT-4, BQ-V.2, BQ-G3, BQ-S9b, GX-1 | Resolved 2026-11-18 (A3-Q15 split: PLAT-4a raw global fetch early, PLAT-4b partition + publish after PLAT-3) |
| A3-C3 | A3 §0 rule 2 forbids touching VD/PLAT/NOR/MAIL/GA inside a BQ task, but BQ-R1 must change explorer tabs and email copy | BQ-R1 is the named exception: public strings only, no layout change. Run it before VD-SM. | BQ-R1, VD-SM, MAIL-1, GA | Resolved 2026-11-18 (BQ-R1 done before VD-SM) |
| A3-C4 | BQ-R1 asks for /experts -> /authors redirects; ADR-PLAT1-LAYOUT made the root -> /california move a clean break without redirects | PLAT-1's rule covers that move only. BQ-R1 adds redirect stubs for renamed routes; `expert.html`, data keys and file names stay unchanged (A3-Q4 confirmed 2026-11-18). | BQ-R1 | Resolved 2026-11-18 |
| A3-C5 | A3-D8 / rule 8 "no person-level rankings" vs shipped person-level features (m-quotient and rising score on expert pages, ADR-EXPERT-METRICS; GX-SEO top-20,000 selection) | A3-D8 governs new A3 outputs only; owner 2026-11-18 (A3-Q2): keep every shipped person-level feature (m-quotient, rising score, GX-SEO top-20,000). | BQ-3.4, BQ-V.4; ADR-EXPERT-METRICS; GX-5 | Resolved 2026-11-18 |
| A3-C6 | A3 §0 rule 14 (no publisher full text) vs the S6 full-text pipeline | Compatible: S6 already processes only selected copies with CC BY/CC0 evidence (G-8). BQ tasks store no full text; Zotero PDFs are read locally into gitignored `scratch/pdfmd/` for quote checks only. | S6.x, all BQ | Open |
| A3-C7 | A3 lists code and gold licences as pending (from `pyproject.toml`) | Code is MIT (`LICENSE`, ADR-002) and derived data CC BY (`LICENSE-DATA.md`); BQ-0 fixes the stale pyproject string; new code (PubMed port) is MIT; gold licence default CC BY (A3-Q9). | BQ-0, BQ-S9, BQ-G6 | Open |
| A3-C8 | PubMed port "via the standard library or requests"; `requests` is not a dependency | Standard library `urllib` only; no new dependency, so A3-D9 is not triggered. | BQ-S9 | Open |
| A3-C9 | A3 §5.9 says `fetch_trend_global.py` does not handle 429 | False: it uses the shared `_request_json` path (throttle, per-second 429 retry, budget guard charges rejected 429s). The real gap is plan refusals returned as 429 that defer quietly (TODO ING note); BQ-2.2 adds a stale flag and surfaces them. BQ-S8 verifies and documents. | BQ-S8, BQ-2.2 | Open |
| A3-C10 | A3 Module V names graphology JS layouts (layout-noverlap, communities-louvain); the repo precomputes ForceAtlas2 positions and communities in Python (`build_network.py`) | Precompute in Python with networkx (Louvain is in networkx); new npm packages fall under the A3-D9 standing approval (A3-Q13), recorded per package. | BQ-V.1 | Open |
| A3-C11 | Overlapping work: BQ-V.4 Works view vs AT-9; BQ-V Authors graph vs GX-7; BQ-6.1 vs S5.2/S5.4; BQ-6.2 vs EM-8; Module 2 vs EM-7 and PLAT-2b | AT-9 is delivered by BQ-V.4; GX-7 by BQ-V.1/V.4; BQ-6.1 reuses S5.2/S5.4 (no second extractor); BQ-6.2 shares the EM-8 heatmap component (A2-C4); BQ-2.x extends `trend_global.json` and shares PLAT-2b's fetch path. | AT-9, GX-7, S5.2, S5.4, EM-8, EM-7, PLAT-2b | Open |
| A3-C12 | A3 §0 rule 10 test baseline (1,702 passed, 9 skips) comes from NET-1 and is stale | BQ-0 records the current baseline; later BQ checkpoints compare against it. | BQ-0 | Open |
| A3-C13 | ADR-GOLD-EVAL-SET limits owner gold labels to the 150 CA-eval works; A3-D5 adds up to 350 global labels | ADR-GOLD-GLOBAL extends it (owner confirmed 2026-11-18, A3-Q3). | BQ-G3, BQ-G4 | Resolved 2026-11-18 |
| A3-C14 | A3 §6 places new files directly in `site/data/`; PLAT-3 introduces `site/data/<region>/` | Global outputs go in `site/data/global/`, California outputs stay in `site/data/` until PLAT-3 moves them; every A3 file is listed in `build_metadata.json`. | all BQ data tasks, PLAT-3 | Open |

## ADR-GOLD-GLOBAL-2026-11-18: global evaluation labels under Add-on A3

- **Status:** Accepted 2026-11-18 (owner confirmed, QUESTIONS A3-Q3).
- **Decision:** extends ADR-GOLD-EVAL-SET. Besides the 150 California evaluation works, the owner labels up to 350 global works chosen by the A3 §4.3 adaptive design (round 0 of >= 10 per stratum, rounds of 25, checkpoints at 100/200/300/350, stop early once P1 is met at a checkpoint); 350 is a ceiling, not a quota. Strata and inclusion probabilities are frozen before labelling (`curation/gold_global_frame_v1.csv`); labels are never repeated; works with `role=guide_example` are excluded from every frame and test set. Claude double-labels 20% (ADR-GATES), reported as LLM-owner agreement. Labelling uses the Streamlit app from BQ-G4.
- **Consequence:** gold_v1 covers both blocks and is immutable after release (BQ-G6).

## ADR-A3-PUBMED-2026-11-18: PubMed coverage QC as a Python port (A3-D23 / A3-D9)

- **Decision (owner, 2026-11-18, per A3-D23):** add `src/atlas/qc/pubmed.py` and `scripts/qc_pubmed_coverage.py` (Python, NCBI E-utilities, standard library only; A3-C8). Purpose: coverage check against PubMed reference sets; not a query source or authority (A3-D24). Licence: new code under the repo's MIT licence (A3-C7); no code is copied from the GPL-3.0 R package `pubmedsearchworkflow` (the owner holds its copyright; easyPubMed is not used). Etiquette: tool name sent, optional API key and contact email only from the environment (A3-Q14). Live calls only behind an explicit flag; tests offline.
