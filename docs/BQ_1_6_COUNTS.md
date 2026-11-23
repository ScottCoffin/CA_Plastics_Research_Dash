# California work counts: definitions and reconciliation (BQ-1.6)

Scope: Add-on A3 §2 lists five California numbers (1,918 / 1,582 / 1,848 / 2,036 / 1,748) that appear in different places on the site and in the labels QC report. This card defines each one and reconciles the differences.

- **Today's values** come from the committed build of 2026-11-18 18:54 UTC (repo HEAD `67133b55`).
- **A3 values** match the committed build of 2026-11-17 (commit `06b84555`) exactly, for all five numbers.
- Regenerate with `py -3.14 scripts/report_ca_counts.py` ([script](../scripts/report_ca_counts.py); `--json` for machine output; [tests](../tests/test_report_ca_counts.py)). The script reads committed files only. It does not read `data/`, run a build, or use the network.

## 1. Definitions card

Each number counts one population. "Published" means on the site. "Plastic-related" means the final plastic flag is true.

| Number (today / A3) | What it counts | Where it appears | Source |
|---|---|---|---|
| **1,919 / 1,918** Explorer California | Every published work with at least one California-affiliated author, of any type, plastic-related or not. | Explorer, "live atlas · N works" | `site/data/global/explore.json` `california.works`, copied from `counts.works` at build time |
| **1,919** California works (About "Works") | The same population as the Explorer figure. | About page (`aboutViewModel` in `framework/src/components/atlas.js`) | `site/data/build_metadata.json` `counts.works`; `site/data/index.json` `counts.works` and the `works` list (1,919 rows) |
| **1,583 / 1,582** California page, plastic-related works | Published California works whose final plastic flag is true, after the rule, owner review, model labels and curation overrides. | Overview, "plastic-related works" card | `site/data/build_metadata.json` `counts.plastic_works` (equal to `flow.plastic_related`) |
| **1,849 / 1,848** California page, type breakdown | Published works of ten named types (articles, reviews, conference papers, preprints, book chapters, conference abstracts, datasets, theses, reports, books). Not limited to plastic-related works. | Overview, "Now: …" line | `site/data/build_metadata.json` `flow.by_type`, summed over the ten names in `typeSummary` in [framework/src/california/index.md](../framework/src/california/index.md) |
| **2,037 / 2,036** labels_qc label rows | One rule-layer label row per unique work, California or not. | [docs/labels_qc.md](labels_qc.md), "Label rows" | written by `src/atlas/nlp/labels.py` |
| **1,749 / 1,748** labels_qc plastic-related rows | Unique works, California or not, that the keyword rule calls plastic-related. This is before owner review, model labels, overrides and the California filter. | [docs/labels_qc.md](labels_qc.md), "Plastic-related rows" | written by `src/atlas/nlp/labels.py` |

The two numbers that look like they should match do not, because they filter different populations. labels_qc works on all 2,037 unique works (before the California filter), so its 1,749 is not a subset of the page's 1,583.

### How the numbers nest (today)

```
2,074 raw OpenAlex records
  - 37 duplicates collapsed
= 2,037 unique works                   (labels_qc: normalized and label rows)
  - 56 no California authorship
  - 62 removed by curation
= 1,919 published California works     (Explorer, About "Works")
  - 336 not plastic-related
= 1,583 published and plastic-related  (page plastic card)

Separately: the Now line counts 1,849 of the 1,919 published works (70 of other types are not named).
labels_qc plastic rows (1,749) are counted on the 2,037 unique works, before the removals above.
```

## 2. Command and output

```
py -3.14 scripts/report_ca_counts.py
```

Output (2026-11-18, HEAD `67133b55`):

