# Handoff - 2026-11-11 (overnight 3) - query v3.1 promoted; grants, monitoring map, experts pipeline fixed

## State
- AT-1 complete: owner labels on the 143-work repeat sample put v3's additions at 53.1%
  precision; clause attribution produced `plastic-v3.1` (additions 70.6%, est. ~83.8%
  overall vs v2 82.8%), now active in `config/queries.yml`; v2 archived as
  `config/queries_v2.yml`. Evidence: `docs/QUERY_AUDIT.md`.
- Grants (owner report): 501/524 awards were flagged plastic on any abstract mention. New
  rule: short-title match, or a reviewed label in `curation/grant_relevance.csv` (275
  abstract-only awards judged by Claude Haiku reviewers); abstract-only default false.
  Live payload now 358 plastic-related.
- Monitoring (owner report): SF Bay matrix codes sw/sed/eff/fish mapped (unknown 200 -> 2);
  map is an SVG California basemap (land + state waters) with Statewide / SF Bay extents,
  matrix colours, ring-segmented mixed clusters and a legend. Checked in headless Edge.
- Experts (owner report): the live page had only ever served the 4-work fixture; CI never
  exported real data and the daily ingest had failed on 429s. Fixed: burst-429 retry and
  throttle, budget guard charges unknown-credit 429s the reserve, version-change full
  backfill (replaces v2 rows), CA-affiliated experts only, and `ingest_works.yml` now
  exports `site/data`, commits and dispatches the deploy.
- S10.2 complete (GOV-B signed; suppressions applied at ingest; response time on About).
  EM-16 LO-9/LO-12 owner-confirmed. S11.1 dropped; S11.3 partial (Haiku grant review).
- Budget: audit attribution calls bypassed the guard; UTC 2026-11-11 spend about $0.69
  (free plan, under $1, but over the $0.25 local stop), so the local backfill was not run.
- Worktree leftovers (not committed on purpose): stale S7.6 watch outputs in
  `docs/SOURCES.md` / `docs/api_notes/source_watch_s7_6.json`; owner's
  `data/processed/p{5,25,100}.parquet`.

## Owner actions (one line each)
1. Check the live Experts tab after the next `ingest_works` run (10:17 UTC daily), or run it now: `gh workflow run ingest_works.yml`.
2. GRANT-REL: spot-check the 76 low-confidence rows in `curation/grant_relevance.csv`, edit `plastic_related` where wrong, and set `owner_review`.
3. EM18-DATES: confirm "18 June 2026" and "1 October 2026" on the DTSC pages.

## Next eligible
- S2.1-B: confirm the CI backfill/export run, then record counts and payload sizes (S3.6
  performance pass becomes measurable on real data).
- Then AT-2 -> AT-3 -> AT-4 -> EM-5 and the S4.2 representative sample.

## Verification
- Full gate passed locally (866 tests); clean-worktree run and CI after push: see
  SESSION_LOG.

Older handoff entries: `.agent/archive/HANDOFF_history.md`.
