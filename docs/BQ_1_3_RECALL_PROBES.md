# BQ-1.3: language and theme recall probes

Live run 2026-11-25 (UTC). Output: `docs/api_notes/bq1_3_recall_probes.json` (schema `bq13-v1`,
query `plastic-v3.1`). Script: `scripts/bq1_3_recall_probes.py`. Tests:
`tests/test_bq1_3_recall_probes.py`.

**These are probes, not recall estimates.** No gold set exists yet, so nothing here says how many
relevant works the v3.1 query finds. Every number below answers a narrower question: what the v3.1
query returns for a given set of works or terms. Each set is reported on its own. Sets are not
random samples, and they are never pooled.

## What was measured

1. **Language probe (no network).** The committed `site/data/global/language_probe.json` (BQ-S4) holds, for
   each of 16 native-language term sets, a fixed-seed sample of up to 50 OpenAlex works and the
   count of that sample that v3.1 also retrieves. The Wilson 95% interval is computed for each set.
2. **Anchor overlap.** The 42 theme anchors from BQ-S6 (`tests/fixtures/theme_anchors.json`) are
   filtered to their OpenAlex IDs in one request, combined with the v3.1 title-and-abstract search and
   the v3.1 type exclusions. Each anchor counts as retrieved if it comes back. Shares are reported per
   theme and per lens group. The request pattern follows BQ-1.5 (`scripts/bq1_5_anchor_overlap.py`).
3. **T10753 overlap (count queries only).** OpenAlex topic T10753 (microplastics) is filtered with
   `primary_topic.id:T10753`, as in `docs/BQ_0_RECON.md`. The script counts T10753 works, v3.1 works and
   their intersection (v3.1 AND T10753), and reports both shares. Topic assignment is OpenAlex's
   classifier, not a relevance judgement.

## Language probe

Share of each fixed-seed sample (seed 20261122) that v3.1 also retrieves. The 16 sets are not pooled.
The sample size `n` is the number of works in the sample, not the OpenAlex count.

| Term set | k/n | Share | Wilson 95% |
|---|---:|---:|---|
| zh-microplastic | 28/50 | 56.0% | 42.3% to 68.8% |
| zh-nanoplastic | 10/23 | 43.5% | 25.6% to 63.2% |
| zh-plastic-pollution | 21/50 | 42.0% | 29.4% to 55.8% |
| ja-microplastic | 14/50 | 28.0% | 17.5% to 41.7% |
| ja-nanoplastic | 5/9 | 55.6% | 26.7% to 81.1% |
| ko-fine-plastic | 21/50 | 42.0% | 29.4% to 55.8% |
| ko-microplastic | 2/5 | 40.0% | 11.8% to 76.9% |
| de-microplastic | 16/50 | 32.0% | 20.8% to 45.8% |
| de-nanoplastic | 12/50 | 24.0% | 14.3% to 37.4% |
| de-plastic-waste-pollution | 4/50 | 8.0% | 3.2% to 18.8% |
| es-pt-microplastic | 14/50 | 28.0% | 17.5% to 41.7% |
| es-marine-litter-pollution | 6/50 | 12.0% | 5.6% to 23.8% |
| fr-microplastic | 3/50 | 6.0% | 2.1% to 16.2% |
| fr-plastic-waste-pollution | 3/50 | 6.0% | 2.1% to 16.2% |
| ru-microplastic | 18/50 | 36.0% | 24.1% to 49.9% |
| no-da-plastic-pollution | 9/50 | 18.0% | 9.8% to 30.8% |

The overlap runs from 6% (fr-microplastic, fr-plastic-waste-pollution) to 56% (zh-microplastic) on
the sample shares. Sample sizes of 5 to 9 (ko-microplastic, ja-nanoplastic) give intervals wider
than 50 points, so those two rows say little. The sample size is up to 50, so the intervals for the
other rows are roughly 20 to 30 points wide. Read the spread across sets with the intervals in mind.

Caveats carried from BQ-S4: OpenAlex language labels are imperfect; non-English papers often have
English titles and abstracts; and lifecycle-and-society and lens terms in other languages were not
probed.

## Anchor overlap (probe)

Credits for the anchor probe: 10 (one request for 42 IDs).

| Group | k/n retrieved | Share | Wilson 95% |
|---|---:|---:|---|
| All anchors | 37/42 | 88.1% | 75.0% to 94.8% |

Per theme:

| Theme | k/n | Share | Wilson 95% | Misses |
|---|---:|---:|---|---|
| waste_recycling | 6/6 | 100% | 61.0% to 100% | none |
| policy | 5/5 | 100% | 56.6% to 100% | none |
| behaviour | 3/3 | 100% | 43.9% to 100% | none |
| lca_bioplastics | 3/3 | 100% | 43.9% to 100% | none |
| litter | 2/2 | 100% | 34.2% to 100% | none |
| ssbd | 0/1 | 0% | 0.0% to 79.3% | `10.1038/s41893-025-01672-z` |
| chemicals | 0/2 | 0% | 0.0% to 65.8% | `10.1016/j.jhazmat.2017.10.014`, `10.1016/j.cogsc.2021.100513` |
| waste_colonialism_justice | 4/6 | 66.7% | 30.0% to 90.3% | `10.1007/978-3-031-51358-9_1`, `10.1017/plc.2025.10005` |
| labour_critique | 4/4 | 100% | 51.0% to 100% | none |
| book | 1/1 | 100% | 20.7% to 100% | none |
| pollution_exposure_health | 4/4 | 100% | 51.0% to 100% | none |
| reviews_2025_2026 | 5/5 | 100% | 56.6% to 100% | none |