| Number | Today | A3 (2026-11-18) | Change | Source (file: field) | Definition |
|---|---:|---:|---:|---|---|
| Explorer: California works | 1,919 | 1,918 | +1 | site/data/global/explore.json: california.works | Published California works (all types, plastic-related or not), copied from counts.works when the explorer was built. |
| California atlas: works | 1,919 |  |  | site/data/build_metadata.json: counts.works | Published works with a California author, after the California filter and curation. |
| California page: plastic-related works | 1,583 | 1,582 | +1 | site/data/build_metadata.json: counts.plastic_works | Published California works whose final plastic_related flag is true. |
| California page: type breakdown (Now line) | 1,849 | 1,848 | +1 | site/data/build_metadata.json: flow.by_type (types named in typeSummary) | Published works of the ten named types, all plastic-related or not; other types are left out. |
| labels_qc: label rows | 2,037 | 2,036 | +1 | docs/labels_qc.md: Label rows | One rule label row per unique work, California or not, before the California filter and curation. |
| labels_qc: plastic-related rows | 1,749 | 1,748 | +1 | docs/labels_qc.md: Plastic-related rows | Unique works, California or not, that the keyword rule calls plastic-related, before owner review, model labels and overrides. |
| Unique works (normalized table) | 2,037 |  |  | site/data/build_metadata.json: flow.unique_works | Works after OpenAlex duplicates are collapsed, before the California filter. |
| Raw OpenAlex records | 2,074 |  |  | site/data/build_metadata.json: flow.records_retrieved | Raw records retrieved: unique works plus duplicates collapsed into them. |
| Dropped: no California author | 56 |  |  | site/data/build_metadata.json: flow.no_ca_authorship | Unique works with no California authorship on any basis; not published. |
| Dropped: removed by curation | 62 |  |  | site/data/build_metadata.json: flow.removed_by_curation | California works removed by curation; computed as unique minus no-CA minus published. |
| Published, not plastic-related | 336 |  |  | site/data/build_metadata.json: flow.not_plastic_related | Published California works whose final plastic flag is not true. |
| Published works not in the Now line | 70 |  |  | site/data/build_metadata.json: flow.by_type (types not named) | Published works of the types the Now line does not name (editorial, other, letter, and so on). |
| Curation exclusions listed | 128 |  |  | site/data/build_metadata.json: curation.works_excluded_listed | Work overrides with exclude set to true; not every one removes a work. |

| Status | Check | Detail |
|---|---|---|
| OK | Explorer California equals atlas works | explore 1919 vs counts.works 1919 |
| OK | Index works equal counts.works | index works list 1919, index counts.works 1919, counts.works 1919 |
| OK | flow.published equals counts.works | flow.published 1919 vs counts.works 1919 |
| OK | Plastic works equal flow.plastic_related | counts.plastic_works 1583 vs flow.plastic_related 1583 |
| OK | Plastic works equal index plastic flags | counts.plastic_works 1583 vs index works with plastic_related true 1583 |
| OK | Labeled works equal counts.works | counts.labeled_works 1919 vs counts.works 1919 |
| OK | By-type counts add to published | sum of flow.by_type 1919 vs flow.published 1919 |
| OK | Flow adds up (unique - no-CA - curation = published) | 2037 - 56 - 62 vs 1919 |
| OK | Curation removals equal flow residual | curation.works_removed 62 vs flow.removed_by_curation 62 |
| OK | Unique works equal labels_qc normalized rows | flow.unique_works 2037 vs labels_qc 2037 |
| OK | Raw records equal labels_qc raw rows | flow.records_retrieved 2074 vs labels_qc 2074 |
| OK | Label rows equal unique works | labels_qc label rows 2037 vs flow.unique_works 2037 |
| NOTE | Now line omits published works | Now line sums to 1849 of 1919; 70 works of unnamed types have no remainder row |
| NOTE | Plastic gap, labels_qc to published | gap 166 (1749 - 1583); net published works flipped from rule to final not-plastic lie between 48 and 166 (non-published works 118); needs a per-work join |
| BUG? | Listed exclusions reach a counted work | 128 listed, 62 removed, 56 non-CA; at least 10 listed exclusions match no work in the unique table |

## 3. Reconciliation

