# Handoff — 2026-11-26 (evening) — owner notes recorded, CG-7a and CG-14 done; next is Codex

## Done

- Owner notes of 2026-11-26 are in the roadmap (commit `05e9d5be`). None of them is started:
  - **AMB-POOL**: remove Renew lease and Return to the pool. A tagged group leaves every pool. When two people tag the same group, the first tag wins and the later one is kept as a blind second tag, never an error (ADR-AMB-POOL-2026-11-26, QUESTIONS AMB-POOL).
  - **AMB-ROSTER-QC**: the roster duplicate and name questions move into the tagging form. H58 is now optional; the owner's 5 decisions stay in `curation/group_merges.csv`, which is uncommitted owner work. Leave it alone.
  - **FAVICON-MAIN**: every page uses the main Plastiverse Live icon, not the paper California.
  - **GP section**: every California Atlas feature on the main site for every region, with a California regression gate first (ADR-GLOBAL-PARITY-2026-11-26).
  - **H57**: the owner authorized the Worker deploy.
- CG-7 is split into 7a and 7b. **CG-7a** is done (`df9232e0`):
  - `atlas.agreement` has weighted kappa, PABAK, AC1 and a bootstrap.
  - `precision_card.json` is now cg-precision-v2 and reads two empty curation CSVs.
- **CG-14** is done (`49e68f38`): a "How this list is made" section on `/groups`, and a pre-filled correction email on the group card.

## Verification

- Main checkout: ruff lint and format, compileall, links, A1-A4 scaffolds, public text, design tokens, `build_groups.py --check`, `git diff --check`.
- Focused tests: 130 (agreement and groups build) and 26 (groups page plus node runtime). `npm run build` passed.
- Clean-worktree full pytest: see SESSION_LOG.
- Not done: no browser walk of CG-14. The close-then-scroll from the card to `#gv-methods` is unverified in a browser.

## Next tasks (in order)

1. **AMB-POOL**, then deploy the Worker (H57 authorized). No D1 migration is needed: reuse `group_leases.expires_at` for the invisible 2-hour hold and leave `renewals` unused. If a migration turns out to be needed, stop and add an owner task.
   - After the deploy, check that `/groups/*` returns 401 without a session.
   - Then ship the GRP-NAME-FIX "Correct the name" field in `framework/src/components/ambassador_groups.js` (payload `name_correction`).
2. **CG-7b**: blind 10% second tags, reviewer sampling, reason-coded edits, audit log (migration 0008), and an export into `curation/group_double_tags.csv` and `curation/group_reviews.csv`. The migration and deploy need a new owner go-ahead; add it to HUMAN_TASKS as H59.
3. **AMB-ROSTER-QC**, then **FAVICON-MAIN** (size S).
4. CG-12, then CG-12b. V-EVID reads the v2 card.
5. **GP-0**: parity inventory `docs/GLOBAL_PARITY.md`, then GP-1 (California regression contract).
6. Then AMB-PARENT-REGION, AMB-MAIL-STYLE, ALERTS-GLOBAL, BQ-S9b, BQ-G3.
7. CG-15 is an owner pilot, and CG-16 follows it.

## Gotchas

- V14 leak guard: no published key or string may contain "excluded". CG-7a uses `dropped_cannot_determine_n`.
- Run the clean-worktree pytest with `PYTHONPATH=<worktree>/src` and `--basetemp` outside the repo.
- Browser harnesses (ignored): `scratch/cg11_walk.py` and `scratch/ambux_walk.py`. Build `framework/dist-ambux` first.
- Open owner items: H58 (optional), H39, H28, H42, H2.
