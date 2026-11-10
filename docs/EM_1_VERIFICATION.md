# EM-1 verification: Add-on A2 vocabularies and Need Ledger

Task: EM-1 in `.agent/TODO.md`; contract in [Add-on A2](add_on_spec_2.md) §§3–4, §6.3 and §9.
Date: 2026-11-09.

## Definition of Done

| DoD item | Result | Evidence |
|---|---|---|
| Existing study_type diffed if present | No controlled vocabulary existed. `study_type` was open text in the annotation schema (`atlas.nlp.annotation`, `atlas.nlp.eval`), and no human gold labels exist, so no old → new mapping is needed and no human label is overwritten. | `config/taxonomy.yml` `add_on_a2.study_type` (15 values) |
| Roster test passes | 70/70 rows, unique IDs equal the §6.3 roster, 20 columns in order, zero hard validation errors | `tests/acceptance/add_on_a2/test_eat10_ledger_roster.py`, `tests/test_need_ledger_em1.py`, `docs/need_ledger_qc.md` |
| 13/14 discrepancy recorded | Recorded verbatim in the QC report; neither total is hard-coded for UI use | `docs/need_ledger_qc.md` |

## Deliverables

- `config/taxonomy.yml` `add_on_a2` block, with values copied from A2 §§3–4. It holds 15 study_type values, 12 compartments, 7 waterbody types, 6 pathways, 7 source categories, 32 product types (16 Table 1, 14 Table A1, 2 footnote) plus parent/subtype map, size_class, size_subclass, 12 region values, 4 drivers, 20 keyword flags, and an [INF] base-matrix map (A2-C2). Pre-A2 consumers read only `domain_tags`, so S2.3 outputs are unchanged.
- `config/a2_keyword_rules.yml`: candidate rules for all 20 flags and 32 product types (`[E]`, lead-written). Precision is unmeasured until the EM-4 spot-check (A2-C15). `tests/test_a2_keyword_rules.py` pins ID parity with the taxonomy, checks that patterns compile, and covers 17 positive/negative examples, including a regression for an alternation bug ("entire" matching tire).
- `atlas.evidence.need_ledger` + `scripts/build_need_ledger.py` read the owner XLSX into the deterministic `config/need_ledger.csv` (A2-INT-1 default). `--check` fails when the CSV or QC report is stale. Every `cell_rule`/`evidence_cols` literal and `kw_` flag exists in the taxonomy (EAT-10).
- `atlas.evidence.quote_check` + `scripts/check_need_ledger_quotes.py`: a local-only quote regression against the owner's PDFs (`--pdf-dir`/`ATLAS_A2_PDF_DIR` plus a `--map` file). Its report goes to ignored `data/interim/` and holds statuses and ratios only, never quote text. With no PDFs it skips with exit 0.
- `docs/LABELING_GUIDE_A2_ADDENDUM.md`: a draft `guide_v2` addendum. `guide_v1` stays frozen; approval is `QUESTIONS.md` EM-1-A.
- EAT-2 and EAT-10 are now real offline tests. `scripts/check_a2_scaffold.py` allows only these two stubs to hold tests.

## Owner follow-up (2026-11-09)

- Quote regression run against the owner's Zotero PDFs (MON2026, DTSC_WP,
  DTSC_2023, DTSC_BG2025; no ledger row uses OPC2022 or DTSC_WP as
  `source_doc`). Result: **69/70 `match_on_page`**. The one exception, N3.2, is
  accepted: the source PDF (p. 46) misprints "minimum" as "mimum", and the owner
  ruled on 2026-11-09 to keep "minimum" with no [sic]. The checker therefore
  reports N3.2 as `not_found` (similarity 0.972), so `--strict` exits 1 by design.
  The report is in ignored `data/interim/need_ledger_quote_check.json`.
- The checker now matches elided quotes (`…`) segment by segment, and it
  tolerates one layout interruption (running header or footer, figure label,
  table-cell wrap) of at most 400 characters, with each half at least 20
  characters. Three false misses were genuine quotes split this way: N1.6
  (figure label, PDF 30), N2.2 (page footer and photo caption, PDF 36–37) and M3
  (table-cell wrap, PDF 61). The `pdf-to-markdown` extraction confirms the wording
  of all three; M3 reads contiguously there.
- Ledger edits in the owner XLSX, each with a dated row note: N2.9 shortened
  from 34 to 28 words by eliding two citations (`…`); N4.1 shortened from 38 to
  29 words as a contiguous verbatim span; trailing whitespace was removed from
  multi-line cells (41 cells, whitespace only). The QC report now has no findings.
- `guide_v2` (`guide_v1` plus the addendum) was approved 2026-11-09; hashes are in
  `docs/LABELING_GUIDE_REVIEW.md`.

## Commands

- `py -3.14 scripts/check_em1.py` passed. It covers vocab counts, rule parity and compilation, the discrepancy record, `build_need_ledger.py --check`, the A2 scaffold, and the quote-check skip path.
- Full gate passed: links, A1/A2 scaffolds, lint, 367 tests passed / 10 skipped (477 / 9 after the 2026-11-09 follow-up), build, and `git diff --check`.
