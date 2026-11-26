# Site data layout (PLAT-3 slice 3b, 2026-11-25)

Owner decision 2026-11-25 (QUESTIONS PLAT3-DATA-PATH): California's data moves from `site/data/` to
`site/data/california/`, a clean break like PLAT-1 (old JSON URLs return 404). Each region writes the same file set
under `site/data/<region>/`; the region registry (`regions/_registry.yml`, field `site_data_dir`) names the folder.

| Folder | Contents | Written by |
|---|---|---|
| `site/data/california/` | `aggregates.json`, `authors/`, `build_metadata.json`, `bundle/`, `dtsc_timeline.json`, `expert_badges.json`, `grants.json`, `index.json`, `quality.json` (BQ-1.4, schema `bq1-v1`, `scripts/build_quality_json.py`), `institution_works/`, `institutions.geojson`, `institutions.json`, `journal_metrics.json`, `linkouts.json`, `methods_flow.json`, `monitoring.json`, `network.json`, `network_metrics.json`, `opc_actions.json`, `open_calls.json`, `pubmed_coverage.json`, `research_networks.json`, `search_index.json`, `topic_bursts.json` (BQ-4.4, schema `bq4-v1`, `scripts/build_topics_json.py`), `topics_timeseries.json` (BQ-4.4, schema `bq4-v1`, `scripts/build_topics_json.py`), `work_text/`, `works_detail.json` | the California pipeline (export, network, search index, policy, funding, monitoring builders) |
| `site/data/global/` | `countries.json` (PLAT-4b Tier B aggregates), `groups/` (Add-on A4 groups layer: `roster.json`, `roster_manifest.json` from `scripts/build_groups_roster.py`; `groups.json`, `groups_tree.json`, `groups_graph.json`, `coverage.json`, `flows.json`, `precision_card.json` from `scripts/build_groups.py`; local-only roster files stay in ignored `data/raw/bffp/` and `data/interim/bffp/`), `graphs/` (BQ-V.1 global graphs: institutions `institutions.json`, `institutions_phone.json`, `layout_institutions.bin`; authors `authors.json`, `authors_phone.json`, `layout_authors.bin`; `graphs_manifest.json`; works `works.json`, `works_phone.json`, `layout_works.bin`, `works_manifest.json` (`scripts/build_global_works_graph.py`); `exports/` GEXF and GraphML downloads from `scripts/build_graph_exports.py`, gzip-only above 5 MB), `pubmed_coverage.json` (BQ-S9b stage 2), `evidence_cells.json`, `explore.json`, `explore_sample.json`, `global_counts.json`, `world_raster.json`, `places.json` (AMB-1 place-search index, `scripts/build_places_index.py`), `quality.json` (BQ-1.4 corpus-quality status for `/quality`, `scripts/build_quality_json.py`; the California copy is in `site/data/california/`, not at the root, as A3 section 7 names it), plus (moved here) `trend_global.json`, `language_probe.json`, `denominators.json` | global builders; the denominator series mixes global series (A, B) with California series (C, D) and is read by both `/explore` and `/california/evidence` |
| `site/data/<slug>/` (region folders: `norway/`, `belgium/`) | `region.json` (REG-1 region page payload, schema `region-v1`; the same file name in every region folder) | `scripts/build_region_pages.py` (`--check` validates and fails when stale; see `docs/REGION_PAGES.md`) |
| `site/data/<slug>/` (every region folder, including `california/`) | `ambassador_institutions.json` (schema `amb-v1`, eligible institutions and domains) and `ambassador_cases.json` (schema `amb-cases-v1`, stream A case queues) | `scripts/build_ambassador_data.py` (`--check` validates and fails when stale; see `docs/AMBASSADORS_SPEC.md`) |
| `site/data/` (root) | `release.json`, `status.json` | site-wide metadata (release pipeline, status) |

Rules:

- Python code gets California's folder from `atlas.regions.scope.region_data_dir()`; do not hard-code
  `site/data/california`. Global files keep their explicit `site/data/global/` paths.
- Front-end code builds data URLs from one helper (California files under `data/california/`), never `data/<file>`.
- The release snapshot packages the top-level JSON of each data folder; the "no abstracts" rule applies to every folder.
