# Handoff - 2026-11-10 (late) - Monitoring, funding and governance checkpoints sealed

## State
- Closed today (all pushed; CI green on `1a3c19e`; 739 tests): S7.3 (SF Bay / 5 Gyres
  CC BY 4.0), S7.5 (public cleared observations), S7.6, S7.7 (Karapetrova 2026 Sierra
  snow, 40 rows), S7.8 (CEDEN concentrations by SampleID + weekly CEDEN watch), S8.7
  (NOAA MDP via USAspending ALN 11.999), S8.8 (FAAST awarded proposals), S10.4, SPK-1.
  The site moved to https://plastiverse.live/ (HTTPS enforced).
- Live monitoring payload: 298 observations (258 SF Bay + 40 Sierra), 56 QA samples
  excluded, 146 with concentrations. Publication is gated by `config/monitoring_publication.yml`.
- Prepared, awaiting owner: S10.2 governance checklist (`docs/GOVERNANCE_CHECKLIST.md`),
  S10.3 Zenodo release (`docs/REPRODUCIBILITY.md`, `make reproduce`).
- AT-1 labelling is in progress by the owner in the local app
  (`py -3.14 -m streamlit run scripts/review_query_audit_app.py`): 204/354 works labelled
  at last check. `docs/QUERY_AUDIT_REVIEW.csv` is the owner's uncommitted work; never
  overwrite it.
- Worktree leftovers (not committed on purpose): `docs/SOURCES.md` S7.6 rows and
  `docs/api_notes/source_watch_s7_6.json` from a pre-fix live run (the weekly workflow
  rewrites them); `data/processed/p{5,25,100}.parquet` (owner's R2 upload copies).

## Owner actions (one line each)
1. Finish AT-1 labels in the review app, then say "labels done".
2. LICENSE-A: confirm MIT (code) + CC BY 4.0 (derived data) so LICENSE can be written.
3. Zenodo: enable the repo under zenodo.org → Account → GitHub, then say "Zenodo on" (DOI minting is permanent; the agent waits).
4. S10.2: review the "Needs owner decision" rows in `docs/GOVERNANCE_CHECKLIST.md` and sign off.
5. Optional: `www.plastiverse.live` is proxied by Cloudflare; set it to DNS-only CNAME → scottcoffin.github.io or delete it.

## Next eligible
- After 1: AT-1 precision report and noise-term review → S1.5-A promotion decision →
  AT-2 → AT-3 → AT-4; S3.6, S4.2, S6.1 on real data.
- After 2+3: S10.3 release (tag `vYYYY.MM.DD`, snapshot ZIP attached).
- No gate: S10.2 agent-fixable gaps ("Is this you?" link, removal/suppression mechanism,
  work-override consumer, author merge/split, REUSE rows for grant APIs and ROR,
  affiliation disclosure); sample-table paging on the Monitoring tab.

## Verification commands
- Full gate per CLAUDE.md, plus the clean-worktree run and CI after push.

Older handoff entries: `.agent/archive/HANDOFF_history.md`.
