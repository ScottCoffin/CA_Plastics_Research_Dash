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
| `build_metadata.json` | Build timestamp, `counts`, per-file raw and gzip byte sizes, and total payload sizes. This is the S3.1 size log. `counts` holds the index counts plus the Overview card counts (VD-13), each matching the default view of its page: `plastic_works` (slim works with `plastic_related` true, the Evidence map figure); `awards` (`grants.json` rows whose `plastic_related` is not false, the Funding default view); `monitoring_samples` (`monitoring.json` `sample_count`) and `monitoring_sources` (length of its `datasets`), both omitted for a private preview; `network_experts` and `network_links` (`network.json` nodes, and edges between two listed nodes with weight at least 1, the Network page default). A key is omitted when its source file is missing or unreadable. `scripts/build_network.py` refreshes the two network keys after it rewrites `network.json`. `index.json` `counts` keeps only the index counts. |
| `journal_metrics.json` | Journal metrics for the Evidence map publication table (VD-34; `scripts/fetch_journal_metrics.py`, `--check` fails when stale). `schema_version` 1, `generated_at`, `source` (`OpenAlex sources summary_stats`), `coverage`, `journals` (array of items with `name`, the journal as `works_detail.json` spells it, plus `source_id`, `issn_l`, `two_yr_mean_citedness` = OpenAlex's open analogue of the impact factor, 3 decimals or null, `h_index`, `type`), plus `unmatched_journals`, `name_mismatches` (metrics withheld) and `ambiguous_journals`. Optional for the page. Details in `docs/DATA_DICTIONARY.md`. |
| `network.json` | Expert collaboration network for `/network` (S9.4; `scripts/build_network.py`, `--check` fails when stale). Top-level keys: `schema_version` (`s9.4-v1.1`), `generated_at`, `method` (edge weight, community, layout, `community_labels` and networkx version), `communities` (integer count), `community_labels` (VD-20; one entry per community of at least 4 experts, in community order: `community` index, `size`, `institution` `{name, share}` or null, `topic` `{tag, share, lift}` or null; thresholds are in `method.community_labels`), `nodes` (`id`, `name`, `x` and `y` in [-1, 1] from a ForceAtlas2 layout started from a seeded spring layout, see `method.layout`; `community`, `degree`, `strength`, `plastic_works`, `topics`, `institution_ids`, `institutions`, `sectors`, `primary_affiliations`, `current_in_ca`) and `edges` (`source`, `target`, `weight`, `years`). `community_labels` is new in `s9.4-v1.1`; readers must treat it as optional, as the page does. |
| `network_metrics.json` | Collaboration-structure metrics (BQ-3.2; `scripts/build_network_metrics.py`, `--check` fails when stale, ignoring `generated_at`; offline). `schema_version` (`bq3-v1`), `generated_at`, `source` (index build timestamp), `method`, `ascertainment_note`, `definitions` (plain-language text per metric), `corpus` (plastic-related work counts) and `graphs` (`authors` = G-A, `institutions` = G-I; each has `windows` for `all`, `2011-2015`, `2016-2020`, `2021-2025` and `2026` with `partial` true). Per window: nodes, edges, components, giant component, density, clustering, isolates, degree quantiles, communities, modularity and three edge fractions. Aggregates only: no author or institution ids or names. Licence: derived counts from `index.json`. |

| `pubmed_coverage.json` | PubMed coverage check (BQ-S9 part C; `scripts/build_pubmed_coverage_json.py`, `--check` fails when stale and skips when the interim PubMed runs are absent). `schema_version` `bqs-pm-v1`, `generated_at`, `source`, `definition`, `atlas_corpus`, `reference_sets` (`r1` and `r2`: counts, coverage, coverage by year, join rates, manifest hash), `miss_triage` (fixed-seed miss sample, triage labels, and a false-negative share with a Wilson 95% interval once labelled) and `triage_classes`. Fields in `docs/DATA_DICTIONARY.md`. |
| `language_probe.json` | Native-language OpenAlex probe for BQ-S4 (`scripts/fetch_language_probe.py`; `--check` validates the committed file, `--offline` rebuilds it from the local response cache). `schema_version` `bqs-v1`, `generated_at`, `query_version`, `vocabulary_version`, `source`, `sample_seed`, `sample_limit`, `method`, `cost` (`credits`, `usd`), `term_sets` (sixteen A3 §5.7 sets: `id`, `languages`, `terms`, `query`, `a3_count_2026_11_18`, `count`, `language_label_counts`, `fetched_at`, `sample` (up to 50 works: `id`, `title`, `language`, `year`, `venue`, `in_v31`), `sample_size`, `sample_in_v31`, `sample_language_label_counts`), `caveats` and `not_covered`. Titles are OpenAlex metadata; no abstracts. |
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
