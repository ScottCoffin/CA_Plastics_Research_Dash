# Data dictionary: public site payloads (S10.2)

Prepared 2026-11-10 for owner sign-off through `docs/GOVERNANCE_CHECKLIST.md`.
This page describes every public file under `site/data/` and the Atom feed at
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

### `site/data/index.json`

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

### `site/data/authors/<author_id>.json`

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
`facet_tags`, `plastic_related`, `plastic_tier`, `study_type`, `needs_review`.

### `site/data/institutions.json`

Purpose: California institution registry used by the Institutions view.
Top-level keys: `schema_version`, `generated_at`, `institutions` (array).
Licence: institution names and identifiers from OpenAlex and ROR. ROR and OpenAlex licences are not recorded in `docs/REUSE.md`; owner decision pending.

`institutions[]` row fields: `inst_id` (string, atlas key), `name` (string), `ror`
(string or null, ROR identifier URL), `atlas_type` (string, reviewed institution type),
`ca_flag` (boolean), `city` (string), `region` (string), `lat`, `lon` (number or null),
`work_count` (integer), `author_count` (integer), `years` (array of integer),
`domain_tags` (array of string).

### `site/data/institutions.geojson`

Purpose: map layer for California institutions with coordinates.
Type: GeoJSON `FeatureCollection` of `Point` features. Each feature's `properties`
mirror the `institutions[]` fields above (`inst_id`, `name`, `ror`, `atlas_type`,
`ca_flag`, `city`, `region`, `work_count`, `author_count`, `years`, `domain_tags`).
Licence: as `institutions.json`. Coordinates come from the OpenAlex institution `geo`
record, with the ROR location as fallback (`src/atlas/ingest/institutions.py`). Neither
source's licence is recorded in `docs/REUSE.md`. Owner decision pending.

### `site/data/aggregates.json`

Purpose: year, type and tag counts used by the site views.
Top-level keys: `schema_version`, `generated_at`, `by_year`, `by_type`, `by_tag`.
Licence: derived counts; as `index.json`.

- `by_year[]`: `year` (integer), `count` (integer), `plastic_related_count` (integer).
- `by_type[]`: `type` (string), `count` (integer), `plastic_related_count` (integer).
- `by_tag[]`: `tag` (string; domain or facet ID), `count` (integer), `plastic_related_count` (integer).

### `site/data/build_metadata.json`

Purpose: build log for the static export (timestamp, row counts, payload sizes).
Top-level keys: `schema_version`, `generated_at`, `counts`, `files` (object keyed by
relative path, for example `index.json` or `authors/<author_id>.json`), `payload_bytes`
(integer), `payload_gzip_bytes` (integer).
Licence: project operational output; no third-party content. Owner decision applies only to the repository licence.

- `counts`: `authors`, `ca_institutions`, `institutions`, `labeled_works`, `works` (integers).
- `files[path]`: `bytes` (integer), `gzip_bytes` (integer).

### `site/data/grants.json`

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

### `site/data/monitoring.json`

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

### `site/data/open_calls.json`

Purpose: open calls listed on the Funding view.
Top-level keys: `generated_at`, `calls` (array), `licence` (string), `source_url` (string).
Licence: the file records `Other (Public Domain)` as stated by the source. This is the source's own statement and is not independently verified here.

`calls[]`: empty at the time of writing (0 rows). No field list is documented yet; add one when the first call is listed.

### `site/feed.xml`

Purpose: Atom feed of newly indexed California-connected papers and newly recorded awards.
Format: Atom 1.0 (`http://www.w3.org/2005/Atom`).
Feed-level elements: `id`, `title`, `subtitle`, `link` (self and alternate), `updated`, `author/name`.
Entry elements (one per item; 32 at the time of writing): `id` (tag URI, frozen
across releases), `title`, `link` (alternate; points to the source record), `updated`
(ISO date-time), `summary` (text: short summary and attribution, not full records),
`category` (`term`, for example `award`).
Licence: summaries are derived; the feed links to each source record for details.

## Files not listed

Files in `site/` outside `site/data/` and `site/feed.xml` (for example `index.html`,
`status.html`, `assets/`, `stlite/`) are application code and static assets, not
data payloads, and are out of scope for this dictionary.