Lens groups. The brief asks for "per-lens" overlap, but the anchors carry no lens tag, and the repo
does not define which theme belongs to which lens. The script uses an assumed grouping, from the
three theme groups in A3 section 4.3 (pollution-core, lifecycle-and-society, lens-candidate):

| Lens group (assumed) | Themes | k/n | Share | Wilson 95% |
|---|---|---:|---:|---|
| pollution_core | litter, chemicals, pollution_exposure_health | 6/8 | 75.0% | 40.9% to 92.9% |
| lifecycle_and_society | waste_recycling, policy, behaviour, lca_bioplastics, ssbd, book, reviews_2025_2026 | 23/24 | 95.8% | 79.8% to 99.3% |
| lens_candidate | waste_colonialism_justice, labour_critique | 8/10 | 80.0% | 49.0% to 94.3% |

The grouping is a default for the lead to confirm (see Review items). A different grouping changes
only the lens table, not the per-theme table or the probe itself.

Reading the anchor result:

- The overall 37 of 42 is a probe on works that are known to be relevant, selected from the
  literature. It is not a rate for the corpus.
- The 5 misses are reported with their titles in the JSON. The title-level reasons are hints only,
  as in BQ-1.5. The misses include one chemicals-in-plastics title, a title that frames the topic as
  plastic waste colonialism, and a trade-policy title. The JSON does not say whether these works carry
  a v3.1 phrase in the abstract, because the abstract was not checked.
- The `ssbd` miss is the work the lead overrode into the anchor set in BQ-S6. Its abstract is about
  bisphenol chemistry, so a miss there is expected.
- Theme sizes are 1 to 6. The intervals for single-anchor themes span most of the scale.

## T10753 overlap (count queries)

| Quantity | Count |
|---|---:|
| T10753 works (`primary_topic.id:T10753`, with v3.1 type exclusions) | 78,671 |
| v3.1 works (query and type exclusions) | 136,323 |
| Intersection (v3.1 AND `primary_topic.id:T10753`) | 64,606 |

- **Share of T10753 works retrieved by v3.1: 82.1% (Wilson 95%: 81.9% to 82.4%).**
- **Share of v3.1 works with T10753 as primary topic: 47.4% (Wilson 95%: 47.1% to 47.7%).**

Both denominators apply the v3.1 type exclusions. The OpenAlex `works_count` for T10753 is 93,500,
which includes all work types. The type-excluded count is lower, and that is why it is used here.
Without the exclusions, the T10753 denominator would include types that v3.1 cannot return, and the
share would be biased down.

Limitations: topic assignment is OpenAlex's `primary_topic` classifier. The share describes how well
the two sets overlap in OpenAlex's own labels. It does not check whether either set is correct.
The counts are full-index totals, not samples, so the Wilson intervals describe only sampling-style
uncertainty and do not cover the classifier error. Read them as indicative.

## Cost and calls

Four live calls, 31 credits in total (USD 0.0031 at the BQ-S6 rate of USD 0.0001 per credit). The
cap is 300 credits, and the run never came near it.

| Call | Filter | Credits |
|---|---|---:|
| anchor_probe_1 | v3.1 search, type exclusions, `ids.openalex` (42 IDs) | 10 |
| t10753_count | `primary_topic.id:T10753`, type exclusions | 1 |
| v31_count | v3.1 search, type exclusions | 10 |
| v31_and_t10753_count | v3.1 search, type exclusions, `primary_topic.id:T10753` | 10 |

No language-probe call was made. Counts are never OR-split. Responses are cached in
`data/interim/bq1_3/` (gitignored).

## Reproduce

    py -3.14 scripts/bq1_3_recall_probes.py            # live: reuses cache, fetches the rest (31 credits, cap 300)
    py -3.14 scripts/bq1_3_recall_probes.py --offline  # rebuild the JSON from data/interim/bq1_3/
    py -3.14 scripts/bq1_3_recall_probes.py --check    # validate the committed JSON; SKIP if no cache
    py -3.14 -m pytest -q tests/test_bq1_3_recall_probes.py

## Review items for the lead

1. **Lens grouping.** Lens groups are an assumed mapping of themes to the A3 section 4.3 strata. The
   anchors carry no lens tags. Confirm the mapping or give the lens assignments to use.
2. **T10753 denominator.** Both T10753 and v3.1 counts apply the v3.1 type exclusions. The brief did
   not say. The raw T10753 count without exclusions can be added as a count-only query (1 credit) if
   the lead prefers it.
3. **Anchor misses.** The title-level reasons are hints. An abstract check would take a
   fetch of the abstracts, which the offline cache does not hold.
