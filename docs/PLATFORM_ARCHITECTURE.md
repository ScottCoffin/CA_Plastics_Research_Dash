# Plastiverse platform: one engine, many regions

Status: proposal, 2026-11-17. Decisions recorded by the owner on 2026-11-17: one monorepo;
California moves to `plastiverse.live/california` with a clean break (old URLs are not kept);
the root becomes a global landing page; Norway (`/norway`) is the next MVP with publications and
experts, funding, monitoring and policy; weekly email digest through Buttondown.

Audience: the owner and the agents that will build it. Items marked [VERIFY] are unconfirmed and
must be checked against the source before any public text uses them.

## 1. Goals and constraints

- Many regions, possibly thousands (countries, states and provinces, the EU, river basins). One
  engine serves them all, so a fix or new feature lands everywhere at once.
- A few regions are curated in depth (California, Norway). The rest get an automatic profile
  from shared open data.
- The site stays static: no application server and no database to operate. Daily jobs run in
  GitHub Actions; data ship as JSON and Parquet files.
- The free OpenAlex plan caps spending at USD 1 per key per day. Since 2026-11-16 the
  `from_updated_date` filter is paid (`docs/api_notes/openalex_plan_limits.md`).
- One design system (Plane Poster). Each region gets its own silhouette and one accent colour;
  the four task colours keep their meaning everywhere.

## 2. The key idea: ingest once, partition locally

Today the daily ingest asks OpenAlex for plastics works *with a California author*. Repeating
that per region would multiply credits by the number of regions, which is impossible at
thousands of regions.

Instead:

1. **One global ingest.** Run the reviewed plastics query (`config/queries.yml`) with no
   geographic filter, incrementally by publication date with the adaptive lookback already in
   place. The global plastics corpus is roughly 100,000 works [VERIFY: count with one
   `group_by` call]. A one-off backfill is about 1,000 pages (about USD 1, spread over two days);
   a normal day is a few pages.
2. **Partition locally.** Every authorship carries institution countries, ROR IDs, and raw
   affiliation strings. A region is a *predicate* over authorships: country code, ROR
   `country_subdivision_code` or `geo.region`, or raw-affiliation place names from a gazetteer.
   Assigning a work to every region it touches is a local DuckDB join and costs nothing.
3. **Region-specific enrichment** (funders, monitoring, policy, hand-made overrides) runs only
   for curated regions.

So 1 region and 5,000 regions cost the same in OpenAlex credits. Compute grows with regions
(local joins and file writes), not with API calls.

## 3. Region tiers

| Tier | Example | What it gets | Who maintains it |
|---|---|---|---|
| **A, curated** | California, Norway | Full site: experts, network, institutions, evidence map, funding, monitoring, policy, digest, SEO pages | Region config + source adapters + owner review |
| **B, automatic** | Every country; US states; Canadian provinces; EU | Publications, experts, institutions, network, trend and topic map, from the global corpus only | Generated from a registry (no hand work) |
| **C, indexed** | Any place with fewer than N works | A card on the global page and a search result, rendered client-side from the global index | Nothing |

A region is promoted from B to A by adding a config folder and adapters. Nothing is forked.

## 4. Repository layout (monorepo)

```
src/atlas/                 engine (Python): ingest, normalize, label, partition, export
  regions/                 region registry + predicates (new)
  adapters/                source adapters by kind (funding/, monitoring/, policy/) (new;
                           today's California adapters move here unchanged)
regions/
  _registry.yml            every region: slug, name, tier, parent, predicate, status
  california/              Tier A: region.yml, queries overrides, adapters list, overrides CSVs,
                           policy timelines, palette.json, outline.geojson
  norway/                  Tier A (MVP)
framework/src/             ONE Framework app
  index.md                 global landing (plastiverse.live/)
  [region]/*.md            parameterized pages (Framework 1.13 dynamic routes via `dynamicPaths`)
  components/              shared components; read the region from the URL path
site/data/
  global/                  global index, counts, region list, map
  <region>/                same file set per region (index.json, works_detail.json, ...)
```

Rules:

- **No region names in engine code.** Everything California-specific (the 44 modules that name
  California today: `RAW_AFFILIATION_TERM = "California"`, `ca_polygons`, RWQCB regions, CA Sea
  Grant, OPC, CEDEN, DTSC) moves behind region config or into `regions/california/` adapters.
  A test greps `src/atlas` for region names and fails on new ones.
