# Handoff - 2026-11-10 - Overnight run finished; only owner-gated work remains

## State
- Completed overnight (all pushed; full suite 650 passed, 9 skipped): SPK-2,
  SPK-3, SPK-4 (gates G-PARQ, G-SHELL, G-FACET decided), S8.2–S8.6 (NIH, NSF,
  USAspending, Sea Grant, OPC/Delta + cross-source dedupe), S8.9 (open-calls
  panel), S8.10 (Funding awards UI, `site/data/grants.json`), S9.1 (17 work-grant
  links), S9.2 (work-dataset links UI), S10.1 (status page + drift alarms),
  S11.4 (Atom feed). Partial: SPK-1 (Pages leg done), S10.4 (CI green blocked by S7.6).
- Earlier the same day: Add-on A2 integration, EM-1, EM-2 (partial), S8.1.
- CI is red only on the owner's committed S7.6 test (`tests/test_source_watch_s7_6.py`:
  import order + one failing test). The owner's uncommitted S7.6 WIP fixes it locally.
- Gate rule added: also run the checks in a clean `git worktree` and confirm CI after
  pushing (ignored local files had hidden CI failures).

## Owner actions (one line each; reply in QUESTIONS.md or chat)
1. Commit the S7.6 WIP (`src/atlas/source_watchlist.py`, `tests/test_source_watch_s7_6.py`) → CI green, then check off S10.4.
2. SPK-1 R2: do the 5 steps in `docs/SPK_1_HOSTING.md` and give the bucket URL, or answer "skip R2".
3. AT-1: label the 405-row audit sample (`docs/QUERY_AUDIT.md`); unblocks AT-2 → AT-3 → AT-4 → AT-5 / EM-5+.
4. S1.5-A: promote `plastic-v2-candidate` (or revise it); unblocks real-data site, S3.6, S4.2, S6.1.
5. EM-3 / S4: start gold-set annotation under `guide_v2`; unblocks S5.x and EM-4.
6. S7.3-A: reuse terms for the SF Bay / 5 Gyres data; unblocks S7.3 and S7.5.
7. S8.7: which years of NOAA Marine Debris awards. S8.8: State Water Board funding guidance (`docs/AWARDS_DATA.md`).
8. Quick confirms (defaults in use): TODO-A (re-check S6.2/S6.3?), S8.6-A, S8.10-A, S9.1-A, S9.1-B (COAST phrase), S9.2-A.
9. Later sign-offs: S9.3 profile review, S10.2 governance, S10.3 archive choice.
10. Housekeeping: idle `python -` processes (PIDs 32200, 45096, 22944, 37256) from stuck heredocs; killing them was not permitted to the agent.

## Next eligible once answered
- After 1: check off S10.4.
- After 2: run `spikes/spk1_hosting/measure.py` against R2 → close SPK-1.
- After 3: AT-1 → AT-2 → AT-3, then AT-4 (all spike gates are decided) → EM-5, EM-7, EM-16..18.
- After 4: S3.6 performance on real data, S4.2, S6.1 coverage, real-data exports (feed and grants unaffected).
- After 5: S5.1–S5.7, EM-4, EM-8, EM-11.
- Optional, no gate: S11.1 (stlite fallback; low value now that G-SHELL = Framework).

## Verification commands
- Full gate per CLAUDE.md, plus the clean-worktree run; acceptance scripts `scripts/check_<task>.py` for every task above.

Older handoff entries: `.agent/archive/HANDOFF_history.md`.
