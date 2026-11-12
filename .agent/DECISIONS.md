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
