# Decisions

ADR-style decisions belong here with date, alternatives, rationale, and decision
owner. Unanswered items continue to use the defaults in `spec.md` Part G and
remain listed in `QUESTIONS.md`.

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
