# VD-19 verification: site-wide header search

The header search covers experts, institutions, topics, funders and agencies, glossary terms,
related resources and pages. It opens a combobox on the header input and a results page at
`search#q=<query>`.

## What changed

- `src/atlas/build/search_index.py` and `scripts/build_search_index.py` (`--check` fails when stale).
- `site/data/search_index.json` (committed, rebuilt once) and the ingest step and staged output in
  `.github/workflows/ingest_works.yml`, after `build_network.py`.
- `site/assets/site_search.js` and `site/assets/site_search.css`: the combobox, the results page and the
  expert hero form handler (moved from the header's inline script).
- `framework/src/search.md`: the results page, `noindex`, not in `PAGE_GROUPS`, `PAGE_PATHS`, `llms.txt`
  or the sitemap (nothing needed changing there; a test checks it).
- `framework/observablehq.config.js`: `atlasHeader()` form, labels and toggle strings; `head` loads the CSS
  and a small loader for the script. `framework/scripts/postbuild.mjs` restores both on pages with their
  own head (for example `search` and `styleguide`).
- `docs/SITE_DATA.md`, `docs/DATA_DICTIONARY.md`; tests `tests/test_search_index.py` (new),
  `tests/test_vd3_shell.py` and `tests/test_vd5_overview.py` (old header text and handler location).

## Index size

| Type | Items | Source |
|---|---:|---|
| page | 11 | Overview plus the nav pages in `PAGE_GROUPS` |
| expert | 2,635 | `index.json` authors (no emails or abstracts) |
| institution | 211 | `institutions.json`, California-flagged (the Institutions page default) |
| topic | 19 | 11 research topics and 8 matrices (`site/assets/topics.js`) |
| funder | 19 | 10 funder agencies and 9 other funder names (`grants.json`) |
| term | 15 | `framework/src/glossary.md` |
| resource | 13 | `site/data/linkouts.json` |

Total 2,923 items: 260,917 bytes raw, 61,279 bytes gzip (target 150 KB gzip).
Client: `site_search.js` 16,198 bytes (4,454 gzip); `site_search.css` 4,006 bytes (1,274 gzip).

## Href targets (checked in the browser, `scratch/w2/verify_hrefs.py`)

- `funding#fa=NSF` selects "NSF" in the agency filter; `funding#q=National+Science+Foundation` fills the search.
- `experts#tag=air` and `experts#tag=matrix%3Aair` set the tag filter.
- `institution#inst=I4210160856` opens UC Davis Health.
- `glossary#access-tiers` scrolls to the term.
- `expert.html#author=<id>` opens the classic expert profile (the design's choice; the Experts drawer
  uses `experts#author=`).

## Browser checks (`scratch/w2/verify_search.py`, Chromium, local preview on port 8772)

- On `experts` and `glossary`, typing `davis` shows Experts (138) and Institutions (4); `microfiber`
  shows Glossary terms (1); `NSF` shows Funders and agencies (1); `access tiers` shows the glossary term;
  `marine` shows Experts, Institutions, Topics and Related resources.
- `glossary term` shows no match. Every query word must match, and no entry contains both words.
- Keyboard: ArrowDown, Home and End move the active option; Enter opens the selected profile; Escape closes.
- Enter with no active option opens `search#q=davis`; its groups and counts match the combobox totals.
- Results page search box updates the hash and the list.
- The hero form still opens `experts#search=davis`.
- Index failure (route blocked): the status says search is unavailable and Enter opens `experts#search=davis`.
- Mobile at 390 px: the panel fits (listbox x 13, width 364), `scrollWidth` 390; toggle label "Hide search".
- Accent-insensitive: `jose` matches "José ...".
- axe (WCAG 2.x A/AA) with the listbox open and on the results page: no violations.
- Console errors: none.

## Audit and checks

- `ux_audit.py` on `/`, `experts`, `glossary`, `search` at desktop and 375 px: axe 0 violations, 0 small
  targets, 0 unlabeled controls, no horizontal overflow, no heading skips, no console errors.
- Build: `ATLAS_FW_OUT=dist-w2 npm run build` succeeded; all 14 built pages carry the search assets and the
  header form. `assemble_site.py` ran into `scratch/w2_site`.
- `pytest tests/test_search_index.py`: 16 passed. Focused selection (`-k "search or header or at5 or site_data
  or public_text"`): 112 passed, 9 skipped (placeholders), 1,720 deselected.
- `build_search_index.py --check`: current.
- `check_at5.py --dist dist-w2`: passed (static and build).
- `check_public_text.py` (CI default): passed (18 files); with `framework/dist-w2`: passed (14 files).
- `check_doc_links.py`: passed (175 files).
- `ruff check .` and `ruff format --check .`: passed (627 files).
- `git diff --check`: no whitespace errors.

## Open issues and decisions

- The `framework/observablehq.config.js` footer hunk ("Source code" link removed) was already
  uncommitted and is not part of this change.
- `site/data/build_metadata.json` (the S3.1 size log) does not list `search_index.json`; it was not edited.
- The workflow step was not run (no network). It uses only the Python standard library, so it should run on
  the workflow's Python 3.11.
- The results page renders in the browser. Without JavaScript it shows a text note only.
- Funder names containing `;` (combined chains) are left out of the index.

## Lead follow-up (2026-11-16)
- The Overview hero form now uses the same site-wide combobox (`data-atlas-site-search`, action
  `./search`, `name="q"`, button "Search"); `.atlas-hero__search` anchors the listbox. Tests updated
  (`test_vd5_overview.py`, `test_search_index.py`). The `data-atlas-expert-search` fallback in
  `site_search.js` stays for any cached old markup.
- `npm run build` on the combined tree passes (the workers' build failures came from an intermediate
  state of the head change). Header dropdown checked for "davis" in the assembled preview.
