# Handoff - 2026-11-14 - Framework at the root, network, institution page, badges, a11y pass

## Done this session (checks: full gate, ruff, AT-5 build + check, public text, S3.8 and S10.2
## checks, six UX-18 tasks on an assembled local copy, clean-worktree pytest before push)
- AT-5 / H16 switch: the deploy assembles the Framework app at the site root
  (`scripts/assemble_site.py`); `/app/*`, `grants.html`, `sem.html` redirect with the hash kept;
  classic `#tab` links redirect; `atlas.js` `siteRoot()` replaces the `../data/` assumption.
- UX-30: the Evidence map heatmap always narrowed the table (Edge and Firefox), but nothing showed
  it. Now: marked and dimmed cells, column buttons, "Show in table", a banner and headline count.
- UX-31: `/institution#inst=<id>` full page (tiles, per-year chart, sized topic chips that filter,
  lead authors, collaborators, journals, most-cited, publication table); names link to it.
- S9.4: sigma.js + graphology network (zoom, drag, search, panel, colour/size modes, ForceAtlas2);
  networkx declared; the daily ingest rebuilds `network.json` (S9.4-DEP).
- REL-2: auxiliary topic "Plastic-associated chemicals" (102 works tagged, 94 published) with the
  coverage disclaimer (chip tooltip, glossary, Evidence map).
- S9.3 (partial): `expert_badges.json` (89 experts) and badges, Funding, Datasets, Co-author
  institutions and a template topic sentence on expert.html.
- S3.8: robots.txt names AI crawlers with Allow; sitemap and llms.txt list root routes.
- UX-19: assisted WCAG 2.2 AA pass, `docs/UX_19_ACCESSIBILITY_PASS.md` (12 failure rows, no fixes).
- UX-20: session plan refreshed for the switched site; task card and results template added.
- Daily ingest fix: it failed on 2026-11-12 and 2026-11-13 (`run_daily_ingest()` lacked the
  `publication_date_cap` the runner passes since 5d3aa61d), so site data last refreshed 2026-11-11.
  The parameter is now forwarded; regression test in `tests/test_ci_guards_at11.py`.
- Clean worktree (owner, 2026-11-14): gold-label sheet `curation/annotations/annotations_SC.csv`
  committed (38 of 580 rows labelled); stray local source-watch run discarded (patch in
  `scratch/source_watch_local_run_2026-11-10.patch`); Quarto preview and SPK-1 parquets gitignored.
- Peer session (2026-11-13): owner did H20 (Search Console + sitemap); folded into these records.

## Not verified / left
- Live after deploy 43575952984 (2026-11-14): Framework is the root; GitHub Pages serves
  `experts.html` for `/experts` (no SEO-folder collision); six UX-18 tasks pass on
  https://plastiverse.live/; Evidence map selection, network (canvas 0.58 s), institution page,
  legacy `#institutions?...` redirect and 375 px checks pass with no page errors. CI 43575952979
  green. Lighthouse SEO still unmeasured.
- UX-19 rows are recorded, not fixed (spec). Fixing them is the next UX task.
- Network: hover, drag, wheel zoom and full screen were not exercised by automation; the WebGL
  fallback was not forced. One unexplained "element is not enabled" flake in a worker run.
- UX-13 remainder: expert.html in the app shell; URL state on Funding and Monitoring.

## Next eligible
0. Confirm the next scheduled `Daily works ingestion` run succeeds (it now also builds the
   network and badges).
1. Fix the UX-19 failure rows (new task), then UX-13 remainder.
2. After H21/H23 answers: close S9.4 and S9.3. After H20b: close S3.8 (with Lighthouse).
3. S5 chain (then EM-4 -> EM-8..13) after H9.

## Owner actions (details in `.agent/HUMAN_TASKS.md`)
- H21 network review (now sigma.js); H23 institution pages + 10 expert profiles (S9.3);
  H22 screen-reader check (optional); H20b Bing + Rich Results (optional); H18 sessions (optional).
- QUESTIONS: H16-STUBS (redirect map), S9.3-NAMES (PI name matching), REL-TITLE (explained in the
  session report).
