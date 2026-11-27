# Global parity inventory (GP-0)

Status: inventory only, written 2026-11-26 for ADR-GLOBAL-PARITY-2026-11-26 (TODO section GP). No code, data or
build changed. Every row was checked against the repo files named in it. Where a claim could not be confirmed
from the files, the row says so.

Conventions: "CA" is the California Atlas under `/california/`. "Region-generic" means a view that already works
for any region, or for the global set, through `/explore`, `/norway/`, `/belgium/` or `/quality`. Cost figures
are **estimates** unless marked as repo-verified. OpenAlex prices (repo-verified, `docs/GLOBAL_EXPERTS_ASSESSMENT.md`):
list call USD 0.0001 (1 credit), search call USD 0.001 (10 credits), single lookup free, `/authors` batch of 100
about 1 credit per author.

## 1. Page and view table

Data sizes are from `wc -c` on 2026-11-26 unless marked "est.". Builders are the scripts or modules that write the file.
"Cross-links" lists links that leave the view. Hash state (`#author=`, `#inst=`, `#topic=`) is the URL contract used by the page.

| Route | Feature / view | Cross-links (leaves view → lands) | Data file(s) under `site/data/california/` | Builder script(s) | Region-generic equivalent today | Gap for a region filter | Cost to close (estimate unless marked) |
|---|---|---|---|---|---|---|---|
| `/california/` | Overview: headline counts and charts (`framework/src/california/index.md`) | → every nav page (index.md:14-91) | `build_metadata.json` (320 KB) | `scripts/build_export_site.py` (via `src/atlas/build/export_site.py:1130`) | `/` (global home, `framework/src/index.md`); `/norway/`, `/belgium/` (region.json headline stats) | Region overview charts exist only for CA; region.json has works_by_year and stats | 0 credits; small |
| `/california/authors` | Author list with search and profile panel (`framework/src/components/experts.js`, `experts_model.js`) | List row → classic profile `expert.html#author=` (experts_model.js:230); profile co-authors → `expert.html#author=` (shared/expert_page.js:211); profile institutions → `institution#inst=` (expert_page.js:507) | `authors/<id>.json` (26 MB, 2,680 files), `index.json` (2.8 MB), `institutions.json` (1.3 MB), `expert_badges.json` (46 KB) | `build_export_site.py` (authors/, index.json); `build_expert_badges.py` | `/explore` Authors tab (`components/explore.js`, `explore.json`, 160 KB): list only, no profile; `/norway/` top_researchers (10 names) | No per-region author list or profile route; list is CA-only (`experts.js` loads CA files) | GX-2 `/authors` refresh about 4,000 credits per global refresh; works-by-year about 1 credit per author, 50k-100k one-off for experts above threshold (GX-2 est.). Full profiles at global scale 2-4 GB, so R2 (GX-3) |
| `/california/expert.html` | Classic interactive expert profile (`site/california/expert.html`, hash `#author=`) | → `institution#inst=` (expert_page.js:507); → other experts (expert_page.js:211); badges (expert_page.js:309) | `authors/<id>.json`, `research_networks.json` (2 KB), `institutions.json`, `expert_badges.json` | `build_export_site.py`; `build_research_networks_json.py`; `build_expert_badges.py` | None: no region-agnostic profile route (region.json has no profile data) | GX-4: make the page region-agnostic; it reads CA files or R2 shards | As for `/california/authors`; no new pulls needed for the page itself |
| `/california/network` | Collaboration network and metrics (`network.js`, `network_model.js`, `network_metrics.js`) | Node → `expert.html#author=` (network.js:64); node → `authors#author=` (network.js:69); hash state `#topic=&sector=&inst=&year_from=` (network_model.js:54) | `network.json` (314 KB), `network_metrics.json` (32 KB) | `build_network.py`; `build_network_metrics.py`; `build_graph_exports.py` | `/explore` Network tab (`graphs/authors.json`, `graphs/institutions.json`, `graph_viewer.js`); builders `build_global_graphs.py`, `build_global_works_graph.py` | Global graph exists but has no per-country or per-community slice (GX-7); no node → region profile link | 0 credits (built from the local corpus, PLAT-4). Compute time only |
| `/california/institutions` | Institution list, tiers and map (`institutions.js`, `inst_tiers.js`, `svg_map.js`) | Row → `institution#inst=` (institutions.js:171); top authors → `authors#author=` (institutions.js:157) | `institutions.json` (1.3 MB), `index.json`, `institutions.geojson` (156 KB), `bundle/inst_tiers.json` | `build_institutions.py`; `build_institution_types.py`; `build_export_site.py` (institutions.geojson, aggregates) | `/explore` Institutions tab; `/norway/` top_institutions (list) | No per-region institution list with tiers and map; tier rules are CA-specific | 0 credits (institutions come from the corpus). Pages about 1.5 MB per CA-sized set (est.) |
| `/california/institution` | Institution profile: experts, publications, topics, networks (`institution.js`, `institution_model.js`, hash `#inst=&section=`) | Experts → `authors#author=` (institution.js:235, 333); parent and child institutions → `institution#inst=` (institution.js:262, 307); networks from `research_networks.json` (institution_model.js:261) | `institution_works/<id>.json` (2,259 files, 32 MB), `institutions.json`, `research_networks.json` | `build_export_site.py` (institution_works, line 423); `build_research_networks_json.py` | None | No institution profile for any region (GP-5) | 0 credits. About 14 KB per CA institution (est. from 32 MB / 2,259); global count unknown, so R2 may be needed |
| `/california/monitoring` | Monitoring sites: map, table, CSV (`monitoring.js`, `monitoring_view.js`, `svg_map.js`) | → `glossary#access-tiers` (monitoring.js:404); CSV download | `monitoring.json` (282 KB) | `build_monitoring_export.py`; `src/atlas/build/monitoring.py` | `region.json` `monitoring` section: placeholder text only ("To be confirmed by a local researcher") | Needs each region's own monitoring sources and an adapter per source | 0 OpenAlex credits. Owner and local-source work, not API cost |
| `/california/funding` | Funding Sankey, grants and open calls (`funding.js`, `funding_viz.js`, `funding_viz_model.js`) | CSV download of awards; no other outbound links found in `funding.js` or `funding_viz.js` (verify in GP-7) | `grants.json` (466 KB), `open_calls.json` (279 B); `ca_plastics_awards_filtered.csv` (download) | `build_grants_export.py` (+ `src/atlas/build/grants_export.py`); `build_open_calls.py`; `build_work_grant_links.py` | `region.json` `funding` section: placeholder only | Region funder sources and a Sankey model per region (NOR-1..5 pattern) | OpenAlex funder fields come with the corpus (0 extra, est.). Per-region funder list calls about 1 credit each (est. hundreds of credits per region). Pages: grants about 0.5 MB per CA-sized set |
| `/california/topics` | Topic time series and bursts (`topics_page.js`, `shared/topics.js`) | Topic tags feed the evidence page through `#topic=` (evidence_model.js:48); topics_page.js outbound links not verified | `topics_timeseries.json` (237 KB), `topic_bursts.json` (18 KB) | `build_topics_json.py` | `/explore` Trend tab (`trend_global.json`, `denominators.json`) and Evidence map by topic | Per-region time series and bursts | 0 credits (counts from the corpus). Pages about 0.3 MB per region (est.) |
| `/california/evidence` | Evidence map, work table, flow and trend (`evidence.js`, `ev_heatmap.js`, `ev_table.js`, `v3_flow.js`, `v4_trend.js`) | Hash state `#topic=&ca_led=&year_from=&year_to=&q=` (evidence_model.js:48); work row → DOI, open-access copy, OpenAlex record (ev_table.js:63-68, external); policy → `./evidence#q=` and `#topic=` (policy.js:131, 133) | `works_detail.json` (1.39 MB), `work_text/abstracts.json` (2.5 MB), `journal_metrics.json` (110 KB), `methods_flow.json` (2 KB) | `build_export_site.py` (works_detail, work_text); `scripts/fetch_journal_metrics.py`; `build_methods_flow_json.py` | `/explore` Evidence map tab (`evidence_cells.json`, 1.6 KB; `scripts/fetch_evidence_cells.py`) and Countries tab | No region-filtered work table with abstracts and journal metrics; `ca_led` is CA-specific | 0 OpenAlex credits (local partition, PLAT-4). Journal metric source per region: est. 0 to a few hundred credits. Pages: about 0.7 KB per work in works_detail and 1.2 KB per abstract (est.), so about 260 MB at global scale (136,086 works in PLAT-4a) |
| `/california/policy` | Policy tracker: DTSC timeline and OPC actions (`policy.js`) | Item → `./evidence#q=` and `#topic=` ("In the Atlas", policy.js:131-133, 181); source and law links, external (policy.js:81, 174, 178) | `dtsc_timeline.json` (4 KB), `opc_actions.json` (10 KB) | `build_dtsc_timeline_json.py` (+ `src/atlas/dtsc_timeline.py`); `build_opc_actions_json.py`; `scripts/review_opc_mapping_app.py` | `region.json` `policy` section: placeholder only | Region policy sources and item-to-work mapping; current sources are CA-only | 0 credits. Owner or local-researcher curation; if more than 10 cases need review, use a Streamlit review app (CLAUDE.md rule) |
| `/california/quality` | Quality and prediction page (`quality.js`) | Not checked for outbound links | `quality.json` (3 KB) | `build_quality_json.py` (writes both CA and global); `build_quality_predictions.py` | `/quality` (`framework/src/quality.md`), `site/data/global/quality.json` | Region filter on `/quality`; needs per-region prediction CSVs | 0 credits; negligible Pages |
| `/california/resources` | Related resources and linkouts (`resources.js`) | → `institution#inst=` (resources.js:63) | `linkouts.json` (10 KB) | `build_linkouts_json.py` (+ `src/atlas/linkouts.py`) | None | Curated list per region | 0 credits (curation by owner or ambassadors) |
| `/california/search` | Search across authors, institutions, topics, funders, glossary, resources (`search.md`; header form `./search`, `framework/observablehq.config.js:117`) | Results → any profile or page (loader not located in `framework/src/components`; verify before GP-10) | `search_index.json` (305 KB) | `build_search_index.py` (+ `src/atlas/build/search_index.py`) | None on the main site; global search across regions is planned as PLAT-5 (`docs/PLATFORM_ARCHITECTURE.md:150`) | Region-filtered search; sharded index for global size (GX-3) | 0 credits. Global index is est. hundreds of MB, so shard it and put it on R2 |
| `/california/glossary` | Glossary of terms (`glossary.md`, static) | Terms are linked from monitoring (monitoring.js:404) | none | none (static page) | None | No region pages link to it | 0 |
| `/california/about` | About, methods flow, release and pipeline health (`about.md`, `about_flow.js`) | → classic `status.html` and `feed.xml` (about.md) | `build_metadata.json`, `methods_flow.json`; root `release.json` | `build_export_site.py`; `build_methods_flow_json.py`; `build_release_snapshot.py` | Root `/status.html` (classic, `build_status_page.py`); global index metadata | Region-aware methods text | 0 credits |
| `/california/styleguide` | Internal design reference (`styleguide.md`) | None needed | none | none | None | Not a user feature; exclude from parity | 0 |
| `/california/experts/<id>/`, `/california/institutions/<id>/` | Static SEO entity pages and sitemaps (deploy only, gitignored) | Interactive link `expert.html#author=` (`src/atlas/build/seo.py:283`) | reads `index.json`, `institutions.json`, `build_metadata.json` | `scripts/build_seo_pages.py` → `src/atlas/build/seo.py` (`REGION_PATH = "/california"`, seo.py:32) | None (GX-5 plans top-N person pages) | Region-aware SEO pages and sitemap shards | 0 credits. Pages budget: top N about 150 MB (GX-5 est.) |
| `/california/feed.xml` | Atom feed (classic) | Feed items → CA pages | feed built from `grants.json`, `index.json` | `scripts/build_feed.py` (+ `src/atlas/build/feed.py`) | Root `/feed.xml` (site/feed.xml) | Per-region feed | 0 credits |

