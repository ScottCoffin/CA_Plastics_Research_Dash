# Topic evolution page (BQ-4.4)

The public page `/california/topics` (`framework/src/california/topics.md`). It reads two files
written by `scripts/build_topics_json.py` from the analytics outputs of BQ-4.1 to BQ-4.3 (see
`docs/TOPIC_SERIES.md`, `docs/RISING_SHARE.md`, `docs/TAG_COOCCURRENCE.md`).

    py -3.14 scripts/build_topic_series.py
    py -3.14 scripts/build_rising_share.py
    py -3.14 scripts/build_tag_cooccurrence.py
    py -3.14 scripts/build_topics_json.py           # writes site/data/california/*.json
    py -3.14 scripts/build_topics_json.py --check   # fails when the files are stale or inputs are missing

Code: `scripts/build_topics_json.py`. Tests: `tests/test_build_topics_json.py` (synthetic inputs),
`tests/test_topics_page.py` (page and renderer wiring). Renderer: `framework/src/components/topics_page.js`
with `topics_page.css`. The page loads both files lazily through `loadJson`, which uses the California
data helper. The inputs are gitignored, so `--check` only works on a machine with `data/processed/analytics/`.

## Files

Both files carry `schema_version` (`"schema": "bq4-v1"`), `generated_at` (ignored by `--check`),
`scope: "california"`, `as_of`, `last_complete_year`, and a `version` block: the schema of each source
file, the sha256 of each source JSON, and the labels snapshot `content_sha256`.

`topics_timeseries.json`
- `notice`: "Tag labels come from rules; no tag has been validated against gold labels yet."
- `page_scope`, `accuracy_rule`, `plastic_related_by_year`, `tags_excluded`.
- `tags[]`: `tag`, `label`, `approval`, `status`, `accuracy_state`, `complete_works` (works in complete
  years), `by_year[]` (`year`, `count`, `share`, `partial`), `label_source_totals` (`all_sources`,
  `owner_model_only`, `rule_only`).
- `lens`: `status`, `message`, `caption`, `framing_rule`, `series`. Lens counts are separate from topics.
- `cooccurrence`: `window` (`complete_years`), `variant` (`all_sources`), `window_years`, `min_pair_n`,
  `pairs[]` (`a`, `b`, `label_a`, `label_b`, `n_ab`, `n_a`, `n_b`, `N`, `jaccard`, `lift`, `phi`,
  `status`: `sufficient` or `insufficient_data`).

`topic_bursts.json`
- `test`, `alpha`, `window_years`, `min_window_works`, `statistical_screen` (no multiple-testing
  correction), `flagged`, `tags_excluded`.
- `tags[]`: `tag`, `label`, `accuracy_state`, `flag`, `reasons_failed`, `trend` (`z`, `p`,
  `slope_sign`), `window_years`, `window_count`, `total_complete_years`, `sensitivity` (per variant
  status), `loio` (`pass`, `worst_p`, `worst_institution`, `institutions_tested`).
- `bursts`: `{"status": "not_computed", "reason": ...}`. Kleinberg bursts are not implemented.

## Accuracy state

Assigned per tag by `accuracy_state()`, in this order:

1. `validated`: a per-tag F1 from gold labels exists. The builder reads no gold files, and none
   exist yet, so no tag is validated.
2. `insufficient data`: the tag has `no_labels_yet`, or fewer than 10 works in complete years
   (partial years are not counted; 9 is insufficient, 10 is experimental).
3. `experimental`: everything else.

The page shows the state as text. The co-occurrence table greys pairs with `insufficient_data`
and labels them "insufficient data". Rising flags are shown as text ("Flagged as rising"), never colour alone.
