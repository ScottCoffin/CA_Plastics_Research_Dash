# Handoff — 2026-11-17 (end of session) — platform pivot started: /california, global landing, Norway

## State in one paragraph
Everything listed under "Done" is committed, pushed, and deployed green (CI + Pages). The owner set
a new direction late in the session: California moves to `plastiverse.live/california` (clean
break, no redirects); the root becomes a global landing page designed with Impeccable (structure
locked); Norway is the next MVP; one monorepo; weekly email via Buttondown. The architecture plan
is `docs/PLATFORM_ARCHITECTURE.md` (owner has not yet reviewed it in detail). Three workers were
stopped for budget: PLAT-1 (move) and PLAT-2a (global map data) had changed nothing; MAIL-1
(digest) was finished and is committed with its schedule disabled (see Open findings).

## Done this session (highlights; details in TODO and SESSION_LOG)
- VD-27..VD-35: favicon and mark, full-width text, Funding heatmap filters, Experts/Network fixes,
  network mobile, tooltips, homepage map spring intro (every load), creator credit replaces the
  disclaimer, Resources icons (13/13, owner logos for ToMEx/One4All/DTSC) and steward institution
  links, no repo links (corrections go to mailto theplastiverse@gmail.com), Evidence journal filter
  and "2-yr mean citedness (OpenAlex)" column, compact page heads.
- EM-17 partial: OPC Solutions track panel + review app (owner review H28 pending).
- Ingest repair: OpenAlex made `from_updated_date` paid (HTTP 403 from 2026-11-16). Incremental
  runs use `from_publication_date` with an adaptive lookback, Sunday deep sweep, `OpenAlexPlanError`,
  and a "Daily ingest failing" issue (label `ingest-alert`). The derived files (institution types,
  journal metrics) rebuild after the export. The owner's missing paper (doi 10.1021/acsestwater.6c01560) is live.
- NOTIFY-AB: About "Get updates" panel (feed + ntfy topic `plastiverse-california`), daily ntfy post.
- H27 HTTPS enforced (verified 2026-11-17).

## In flight / next (in this order)
1. **MAIL-1 fix, then enable.** `src/atlas/build/digest.py` selects "new this week" by
   `works_detail.first_seen`, but the 2026-11-11 re-ingest reset `first_seen` for most works (dry
   run: 1,565 works for one week). Fix the selection (e.g. require `pub_date` within the last ~60
   days as well as `first_seen` in the window, or persist a first-seen ledger that survives
   re-ingests). Then re-enable the cron in `.github/workflows/weekly_digest.yml`. It sends only when
   the `BUTTONDOWN_API_KEY` secret exists (owner H29), and the API flow is draft → publish
   (`docs/api_notes/buttondown.md`). Send the owner a test first.
2. **PLAT-1 move California to /california (clean break).** The brief is in this session's
   transcript; summary: move `framework/src/*.md` pages into `framework/src/california/`, fix
   relative imports and siteRoot data paths, set PAGE_GROUPS/nav/footer under /california, root
   `index.md` becomes a placeholder until PLAT-2, SEO pages to `/california/experts/<id>/` etc.,
   sitemap/robots/llms/feed links/search index/ntfy click URL/digest site_url, remove redirect-stub
   generation in `scripts/assemble_site.py`, update tests deliberately. Cross-cutting, so the lead
   or an Opus worker implements and `sonnet-reviewer` reviews. After deploy: owner resubmits the
   sitemap in Search Console.
3. **PLAT-2a global data**: Natural Earth 110m admin-0 outlines → `site/assets/world/` (public
   domain; script `scripts/build_world_map.py`), California outline for the red overlay, and
   `scripts/build_global_counts.py` → `site/data/global/global_counts.json` (OpenAlex group_by
   `authorships.countries`, total, by year, new this week via `from_publication_date`; ≤ 60 credits;
   never paid filters). Wire into the daily workflow after it works.
4. **PLAT-2 build the global landing** (Impeccable, code-led). Direction contract:
   `.impeccable/surfaces/framework-src-index-md.md`; chosen sketch:
   `.impeccable/mocks/decision/assigned.html` (Tile cartogram). Owner steer: a real world map with
   country outlines; built regions vermilion, all others white/grey/black by volume; keep the
   four-plane stats strip from the "Region doors" sketch; built regions breathe on hover; springy
   assembly of continents on every load (like California); text saying regions are added by user
   interest and need, and that region experts are needed for guidance and QA/QC. Finish with the
   Impeccable finish reviewer and documenter (DESIGN.md), per new-work.md section 7.
5. PLAT-3 (region abstraction), PLAT-4 (global ingest + local partition), NOR-1..5: see
   `docs/PLATFORM_ARCHITECTURE.md` section 8 and the TODO entries.

## Open findings
- Daily-ingest plan refusals returned as HTTP 429 still defer without an alert; failures after a
  good refresh do not alert.
- `.agent/MEMORY.md` is about 280 lines (target 200); compact it at a quiet checkpoint.
- Impeccable doctor reports setup drift (config `buildPath` unset); run `/impeccable doctor` only if the owner asks.

## Owner actions (one line each)
- H29: create the Buttondown account and add the `BUTTONDOWN_API_KEY` repository secret, then say "Buttondown ready".
- H28: review the 22 OPC mapping rows (`py -3.14 -m streamlit run scripts/review_opc_mapping_app.py`).
- Review `docs/PLATFORM_ARCHITECTURE.md` (especially the Norway sources marked [VERIFY] and the tier model).
- After PLAT-1 deploys: resubmit `https://plastiverse.live/sitemap.xml` in Google Search Console.