Classic pages that are retired at the root (`app`, `grants.html`, `sem.html`, `expert.html`, `experts`, `institutions`)
are removed by `src/atlas/build/assemble.py:34` with no redirects. The CA `expert.html` survives under `/california/`.

## 2. Cross-navigation graph

| Link type | Where it is implemented | Lands on |
|---|---|---|
| Author list row → profile | `framework/src/components/experts_model.js:230` (`expert.html#author=`) | Classic CA profile (`site/california/expert.html`) |
| Co-author name in a work → profile (if the co-author is an expert) | `framework/src/components/shared/expert_page.js:211` | Classic CA profile |
| Network node → profile or Framework author view | `components/network.js:64` (classic), `:69` (`authors#author=`) | Same |
| Institution profile → author | `components/institution.js:235`, `:333` (`authors#author=`) | `/california/authors` |
| Institution ↔ institution (parent, child) | `components/institution.js:262`, `:307` (`institution#inst=`) | `/california/institution` |
| Author → institution | `components/shared/expert_page.js:507` | `/california/institution` |
| Institutions list → profile or author | `components/institutions.js:171`, `:157` | Same |
| Resources → institution | `components/resources.js:63` | `/california/institution` |
| Topic tag → filtered works | Hash contract `#topic=…&ca_led=…&q=` (`components/evidence_model.js:48`) | `/california/evidence` |
| Network filter → topic, sector, institution | Hash contract (`components/network_model.js:54`) | `/california/network` |
| Institution sections | Hash contract `#inst=&section=` (`components/institution_model.js:21`) | `/california/institution` |
| Policy item → works (search or topic) | `components/policy.js:131`, `:133`, `:181` | `/california/evidence#q=` or `#topic=` |
| Monitoring term → glossary | `components/monitoring.js:404` | `/california/glossary` |
| Work → DOI, OA copy, OpenAlex record | `components/ev_table.js:63-68` (external) | Outside the Atlas |
| Explore authors and institutions → OpenAlex | `components/explore.js:746`, `:754` (external) | Outside the Atlas |
| Header search → search page | `framework/observablehq.config.js:117` (`./search`) | `/california/search` |
| Explore region menu → California (the only live atlas) | `framework/src/explore.md:37-42` (`./california/`); Norway page menu links `../california/` (`framework/src/norway/index.md`) | `/california/` |
| SEO entity page → interactive profile | `src/atlas/build/seo.py:283` | Classic CA profile |

