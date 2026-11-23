# BQ-S10: review-string replay (PubMed counts and v3.1 overlap)

Two of three published review strings were replayed; the third has no string to replay. Counts were run
on 2026-11-23 (UTC; the session date was 2026-11-22). PubMed calls are free; OpenAlex used 88 of the
120-credit task limit (44 per review). Machine copy: `docs/api_notes/bq_s10_replay.json`. Code:
`scripts/replay_review_strings.py`. Strings: `config/pubmed/review_strings/`.

## What was measured

For each review we took the PubMed search string exactly as printed and counted its records in PubMed
(count only, no records downloaded). We then drew a fixed random sample of 200 of those PMIDs and asked
OpenAlex two questions about each: is the record in OpenAlex at all, and does the Atlas v3.1 query
retrieve it. The result is **overlap** between two searches, not recall. Neither search is a gold
standard, and the v3.1 check runs on OpenAlex title and abstract text, not on PubMed fields.

## Results

| Item | Özkan Vardar and Vardar (2026) | Tran et al. (2026) |
|---|---|---|
| String source | Table 1, PubMed row (PDF page 4) | Additional File 1 (MOESM1), PubMed row |
| Article licence | CC BY 4.0 | CC BY-NC-ND 4.0 (the brief said CC BY; the article states NC-ND) |
| Published PubMed count (search date) | 1,089 (5 March 2026) | 2,199 (26 December 2024) |
| Count today, no date limit | 1,411 | 2,284 |
| Count of records entered by the search date (Entrez date) | 1,089 | 1,565 |
| Count by publication date up to the search date (pdat) | 1,128 | 1,567 |
| Per-block counts (each OR block alone, no date limit) | particle 28,433; intestinal 783,140; toxicity 2,570,755 | human MeSH 24,004,110; microplastic 25,622; outcome 12,581,331; positive part without NOT 3,593 |
| Repeated terms within an OR block | none (23 terms, 23 after normalising) | none (21 terms, 21 after normalising); one unmatched `)` as printed |
| Sample | 200 of 1,411 PMIDs | 200 of 2,284 PMIDs |
| In OpenAlex | 200 of 200 = 100.0% (Wilson 95%: 98.1 to 100.0) | 199 of 200 = 99.5% (97.2 to 99.9) |
| Retrieved by the Atlas v3.1 query | 195 of 200 = 97.5% (94.3 to 98.9) | 198 of 200 = 99.0% (96.4 to 99.7) |
| v3.1 share among sampled records in OpenAlex | 97.5% | 99.5% |
| Included-study list openly available? | Not confirmed in full. The main text has Table 2 (major key studies) and cites Supplementary Material 1, which was not retrieved. The 90 included studies are not listed in full in the main text. | Table 2, "List of included papers", is in the open-access article. Its rows were not checked, and nothing is compiled here. |
| OpenAlex calls and credits | 8 calls, 44 credits | 8 calls, 44 credits |

Ortiz-Balsero et al. (2026): not replayed. Status: "not available: supplementary Text S1 not in Zotero;
owner to supply".

## Reading the numbers

- **Özkan Vardar and Vardar (2026).** The string as printed, limited to records entered in PubMed by the
  stated search date (5 March 2026), returns 1,089, the published figure. This is the one case where the
  replay reproduces the paper's count. The publication-date cut (1,128) is higher because it leaves out
  records whose print date falls later.
- **Tran et al. (2026).** The string as printed does not reproduce 2,199. With the same entry-date cut
  (26 December 2024) it returns 1,565. Probes (count only, not stored in the JSON) show that the same
  cut without the NOT clause returns 2,285, which is closer to 2,199. The full string returns 1,960 with
  entry dates to 31 December 2025. None of these establishes which query produced the published figure.
  Quote 2,199 only with that caveat; the authors' search log would settle it.
- Neither review has a within-block duplicate. The transcription-duplicate concern in A3 §5.10.1 is not
  borne out for these two PubMed strings. The defect found in Tran et al. is a parenthesis, not a term.

## Transcription and repair

