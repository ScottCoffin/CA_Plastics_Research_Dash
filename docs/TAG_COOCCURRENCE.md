# Tag co-occurrence (BQ-4.3)

The data layer for the topic evolution page (BQ-4.4). It counts how often pairs of approved topic
tags appear on the same California plastic-related work. Nothing is published here: BQ-4.4 reads the
output and writes its own site file.

    py -3.14 scripts/build_tag_cooccurrence.py                          # write the output
    py -3.14 scripts/build_tag_cooccurrence.py --check                  # fail when missing or stale
    py -3.14 scripts/build_tag_cooccurrence.py --as-of 2026-11-25 --split-year 2021

Code: `src/atlas/analytics/tag_cooccurrence.py`. CLI: `scripts/build_tag_cooccurrence.py`.
Tests: `tests/test_tag_cooccurrence.py` (synthetic inputs only).
Output: `data/processed/analytics/tag_cooccurrence.json` (gitignored), schema `bq4-cooc-v1`.

## Input

The frozen labels snapshot `data/processed/analytics/labels_snapshot_v1.parquet`, written by
`scripts/build_topic_series.py` (BQ-4.1, see `docs/TOPIC_SERIES.md`). The build never reads the live
labels, so it stays on the same labels as the topic series. Its `content_sha256` and the taxonomy
`sha256` are recorded in the output. If the snapshot is absent, a plain build fails and `--check`
prints SKIP (CI has no `data/` tree).

## Scope and counting

- Unit: a plastic-related CA work. Works with no year are excluded from every window.
- Tags: approved, non-experimental topic tags from `config/taxonomy.yml` (`reported_tags`). Experimental
  tags are listed under `tags_excluded` and never appear in a pair.
- Windows (inclusive year bounds, see `windows` in the output):
  - `complete_years`: up to the last complete year (the year before the as-of date). This is the default.
  - `all_years`: every dated work, including the partial current year. Reported as the total.
  - `earlier`: complete years before the split year.
  - `recent`: from the split year to the last complete year. The default split year is the first of
    the last five complete years (2021 for an as-of date in 2026); `--split-year` overrides it.
- Label-source variants, as in the topic series: `all_sources`, `owner_model_only` (owner and model
  sources), and `rule_only`. A variant with no labels in any year is `not_testable` and has no windows.
  `owner_model_only` is not testable today because no owner tag overrides exist yet.

## Pair statistics

For each unordered pair of reported tags (a, b), with N the plastic-related works in the window
(including works with no tags in the variant):

| Field | Meaning |
|---|---|
| `n_ab` | works carrying both tags |
| `n_a`, `n_b` | works carrying each tag |
| `N` | plastic-related works in the window |
| `jaccard` | n_ab / (n_a + n_b - n_ab); null when the union is zero |
| `lift` | n_ab * N / (n_a * n_b); null when n_a * n_b is zero |
| `phi` | association strength (Pearson correlation of the two binary tag indicators): (n_ab * N - n_a * n_b) / sqrt(n_a (N - n_a) n_b (N - n_b)); null when the denominator is zero |
| `status` | `sufficient` when n_ab >= 5, otherwise `insufficient_data` |

Pairs are never dropped. Pairs with n_ab below 5 are flagged `insufficient_data` and kept, so the
page can show them with a caveat. The threshold is `MIN_PAIR_N = 5`, so 4 co-occurrences is
insufficient and 5 is sufficient. All floats are rounded to 4 decimals.

Pairs are listed in tag-id order (a sorted before b, and pairs sorted by a then b). Tags are sorted by
id. The JSON is written with sorted keys and a trailing newline, so two builds from the same inputs
are byte-identical. `--check` regenerates the payload and fails unless it matches the file exactly,
which catches changes to the snapshot, the taxonomy, or the as-of and split settings.

## Accuracy states for the page (BQ-4.4)

The page uses the flag per pair. Its accuracy labels (`validated`, `experimental`,
`insufficient data`) are assigned in BQ-4.4, not here. This layer only reports
`sufficient` or `insufficient_data`.

## Limits

- Co-occurrence is a descriptive count on tagged works, not a causal or topical-similarity measure.
  Lift and phi are unstable when counts are small; read them together with n_ab.
- Tag labels are rule-based today. Results depend on the rule tagger until owner and model labels exist.
- Lifecycle tags have no labels yet and appear with zero counts.
- Early years have little volume; the default windows include them only through `all_years`.
- Pairs are computed over all tags at once, with no multiple-comparison adjustment.