Not found in the files read: outbound links from the funding Sankey (`funding.js`, `funding_viz.js`) and from
`quality.js`. The Sankey may be non-navigable today. GP-7 must confirm this before it promises parity.

## 3. Biggest gaps

1. **No region-generic profile layer.** Authors and institutions have profile pages only for CA (`expert.html`,
   `/california/institution`). Global views (`/explore`) list people and organisations but do not open a profile.
   This blocks GP-2, GP-3 and GP-5 and the author ↔ work ↔ institution links.
2. **Region-specific data sources.** Policy, funding and monitoring are CA-only. `region.json` has placeholder
   sections for them, so a region filter would show "to be confirmed" rather than the CA view. These need
   owner or local-researcher input; API cost is near zero.
3. **Scale and hosting.** Per-author files for all global authors are estimated at 2-4 GB (GX assessment). That
   exceeds the Pages budget (1 GB site), so full profiles and the search index need R2 (GX-3). GitHub's hard limit
   is 100 MB per file (docs/PLATFORM_ARCHITECTURE.md), but the project's own hosting rule (G-HOST, decided
   2026-11-10) keeps a file on Pages only while it is at most 25 MB; larger files move to R2.

## 3b. Port design: region exports in the California schema (lead, 2026-11-26)

The California components already read their data through `regionDataUrl()` (`framework/src/components/atlas.js`), which is hard-wired to `data/california/`, and `siteRoot()` already understands `/norway/` and `/belgium/` page depth. So the port reuses the components instead of rewriting them:

1. **Region-aware data URL.** `regionDataUrl()` takes the region from the page path (`/california/`, `/norway/`, `/belgium/`, later any registry slug) and defaults to California, so every California URL stays byte-identical (GP-1 gate).
2. **Region export.** A builder writes California-schema payloads for a registry region from the local global partition (`data/processed/global/works.parquet`, `work_regions.parquet`, and the PLAT-4 slice 4 `authorships.parquet` / `institutions.parquet`): `index.json` (works and authors), `institutions.json`, `institution_works/<id>.json`, author files, and the aggregates each page reads. Fields that need California-only inputs (paid author metrics such as h-index and m-quotient, California relevance review, ca_basis) are null, and every payload says the works are unscreened query hits.
3. **Thin region pages.** `framework/src/<region>/institutions.md`, `institution.md`, `authors.md` and the works views mount the same components, so the features, links and hashes (`#inst=`, `#author=`, `&section=`) match California.
4. **Scale.** Norway and Belgium are small (about 1,300-1,400 works each), so their full profiles fit in Pages now. Every-country scale still needs GX-2..GX-4 and R2 (GX-3); this design does not wait for them.

Order: GP-5 (institutions) first, then GP-2 (authors, registry regions), GP-4 (tags and cross-navigation), GP-8 (works and evidence map). Each slice runs `scripts/check_gp1_contract.py` before and after.