- **One schema for every region.** Each Tier A or B region writes the same files with the same
  schema. The front end never branches on the region; it reads `site/data/<region>/` and hides
  panels whose file is absent (Tier B has no funding file, so no Funding page).
- **Adapters are plugins.** An adapter declares its kind, its output schema (the existing grants,
  monitoring and policy schemas) and its licence. A region lists the adapters it uses. Shared
  adapters (EU CORDIS, NIH, NSF, OSPAR) serve several regions.

## 5. Front end

- One Framework app. Region pages are parameterized routes: `/california/experts`,
  `/norway/experts`. Framework pre-renders each listed path at build time
  (`dynamicPaths` returns Tier A and B slugs). Data load from `/data/<region>/`.
- Thousands of pages: pre-render Tier A plus Tier B regions above a work threshold; Tier C
  uses one generic page (`/region?r=<slug>`) that renders client-side from the global index.
- Hosting: GitHub Pages has a 1 GB site limit and 100 MB files. California alone is 67 MB of data.
  At Tier B scale, data move to the Cloudflare R2 bucket already verified at
  `data.plastiverse.live`, CORS widened to `plastiverse.live`; pages stay on GitHub Pages.
- Design: the Plane Poster system is shared. Per region:
  - **silhouette**: the region outline cut into the four task planes, generated from
    `outline.geojson` by `scripts/build_design_motif.py`;
  - **accent**: one regional colour for eyebrows and the hero rule;
  - **the task colour law stays fixed** (researchers vermilion, monitoring indigo, funding gold,
    evidence ink).
  - Norway proposal: the fjord-indigo monitoring plane, a cold paper tone, and a Nordic red
    accent close to the flag red, checked for WCAG contrast. Mainland and Svalbard are drawn as
    separate planes.
- Search, glossary, About and methods are shared. Region text comes from `region.yml`.

## 6. Global landing page (plastiverse.live/)

A living page about research on the environmental impacts of plastics and microplastics:

- **Hero:** a world map in the Plane Poster style. Countries are shaded by plastics works
  (global corpus), and live regions are marked.
- **Live global numbers:** works, countries, institutions, the year trend
  (`trend_global.json` already exists), and new works this week.
- **Region doors:** California (live), Norway (MVP), and "next" regions. Each is a card with its
  silhouette.
- **This week in plastics research:** the latest global works, with a link to the weekly digest.
- **Get updates** (feed, ntfy, email) and links to Plastiverse tools.

Design is done with the Impeccable workflow (shape, then craft) before building (PLAT-2).

## 7. Norway MVP scope (proposed sources, all [VERIFY])

