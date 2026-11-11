# Handoff - 2026-11-11 (overnight 2) - all ungated work done; owner-gated work remains

## State
- Commits through `98acee5`; see "Verification" for push/CI status. New since last handoff:
  owner governance sign-off recorded (21/22 rows); release `v2026.11.11` archived on Zenodo
  (DOI 10.5281/zenodo.24124017; concept 10.5281/zenodo.24124016; README badge, CITATION.cff);
  query v3 now includes plastics LCA/recycling/alternatives (owner scope); repeat sample
  regenerated (143 works); Monitoring table pages at 50 rows; EM-16 link-out registry and
  weekly HTTP-status checker (dtsc.ca.gov answers 403 = "restricted"); EM-18 curated DTSC
  timeline with validator (UI waits on EM-5).
- Every remaining TODO task is gated on: the AT-1 repeat labels (AT-1 → AT-2 → AT-3 → AT-4 →
  EM-5+, S3.6, S4.2, S6.1), gold-set annotation (S5.x, EM-3/EM-4), or explicit owner gates
  (L3 spikes, S9.3, S10.2 last row, EM-13/14/17). Optional ungated S11.1 (stlite) and
  S11.3 (local review assist) were deliberately left for an owner call.
- Worktree leftovers (not committed on purpose): stale S7.6 watch outputs in
  `docs/SOURCES.md` / `docs/api_notes/source_watch_s7_6.json`; owner's
  `data/processed/p{5,25,100}.parquet` R2 copies.

## Owner actions (one line each)
1. Label the AT-1 repeat sample (143 works): `py -3.14 -m streamlit run scripts/review_query_audit_app.py -- --csv docs/QUERY_AUDIT_REVIEW_V3.csv`, then say "v3 labels done".
2. GOV-B: approve the removal policy (`curation/suppressions.csv` drops a person from every payload at the next build; wording in `docs/CORRECTIONS.md`) and sign the last checklist row.
3. GOV-A: confirm that signing the four decision rows means "keep current behavior" (PI names and ORCIDs shown, Sea Grant scraper kept, registry metadata kept).
4. DNS: edit `www.plastiverse.live` (CNAME → parkingpage.namecheap.com, proxied) to CNAME → scottcoffin.github.io, DNS only; or delete it.
5. Confirm in a browser: LO-9 One4All root URL and LO-12 DTSC Work Plan URL; DTSC timeline dates "18 June 2026" and "1 October 2026".
6. Optional: decide S11.1 (stlite fallback) and S11.3 (local-model review assist): do or drop.

## Next eligible
- After 1: repeat-audit precision → AT1-V3/S1.5-A promotion (switch `config/queries.yml` to
  v3, update S2.3 labels and the checks pinning v2) → S2.1 backfill → AT-2 → AT-3 → AT-4.
- After 2: check off S10.2.

## Verification
- Full gate per CLAUDE.md, the clean-worktree run (slow on this machine: run it in the
  background), and CI after push.

Older handoff entries: `.agent/archive/HANDOFF_history.md`.