GP-10a adds `/norway/topics`, `/belgium/topics`, and a search page and index for each region.
After refreshing the region exports, run `scripts/build_topics_json.py --region <slug>` and
`scripts/build_search_index.py --region <slug>`. Both support `--check` on committed inputs.
The topic share denominator is the unscreened query hits in the region and year. Co-occurrence
uses complete years. The rising-share screen uses the available rule labels and institution
affiliations. Regional owner and model labels and analytic lenses are unavailable. Search indexes
regional pages, published author profiles, institutions, and topics. Topic results open the
regional author list with the tag selected. California retains its own published search index.

## 4. Slice plan (proposed GP-2..GP-10, owner's order)

Each slice must pass the GP-1 California contract unchanged: route list, DOM smoke for each page, link-graph check
(every author, institution and work link resolves), screenshots at 1440 and 390 px, and count checks against
`site/data/california/` (for example 2,680 author files, 2,259 institution files, `network.json` node and edge counts).

| Slice | What it builds | Data it needs | Depends on | Size | California regression checks |
|---|---|---|---|---|---|
| GP-2 Author list and profile per region | Region-agnostic author list and profile (replaces CA-only `experts.js` loads); full profiles on R2 | Global works (PLAT-4), `/authors` records (GX-2), per-expert shards (GX-3), GX-4 expert page | PLAT-3, PLAT-4, GX-2, GX-3, GX-4 | L | Author count and profile sections unchanged; `expert.html#author=` deep links resolve; badges still show; SEO pages unchanged |
| GP-3 Author network per region | Per-region collaboration network and metrics (GX-7 slices) | Local co-author graph from PLAT-4; `network_metrics` rules | GP-2, GX-7, PLAT-4 | M | `network.json` and `network_metrics.json` keys and counts unchanged; node → profile links resolve |
| GP-4 Paper tags and cross-navigation | Work cards with tags; work ↔ author ↔ institution ↔ topic links on the region view | Works with tags; author and institution IDs | GP-2, GP-3, GP-5 | M | Evidence hash state (`#topic`, `#q`, `ca_led`) round-trips; full link-graph check passes |
| GP-5 Institutions per region | Institution list, tiers and map; profile with experts, publications, topics | Institution partition by predicate (PLAT-3); `institution_works` shards | PLAT-3, PLAT-4 | L | `institutions.json` and `institution_works` file counts (2,259); section hashes unchanged |
| GP-6 Policy tracker per region | Policy timelines and actions for each region, with links into the region's evidence view | Region policy sources (owner or local researchers); item-to-work mapping | PLAT-3, GP-4, owner data | M (code), owner-gated (data) | `dtsc_timeline.json` and `opc_actions.json` render the same; "In the Atlas" links resolve |
| GP-7 Funding Sankey per region | Sankey and grants per region using region funder adapters | Funder fields from the corpus; per-region funder sources (NOR-1..5 pattern) | PLAT-4, NOR-1..5 | L | `grants.json` totals; Sankey node and link counts; awards CSV unchanged; confirm or add outbound links |
| GP-8 Evidence map and works table per region | Region-filtered evidence map, work table with abstracts and journal metrics | Local partition (PLAT-4); journal metrics | PLAT-4, GP-4 | M | `works_detail.json` row count; abstracts; journal metrics; `ca_led` filter unchanged for CA |
| GP-9 Monitoring per region | Monitoring sites, map and CSV per region | Region monitoring sources (one adapter each); owner-supplied | PLAT-3; owner data | L | `monitoring.json` dataset and sample counts; map at 1440 and 390 px |
| GP-GROUPS Community groups in the main app (owner 2026-11-26) | Map first on /groups with /explore-style drill-down (World > continent > country > region) and every groups view responding to the scope; per-region progress list below the map; the /explore shell, scope ladder and styling instead of the separate groups look | `roster.json`, `groups.json`, `coverage.json`, `groups_graph.json`, `flows.json` (all `site/data/global/groups/`), `site/assets/world/world.json` | GP-1, CG-12, CG-12b, GA-1..GA-3 | L | GP-1 unchanged (no California route changes) |
| GP-10 Topics, quality, resources, search, about, feed, SEO | Region filter on topics, quality, resources, search, about, feed; top-N SEO pages | Topic series, quality predictions, search index (sharded), link lists | GP-2 (SEO), PLAT-5 (global search) | M | `topics_timeseries.json` and `topic_bursts.json`; `search_index.json` results; sitemap entries |

