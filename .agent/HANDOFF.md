# Handoff - 2026-11-10 (evening) - S7.6, S10.4, SPK-1 closed; only owner-gated work remains

## State
- Closed this session: S7.6 (owner WIP + request-time `Last-Modified` digest fix,
  `96d09e5`), S10.4 (CI green on `96d09e5`), SPK-1 (R2 leg measured at
  `https://data.plastiverse.live/spk1/`: all 206, 1.57 MB read of a 99 MB file;
  `docs/SPK_1_HOSTING.md`). Fixes: S8.9 test pinned to a date (`--today`); S2.4 daily
  ingestion now defers on a 429 that lacks a credit header (the 2026-11-10 run went red).
- Owner confirmed defaults: S8.6-A, S8.10-A, S9.1-A, S9.1-B, S9.2-A, TODO-A. AT-1-A:
  the 405-row sample is approved as the audit set (labels still blank).
- The listed idle `python -` PIDs no longer exist; nothing was killed.
- Worktree: `docs/SOURCES.md` and `docs/api_notes/source_watch_s7_6.json` hold one
  live watch run (2026-11-10, pre-fix false "changed"). They are not committed; the weekly workflow
  rewrites them. Untracked `data/processed/p{5,25,100}.parquet` are the owner's R2
  upload copies; they are safe to delete and must not be committed.

## Owner actions (one line each; reply in QUESTIONS.md or chat)
1. Domain: move the Pages site to `plastiverse.live`? If yes, set the repo's Pages custom domain plus Cloudflare A records (see chat), then tell the agent so it can update URLs. If no, add `https://scottcoff.in` to the R2 CORS `AllowedOrigins`.
2. AT-1: fill `review_label` (relevant / not_relevant) and `reviewer` in `docs/QUERY_AUDIT_REVIEW.csv` (405 rows; ~2-3 h), optionally `noise_terms`.
3. S1.5-A: after 2, decide whether to promote `plastic-v2-candidate` (the precision estimate from 2 informs it).
4. EM-3/S4 annotation: waits on 3 (no representative corpus to sample yet); nothing to do now.
5. S7.3-A: pick a license for SF Bay / 5 Gyres data: "ODC-BY, publish with attribution", "CC BY 4.0", or "ask SFEI first".
6. S8.7: NOAA Marine Debris award years (default proposal: FY2015–present). S8.8: State Water Board funding: ingest, curate by hand, or defer.
7. Later sign-offs: S9.3 profile review, S10.2 governance checklist, S10.3 archive choice (Zenodo vs GitHub release).

## Next eligible once answered
- After 1: update site URLs / R2 origin; re-run `spikes/spk1_hosting/measure.py --origin <site origin>`.
- After 2: AT-1 precision report → AT-2 → AT-3 → AT-4 → AT-5, EM-5, EM-7, EM-16..18.
- After 3: S3.6 on real data, S4.2, S6.1 coverage; then 4 → S5.x, EM-4, EM-8, EM-11.
- After 5: S7.3, S7.5. After 6: S8.7, S8.8.
- Optional, no gate: S11.1 (low value now that G-SHELL = Framework).

## Verification commands
- Full gate per CLAUDE.md, plus the clean-worktree run and CI after push.

Older handoff entries: `.agent/archive/HANDOFF_history.md`.
