# Handoff - 2026-11-11 (overnight) - AT-1 v3 candidate ready; owner-gated work remains

## State
- Pushed, CI green on `e414e62` (779 tests). Since the last handoff: licenses (MIT code,
  CC BY 4.0 data), GitHub release `v2026.11.10` with snapshot ZIP, review-app fixes
  (fixed buttons, Back to last reviewed, `-- --csv`), AT-1 results (owner labelled 354
  works; v2 precision 82.8%), query v3 candidate `config/queries_v3.yml` (89.1% on the
  labelled set, 0 relevant lost, +4% global, named-author recall up, Moore Institute
  always-include, type exclusions), ingester support for `exclude_types` /
  `always_include`, S2.2 near-duplicate collapsing, S10.2 agent gaps (issue link, REUSE
  rows, Plastiverse disclosure, suppression/override/merge curation).
- Zenodo: no record found for `v2026.11.10` ~2.5 h after the release. The repo has no
  webhook visible to this token (scope lacks admin:repo_hook), so the Zenodo-GitHub
  link is probably not active for this repository.
- Clean-worktree pytest took 1 h 35 min on 2026-11-11 (normally ~90 s); all passed.
  Suspect antivirus scanning a fresh worktree; check before the next long session.
- Worktree leftovers (not committed on purpose): stale S7.6 watch outputs in
  `docs/SOURCES.md` / `docs/api_notes/source_watch_s7_6.json`; owner's
  `data/processed/p{5,25,100}.parquet` R2 copies.

## Owner actions (one line each)
1. Label the AT-1 repeat sample (143 works; now includes plastics LCA, recycling, bioplastics): `py -3.14 -m streamlit run scripts/review_query_audit_app.py -- --csv docs/QUERY_AUDIT_REVIEW_V3.csv`, then say "v3 labels done".
2. Zenodo: at zenodo.org → Account → GitHub, confirm `ScottCoffin/CA_Plastics_Research_Dash` is ON (press Sync if offered), then say "Zenodo fixed"; the agent will publish a new release `v2026.11.11` (Zenodo only archives releases made after the switch).
3. Governance checklist (`docs/GOVERNANCE_CHECKLIST.md`): review the "Needs owner decision" rows (PI names on grants, ORCIDs, Sea Grant scraper, monitoring registry licences, GeoNames CC BY 3.0 vs 4.0 note) and the new Plastiverse disclosure sentence on the About tab; sign off.
4. Optional: `www.plastiverse.live` is Cloudflare-proxied; set DNS-only CNAME → scottcoffin.github.io or delete it.

## Next eligible
- After 1: compute repeat-audit precision; if acceptable, AT1-V3 / S1.5-A promotion
  (switch `config/queries.yml` to v3; update S2.3 labels and checks that pin the v2
  version), then S2.1 backfill → AT-2 → AT-3 → AT-4; S3.6, S4.2, S6.1 on real data.
- After 2: release `v2026.11.11`, add the DOI badge to README.
- After 3: check off S10.2.
- No gate: Monitoring sample-table paging; reconcile `config/author_overrides.csv`
  (normalize) with `curation/author_merges.csv` (export).

## Verification commands
- Full gate per CLAUDE.md, plus the clean-worktree run and CI after push.

Older handoff entries: `.agent/archive/HANDOFF_history.md`.
