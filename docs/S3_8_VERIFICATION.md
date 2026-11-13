# S3.8 verification: search-engine findability

## What was built

- `src/atlas/build/seo.py`: stdlib builder. Writes one static page per expert in
  `site/data/index.json` (`site/experts/<id>/index.html`), one per California-connected
  institution with works (`site/institutions/<id>/index.html`), and `site/sitemap.xml`
  (index) with `sitemap-pages.xml`, `sitemap-experts.xml` and `sitemap-institutions.xml`.
- `scripts/build_seo_pages.py --site site [--base https://plastiverse.live]`: CLI wrapper.
- `scripts/check_s3_8.py --site site`: validates `robots.txt`, the sitemaps (well-formed,
  absolute https `<loc>` under the base, at most 50,000 URLs per file), at least 20 sampled
  expert pages and every institution page (one `<title>`, meta description, canonical,
  one parseable JSON-LD block of the right `@type`, no email-like strings, no "abstract"
  text). Exits 1 with messages on failure.
- `site/robots.txt` (allow all crawlers; sitemap reference) and `site/llms.txt`.
- `site/index.html` `<head>` only: canonical, Open Graph tags and a JSON-LD `@graph`
  (WebSite and Dataset, licence CC BY 4.0, DOI 10.5281/zenodo.24124016).
- `.github/workflows/build_deploy.yml`: one best-effort step "Build SEO pages" after
  "Build digest feed".
- `.gitignore`: `site/experts/`, `site/institutions/`, `site/sitemap*.xml` (deploy-only).

Pages are generated at deploy time and not committed. Expert pages use only public
fields (names, affiliations, counts, topic labels, DOI and ORCID links). Abstracts and
contact fields are never copied. Every data string is HTML-escaped. JSON-LD escapes
`<`, `>` and `&`. IDs must match `^[A-Za-z0-9_-]+$` or the record is skipped.

## Checks run

| Command | Result |
|---|---|
| `py -3.14 -m pytest -q tests/test_seo_s3_8.py` | 10 passed |
| `py -3.14 scripts/build_seo_pages.py --site site` | exit 0: 2,614 expert pages, 206 institution pages, 2,831 sitemap URLs, 10,042,025 bytes written (pages and sitemaps) |
| `py -3.14 scripts/check_s3_8.py --site site` | exit 0: `ok`, 25 expert pages sampled of 2,614, 206 institution pages checked |
| `py -3.14 scripts/check_s3_2.py` | exit 0 (S3.2 shell acceptance passed) |
| `py -3.14 -m ruff check src scripts tests` | All checks passed |
| `py -3.14 -m ruff format --check` (4 new Python files) | already formatted |
| `py -3.14 scripts/check_doc_links.py` | exit 0 |
| `git diff --check` (edited tracked files) | clean |

The generated `site/experts`, `site/institutions` and `site/sitemap*.xml` were deleted
after the run, as the deploy-only design requires.

## Assumptions

- `/grants.html` and `/feed.xml` are excluded from the sitemap. The brief's list was
  ambiguous on `/grants.html`; the default is excluded.
- Institution pages are written only when `ca_flag` is true and `work_count` is above
  zero (206 of 211 CA-flagged institutions). Top-expert links appear only for IDs present
  in the expert index, so no link points to a missing page.
- The `<lastmod>` value comes from `build_metadata.json` `generated_at` (2026-11-13).
  It is omitted if that file is missing.
- Stale generated pages are not removed by the builder. CI builds from a fresh checkout,
  so this is harmless there.

## Owner actions

1. AI crawler decision (S3.8-AI): robots.txt currently allows all crawlers.
2. Google Search Console and Bing Webmaster Tools: verify the domain through a Cloudflare
   DNS TXT record, then submit `https://plastiverse.live/sitemap.xml`.
3. Run the Rich Results test on one expert page (for example `/experts/A5000014168/`)
   to check the Person JSON-LD.
4. Confirm after the next deploy that `https://plastiverse.live/robots.txt` and
   `https://plastiverse.live/sitemap.xml` are served.
