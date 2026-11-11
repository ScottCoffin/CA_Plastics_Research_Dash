# EM-18 verification: DTSC regulatory timeline (data part)

Task: EM-18 in `.agent/TODO.md`; contract in [Add-on A2](add_on_spec_2.md) §7 Part B and §9 (EAT-7).
Scope: curated data file and validator only. The UI rendering is not part of this task.

## What is curated

- `config/dtsc_timeline.yml`: 10 entries, hand-curated from DTSC pages and uploaded documents. No scraping, no network calls.
- Top-level `caveat` is the exact sentence "Listing does not by itself create requirements; Priority Product designation is a separate rulemaking." and `caveat_detail` carries the Priority Product categories sentence.
- Dates are kept as DTSC states them in `date_as_stated`; `date_iso` is YYYY-MM-DD when a day is stated and YYYY-MM when only a month is stated.
- Entries include the November 2025 Background Document, the December 2025 workshop and the January 2026 comments as three separate rows.

## Ordering rule

Entries are newest-first by `date_iso` across all kinds, including the two 2024 Work Plan rows. A month-only date sorts as the first day of that month. The validator enforces the rule (non-increasing keys).

## Sources

| Ref | Source | source_url in file |
|---|---|---|
| 8 | DTSC Candidate Chemical List: Microplastics | https://dtsc.ca.gov/scp/candidate-chemical-list_microplastics/ |
| 9 | DTSC Microplastics in Consumer Products research page | https://dtsc.ca.gov/scp/microplastics-in-consumer-products |
| 40 | DTSC release, 2 July 2026 | https://dtsc.ca.gov/2026/07/02/california-finalizes-regulation-adding-microplastics-to-candidate-chemicals-list |
| 7 | Background Document on DTSC's Microplastics in Consumer Products Research (uploaded, no URL) | Linked via ref 9 page; labelled as such |
| 32 | 2024–2026 Priority Product Work Plan (uploaded, no URL) | `null` |

Rows with `source_url: null` are the two Work Plan rows only. The EM-16 link checker reads `source_url` from this file and skips nulls.

## Validation

`src/atlas/dtsc_timeline.py` (`load_timeline`, `validate_timeline`) checks:
- required keys on the top level and on each entry;
- unique `dtsc-NN` ids and an allowed `kind`;
- `date_iso` format and calendar validity;
- `source_url` is https or null;
- exact caveat sentence;
- newest-first order;
- no event text containing "enforce", "effective in reducing" or "implemented".

Tests: `tests/test_dtsc_timeline_em18.py`. Acceptance: `scripts/check_dtsc_timeline.py` (offline).

## Open items

- Date wording for dtsc-01 ("1 October 2026") and dtsc-03 ("18 June 2026") follows the A2 contract text. These were not checked against ref 8 because the work is offline. Confirm the DTSC wording before publication.
- The Background Document (ref 7) and Work Plan (ref 32) have no URL of their own. Rows cite the DTSC research page or no link.
- Remaining work: the UI timeline after EM-16 and EM-5. Link checking belongs to the EM-16 checker, which reads this file.
