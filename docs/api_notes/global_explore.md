# Global explore data (GA-2a)

Two committed files feed the `/explore` page. Both are written by scripts, and the page needs no key.

- `site/data/global/explore_sample.json` comes from `scripts/fetch_global_explore_sample.py`. It holds real OpenAlex samples under the active plastics query: scopes `world`, `US`, `CN` and `NO` (authors, institutions, topics, years, co-author countries, 12 newest works), plus co-author countries for the 15 largest countries that are not US, CN or NO.
- `site/data/global/explore.json` comes from `scripts/build_global_explore.py`, offline. It holds per-country map runs, names, continents, counts, California cells, the world trend and the sample inlined as `sample`.
- Request plan: 35 requests per refresh (4 world, 6 each for US, CN and NO, 13 co-author lists). A search-filter request costs 10 credits, so a refresh is about 350 credits, sent through `BudgetedRun` in `build_global_counts.py` under the daily guards in `config/budget.yml`.
- Raw cache: `data/raw/global_explore_sample/<UTC date>/<label>.json` (git-ignored). Only today's folder is reused. A rerun on the same UTC day, or after a partial failure, sends only the missing requests. `--force` rebuilds the output from those files and does not refetch them, so a real refresh needs a new UTC day.
- Freshness: the output is skipped ("cached") while its `query_version` matches and `fetched_at` is under 7 days old. `fetched_at` is the newest raw file's time.
- `build_global_explore.py --check` exits 1 when the committed file differs from a rebuild. The build reads no clock: trend years run to the year of `global_counts.json` `fetched_at`.
- Names: `NAME_FIX`, then the name in `world.json`, then a fixed table for codes the 110 m map lacks, then the ISO code. No pycountry.
- Known limits:
  - Under the global query some titles are off-topic.
  - Country institution lists include institutions of foreign co-authors, not only the country's own.
  - Continent totals on the page are sums of country counts, so a work with co-authors on two continents counts in both.
  - 36 countries with works have no map cell. The small-country rule gives a cell only within 3 cells, and a neighbour can take the nearest one first (Israel, IL, loses its cell to Palestine, PS).
  - The California works figure (1918) is a constant carried from the prototype, not a pipeline value.
