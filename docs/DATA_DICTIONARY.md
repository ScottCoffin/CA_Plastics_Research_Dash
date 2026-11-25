# Data dictionary: public site payloads (S10.2)

Prepared 2026-11-10 for owner sign-off through `docs/GOVERNANCE_CHECKLIST.md`.
This page describes every public file under `site/data/` (California in `site/data/california/`, global
series in `site/data/global/`, `release.json` and `status.json` at the root) and the Atom feed at
`site/feed.xml`. Field names are taken from the committed exporters
(`src/atlas/build/export_site.py`, `grants_export.py`, `monitoring.py`,
`status.py`, `feed.py`) and the S3.1 contract in `docs/SITE_DATA.md`.

Conventions used below:

- Types are JSON types. `string (ISO date)` is a `YYYY-MM-DD` or ISO-8601 UTC string.
- Every JSON payload carries `schema_version` (`"s3.1"` for the S3 exports) and a
  UTC `generated_at` timestamp where listed.
- `null` means the value was not recorded or not verified. The exporters never
  infer a missing value.
- "Plastic-related", "CA-led" and "CA-sampled" are definitions in the site
  About tab. Labels are provisional screening metadata (see `docs/LABELING_GUIDE.md`),
  not validated classifications.

## Licence summary

The licence column gives the basis as recorded in the repository. No row is a
licence grant by this document. The site-wide derived-data licence is
**not yet confirmed**: ADR-002 sets CC BY for derived data "when upstream source
licenses allow it", and `docs/REUSE.md` records OpenAlex as unknown. See the
checklist for the owner decision.

## Files

### `site/data/california/index.json`

Purpose: slim browse index for the Experts view (works and authors).
Top-level keys: `schema_version`, `generated_at`, `counts`, `works` (array), `authors` (array).
Licence: derived from OpenAlex metadata; OpenAlex licence recorded as unknown in `docs/REUSE.md`. Owner decision pending.

`counts` keys: `authors`, `ca_institutions`, `institutions`, `labeled_works`, `works` (integers).

`works[]` row fields:

| Field | Type | Meaning |
|---|---|---|
| `work_id` | string | OpenAlex work identifier (stable atlas key). |
| `title` | string | Work title as supplied by OpenAlex. |
| `year` | integer | Publication year. |
| `type` | string | OpenAlex work type. Used as a prior only. |
| `author_ids` | array of string | OpenAlex author identifiers on the work. |
| `institution_ids` | array of string | Atlas institution identifiers on the work. |
| `ca_any_author` | boolean | Any author affiliation resolves to a California institution. |
| `ca_led` | boolean | First-author affiliation resolves to a California institution. |
| `cited_by_count` | integer | OpenAlex citation count. Shown as a field only; not used for ranking. |
| `duplicate_work_ids` | array of string | OpenAlex IDs of near-duplicate works (same normalized title with publication years within 1, e.g. preprint and article) collapsed into this kept work during S2.2 normalization. Empty when none. |
| `domain_tags` | array of string | Provisional topic domain tags. |
| `facet_tags` | array of string | Provisional matrix/facet tags. |
| `plastic_related` | boolean | Provisional plastic-related label. |
| `plastic_tier` | string | Provisional tier label. |
| `study_type` | string | Provisional study-type label. |
| `needs_review` | boolean | Row is flagged for owner review. |

`authors[]` row fields:

| Field | Type | Meaning |
|---|---|---|
| `author_id` | string | OpenAlex author identifier (atlas key). |
| `name` | string | Display name as supplied by OpenAlex. Disambiguation may be wrong (see `docs/PRIVACY_REVIEW.md`). |
| `orcid` | string or null | ORCID URL as supplied by OpenAlex when present. |
| `work_count` | integer | Number of tagged works. This is the prominence measure; it is not a performance ranking. |
| `ca_works_count` | integer | Number of those works that are California-connected. |
| `first_year`, `last_year` | integer | Year range of indexed works. |
| `domain_tags` | array of string | Domain tags across the author's works. |
| `institution_ids` | array of string | Atlas institution identifiers in the author's affiliation history. |
| `work_ids` | array of string | Work identifiers in the index. |
| `current_in_ca` | boolean or null | True when any latest (primary) affiliation is a California registry institution; false when none is (OpenAlex country code "CA" is Canada, so only the registry decides); null when unknown. |
| `last_ca_year` | integer or null | Latest year OpenAlex lists the author at a California registry institution. |

Internal, not exported: the normalized authorships table
(`data/processed/normalized/authorships.parquet`) is not in `site/data/`. Its
`author_id_source` column records where each `author_id` came from.

| Field | Type | Meaning |
|---|---|---|
| `author_id_source` | string | `openalex` (OpenAlex supplied the ID); `curated` (`curation/author_attach.csv`); `orcid` (ORCID index or `curation/orcid_author_ids.csv`); `name_institution` (the only known ID with the same full name at a shared institution); empty when no ID could be filled. Authorships with an empty `author_id` are not experts. |