1. **All five numbers are one higher than A3.** The 2026-11-18 build (`67133b55`) adds one raw record compared with the 2026-11-17 build (`06b84555`). Raw records go from 2,073 to 2,074 and duplicates stay at 37, so unique works go from 2,036 to 2,037. Published goes from 1,918 to 1,919, the page plastic count from 1,582 to 1,583, and labels_qc plastic from 1,748 to 1,749. The no-CA (56), curation (62) and not-plastic (336) counts did not move, so the new record is a published, plastic-related California work. The Explorer follows the same path: `explore.json` in commit `776c6aa3` carried 1,918, and `67133b55` carries 1,919. This is a refresh, not a definition change.
2. **1,919 vs 1,583 (published vs plastic).** 336 published works are not plastic-related (`flow.not_plastic_related`). Both numbers are correct for their definitions. The page puts them in separate cards, but the Now line is a third population (1,849 works of all types). Nothing on the page says which population each number uses (bug 2).
3. **1,849 (Now line) vs 1,919 (published).** The line names ten types. The other 70 published works are editorial 41, other 18, letter 5, book-review 2, reference-entry 2, data-paper 1 and supplementary-materials 1 (`flow.by_type`). The line has no remainder entry, so it does not add to the total.
4. **1,749 (labels_qc plastic) vs 1,583 (published plastic): gap 166.** The labels_qc count is the rule layer over all 2,037 unique works. The page count is the final label over the 1,919 published works, after owner review, model labels, overrides and the California filter (`src/atlas/build/export_site.py`). The 118 unique works that are not published can account for at most 118 of the 166. So the net number of published works that the rule calls plastic and the final label does not lie between 48 and 166. Flips in both directions are possible. The committed site files cannot split this; a per-work join of the labels table against published works would (not run here, because `data/` is out of scope for this task).
5. **2,037 (labels rows) vs 1,919 (published).** Exactly 118 unique works are not published: 56 with no California authorship, and 62 removed by curation.
6. **2,074 (raw) vs 2,037 (unique).** 37 raw records are duplicates that collapsed into a unique work (`flow.duplicates_collapsed`). labels_qc reports the same 2,074 raw rows.
7. **62 removed by curation.** `curation.works_removed` is 62 and `flow.removed_by_curation` is 62. The flow value is a residual, so the match is a check, not a proof (bug 4).
8. **Explorer California vs other countries.** The California figure counts curated published works. Other countries in the Explorer use `total_by_country` from `site/data/global/global_counts.json`. That is an OpenAlex count over all years under the active plastics query, with no California filter and no curation (`scripts/build_global_explore.py`). The two are not like-for-like (bug 6).

## 4. Possible bugs

These are differences the committed counts cannot explain, or things that look wrong on inspection. Nothing here was changed; the owned files are this card, the script and its tests.

1. **Listed exclusions that match no work.** `curation.works_excluded_listed` is 128, but only 62 works were removed. Non-California works are dropped before curation runs, so at most 56 of the unmatched exclusions can be non-California works. That leaves at least 10 of the 128 listed exclusions matching no work in the unique table. Possible causes are IDs collapsed as duplicates, or IDs no longer in the OpenAlex pull. Check the `exclude` rows in `curation/overrides_works.csv` against the normalized works table. Medium: an exclusion the owner made that never took effect would stay silent. The report flags this as `BUG?`.
2. **The Now line omits 70 works and has no remainder row.** Fixed 2026-11-22 (CNT-2): the line now reads "Now, all published works: …" and ends with "N works of other types", so it sums to the published total. `typeSummary` in [framework/src/california/index.md](../framework/src/california/index.md) lists ten types and drops editorials, "other", letters, book reviews, reference entries, data papers and supplementary materials. It sits beside the plastic card, and neither line says which population it uses. Presentation bug.
3. **labels_qc has no timestamp.** [docs/labels_qc.md](labels_qc.md) says `Generated at (UTC): runtime`. `src/atlas/nlp/labels.py` uses that literal when no time is passed (`generated_at or "runtime"`). The QC report cannot be dated from its contents; only git history dates it. Minor.
4. **`removed_by_curation` is a residual, not a count.** `_flow()` in `src/atlas/build/export_site.py` computes unique minus no-CA minus published. It agrees with `curation.works_removed` today, but by construction it absorbs any other removal, so the flow block cannot disagree with itself. Only the comparison in the report catches drift.
5. **Stale copies of the A3 values.** [docs/add_on_spec_3.md](add_on_spec_3.md) (line 41) and [docs/GLOBAL_EXPERTS_ASSESSMENT.md](GLOBAL_EXPERTS_ASSESSMENT.md) (line 35) still quote 1,918 published and 2,036 in the corpus, the 2026-11-17 values. This is documentation drift. Not edited here, because those files are outside this task's scope.
6. **The Explorer puts unlike populations side by side.** The California "N works" is a curated published count, and the other countries' figures are raw OpenAlex query counts. The labels look comparable. Definitional presentation issue.

## 5. Not checked

- No build was run, and `site/data/` and `data/` were neither rewritten nor read.
- The per-work split of the 166-work plastic gap needs a join against `data/`, which is out of scope here.
- Owner decisions or new works after 2026-11-18 will move these numbers. The script always reports the current committed values.
