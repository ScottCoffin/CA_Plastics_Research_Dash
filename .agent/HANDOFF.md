# Handoff — 2026-11-27 — California feature port to Norway and Belgium (for Codex)

## Done (all pushed to main; strict clean-worktree gate and GP-1 California contract green at 7bc5b4a6)

- Port design ADR-GP-REGION-EXPORT (docs/GLOBAL_PARITY.md section 3b): `regionDataUrl()` resolves `data/<slug>/` from the page folder (`REGION_SLUGS` in framework/src/components/atlas.js); `scripts/build_region_export.py --region <slug> [--check]` writes California-schema payloads to `site/data/<slug>/` from the LOCAL global partition and raw store; thin region pages reuse the California components; California-only fields are null; unscreened works count via `plastic_related == null && screening_status == "unscreened_query_hit"` and are labelled.
- PLAT-4 slice 4: local `data/processed/global/authorships.parquet` (771,948 rows) and `institutions.parquet` (19,206) via `scripts/partition_global.py`.
- Ported to Norway and Belgium: GP-5 institutions, GP-2 authors (profiles generated from the California page by `scripts/build_region_profiles.py [--check]`), GP-3 collaboration networks (`scripts/build_network.py --region`), GP-4 topic tags (reference labeller on title + raw-store abstract), GP-8 works table and evidence map, GP-8b author links and abstract wording. GP-1 checker now waits for counts to settle (network page flake fixed).
- Earlier this session: CG-7b/7c, GRP-REVIEW-APPLY, FAVICON-MAIN, AMB-ROSTER-QC, CG-12/12b, GRP-ENRICH slices 1-3b, GRP-PLASTICS-QUOTE (Worker 665d4543, H63), GP-0/GP-1, GRP-LLM research (H64 deferred: no budget), GP-GROUPS recorded.

## State

- Production Worker 665d4543 with D1 0008. Working tree clean.
- Region payloads: Norway 18.1 MB, Belgium 14.3 MB (keep each under ~20 MB).

## Next tasks (in order)

1. GP-10a (registry regions): region topics page (`topics_timeseries.json`, `topic_bursts.json`) and region search index (`build_search_index.py --region`, region-aware `site/assets/site_search.js`); add a "Topics" link in `components/region_page.js`. Not started (the agent run stopped before editing anything).
2. EV-A11Y-SELECT: evidence-map selected-state contrast (shared CSS; also fails on California) — mention to the owner because it touches the frozen California design.
3. Region shell branding (header still says "CA Plastics Research Atlas") and GP-GROUPS (groups page into the /explore shell, map first).
4. Every-country scale waits on GX-1 (owner labelling, H39) and R2 (GX-3).

## How to verify any GP slice

`cd framework && npm run build`; `py -3.14 scripts/assemble_site.py --site site --dist framework/dist --out scratch/<x>_site`; `py -3.14 scripts/check_gp1_contract.py --site scratch/<x>_site` (must pass, California unchanged); Playwright on the region pages (0 errors/404s, no data/california requests, axe 0, no overflow at 390). Then the strict gate in a clean `git worktree` (links, scaffolds, ruff check + format, `git diff --check`, full pytest with an external `--basetemp`), and push only when green.

## Gotchas

- Region exports need the local partition and raw store (not in git); CI validates structure only. Rebuild order: partition_global -> build_region_export -> build_network --region -> build_region_profiles.
- src/atlas must not gain region names (ratchet test), comments included.
- Tests run on Linux CI: `sys.executable`, never the `py` launcher. Pipe-free gate checks (LESSONS).
- Chart views: verify in Chromium with a populated fixture; node stubs miss Plot/d3 problems (LESSONS).
- Pinned-string tests break when a California call is wrapped in a region guard: update the pin, keep California behaviour.

## Needs owner input

- H39 (160 global gold works), H9 (gold set), H2 (277 relevance decisions), H42 (43 PubMed records, in progress), H28 (policy mapping, ~15 min); UK Charity Commission and ACNC licence wording (pages blocked the agent). H64 deferred until a budget exists.
