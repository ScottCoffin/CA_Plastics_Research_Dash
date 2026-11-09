# S7.6 future-source watch

The watchlist tracks the planned California statewide plastics pilot and the
CEDEN 2.0 microplastics module as Tier C, manual-review items. It checks only
the two explicitly listed official HTTPS pages. Requests are sequentially
collected with at most three workers, eight-second timeouts, at most 50 URLs,
and a 1 KiB cap for Range fallback responses. Redirects are not followed.
HTTP status and response validators are recorded as availability metadata;
they do not establish data availability, quality, license, or permission to
ingest. A failed or restricted response remains a failed/restricted access
observation and never triggers a license or tier change.

`config/source_watchlist_s7_6.json` stores reasons, source links, and next
review dates. `docs/api_notes/source_watch_s7_6.json` records checked time,
observations, digest history, and whether access metadata changed. The script
replaces only the marked S7.6 generated block in `docs/SOURCES.md`.
`.github/workflows/source_watch_s7_6.yml` checks weekly and on manual dispatch.
It checks out the repository default branch and only stages the two watch
outputs when repository variable `ENABLE_DATA_COMMITS` is exactly `true`.
No private service, data download, model API, or paid request is used.

Run locally with `PYTHONPATH=src python scripts/check_source_watch_s7_6.py`.
Run offline fixtures with `python -m pytest tests/test_source_watch_s7_6.py -q`.
