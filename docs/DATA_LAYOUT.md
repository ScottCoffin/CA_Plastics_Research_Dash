# Site data layout (PLAT-3 slice 3b, 2026-11-25)

Owner decision 2026-11-25 (QUESTIONS PLAT3-DATA-PATH): California's data moves from `site/data/` to
`site/data/california/`, a clean break like PLAT-1 (old JSON URLs return 404). Each region writes the same file set
under `site/data/<region>/`; the region registry (`regions/_registry.yml`, field `site_data_dir`) names the folder.

| Folder | Contents | Written by |
|---|---|---|
| `site/data/california/` | `aggregates.json`, `authors/`, `build_metadata.json`, `bundle/`, `dtsc_timeline.json`, `expert_badges.json`, `grants.json`, `index.json`, `institution_works/`, `institutions.geojson`, `institutions.json`, `journal_metrics.json`, `linkouts.json`, `methods_flow.json`, `monitoring.json`, `network.json`, `network_metrics.json`, `opc_actions.json`, `open_calls.json`, `pubmed_coverage.json`, `research_networks.json`, `search_index.json`, `work_text/`, `works_detail.json` | the California pipeline (export, network, search index, policy, funding, monitoring builders) |
| `site/data/global/` | `evidence_cells.json`, `explore.json`, `explore_sample.json`, `global_counts.json`, `world_raster.json`, plus (moved here) `trend_global.json`, `language_probe.json`, `denominators.json` | global builders; the denominator series mixes global series (A, B) with California series (C, D) and is read by both `/explore` and `/california/evidence` |
| `site/data/` (root) | `release.json`, `status.json` | site-wide metadata (release pipeline, status) |

Rules:

- Python code gets California's folder from `atlas.regions.scope.region_data_dir()`; do not hard-code
  `site/data/california`. Global files keep their explicit `site/data/global/` paths.
- Front-end code builds data URLs from one helper (California files under `data/california/`), never `data/<file>`.
- The release snapshot packages the top-level JSON of each data folder; the "no abstracts" rule applies to every folder.
