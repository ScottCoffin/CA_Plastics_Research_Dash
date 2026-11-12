# EM-6 and EM-7 verification: pipeline flow (V-3) and trend panel (V-4), 2026-11-12

Both views render on the Framework Evidence Map (`/app/evidence`), wired in
`framework/src/components/evidence.js` (`mountV3Flow`, `mountV4Trend`).

## EM-6 V-3 pipeline flow
- `scripts/build_methods_flow_json.py` -> `site/data/methods_flow.json` from the newest
  `release/<date>/methods_card.json` (now 2026-11-11, v2026.11.11). ROSES stages: Searching
  (1,933 raw), Screening (1,896 after near-duplicate collapse, 1,836 California authorship,
  1,774 published, 1,430 plastic-related), Coding (performed; provisional labels), Data
  extraction (not performed), Critical appraisal (not performed), Synthesis (1,429 analysed).
- EAT-4: `tests/test_methods_flow_em6.py` asserts every value equals the card; `--check` guards staleness.
- The flow shows the release snapshot, so its counts differ from the live facet counts
  (1,909 works today); the footer names the release.

## EM-7 V-4 trend panel
- `scripts/fetch_trend_global.py`: one OpenAlex `group_by=publication_year` request under query
  plastic-v3.1 (same title/abstract search, exclusions and type exclusions as ingest), 10 credits
  (USD 0.001), no retries. 134,450 works, 1853-2027. Cache key = query version; refetch after
  30 days or with `--force`; `--dry-run` prints the redacted URL.
- View: stacked works-per-year-by-topic bars from AT-4 bit-set counts (a work with several topics
  counts under each, stated on the page), California share of global output by year (corpus /
  global), current year drawn lighter ("still being indexed"), hidden data table for screen readers.
- Tests: `tests/test_trend_global_em7.py` (cache hit/miss, shape; request mocked),
  `tests/test_framework_v4_trend.py` (pure helpers).

## Checks
- `npm run build`, `check_at5.py --dist dist` (evidence first load 41 KB gzip), headless Edge
  smoke and screenshot of `/app/evidence`; full gate 1,349 tests.

## Known issues
- The last two x-axis labels (2025, 2026) overlap at 1280 px.
- The "Global comparison unavailable" fallback was checked by reading the code only.
