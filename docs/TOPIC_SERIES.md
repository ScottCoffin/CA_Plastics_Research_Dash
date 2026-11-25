# Topic time series (BQ-4.1)

The data layer for the topic evolution page (BQ-4.4). It builds the year series that BQ-4.2
(rising-share flag) and BQ-4.3 (co-occurrence) read. Nothing is published here: BQ-4.4 writes
`site/data/topics_timeseries.json` (bq4-v1) from the output of this step.

    py -3.14 scripts/build_topic_series.py                    # write the two outputs
    py -3.14 scripts/build_topic_series.py --check            # fail when missing or stale
    py -3.14 scripts/build_topic_series.py --refresh-snapshot # accept changed labels (owner)

Code: `src/atlas/analytics/topic_series.py`. Tests: `tests/test_topic_series.py` (synthetic inputs).
Outputs (both gitignored under `data/processed/analytics/`):

- `labels_snapshot_v1.parquet`: the frozen per-work labels used by the series.
- `topic_series.json`: schema `bq4-series-v1`, with each input's sha256 and the snapshot hash.

## Sources

| Input | Used for |
|---|---|
| `config/taxonomy.yml` | reported tags (approved, not `experimental`); lens values |
| `data/processed/work_labels.parquet` | rule topic tags (`domain_tags`), rule lens values (`facet_tags`), rule `plastic_related` |
| `data/processed/normalized/works.parquet` | CA set (`ca_any_author`), publication year, title and abstract for the rules |
| `config/queries.yml` | always-relevant and title-relevant rules; `relevance_policy` |
| `curation/work_relevance.csv`, `curation/work_relevance_model.csv` | owner and assisted relevance calls; accepted model calls (optional file) |
| `curation/overrides_works.csv`, `curation/suppressions.csv` | owner tag overrides; removals (`exclude`, suppressions) |
| `data/processed/global/works.parquet` | global counts by `primary_topic` (unscreened query hits) |

The CA set mirrors the export (`atlas.build.export_site`): CA works only, the export's precedence
for `plastic_related` (rule, then owner and assisted calls, then accepted model calls, then the
always-relevant and title rules, then curation overrides), and the chemicals-in-plastics survival
rule. Owner-reviewed rows are never overridden by the model or the rules. Removed works (suppression
or `exclude`) are dropped before the series.

## Label sources

Each tag label on a work carries a source:

- `rule`: `work_labels.domain_tags`, from the rule tagger.
- `owner`: a `domain_tags` (or `facet_tags`) row in `curation/overrides_works.csv`. It replaces the
  rule tags for that work.
- `model`: reserved. No model topic labels exist; the accepted model file holds plastic-relevance only.

## Labels snapshot

The snapshot holds one row per CA work and label: `work_id`, `publication_year`,
`plastic_related`, `kind` (`topic` or `lens`), `tag`, `label_source`. A work with no labels has one row
with null label fields. Rows are sorted. `content_sha256` is the SHA-256 of the canonical JSON rows,
so the hash does not depend on the file format or the input order.

The series always read the frozen snapshot. If the live labels differ from it, a plain build stops
and the owner decides: `--refresh-snapshot` replaces the snapshot, and `--check` reports the drift.
This keeps every later comparison (BQ-4.2 sensitivity, leave-one-institution-out) on the same labels.

## California series

- Scope: plastic-related CA works. A tag is counted only on those works, matching the site.
- Years: from the first to the last year present, zero-filled. `last_complete_year` is the year before
  the as-of date (2025 on 2026-11-25). Later years carry `partial: true`.
- `count`: works with the tag in the year. `share`: count divided by the plastic-related works of the
  same year (4 decimals; null when that denominator is zero).
- Status: `labelled`, or `no_labels_yet` with the message "no labels yet". Tags with no labels are
  listed, never filled in.
- Sensitivity: `all_sources` (every label), `owner_model_only` (owner and model sources only), and
  `rule_only` (rule source only). Each has a total and counts by year.
- Experimental tags (`culture_media_and_discourse`) are listed under `tags_excluded` and produce no
  series.

## Global series

- Source: OpenAlex `primary_topic_name` (ID in `primary_topic_id`). Unscreened query hits, labelled as
  such in the payload. The global rule tagger is not used until it is validated (A3 BQ-4.1).
- Top 30 topics are ranked by count over complete years (ties by name, then ID). `other` holds every
  other work, including works with no primary topic (`no_primary_topic_total`).
- `check_global_sums` fails the build unless top topics plus `other` equal the yearly total.

## Lens series

`lens` shows analytic-lens counts separately from topic counts. The caption carries the framing rule:
"a lens is counted only when the work itself uses the frame, with a quoted excerpt". A lens is
never inferred from the topic. Lens counts come from `facet_tags` that exactly match a lens value in
`config/taxonomy.yml`. While none exist, the block is `status: no_lens_labels_yet` with an empty series.

## Limits

- Owner tag overrides and model labels are the only non-rule sources; no owner tag overrides exist yet
  and the model is not accepted. The owner and model variants therefore equal zero today.
- Author-level suppressions and merges are not applied to the work set; they are not in the file
  today (`curation/suppressions.csv` has no rows), but would change the CA set if added.
- The CA plastic-related set is recomputed from the same inputs as the export, not read from the
  published site index, so it can differ from the site count if the export changes.
- Global counts are unscreened and not comparable with the curated CA counts.
- The lifecycle tags have no seed words and no labels yet; they appear as "no labels yet" until the
  owner labels works by hand or the rules are extended.
- Years before the corpus has volume are small; read the early years with care.