- **Tran et al. string.** As printed it has seven `(` and eight `)`. PubMed accepted it without error; its
  translation parses it as (humans AND microplastics AND outcomes) NOT (reviews, editorials, comments,
  letters). The local parser in `atlas.qc.pubmed` rejects it. For structure analysis only, the replay
  removes the first unmatched `)`, after `"public health"[MeSH Terms]`. Every count in the table uses the
  string as printed. The repair changes no OR operand.
- **Özkan Vardar and Vardar string.** The PDF text broke words at line ends (`polyethyl-ene`,
  `poly-propylene`). These were rejoined, and the result was checked against the rendered page and against
  the text layer (23 `[tiab]` terms in both).
- **Quotes.** Typeset curly quotes were replaced by ASCII double quotes in both files. No other character
  changed. Each file header records the source, licence, search date and published count.

## Method

- **Counts.** ESearch with `datetype=pdat` and a window from 1800/01/01 to 3000/12/31 (no real limit). The
  date-limited counts use the same window ending on the review's search date. Entrez-date counts use
  `datetype=edat` (see the changes section).
- **Sample.** All PMIDs for the string, from one ESearch with retmax 10,000 (the date-splitting path is
  implemented but not needed here). Sorted by PMID, then ranked by sha256 of `20261122:<PMID>`; the first
  200 are the sample. The same input always gives the same sample.
- **OpenAlex.** One `ids.pmid` filter per batch of 50 PMIDs (full PubMed URLs), for presence. A second
  filter adds the v3.1 `title_and_abstract.search` and the type exclusions, rendered as in
  `scripts/fetch_trend_global.py` (no CA scope; tested against its `build_url`). Requests go through the
  shared OpenAlex path and the daily budget guard. Each review used 44 credits over 8 calls, which matches
  the measured costs in `docs/api_notes/openalex_costs.md` (1 credit per filter-only list, 10 per
  search-filter call) for four calls of each kind.
- **Intervals.** Wilson score intervals, 95%, on each share.

## Limits

- Overlap, not recall. Each review has a sample of 200, so the intervals are a few points wide at the top.
- Both strings are microplastic-centred and so is v3.1. A high overlap is expected and says little about
  the topic as a whole.
- Counts are one PubMed snapshot taken on 2026-11-23 and will move as PubMed indexes records.
- A record that PubMed holds but OpenAlex lacks cannot be retrieved by v3.1; the in-OpenAlex share shows
  how many such records there were in each sample.

## Owner actions

1. Supply Ortiz-Balsero et al. (2026) Text S1 if that review should be replayed. It is not in Zotero.
2. Before quoting Tran et al.'s 2,199, check the authors' search log or ask which string and date gave it.
3. Decide whether to compile the included-study lists. Nothing was compiled here.

## Changes requiring orchestrator review

- `src/atlas/qc/pubmed.py`: `EUtilsClient.count` always sends `datetype=pdat`. A `datetype` parameter would
  let the script use the public method for the Entrez-date count. The script currently makes that one call
  through the private `_get_json`. This file was not changed, as the brief required.
- The brief gave Tran et al. as CC BY. The article states CC BY-NC-ND 4.0, and that is what is recorded.
- The Entrez-date count for both reviews was added after the live runs, using `--entry-date-only` (count
  only, no OpenAlex, so no credits were spent twice). `--live` now includes it.

## Reproduce

```
py -3.14 scripts/replay_review_strings.py --review ozkan_vardar_2026           # dry run, no network
py -3.14 scripts/replay_review_strings.py --review ozkan_vardar_2026 --live    # PubMed counts + OpenAlex check
py -3.14 scripts/replay_review_strings.py --review ozkan_vardar_2026 --entry-date-only
py -3.14 scripts/replay_review_strings.py --review tran_2026                   # dry run, no network
py -3.14 scripts/replay_review_strings.py --review tran_2026 --live
py -3.14 scripts/replay_review_strings.py --review tran_2026 --entry-date-only
```

Tests: `py -3.14 -m pytest -q tests/test_replay_review_strings.py tests/test_qc_pubmed.py`.
