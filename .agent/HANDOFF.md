# Handoff - 2026-11-09 - EM-1 complete; next eligible tasks need owner input

## EM-1 Add-on A2 vocabularies and Need Ledger

### Done
- A2 vocabularies added to `config/taxonomy.yml` (`add_on_a2`); candidate keyword rules (20 flags, 32 product types) in `config/a2_keyword_rules.yml`, with tests.
- `atlas.evidence.need_ledger` + `scripts/build_need_ledger.py`: XLSX → deterministic `config/need_ledger.csv` and `docs/need_ledger_qc.md`. 70/70 roster rows, zero hard errors, taxonomy cross-check passes (EAT-2 and EAT-10 are now real tests).
- `atlas.evidence.quote_check` + `scripts/check_need_ledger_quotes.py`: local-only check of quotes against the owner's PDFs (skips without PDFs).
- `docs/LABELING_GUIDE_A2_ADDENDUM.md`: draft `guide_v2` addendum. The lead fixed its offshore wording to match `guide_v1` §3 (`partial`).
- Earlier this session: A2 integration (`35a2f95`), budget test date fix (`4b2154f`), and owner acceptance of all pending defaults (ADR-DEFAULTS-2026-11-09).

### State and next
- Owner actions: run the quote check on local PDFs; shorten the N2.9 and N4.1 quotes (>30 words) in the XLSX, then run `build_need_ledger.py`; answer EM-1-A (approve the addendum).
- SPK-1..SPK-4 are eligible but need owner authorization for new dependencies (DuckDB-Wasm, Mosaic, Observable Framework/Node) and for live hosting tests (Pages deploy of synthetic Parquet, Cloudflare R2). They were not started.
- EM-3 waits for EM-1-A approval plus labelling. EM-15 is an owner-run R script. EM-2's partial path (fetch the Regional Board layer, EAT-12) needs live network calls, which no task has authorized yet.
- S7.6 is owner WIP (`src/atlas/source_watchlist.py`, `tests/test_source_watch_s7_6.py`) and was left unstaged.

### Verification commands
- `py -3.14 scripts/check_em1.py`
- Full gate: links + A1/A2 scaffolds + `make lint test build` (367 passed, 10 skipped) + `git diff --check`

Older handoff entries: `.agent/archive/HANDOFF_history.md`.
