# Need Ledger QC report (Add-on A2, EM-1)

Generator: `scripts/build_need_ledger.py` (module `atlas.evidence.need_ledger`).
Regenerate with `py -3.14 scripts/build_need_ledger.py`; do not edit by hand.

## Input

- File: `docs/opc_needs_csv_Need_Ledger_Data_File_companion_to_Add_on_Spec_A2.xlsx`
- SHA-256: `068bce0f216194da98b1204b665d40269afe56cd99f2c1cc41bc0a84c1f525fa`
- Rows: 70 (roster 70)
- Hard validation errors: 0 (a failing run writes no output)

## Row counts per block

| Block | Rows |
| --- | ---: |
| 1 | 11 |
| 2 | 10 |
| 3 | 3 |
| 4 | 6 |
| M | 5 |
| X | 2 |
| D | 14 |
| DI | 16 |
| DC | 3 |

## Enum tallies

### statement_type

| Value | Rows |
| --- | ---: |
| management_question | 8 |
| stated_gap | 19 |
| recommended_activity | 8 |
| dtsc_information_request | 28 |
| dtsc_screening_statement | 2 |
| listing_criterion | 3 |
| extension_not_in_source | 2 |

### quote_verification

| Value | Rows |
| --- | ---: |
| direct_page_text | 40 |
| analyst_transcribed | 30 |

### rule_confidence

| Value | Rows |
| --- | ---: |
| medium | 51 |
| low | 19 |

### source_doc

| Value | Rows |
| --- | ---: |
| OPC2022 | 0 |
| MON2026 | 37 |
| DTSC_WP | 0 |
| DTSC_BG2025 | 30 |
| DTSC_2023 | 3 |
| DTSC_LIST | 0 |
| DTSC_RES | 0 |

## Findings (non-blocking)

- quote_length: 2

Details:

- quote_length: N2.9 quote has 34 words
- quote_length: N4.1 quote has 38 words

## Documented source discrepancy

The 2022 Strategy's Executive Summary states 22 recommended early actions and 13 research priorities (PDF 5). The Strategy has exactly 22 distinct early-action codes (PDF 22–24) and 14 distinct research-priority codes (Chapter 2B; PDF 30, repeated PDF 33–34). The atlas records "13" as a documented source discrepancy, hard-codes neither total in UI text, and does not speculate about the reason.