Internal, not exported: the normalized works table
(`data/processed/normalized/works.parquet`) is not in `site/data/`. Its `pmid` column is the
PubMed join key for the PubMed coverage check (BQ-S9).

| Field | Type | Meaning |
|---|---|---|
| `pmid` | string or null | PubMed ID digits (for example `35862566`) from OpenAlex `ids.pmid`, which OpenAlex gives as a PubMed URL; the URL prefix is stripped. Null when OpenAlex has no `ids.pmid` or the value is not digits. Nullable. |

### `site/data/california/authors/<author_id>.json`

Purpose: one detail document per author for the Experts drawer.
Top-level keys: `schema_version`, `author` (object), `works` (array).
Licence: as `index.json`. These files are present for each indexed author.

`author` object: the same fields as an `authors[]` row in `index.json`.

`works[]` row fields (full work record): `work_id`, `title`, `year`, `pub_date`
(string, ISO date or null), `type`, `journal` (string), `doi` (string), `abstract`
(string, as supplied by OpenAlex), `author_ids`, `institution_ids`, `ca_any_author`,
`ca_led`, `cited_by_count`, `is_oa` (boolean), `oa_status` (string), `oa_url` (string),
`license` (string, as recorded by OpenAlex or null), `last_updated` (string, ISO date),
`openalex_topics` (array of string), `primary_topic` (string), `domain_tags`,
`facet_tags`, `plastic_related`, `plastic_tier`, `study_type`, `needs_review`,
`authors` (array of `{id, name}` in byline order, first 20 authors; `id` may be empty),
`author_count` (integer, all authors), `author_institution_ids` (this author's own institutions).
`profile` (optional): ORCID biography, keywords and links, plus `photo` (`thumb_url`, `license`,
`credit`, `source_url`) for owner-approved photos; local photos live in `site/assets/experts/`.

### `site/data/california/network.json`

Purpose: expert collaboration network page (`/network`; sigma.js renderer since 2026-11-13). Top-level keys: `schema_version`,
`generated_at`, `method` (edge weight, community and layout methods, networkx version),
`communities` (count), `community_labels`, `nodes`, `edges`. `community_labels[]` (since schema
`s9.4-v1.1`, VD-20): `community`, `size`, `institution` (`{name, share}` or null: the most common
primary affiliation, kept at share >= 0.35 and >= 2 members), `topic` (`{tag, share, lift}` or null:
the most over-represented topic with community share >= 0.4 and lift >= 1.15); communities with
fewer than 4 members are not labelled. Node fields: `id` (author_id), `name`, `x`, `y` (seeded
ForceAtlas2 layout since VD-20, scaled to [-1, 1]),
`community`, `degree`, `strength`, `plastic_works`, `topics` (top tags of the expert's
plastic-related works), `institution_ids`, `institutions`, `sectors`, `primary_affiliations`,
`current_in_ca`. Edge fields: `source`, `target`, `weight` (co-authored plastic-related works),
`years` (weight per year). Licence: as `index.json`. Written by `scripts/build_network.py` from
`index.json` and `institutions.json`; `--check` fails when stale. The daily ingest rebuilds it
(networkx is a declared dependency since 2026-11-13).

### `site/data/california/network_metrics.json`
Purpose: collaboration-structure metrics (BQ-3.2, Add-on A3 §7 Module 3). Written by `py -3.14 scripts/build_network_metrics.py` from `index.json`, `institutions.json` and `build_metadata.json` (offline). `--check` fails when stale and ignores `generated_at`. Top-level keys: `schema_version` (`bq3-v1`), `generated_at`, `source` (`index_build_timestamp`), `method`, `ascertainment_note`, `definitions` (plain-language text per metric), `corpus` (`plastic_related_works`, `works_in_year_windows`, `works_before_2011`, `works_without_year`, `works_with_no_california_author`) and `graphs` (`authors` = G-A and `institutions` = G-I; each has `label`, `unit` and `windows`). A window has `window` (`all`, `2011-2015`, `2016-2020`, `2021-2025` or `2026`), `years`, `partial` (true for 2026), `works`, `nodes`, `edges`, `components`, `components_with_edges`, `giant_component_nodes`, `giant_component_share`, `density`, `average_clustering`, `isolates`, `isolate_share`, `degree` (`min`, `p25`, `median`, `p75`, `p90`, `max`), `communities`, `modularity`, and `cross_institution`, `cross_sector`, `out_of_region` (each `{fraction, edges_considered}`). Edge weight is the number of works on which both ends are listed. Top-level `null_model` (BQ-3.3, added in the same schema `bq3-v1`; absent when `--null-replicates 0`): `replicates`, `seed` (42), `method`, `reading` and `limits` (plain-language text), `graphs` (`authors` and `institutions`, each with `label` and `windows`; a null window has `window`, `replicates`, `seed`, `nswap`, `max_tries`, `swaps_succeeded` (`min`, `mean`, `max`), `attempts_mean`, `nodes`, `edges` and `statistics`, keyed by `average_clustering`, `modularity` and `giant_component_share`, each with `observed`, `null_mean`, `null_sd`, `z`, `p_two_sided` and `replicates_used`) and `sensitivity` (G-A all years: `observed`, `merge_same_name_within_component` and `split_authors`, each with node counts, `statistics` and `delta`; the split block also has `authors_split` and `split_share`). Aggregates only: no author or institution ids or names. Licence: derived counts from `index.json`.

### `site/data/california/search_index.json`

Purpose: header search across the Atlas (VD-19; `site/assets/site_search.js`, results page `/search`). Top-level keys: `schema_version` (1), `generated_at` (from `index.json`), `types` (type names; an item's first value is its index here) and `items`, each `[type_index, label, detail, href]`. Types: `page` (nav pages), `expert` (`expert.html#author=<id>`), `institution` (California institutions, `institution#inst=<id>`), `topic` (`experts#tag=<tag>`; matrices use `matrix:<key>`), `funder` (`funding#fa=<agency>`, or `funding#q=<name>` for funder names that are not agency names), `term` (`glossary#<id>`) and `resource` (the resource's `root_url`, or `resources`). Detail is the primary affiliation, institution type and city, research or matrix label, funder type, glossary excerpt or resource relation. No abstracts or e-mail addresses. Written by `scripts/build_search_index.py` (daily ingest) from `index.json`, `institutions.json`, `grants.json`, `linkouts.json`, `site/assets/topics.js`, `framework/src/components/shared/labels.js`, `framework/observablehq.config.js` and `framework/src/glossary.md`; `--check` fails when stale. Licence: as `index.json`.

### `site/data/california/expert_badges.json`

Purpose: funding and data-stewardship badges on the expert profile page (`expert.html`).
Top-level keys: `schema_version` (`s9.3-v1`), `generated_at`, `method` (plain-language source
notes), `experts` (author_id -> entry; experts with no badge are absent). Entry fields: `grants`
(list of `grant_key`, `title`, `funder`, `org`, `start`, `end`, `url`, `amount`, `match`:
`linked_work` when an OpenAlex award ID on one of the expert's works matches the grant, `pi_name`
when the principal investigator's name matches the expert, unambiguously, at a California
organisation) and `datasets` (`count` of plastic-related DataCite datasets the expert authored via
ORCID, versions collapsed; `items`: up to five with `doi`, `title`, `publisher`, `year`). Only
plastic-related grants from `grants.json` count; the page decides "active" from `end`. Licence: as
`grants.json` and `index.json`. Written by `scripts/build_expert_badges.py` (daily ingest) from
`index.json`, `grants.json`, `data/processed/work_grant_links.parquet` and
`data/processed/expert_datacite_outputs.parquet`.

### `site/data/california/works_detail.json`

Purpose: publication table on the Evidence map (one row per published work).
Top-level keys: `schema_version`, `works` (array). Licence: as `index.json`.
Row fields: `work_id`, `title`, `year`, `pub_date`, `first_seen` (date first ingested), `doi`,
`journal`, `type`, `cited_by_count`, `is_oa`, `oa_url`, `plastic_related`, `ca_led`,
`domain_tags`, `facet_tags`, `authors` (array of names, first 20), `author_count`,
`has_abstract` (boolean). Written by `scripts/build_export_site.py`.

### `site/data/california/work_text/abstracts.json`

Purpose: abstracts for the Evidence map table, loaded only when a reader expands one. Kept in a
subfolder so the abstract-free release snapshot does not package it.
Top-level keys: `schema_version`, `abstracts` (object, work_id -> abstract text with email
addresses redacted). Licence: abstracts as supplied by OpenAlex (as `authors/*.json`).

### `site/data/california/institutions.json`

Purpose: California institution registry used by the Institutions view.
Top-level keys: `schema_version`, `generated_at`, `institutions` (array).
Licence: institution names and identifiers from OpenAlex and ROR. ROR and OpenAlex licences are not recorded in `docs/REUSE.md`; owner decision pending.

`institutions[]` row fields: `inst_id` (string, atlas key), `name` (string), `ror`
(string or null, ROR identifier URL), `atlas_type` (string, reviewed institution type),
`ca_flag` (boolean), `city` (string), `region` (string), `lat`, `lon` (number or null),
`work_count` (integer), `author_count` (integer), `years` (array of integer),
`domain_tags` (array of string).

### `site/data/california/institutions.geojson`

Purpose: map layer for California institutions with coordinates.
Type: GeoJSON `FeatureCollection` of `Point` features. Each feature's `properties`
mirror the `institutions[]` fields above (`inst_id`, `name`, `ror`, `atlas_type`,
`ca_flag`, `city`, `region`, `work_count`, `author_count`, `years`, `domain_tags`).
Licence: as `institutions.json`. Coordinates come from the OpenAlex institution `geo`
record, with the ROR location as fallback (`src/atlas/ingest/institutions.py`). Neither
source's licence is recorded in `docs/REUSE.md`. Owner decision pending.

### `site/data/california/aggregates.json`

Purpose: year, type and tag counts used by the site views.
Top-level keys: `schema_version`, `generated_at`, `by_year`, `by_type`, `by_tag`.
Licence: derived counts; as `index.json`.

- `by_year[]`: `year` (integer), `count` (integer), `plastic_related_count` (integer).
- `by_type[]`: `type` (string), `count` (integer), `plastic_related_count` (integer).
- `by_tag[]`: `tag` (string; domain or facet ID), `count` (integer), `plastic_related_count` (integer).

### `site/data/california/build_metadata.json`

Purpose: build log for the static export (timestamp, row counts, payload sizes).
Top-level keys: `schema_version`, `generated_at`, `counts`, `files` (object keyed by
relative path, for example `index.json` or `authors/<author_id>.json`), `payload_bytes`
(integer), `payload_gzip_bytes` (integer), `flow` (optional, FLOW-1; see below).
Licence: project operational output; no third-party content. Owner decision applies only to the repository licence.

- `counts`: `authors`, `ca_institutions`, `institutions`, `labeled_works`, `works` (integers).
- `files[path]`: `bytes` (integer), `gzip_bytes` (integer).
- `flow` (optional; omitted when `ca_authors_only` is off or the works table has no `ca_any_author`; a missing key means "use the archived release"):
  - `records_retrieved`: `unique_works` + `duplicates_collapsed` (integer).
  - `duplicates_collapsed`: total `duplicate_work_ids` length over the normalized works, null as 0 (integer).
  - `unique_works`: works in the normalized table before curation (integer).
  - `no_ca_authorship`: unique works whose `ca_any_author` is not true (integer).
  - `removed_by_curation`: `unique_works` - `no_ca_authorship` - `published` (integer).
  - `published`: works in `index.json`, the same as `counts.works` (integer).
  - `plastic_related`: published works with `plastic_related` true (integer).
  - `not_plastic_related`: `published` - `plastic_related` (integer).
  - `by_type`: object from OpenAlex work type to published count (`unknown` when empty); values sum to `published`.

### `site/data/california/grants.json`

Purpose: public award records from named funders, shown in the Funding view.
Top-level keys: `schema_version`, `generated_at`, `caveat` (string), `columns` (array of
string, the row field names), `counts` (`exported_rows`, `input_rows`, `undated_rows`;
integers), `sources` (object keyed by source name: `ca_sea_grant`, `nih_reporter`,
`nsf_awards`, `opc_council`, `usaspending`; each with `rows` (integer), `amount_rows`
(integer), `funder_type` (string), `amount_basis` (string)), `aggregates`
(`by_institution_type`, `by_year_funder_type`), `rows` (array).
Licence: award records are public funder records. Per-source licence terms are **not recorded in `docs/REUSE.md`**. Owner decision pending.

`rows[]` fields (21, as `columns`):

| Field | Type | Meaning |
|---|---|---|
| `grant_key` | string | Atlas key for the award record. |
| `source` | string | Source name (see `sources`). |
| `title` | string | Award title. |
| `pi_names` | array of string | Principal-investigator names as listed in the source record. Personal names; see `docs/PRIVACY_REVIEW.md`. |
| `org`, `org_state`, `institution_type` | string | Recipient organization, state, and reviewed type. |
| `start`, `end` | string or null | ISO dates from the record. |
| `fiscal_year` | integer or null | Fiscal year of the record. |
| `amount` | number or null | Amount as reported. Basis is in `amount_basis`. |
| `amount_basis` | string | Basis of the amount (for example fiscal-year total cost or estimated total). Not comparable across sources. |
| `currency` | string | Currency code, for example `USD`. |
| `funder`, `funder_type`, `funder_chain` | string, string, array | Funder name, federal/state/other type, and parent chain. |
| `program` | string or null | Program name from the record. |
| `url` | string or null | Link to the source record. |
| `plastic_related` | boolean | Provisional label. |
| `domain_tags` | array of string | Provisional topic tags. |
| `ca_led` | boolean | California-led flag carried from the source-record derivation in `grants_export.py` (provisional). |

### `site/data/california/monitoring.json`

Purpose: monitoring-source catalogue and rights-cleared sample observations.
Top-level keys: `schema_version`, `generated_at`, `publication_mode` (string;
currently `public_cleared`), `coverage_basis` (string), `datasets` (array),
`sample_count` (integer), `samples` (array).
Licence: `samples` contain only rows from datasets listed in
`config/monitoring_publication.yml`. At the time of writing that is one dataset,
`sf_bay_5gyres_microplastics`, licensed CC BY 4.0 by owner determination
(QUESTIONS S7.3-A). The `datasets` array is a source registry: most entries record
their licence as unknown or provider-dependent and carry no observations.

`datasets[]` fields (23): `id`, `name`, `steward`, `entity_type`, `status`, `region`,
`sample_matrix` (array), `format` (array), `cadence`, `access_method`, `access_tier`,
`provenance_type`, `provenance_note`, `provenance_url`, `url`, `citation`,
`license` (string, as recorded), `measurement_status`, `plastic_classes` (array),
`seed_eligible` (boolean), `contributor_in_ca` (boolean or null), `evidence_excerpt`
(string), `last_checked` (string, ISO date).

`samples[]` fields (14): `sample_id`, `dataset_id`, `citation` (string),
`contributor` (string, organization or project name), `date` (string, ISO date),
`lat`, `lon` (number), `in_ca_land`, `in_ca_state_waters` (boolean),
`matrix` (string or null), `method` (string), `particle_count` (integer),
`concentration_value` (number or null), `concentration_unit` (string or null).

### `site/data/status.json`

Purpose: pipeline and ingestion status for the Status page.
Top-level keys: `generated_at`, `actions_status` (string), `drift_status` (string),
`actions_runs` (array), `alarms` (array), `deltas` (null when unavailable),
`history_records` (integer), `label_rates_series` (object keyed by label class),
`last_success_by_workflow` (object keyed by workflow), `recent_runs` (array), `spend` (object).
Licence: project operational output; no third-party content.

- `recent_runs[]` fields: `run_id`, `workflow`, `status`, `run_at_utc` (string),
  `works_added`, `works_total`, `labels_total` (integers), `api_spend` (number or null).
- `spend`: `latest`, `runs_with_spend` (integer), `total_cost_usd` (number), `total_credits` (number).

### `site/data/california/open_calls.json`

Purpose: open calls listed on the Funding view.
Top-level keys: `generated_at`, `calls` (array), `licence` (string), `source_url` (string).
Licence: the file records `Other (Public Domain)` as stated by the source. This is the source's own statement and is not independently verified here.

`calls[]`: empty at the time of writing (0 rows). No field list is documented yet; add one when the first call is listed.

### `site/data/california/journal_metrics.json`

Purpose: the journal column and the "2-yr mean citedness (OpenAlex)" sort on the Evidence map publication table
(VD-34). Written by `py -3.14 scripts/fetch_journal_metrics.py` (live: one OpenAlex list call per 100 works and per
100 sources, about 30 credits; `--offline` rebuilds it from the ignored cache `data/interim/journal_metrics_raw.json`;
`--check` fails when the file is malformed or its journal names no longer match `works_detail.json`).
`two_yr_mean_citedness` is OpenAlex's open analogue of the impact factor: the average citations received this year by
a source's works from the two previous years. It is not Clarivate's Journal Impact Factor, which is proprietary.
Top-level keys: `schema_version` (1), `generated_at` (UTC timestamp), `source` (`OpenAlex sources summary_stats`),
`coverage` (integer counts: `works`, `works_with_source`, `journals`, `journals_with_source`, `journals_with_metric`),
`journals` (array sorted by name; each item's `name` is the journal exactly as `works_detail.journal` spells it; a list rather than
an object keyed by name, because the release snapshot refuses any JSON key that starts with "abstract"), `unmatched_journals` (names
whose works have no OpenAlex primary source), `name_mismatches` (the OpenAlex source has a different display name, so its
metrics are withheld) and `ambiguous_journals` (the name's works sit in more than one source; the source holding most of
them is used).

`journals[]` items: `name` (above), `source_id` (OpenAlex source id such as `S41143188`), `issn_l` (string or null), `two_yr_mean_citedness`
(number of at least 0, rounded to 3 decimals, or null), `h_index` (integer or null) and `type` (for example `journal` or
`repository`, or null).
Licence: derived from OpenAlex source metadata; check OpenAlex's current terms before reuse.

### `site/data/california/linkouts.json`

Purpose: the Evidence Map's related-resources strip (EM-5). Written from `config/linkouts.yml`
by `py -3.14 scripts/build_linkouts_json.py` (`--check` fails when it is stale).
Top-level keys: `schema_version` (`em5.v1`), `source` (string), `entries` (array, 13 at the time of writing).
Licence: project metadata; names and descriptions are quoted from each steward, and nothing
from the linked resources is copied (link-only, Add-on A2 §8).

`entries[]`: `id`, `name`, `icon` (VD-32: site-root path `assets/linkouts/<id>.png` or `.svg`, or null
when the card has no stored icon; written from `config/linkout_icons.yml`, fetched by
`scripts/fetch_linkout_icons.py`), `initials` (1 to 3 capitals shown on a neutral plane when `icon` is
null), `steward`, `steward_source` (https URL where the steward is named, or null), `steward_inst_id`
(VD-32: an `inst_id` in `institutions.json` for a steward that is an Atlas institution, or null; the
steward name links to `./institution#inst=<id>`), `description`, `relation`, `root_url` (https), `topics`
(topic tags that show the entry), `default` (boolean: shown when no topic-specific entry matches),
`description_source` (https URL where the steward states the description), `update_model` (string,
or "not stated"), `terms_status` (`recorded` or `not recorded`), `terms` (string, or null when the
steward's terms are not stated), `url_status` (`as_stated`, `owner_confirmed`, `to_confirm` or
`unavailable`), `disclosure` (string, or null when none applies; the Atlas owner's stated interest,
e.g. LO-8 and LO-13). The Related resources page (EM-16) lists every entry.

### `site/data/california/research_networks.json`

Purpose: the research networks and consortia that the Atlas links to (NET-1). Written from
`config/research_networks.yml` by `py -3.14 scripts/build_research_networks_json.py` (`--check`
fails when it is stale). The static institution pages (`/institutions/<id>/`) show a network where
the institution hosts it or has listed contributors in it.
Top-level keys: `schema_version` (`net1.v1`), `source` (string), `networks` (array, 1 at the time of writing).
Licence: link-only, as for the link-out registry. Names, descriptions and focus areas are quoted
from the steward's own pages; nothing is fetched or scraped. The full contributor roster is not
published: only the roster size and the Atlas expert IDs of listed contributors appear. The logo
image (`logo.path`, under `site/assets/`) is not covered by this file; its permission is still to
be confirmed (owner task H26).

`networks[]`: `id` (`NET-<n>`), `name`, `url` (https), `steward`, `steward_source` (https),
`description`, `description_source` (https), `focus_areas` (array of strings), `related_links`
(array of `label` and `url`), `host_institution_ids` and `member_institution_ids` (institution IDs,
either OpenAlex-style such as `I84218800` or a local ID such as `CAAG-OEHHA`), `listed_contributor_count`
(integer), `roster_as_of` (`YYYY-MM-DD`), `atlas_contributors` (array of `author_id` and `name`),
`logo` (`path`, relative to the site root, and `alt`), `disclosure` (string). The name variants,
URL status, logo source, terms and permission fields stay in the YAML only.

### `site/data/california/dtsc_timeline.json`

Purpose: the Policy page's DTSC microplastics regulatory timeline (EM-18, Add-on A2 §7 Part B). Written from `config/dtsc_timeline.yml` by `py -3.14 scripts/build_dtsc_timeline_json.py` (`--check` fails when it is stale).
Top-level keys: `schema_version` (`em18.v1`), `source` (string), `caveat` (the required "Listing does not by itself create requirements" sentence), `caveat_detail` (string), `order` (`newest_first`), `entries` (array).
Licence: curated by hand from DTSC pages and uploaded documents; no scraping. Dates are as DTSC states them.

`entries[]`: `id` (`dtsc-NN`), `date_as_stated` (verbatim from DTSC), `date_iso` (`YYYY-MM-DD` or `YYYY-MM`), `event`, `source_label`, `source_url` (https or null), `kind` (`workshop`, `proposal`, `background`, `finalized`, `effective` or `work_plan`).

### `site/data/california/opc_actions.json`

Purpose: the Policy page's OPC Solutions track, the 22 recommended early actions in the Ocean Protection Council's Statewide Microplastics Strategy (EM-17, Add-on A2 §7 Part A), with a draft link to Global Plastic Laws topics. Written from `config/opc_early_actions.yml` by `py -3.14 scripts/build_opc_actions_json.py` (`--check` fails when it is stale).
Top-level keys: `schema_version` (`em17.v1`), `source` (string), `mapping_status` (`draft` or `owner_reviewed`), `strategy` (`label`, `url` (https) and `adopted`), `gpl` (`name`, `steward`, `base_url` (https), `california_search_url` (https), `disclaimer` (the Global Plastic Laws sentence) and `topics`, an object that maps each topic slug to its name), `objectives` (array of `id` and `name`), `actions` (array).
`actions[]`: `code` (`2A.N.N`), `objective` (an `objectives[].id`), `group`, `summary` (the Atlas's paraphrase, 200 characters or fewer), `deadline_as_stated` (verbatim from the Strategy), `deadline_year` (integer), `pdf_page`, `gpl_topics` (topic slugs from `gpl.topics`; may be empty), `atlas` (either `q`, search text, or `topic`, a key from `site/assets/topics.js`).
Licence: curated by hand from the Strategy; no scraping. Summaries are the Atlas's own words, not the Council's.

### `site/data/california/methods_flow.json`

Purpose: the V-3 pipeline flow diagram on the Evidence Map (EM-6, Add-on A2 §5). Counts are copied from the newest `release/<date>/methods_card.json` (AT-10). Written by `py -3.14 scripts/build_methods_flow_json.py` (`--check` fails when it is stale).
Top-level keys: `schema_version` (`em6.v1`), `release_date` (`YYYY-MM-DD`), `release_version` (string from `site/data/release.json` when its date matches, else null), `query_version` (string), `template` (`name`: ROSES flow diagram for systematic maps; `licence`: `CC BY 4.0`), `stages` (array, in flow order).
Licence: the ROSES template is credited under CC BY 4.0; counts are project metadata.

`stages[]`: `stage` (string), `status` (`performed` or `not performed`), `steps` (array; empty for stages with no count), `note` (string or null).
`stages[].steps[]`: `label` (string), `value` (integer count), `source` (string naming the methods-card field the count comes from).

### `site/data/global/trend_global.json`

Purpose: the global denominator for the V-4 trend panel on the Evidence Map (EM-7, Add-on A2 §5). Works per publication year for all OpenAlex works matching the active plastics query (same type exclusions, no institution filter). Written by `py -3.14 scripts/fetch_trend_global.py` (one OpenAlex `group_by=publication_year` request; `--dry-run` prints the URL without a call; cached by `query_version` for 30 days, `--force` refetches).
Top-level keys: `schema_version` (`em7.v1`), `query_version` (the active query, e.g. `plastic-v3.1`), `fetched_at` (UTC ISO 8601), `source` (`OpenAlex group_by publication_year`), `by_year` (object: year string to integer count, sorted by year).
Missing file: the panel shows the per-topic chart and "Global comparison unavailable."

### `site/feed.xml`

Purpose: Atom feed of newly indexed California-connected papers and newly recorded awards.
Format: Atom 1.0 (`http://www.w3.org/2005/Atom`).
Feed-level elements: `id`, `title`, `subtitle`, `link` (self and alternate), `updated`, `author/name`.
Entry elements (one per item; 32 at the time of writing): `id` (tag URI, frozen
across releases), `title`, `link` (alternate; points to the source record), `updated`
(ISO date-time), `summary` (text: short summary and attribution, not full records),
`category` (`term`, for example `award`).
Licence: summaries are derived; the feed links to each source record for details.

### `site/data/release.json`

Latest archived release, written from `config/release.yml` by
`py -3.14 scripts/build_release_snapshot.py --write-site-release` (AT-10). The About tab
links to it. CC BY-NC 4.0.

| Field | Type | Meaning |
|---|---|---|
| `version` | string | Release tag (for example `v2026.11.11`). |
| `date` | string | Release date (YYYY-MM-DD). |
| `doi` | string | Zenodo version DOI. |
| `concept_doi` | string | Zenodo concept DOI (always resolves to the latest version). |
| `doi_url`, `concept_url` | string | `https://doi.org/` links for the two DOIs. |

### `site/data/california/pubmed_coverage.json`

Purpose: the PubMed coverage check (BQ-S9 part C, Add-on A3 §5.11). Each reference set is a PubMed search for plastics papers with a California affiliation (stage 1, `data/interim/pubmed/`, not committed); coverage is the share of its PMIDs that appear among the published Atlas works, joined by PMID and then by DOI. Written by `py -3.14 scripts/build_pubmed_coverage_json.py` from the interim runs, `data/processed/normalized/works.parquet` and the published subset in `site/data/california/index.json`. No network calls. `--check` fails when the committed file is stale and exits 0 with a SKIP message when the interim runs are absent (CI). Coverage is not a completeness rate: read `definition` before quoting it.
Top-level keys: `schema_version` (`bqs-pm-v1`), `generated_at`, `manifest_schema` (`bqs-pm-manifest-v1`), `failure_taxonomy_version`, `stage` (1), `source`, `definition` (plain-language text), `atlas_corpus` (`published_works`, `published_with_pmid`, `normalized_works`, `normalized_with_pmid`), `reference_sets` (keys `r1` and `r2`), `miss_triage` and `triage_classes` (class ids from `config/failure_taxonomy.yml`).
Licence: derived counts. PMIDs, DOIs and years come from NCBI E-utilities; the Atlas side is as `index.json`.

`reference_sets.<r1|r2>`:

| Field | Meaning |
|---|---|
| `description`, `affiliation`, `stage` | Plain-language name of the set; the PubMed affiliation term (`California`); pipeline stage (1). |
| `query_translation`, `run_timestamp`, `manifest_sha256` | From the run manifest: PubMed's query translation, run time (UTC), SHA-256 of the manifest file bytes. |
| `reference_pmids` | Unique PMIDs in the set. |
| `found_published`, `found_published_by_pmid`, `found_published_by_doi` | Reference PMIDs covered by a published Atlas work, and the split by join key. |
| `misses` | `reference_pmids` minus `found_published`. |
| `found_unpublished_corpus` | Misses found in the normalized works table but not published (curation or relevance drops; a diagnostic, not a coverage figure). |
| `coverage_published` | `found_published` / `reference_pmids`, rounded to 4 decimals. |
| `coverage_by_year` | Object keyed by publication year (`unknown` when the year is missing): `reference`, `found`, `coverage`. Recent years lag because MeSH indexing lags. |
| `join_rate` | `published`: share of published works with a PMID; `normalized`: share of all normalized works with a PMID. |

`miss_triage`: `sample_size`, `seed` (20261122), `sample_rule` (the first `min(50, misses)` misses ordered by SHA-256 of `seed:pmid`), `misses_total` (the union of both sets' misses, deduplicated by PMID), `triage_file` (`curation/pubmed_miss_triage_v1.csv`), `labelled` (rows with a non-blank `triage_class`) and `false_negative_classes` (taxonomy classes with direction `false_negative`). With no labels the block carries `status: "pending owner triage"`. Once `labelled` is above zero it carries `false_negative_share`: `count` (labelled rows in a false-negative class), `n` (= `labelled`), `share` and `wilson_95` (Wilson 95% interval). The triage sheet is never overwritten when it holds reviewer entries.

### `site/data/global/language_probe.json`

Purpose: the native-language probe of OpenAlex (BQ-S4, Add-on A3 §5.7). There are sixteen term sets, one per group of registered native-language strings (`config/search_vocabulary_v1.yml`, the A3 §5.7 rows). For each set the file gives the OpenAlex count, the language labels of its works, a fixed-seed sample of up to 50 works, and the share of that sample that the main v3.1 query also retrieves. The overlap is a share of the sample, not a completeness rate. Written by `py -3.14 scripts/fetch_language_probe.py` (about 64 OpenAlex requests, cost recorded in `cost`; responses are cached under `data/interim/language_probe/`). `--offline` rebuilds the file from that cache with no network calls; `--check` validates the committed file and writes nothing; `--offline --check` also compares it with a rebuild from the cache. The probe stops when its own logged spend would exceed USD 0.09.
Top-level keys: `schema_version` (`bqs-v1`), `generated_at` (UTC ISO 8601), `query_version` (`plastic-v3.1`), `vocabulary_version` (`search_vocabulary_v1`), `source`, `sample_seed` (20261122), `sample_limit` (50), `method` (plain-language text), `cost` (`credits` and `usd`: the OpenAlex credits behind the file and the conservative USD figure, at USD 0.0001 per credit), `term_sets` (array, below), `caveats` and `not_covered` (arrays of text).

`term_sets[]`:

| Field | Meaning |
|---|---|
| `id`, `languages`, `terms`, `query` | Probe identifier; language codes; the registered strings; the OpenAlex `title_and_abstract.search` expression built from them. |
| `a3_count_2026_11_18` | The A3 §5.7 probe count, for comparison. The search form behind it is not confirmed by this probe (see `caveats`). |
| `count` | OpenAlex `meta.count` for the works matching the set. |
| `language_label_counts` | Works per OpenAlex language label, for the whole set. `unlabelled` is the remainder with no language label. `null` when the optional request was skipped by the budget guard. |
| `fetched_at` | UTC time of the count request. |
| `sample_seed`, `sample` | The fixed seed; up to 50 works as `{id, title, language, year, venue, in_v31}`: OpenAlex work ID, OpenAlex title, language label, publication year, primary-location venue, and whether the v3.1 query also retrieves the work. |
| `sample_size` | Number of works in `sample` (`min(count, 50)`). |
| `sample_in_v31` | Sample works with `in_v31` true. This is the overlap on the sample only. |
| `sample_language_label_counts` | Language labels within the sample. |

Titles and venues are OpenAlex metadata. No abstracts are published.
Licence: derived from OpenAlex metadata; OpenAlex licence recorded as unknown in `docs/REUSE.md`. Owner decision pending.

### `site/data/global/denominators.json`

Purpose: the public global-denominator file (BQ-2.4, Add-on A3 Module 2). It feeds the V-4 trend panel on `/california/evidence` and the Trend tab on `/explore`. Written by `py -3.14 scripts/build_denominators_json.py` from the ignored `data/processed/analytics/denominator_series.json` (run `scripts/build_denominator_series.py` first). `--check` validates the committed file (schema, allowed ratios only, no ratio with D or B2) and, when the ignored input exists, fails if the file is stale; with the input absent it prints SKIP for the staleness check and exits 0. Top-level keys: `schema_version` (`bq2-v1`), `generated_at`, `version` (`query_version`, `as_of`, `last_complete_year`, `window_start`, `window_end`), `source` (input schema and SHA-256), `what_this_is_and_is_not` (`is`, `is_not`), `series` (A, A-article_review, B, B-article_review, C, D: `id`, `label`, `counting_unit`, `sensitivity`, `beside_only`, `comparable_with`, `retraction_split`, `undated_records`, `years` with `year`, `count`, `retracted`, `partial_year`), `ratio_pairs` (B/A, C/A and B-article_review/A-article_review, each with `numerator`, `denominator`, `label`, `sensitivity`), `not_computed` (B2, listed only), and `metrics` (the BQ-2.3 block: window, partial years, CI level, method, per-series `trend` with CAGR and 95% interval, and `shares`). Counts are OpenAlex records by publication year. D is curated works, is beside-only, and is never divided.

### `site/data/california/bundle/`

AT-4 serving bundle (bit-set facets, title search, institution tiers, abstract-free
Parquet). See `docs/SITE_DATA.md` and `docs/AT_4_VERIFICATION.md`. CC BY-NC 4.0.

## Files not listed

Files in `site/` outside `site/data/` and `site/feed.xml` (for example `index.html`,
`status.html`, `assets/`, `stlite/`) are application code and static assets, not
data payloads, and are out of scope for this dictionary.