Overall: about 9 slices, four of them L. The first two (GP-2 and GP-3) carry most of the cost and most of the R2
decision. GP-6, GP-7 and GP-9 depend on owner-supplied sources, so they should start as soon as the owner names
the first region's sources.

## GP-1 contract (California regression gate)

Every GP slice must leave the California atlas unchanged. `scripts/check_gp1_contract.py` checks the
recorded contract in `config/gp1_california_contract.json` (schema `gp1-v1`, recorded 2026-11-26):

- **Routes**: the 16 Framework pages in `framework/src/california/*.md` plus the classic `california/expert.html`
  must exist in the assembled site.
- **DOM smoke** (headless Chromium, served on 127.0.0.1 on a free port; every other request is aborted):
  each page returns HTTP 200 with no `pageerror`, its root selector reaches the recorded minimum count
  (80% of today's count), its `<main>` text reaches its minimum length, and there is no horizontal
  overflow at 390 px.
- **Link graph** (offline, from `data/california/`): every author, institution and work reference that the
  UI turns into a link resolves. Broken links must be 0 (or listed in the contract `allowlist`).
  Co-authors who are not in the atlas index are plain text and are reported as "unlinked by design".

Before and after each GP slice (about 1 minute; needs Node for the build and Playwright Chromium):

```bash
cd framework && npm run build && cd ..
py -3.14 scripts/assemble_site.py --site site --dist framework/dist --out scratch/gp1_site
py -3.14 scripts/check_gp1_contract.py --site scratch/gp1_site --screenshots scratch/gp1_shots
```

Run the first command before the slice to confirm the baseline passes, and again after it. Compare the
screenshots in `scratch/gp1_shots/` (`<page>-1440.png` and `<page>-390.png`) by eye. `--links-only` runs the
link graph alone without a browser. `--record` rewrites the contract; use it only for an intended California
change, and say why in the commit. A failing run exits 1 and lists each problem. The unit tests are in
`tests/test_gp1_contract.py` and do not need a browser.

Baseline (2026-11-26, the assembled site from the working tree at commit 484a07ad): 17 routes; 257,265 links
checked, 0 broken, 154,427 unlinked by design; runtime about 50 s in the browser and 2.5 s for the link graph.