| Area | Candidate sources | Notes |
|---|---|---|
| Publications, experts | Global corpus with a Norway predicate (country code NO; ROR subdivisions for fylker) | Add Norwegian query terms (mikroplast, plastforurensning) for titles and abstracts in Norwegian |
| Institutions | ROR (country NO), OpenAlex institutions | Includes research institutes (NIVA, NILU, SINTEF, Akvaplan-niva, NORCE, Havforskningsinstituttet) |
| Funding | Research Council of Norway project bank (Prosjektbanken); EU CORDIS projects with Norwegian partners; Handelens Miljøfond (retailers' environmental fund, a major plastics funder) | CORDIS is a shared adapter reusable for every EU or EEA region |
| Monitoring | Norwegian Environment Agency monitoring programmes and the Vannmiljø database; MOSJ (Svalbard); MAREANO seafloor litter; OSPAR beach litter for Norwegian beaches | Licence review per source, as in California (S7.2) |
| Policy | Norway's national plastics strategy; EU and EEA rules (single-use plastics directive, REACH microplastics restriction); UN plastics treaty negotiations | Hand-curated timeline like the DTSC timeline |
| Geography | Kartverket place names and boundaries; Norwegian territorial waters and EEZ | Replaces the CA gazetteer and state-waters polygon |
| Language | English interface first; Norwegian strings later (i18n file per region) | |

## 8. Phased plan

| Phase | Task | Outcome |
|---|---|---|
| P0 | PLAT-0 this document; owner review | Agreed architecture |
| P1 | PLAT-1 move California to `/california` (clean break), root free for the global page | Same site at the new path |
| P1 | MAIL-1 weekly Monday digest (Buttondown), NOTIFY-AB feed panel and ntfy | Updates channels |
| P2 | PLAT-2 global landing design (Impeccable) and build | plastiverse.live/ live |
| P3 | PLAT-3 region abstraction: registry, `--region` on every pipeline command, `site/data/<region>/`, dynamic routes; California as the first region with no visible change | Engine ready for a second region |
| P3 | PLAT-4 global ingest + local partition (backfill over two days within the daily budget) | Every country gets Tier B data |
| P4 | NOR-1..NOR-5: Norway predicate and terms, institutions, funding adapters, monitoring (licence review), policy timeline | /norway MVP |
| P5 | PLAT-5 Tier B pages for the top regions; R2 data hosting; global search across regions | Scale-out |

Each phase is a set of normal TODO tasks with acceptance checks. The California site must pass
its existing tests unchanged after PLAT-3 (regression gate).

## 9. Risks

- **Moving 44 modules behind region config** is the largest change. Do it behind the existing
  test suite, with California byte-identical outputs as the gate.
- **Clean break:** search engines drop the old URLs. Resubmit the sitemap in Search Console after
  PLAT-1.
- **Global corpus quality:** the query was tuned on California works. Precision in other
  regions and languages needs a labelled sample per Tier A region.
- **Credits:** the global backfill must be split across days by the budget guard. Never use
  paid filters.
- **Licences:** each new monitoring or funding source needs the same rights check as S7.2
  before rows are published.

## 10. Region registry (PLAT-3 slice 1)

Slice 1 adds the registry only. No pipeline, export, site or Framework behaviour changes.

- `regions/_registry.yml` lists every region: `slug`, `name`, `tier` (`root`, `A`, `B`, `C`),
  `parent` (slug or null), `status` (`active`, `planned`, `retired`) and `predicate`
  (null for `root`, required otherwise). It has `schema_version: 1`.
- `regions/california/region.yml` holds the California site path (`/california/`), the
  current data directory (`site/data/`), the outline asset (`site/assets/ca_boundaries.geojson`)
  and an inventory of the California-specific adapters that exist today. Nothing moves yet.
- `src/atlas/regions/registry.py` provides the `Predicate` and `Region` dataclasses and
  `load_registry(path)`, `get_region(slug)` and `regions(tier=None)`. Validation is strict:
  unknown or missing keys, duplicate slugs, unknown parents, bad tiers or statuses, and
  malformed predicates all raise `ValueError`. Nothing calls the loader yet.
- `tests/test_regions_registry.py` loads the real registry and checks it against tmp-path
  fixtures.
- `tests/test_region_names_ratchet.py` counts region-name terms (`California`, `Californian`,
  `RWQCB`, `CEDEN`, `DTSC`, `OPC`, `Sea Grant`) per `src/atlas/**/*.py` file, excluding
  `src/atlas/regions/`. It compares the counts with `tests/fixtures/region_names_baseline.json`.
  A file may not gain matches and a new file may not contain any. Counts may fall. To lower
  the baseline after removing names, run `py -3.14 tests/test_region_names_ratchet.py --write-baseline`.

The California predicate describes today's behaviour and cites each source in a comment in
`regions/_registry.yml`. It has these fields:

| Field | Meaning today | Source |
|---|---|---|
| `openalex_institution_filter` | `geo.region:California`, the exact OpenAlex filter for the institution seed | `src/atlas/ingest/institutions.py` |
| `ror_subdivision_codes` | `CA`, the GeoNames `country_subdivision_code` on a ROR location | `src/atlas/ingest/institutions.py` (`_ror_location`) |
| `country_codes` | `US` | `src/atlas/ingest/normalize.py` (institution `ca_flag`) |
| `institution_region_names` | `California`, matched against the institution `region` | `src/atlas/ingest/institutions.py`, `normalize.py` |
| `raw_affiliation_terms` | the search term `California` and the strict affiliation patterns | `src/atlas/ingest/openalex.py`, `src/atlas/ingest/normalize.py` |
| `ca_basis_values` | `registry`, `raw_affiliation`, `author_carry_forward`, `escholarship` | `src/atlas/ingest/normalize.py` |

Later slices:

- **Slice 2:** `--region` on the pipeline commands reads the registry. The default stays `california`.
- **Slice 3:** the outputs move to `site/data/<region>/`. California outputs must stay byte-identical,
  and `regions/california/region.yml` `data_dir` changes to `site/data/california/`.
- **Slice 4:** Framework dynamic routes (`[region]/*.md`) read the region from the URL.
