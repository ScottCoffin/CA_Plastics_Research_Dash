# BQ-R1 verification: "Authors", never "Experts" (2026-11-18)

Owner rule A3-D0. Public strings only (A3-C3); data keys, JSON fields, CSS classes, element ids, JS
identifiers, file names (`experts.js`, `experts.css`, `expert.html`), URL hash values and the static profile
paths `/california/experts/<id>/` plus `sitemap-experts.xml` are unchanged (A3-C4, A3-Q4 confirmed).

## What changed
- Route: `framework/src/california/experts.md` moved to `authors.md` (`/california/authors`, h1 "Authors").
  `framework/scripts/postbuild.mjs` writes a noindex redirect stub `california/experts.html` that keeps the
  query and hash (`ROUTE_STUBS`, `redirectStub`). Nav, Overview links, landing links, `/explore` tab label,
  site search fallback URL, search index hrefs, `PAGE_PATHS`/sitemap and `llms.txt` point to `/authors`.
- Visible text in Framework pages and components, the profile page `site/california/expert.html`,
  `site/assets/site_search.js`, SEO pages (`src/atlas/build/seo.py`), badge and network method strings
  (`expert_badges.py`, `network.py`; the committed JSON strings were patched to match, the daily ingest
  rebuilds them), and a new first glossary term **Author** with the A3 definition.
- `scripts/check_public_text.py`: new terminology rule, `\bexperts?\b` in HTML text nodes fails, except inside
  `<cite>`, `<code>`, `<q>`, `<kbd>` or `data-public-text="quoted"` (SEO work titles are now marked), legacy
  file names (`expert.html`, `experts/`, `experts_`, `experts-`), and the undeployed classic `site/index.html`.

## Method
A scratch rewrite tool changed words only in prose and inside JS string literals that contain a space
(outside `${...}`), and route links by explicit patterns; every changed line was reviewed by word diff. One
file-name slip (`expert.html` -> `author.html` in two places) was caught and reverted.

## Checks (2026-11-18)
- `check_public_text.py` on an assembled build with deploy-built SEO pages: OK, 2,882 files.
- Browser (Playwright, assembled preview): `/california/experts#tag=air` lands on
  `/california/authors#tag=air`; no visible "expert(s)" on `/california/authors`, `/network`,
  `/institutions`, `/glossary`, `/california/`, `/explore` after runtime rendering.
- axe (machine audit tool, desktop and 375 px): 0 violations on authors, network, glossary, California
  home, explore.
- Tests: expectations updated to the new path and words only; new `tests/test_bqr1_authors.py`.

## Independent review (Haiku, read-only) and fixes
- Bug fixed: the rewrite renamed a `PANELS` object key in `components/explore.js`, so the `/explore`
  Authors tab (`view=experts`) would have thrown. Restored; every `/explore` tab now renders with no page
  errors (Playwright, assembled preview).
- Fixed: profile-page list links go to `authors` directly (not through the stub); audit scripts
  (`ux19_a11y_pass.py`, `ux_tasks.py`, `design_snapshots.py`) target `/california/authors`; `llms.txt`
  heading; circular About sentence; "local researchers" for community guides everywhere; SEO title
  "plastics researcher"; CSV download name `ca-plastics-atlas-authors.csv`.
- Checker hardened: visible attributes (`placeholder`, `title`, `aria-label`, `alt`) are scanned;
  Atlas-written JSON method text (`$.method...` in `network.json`, `expert_badges.json`) is scanned;
  "expert-led" no longer slips through. Linkout descriptions quote stewards and stay exempt.
- Kept as is: the no-JS meta refresh drops the hash (the script keeps it).
- Checker on the assembled build with SEO pages after the fixes: OK, 2,882 files.
