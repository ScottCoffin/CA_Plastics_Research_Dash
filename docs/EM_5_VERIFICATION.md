# EM-5 verification: Evidence Map shell (2026-11-12)

Add-on A2 §5: "One tab, shared URL-hash filter state, A1 bit-set facets (AT-4). Distinct works
only. Every cell opens a drawer. A contextual related-resources strip follows the filters."
Built as an Observable Framework page (ADR-EM5-FRAMEWORK-2026-11-12), deployed at `/app/evidence`.

## What exists

- `framework/src/evidence.md`, `components/evidence.js`, `components/evidence_model.js`,
  `components/evidence.css`.
- Facets from the AT-4 bundle (`site/data/bundle/`) through the shared `facets.js` engine:
  topic, CA-led, sector, type, open access, plastic-related (checkbox groups with live counts),
  year range, title search; institution is valid in the hash but has no UI yet.
  "N distinct works match" counts distinct works (bit-set popcount).
- Hash state: `#topic=a,b&ca_led=yes&year_from=2015&year_to=2024&q=...`.
- Shared works drawer (`openWorksDrawer(title, workIds, opener)`, native `<dialog>`, newest
  first, 50 per page, links to OpenAlex). Later views (EM-8 matrix cells) reuse it.
- Related-resources strip from `site/data/linkouts.json` (EM-5a: `atlas.linkouts.strip_entries`,
  `scripts/build_linkouts_json.py --check`). Rules live in `config/linkouts.yml`
  `trigger_rules`: `topic=<tag>` or `default` (owner question EM5-STRIP, default rules in use).
- Placeholders for V-1 (EM-8), V-2 (EM-9), V-3 (EM-6), V-4 (EM-7), V-5 (EM-10).

## Checks run

- `npm run build` exit 0; `scripts/check_at5.py --dist dist` pass.
- Payload (DoD): the page's own modules and CSS ~17 KB gzip; with the facet bundle ~112 KB
  gzip, under the 3 MB landing budget.
- Headless Edge smoke: page renders topic labels with counts, "distinct works", and the strip.
- `tests/test_framework_evidence.py` (hash round-trip, strip rule, drawer paging),
  `tests/test_linkouts_strip_em5.py` (rule parsing, public field set, staleness, no Minderoo,
  topic tags exist in the bundle). Full gate: lint, 1,317 tests, build, links, scaffolds.

## Not verified

- The drawer dialog (open, Escape, focus return) was not exercised in a real browser; the
  smoke only dumps the DOM. Owner check in HUMAN_TASKS H16.
- Title search uses the substring `searchBits`, not MiniSearch ranking.
- `works_index.json` is fetched twice (engine + titles); cached by the browser, small.
