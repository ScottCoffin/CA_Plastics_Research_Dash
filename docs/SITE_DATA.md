# Static site data contract (S3.1)

`scripts/build_export_site.py` converts the normalized C3 Parquet tables into
small, deterministic JSON payloads under `site/data/california/` (California; PLAT-3 slice 3b moved them
there), `site/data/global/` (global series) and `site/data/` (release and status). See `docs/DATA_LAYOUT.md`.
The exporter is a
build step; the browser never needs PyArrow or Parquet support.

All payloads use `schema_version: "s3.1"`, compact UTF-8/ASCII JSON, stable ID
ordering, and UTC `generated_at` metadata.  The default build inputs are the
S2.2 normalized tables and the optional S2.3 `work_labels.parquet` output.
Missing labels are retained as `null` and are never inferred by the exporter.

## Files

| File | Contract |
|---|---|
| `index.json` | `counts`, slim `works`, and slim `authors` arrays. Work rows contain IDs, title/year/type, CA flags, citation count, author/institution IDs, and provisional label fields. Author rows contain IDs, display fields, year range, work IDs, and institution IDs. |
| `authors/<author_id>.json` | One detail document per author with the indexed author row and full work rows (abstract, DOI, journal, OA fields, topics, and label fields). |
| `institutions.json` | Institution rows with reviewed type/CA flag, coordinates, work and author counts, year coverage, and tags. |
| `institutions.geojson` | GeoJSON `FeatureCollection` of California institutions with non-null coordinates. Properties mirror the institution summary. |
| `aggregates.json` | `by_year`, `by_type`, and `by_tag` arrays. Each row has `count` and `plastic_related_count`; tag rows combine taxonomy domain and matrix facet IDs. |
| `search_index.json` | Header search index (VD-19, `scripts/build_search_index.py`): `schema_version` 1, `generated_at`, `types` (`page`, `expert`, `institution`, `topic`, `funder`, `term`, `resource`) and `items` as `[type_index, label, detail, href]`, hrefs relative to the site root. Experts from `index.json`; California institutions from `institutions.json`; funders from `grants.json`; resources from `linkouts.json`; topics and matrices from `site/assets/topics.js`; terms from `framework/src/glossary.md`; pages from the nav in `framework/observablehq.config.js`. Public fields only: no abstracts or e-mail addresses. Loaded once by `site/assets/site_search.js`. The daily ingest rebuilds it; `--check` fails when stale. |
| `global/places.json` | Place-search index for `/explore` (AMB-1): `schema` `places-v1`, `kinds`, `parents`, `markers` (small-country dots as `[iso, lon, lat]`), `licence`, `credit` and `entries` as `[name, kind, parent, iso2, geom, population]`. Countries (world-atlas 50m), regions (Natural Earth admin-1 10m) and cities of 15,000 people or more (GeoNames `cities15000`, CC BY 4.0). Built by `scripts/build_places_index.py`; `--check` exits 1 when stale. |
| `california/quality.json` | BQ-1.4 corpus-quality payload for `/california/quality`: schema `bq1-v1`, `generated_at`, `scope`, `status`, `status_text`, `checkpoint`, `labels` (labelled and planned counts), `what_this_is_and_is_not`, `design`, and per-estimand `status`, `what`, and (only at a final checkpoint with status `ok`) `point`, `interval`, `n`, `method`, `flags`, `note`. Until then every estimand reads `no_validated_estimate` with "No validated estimate yet". Built by `scripts/build_quality_json.py`; `--check` exits 1 when stale. |
| `global/quality.json` | The same schema for `/quality` (global scope: E1g, E2g, E7). Built by `scripts/build_quality_json.py`; `--check` exits 1 when stale. |
| `build_metadata.json` | Build timestamp, `counts`, per-file raw and gzip byte sizes, and total payload sizes. This is the S3.1 size log. `counts` holds the index counts plus the Overview card counts (VD-13), each matching the default view of its page: `plastic_works` (slim works with `plastic_related` true, the Evidence map figure); `awards` (`grants.json` rows whose `plastic_related` is not false, the Funding default view); `monitoring_samples` (`monitoring.json` `sample_count`) and `monitoring_sources` (length of its `datasets`), both omitted for a private preview; `network_experts` and `network_links` (`network.json` nodes, and edges between two listed nodes with weight at least 1, the Network page default). A key is omitted when its source file is missing or unreadable. `scripts/build_network.py` refreshes the two network keys after it rewrites `network.json`. `index.json` `counts` keeps only the index counts. |
| `journal_metrics.json` | Journal metrics for the Evidence map publication table (VD-34; `scripts/fetch_journal_metrics.py`, `--check` fails when stale). `schema_version` 1, `generated_at`, `source` (`OpenAlex sources summary_stats`), `coverage`, `journals` (array of items with `name`, the journal as `works_detail.json` spells it, plus `source_id`, `issn_l`, `two_yr_mean_citedness` = OpenAlex's open analogue of the impact factor, 3 decimals or null, `h_index`, `type`), plus `unmatched_journals`, `name_mismatches` (metrics withheld) and `ambiguous_journals`. Optional for the page. Details in `docs/DATA_DICTIONARY.md`. |
| `network.json` | Expert collaboration network for `/network` (S9.4; `scripts/build_network.py`, `--check` fails when stale). Top-level keys: `schema_version` (`s9.4-v1.1`), `generated_at`, `method` (edge weight, community, layout, `community_labels` and networkx version), `communities` (integer count), `community_labels` (VD-20; one entry per community of at least 4 experts, in community order: `community` index, `size`, `institution` `{name, share}` or null, `topic` `{tag, share, lift}` or null; thresholds are in `method.community_labels`), `nodes` (`id`, `name`, `x` and `y` in [-1, 1] from a ForceAtlas2 layout started from a seeded spring layout, see `method.layout`; `community`, `degree`, `strength`, `plastic_works`, `topics`, `institution_ids`, `institutions`, `sectors`, `primary_affiliations`, `current_in_ca`) and `edges` (`source`, `target`, `weight`, `years`). `community_labels` is new in `s9.4-v1.1`; readers must treat it as optional, as the page does. |
| `network_metrics.json` | Collaboration-structure metrics (BQ-3.2; `scripts/build_network_metrics.py`, `--check` fails when stale, ignoring `generated_at`; offline). `schema_version` (`bq3-v1`), `generated_at`, `source` (index build timestamp), `method`, `ascertainment_note`, `definitions` (plain-language text per metric), `corpus` (plastic-related work counts) and `graphs` (`authors` = G-A, `institutions` = G-I; each has `windows` for `all`, `2011-2015`, `2016-2020`, `2021-2025` and `2026` with `partial` true). Per window: nodes, edges, components, giant component, density, clustering, isolates, degree quantiles, communities, modularity and three edge fractions. Aggregates only: no author or institution ids or names. Licence: derived counts from `index.json`. |

| `pubmed_coverage.json` | PubMed coverage check (BQ-S9 part C; `scripts/build_pubmed_coverage_json.py`, `--check` fails when stale and skips when the interim PubMed runs are absent). `schema_version` `bqs-pm-v1`, `generated_at`, `source`, `definition`, `atlas_corpus`, `reference_sets` (`r1` and `r2`: counts, coverage, coverage by year, join rates, manifest hash), `miss_triage` (fixed-seed miss sample, triage labels, and a false-negative share with a Wilson 95% interval once labelled) and `triage_classes`. Fields in `docs/DATA_DICTIONARY.md`. |
| `language_probe.json` | Native-language OpenAlex probe for BQ-S4 (`scripts/fetch_language_probe.py`; `--check` validates the committed file, `--offline` rebuilds it from the local response cache). `schema_version` `bqs-v1`, `generated_at`, `query_version`, `vocabulary_version`, `source`, `sample_seed`, `sample_limit`, `method`, `cost` (`credits`, `usd`), `term_sets` (sixteen A3 §5.7 sets: `id`, `languages`, `terms`, `query`, `a3_count_2026_11_18`, `count`, `language_label_counts`, `fetched_at`, `sample` (up to 50 works: `id`, `title`, `language`, `year`, `venue`, `in_v31`), `sample_size`, `sample_in_v31`, `sample_language_label_counts`), `caveats` and `not_covered`. Titles are OpenAlex metadata; no abstracts. |
| `countries.json` | Tier B country aggregates from the global partition (PLAT-4b slice 3; `scripts/build_tier_b.py`, `--check` validates and fails when stale against the ignored partition, SKIP for the staleness check when it is absent). `schema_version` `plat4b-v1`, `generated_at`, `query_version`, `screening_status` `unscreened_query_hit`, `what_this_is_and_is_not`, `tier_rule`, `years`, `tier_counts`, `countries` (per ISO country: `tier`, `works_total`, `works_by_year`, `works_with_pmid`, `first_year`, `top_primary_topics`), `registry_regions` (same counts, matched by the region predicate). Not yet read by the pages. |
| `graphs/institutions.json`, `graphs/institutions_phone.json`, `graphs/layout_institutions.bin`, `graphs/graphs_manifest.json` | Global institution collaboration graph (BQ-V.1 slice 1; `scripts/build_global_graphs.py [--check]`, ~7 min from the ignored raw store). JSON: `fields`, `nodes.rows` [id, display_name, ror, country_code, type, works, community], `edges.rows` [source, target, weight] (node indices); thinned to the BQ-V.0 budgets (desktop 60,000 edges, top-8 per node; phone 5,000 nodes, 15,000 edges, top-3). Layout: float32 little-endian x,y per node in node order. Manifest (bqv-v1): caps, thinning, seed, sources, `screening_status: unscreened_query_hit`. No people. |
| `graphs/authors.json`, `graphs/authors_phone.json`, `graphs/layout_authors.bin` | Global author collaboration graph (BQ-V.1 slice 2; same builder, ~11 min). Pollution-core backbone (78,045 works; works with more than 25 authors add no edges); nodes [id, display_name, country_code, works, community], edges [source, target, weight]; desktop 20,000 nodes / 60,000 edges, phone 5,000 / 10,141 (thinned like the institution graph). Public OpenAlex author names (owner 2026-11-25, QUESTIONS GLOBAL-AUTHORS); no email, affiliation strings or ORCID. |
| `graphs/works.json`, `graphs/works_phone.json`, `graphs/layout_works.bin`, `graphs/works_manifest.json` | Global works similarity graph (BQ-V.1 slice 3; `scripts/build_global_works_graph.py [--check]`, needs the `ml` extra; docs/NETWORK_BUILD.md §16c). The 15,000 most cited pollution-core backbone works; edges join each work to its 5 most similar works by bge-small title-and-abstract embeddings (phone: 5,000 works, 3 neighbours), trimmed to 60,000 / 15,000 edges. Nodes [id, title, year, cited_by_count, embedding_quality, community]; `embedding_quality` is `low` for non-English works. Own manifest (bqv-v1). No abstracts or people. |
| `graphs/exports/*` | GEXF and GraphML downloads of the global institution and author graphs and the California network (BQ-V.6; `scripts/build_graph_exports.py [--check]`, docs/NETWORK_BUILD.md §17). Node attributes, positions, edge weights, licence line; files over 5 MB are committed as `.gz` only; `exports/manifest.json` (bqv6-v1) lists files, sizes and sha256. |
| `norway/region.json`, `belgium/region.json` | Region page payloads (REG-1, schema `region-v1`; `scripts/build_region_pages.py`, `--check` validates the schema, the placeholder rule, the privacy rule and equality with `countries.json`, and fails when stale against the ignored partition, SKIP for the staleness check when it is absent). `stats`, `works_by_year` and `top_topics` come from the `countries.json` entry for the ISO code; `top_institutions`, `top_researchers` (`id`, `name`, `works` only) and `partner_countries` come from the partition and raw pages; `sections` are the local candidates from `regions/<slug>/region.yml`, each with `status` `to_confirm` until a local collaborator confirms it. `screening_status` `unscreened_query_hit`. Read by the region page (framework, separate slice). |
| `<slug>/ambassador_institutions.json`, `<slug>/ambassador_cases.json` | Ambassador eligibility allowlist and stream A case queues for California, Norway and Belgium (AMB-1 step 1, schemas `amb-v1` and `amb-cases-v1`; `scripts/build_ambassador_data.py`, `--check` validates and fails when stale against the ignored inputs, SKIP for staleness when they are absent). Institutions only (`id`, `name`, `type`, `works`, `domains`, `needs_domain`); cases carry public evidence only. Read by the ambassador pages (later slice). |
| `pubmed_coverage.json` | PubMed coverage check, stage 2 (BQ-S9b; `scripts/build_pubmed_coverage_json.py --scope global [--check]`). `schema_version` bqs-pm-v1, `scope` global, `stage` 2, `caveat`, `join_method`, `atlas_corpus` (works, PMID/DOI counts, works_sha256), `reference_sets` r1/r2 (counts, coverage, coverage_by_year). No PMID lists. |
| `denominators.json` | Global denominators for the V-4 trend panel and the Explore Trend tab (BQ-2.4; `scripts/build_denominators_json.py`, `--check` validates and fails when stale against the ignored `denominator_series.json`, SKIP when that input is absent). `schema_version` `bq2-v1`, `generated_at`, `version`, `source`, `what_this_is_and_is_not`, `series` (A, A-article_review, B, B-article_review, C, D: yearly counts), `ratio_pairs` (B/A, C/A, B-article_review/A-article_review), `not_computed` (B2), `metrics` (BQ-2.3 counts, index, CAGR with 95% interval, shares). Lazy-loaded by the pages. |
| `bundle/` | AT-4 serving bundle (`scripts/build_bundle.py`, `docs/AT_4_VERIFICATION.md`): `works_index.json` (ordered work IDs, titles, years; record i = bit i), `facets.json` + `facets.bin` (Appendix C bit-sets: year, type, topic, plastic, ca_led, institution, sector, oa), `inst_tiers.json` (AT-3 rank-range tiers), `parquet/` (abstract-free `works`, `inst_counts`, `inst_tiers`, `year_tag`; DuckDB 2.0.0 zstd), `manifest.json` (sizes). Read in the browser with `site/assets/facets.js` (`window.AtlasFacets`). |

The initial C5 target is an initial payload below 3 MB gzip.  A build that
exceeds the target must retain the recorded sizes here and document the reason
before introducing DuckDB-Wasm or another client-side query engine.

### `build_metadata.json` flow (FLOW-1)

`build_metadata.json` has an optional top-level `flow` object: a PRISMA-style count for the daily export. `unique_works` and `no_ca_authorship` come from the normalized works table as read, before the non-California filter and curation; `published` and the plastic split come from the exported index. The exporter raises `ValueError` if the counts stop adding up. The key is omitted when `ca_authors_only` is off (the test and fixture builds) or the works table has no `ca_any_author` column. Consumers should treat a missing `flow` as "use the archived release".

- `records_retrieved`: `unique_works` + `duplicates_collapsed` (integer).
- `duplicates_collapsed`: total length of the `duplicate_work_ids` lists across the normalized works; null counts as 0 (integer).
- `unique_works`: works in the normalized table before curation (integer).
- `no_ca_authorship`: unique works whose `ca_any_author` is not true (integer).
- `removed_by_curation`: `unique_works` - `no_ca_authorship` - `published`; equals `curation.works_removed` when the curation files agree (integer).
- `published`: works in `index.json`, the same as `counts.works` (integer).
- `plastic_related`: published works with `plastic_related` true, the same as `counts.plastic_works` (integer).
- `not_plastic_related`: `published` - `plastic_related`; includes unlabelled works (integer).
- `by_type`: object keyed by OpenAlex work type (`unknown` when empty) with the published count; values sum to `published`. The exporter sorts by count, but the JSON writer sorts keys, so the file lists types alphabetically; sort by value when order matters.

## Rebuild and check

```powershell
py -3.14 scripts/build_export_site.py
py -3.14 scripts/check_s3_1.py
```

The acceptance script uses the committed S2.2 fixture and checks deterministic
ordering, complete author-detail joins, aggregate counts, California map
features, and the payload budget without contacting OpenAlex.

## S3.2 browser consumer

`site/index.html` consumes the four top-level JSON files with relative browser
fetches, so the same shell serves the committed fixture and a later real-data
export without a client build step. The Experts filter state is kept in the URL
hash; Monitoring and Funding are reserved stubs until their ingestion stages.

## Region institution exports (GP-5)

`scripts/build_region_export.py --region <slug>` writes the California institution
payloads for a non-default registry region (`norway`, `belgium`) under
`site/data/<slug>/`: `institutions.json`, `index.json` (only the works and authors
those institutions reference) and `institution_works/<inst_id>.json`. The keys match
the California files (`schema_version` `s3.1`), and `tests/fixtures/region_export/california_keys.json`
pins the California key sets. The module is `src/atlas/build/region_export.py`.

- Input: the ignored global partition (`data/processed/global`). Region works are
  `work_regions` rows of kind `country` with the region's ISO code; institutions are
  registry institutions with that `country_code` that appear on a region work.
- Every work has `screening_status: "unscreened_query_hit"`. `plastic_related`,
  California labels, paid author metrics and `ca_connection` are null or absent.
- `domain_tags` and `facet_tags` are empty lists. Expert topics use the OpenAlex
  primary topic name.
- `atlas_type` maps the OpenAlex type (company; nonprofit, funder, facility,
  archive and healthcare to `nonprofit/NGO`). Education and government map to `other`.
- `lat`, `lon` and `city` are null. `scope` is `region` and `ca_flag` is false.
- `institutions.json` and `index.json` carry a `method` note with these rules.
- `--check` validates the committed files and, when the partition exists, fails on
  any byte difference from a rebuild. `generated_at` is reused from the committed file.

## Region author files (GP-2)

`scripts/build_region_export.py --region norway|belgium` also writes `site/data/<slug>/authors/<author_id>.json` in the California author-file layout (`author`, `schema_version`, `works`). Only authors with two or more works in the region get a file; they are the only rows in the region `index.json` `authors` list and the only experts with `in_atlas_index: true`, so every author link resolves. California-only values are null (`h_index`, `m_quotient`, rising, `ca_*`, `current_in_ca`, photos, bios); `affiliation_history` lists the region institutions with years. Profiles are `site/<slug>/expert.html` copies of the California profile that read `data/<slug>/`, with the California badge and network files skipped. Region sizes at GP-2: norway about 15.6 MB and belgium about 12.3 MB, both under the 20 MB Pages budget.

## Region collaboration networks (GP-3)
`scripts/build_network.py --region norway|belgium [--check]` writes `site/data/<slug>/network.json` in the California `s9.4-v1.1` layout from the region's `index.json` and `institutions.json`. Region works are unscreened (`plastic_related` null), so `atlas.build.network.unscreened_region_index` counts every region work as a co-authored work; author volume is `work_count` and the tie-break is `cited_by_count`. `method.works` says so. Index authors are the authors with a region file, so every node's profile resolves to `site/<slug>/expert.html#author=<id>`. The region pages (`framework/src/{norway,belgium}/network.md`) omit the California metrics panel, so no `network_metrics.json` is written for regions, and hide the "Now in California" filter because `current_in_ca` is null there. Sizes at GP-3: norway about 390 KB and belgium about 292 KB.
