# CNT-1: exclusions that matched no work

Date: 2026-11-22. Source of the question: bug 1 in `docs/BQ_1_6_COUNTS.md` section 4.

## What was checked

`scripts/report_unmatched_overrides.py` (read-only, offline) places every row of
`curation/overrides_works.csv` against the normalized works table, the raw OpenAlex store
and the published index. Run it with `py -3.14 scripts/report_unmatched_overrides.py`
(add `--json` for machine output).

## Counts for exclude rows, before and after

| Class | Meaning | Before | After |
|---|---|---:|---:|
| applied | In the corpus, California, and off the published site | 62 | 62 |
| ca_still_published | Exclusion recorded, but the site still shows the work until the export is rebuilt | 0 | 2 |
| non_ca | In the corpus but not California | 0 | 0 |
| collapsed_duplicate | ID was merged into another work (the keeper) | 3 | 3 |
| in_raw_only | In the raw pull only | 0 | 0 |
| not_in_corpus | In neither the raw pull nor the normalized table | 63 | 63 |
| **Total** | | **128** | **130** |

The earlier estimate of "at least 10" unmatched was too low. Before this change, 66 of 128
exclusions did not match a work row. Of these, 63 match nothing in any store, and 3 point at
merged duplicates. No exclusion points at a non-California work.

Other fields (369 `plastic_related` rows, unchanged): 355 applied, 5 collapsed duplicates,
9 not in corpus. These are reported only.

Checks with no findings: no duplicate work_id+field rows, no exact duplicate rows, no
exclude row with a value other than `true`, and no ID outside the `W<number>` form.

## The three merged duplicates

| Duplicate ID | Keeper | Keeper published? | Keeper already excluded? | Outcome |
|---|---|---|---|---|
| W4391980109 | W4391214784 | yes | no | Carried (see rows added) |
| W4400038731 | W4403000424 | yes | no | Carried (see rows added) |
| W4408929499 | W4415514930 | no | yes | Already effective through the keeper |

Before the fix, the first two exclusions had no effect at all.

## Rows added

Two exclude rows, for the keepers, with reviewer `agent-CNT-1` and date 2026-11-22. The
reason keeps the owner's original text:

- W4391214784: `CNT-1: carried from W4391980109 (collapsed duplicate); AT-1 owner audit label (QUERY_AUDIT_REVIEW_V3.csv): not_relevant`
- W4403000424: `CNT-1: carried from W4400038731 (collapsed duplicate); AT-1 owner audit label (QUERY_AUDIT_REVIEW_V3.csv): not_relevant`

Both titles match their duplicate's title (case and punctuation ignored), so neither row was
flagged.

**Placement differs from the brief.** The rows sit directly under the header, not at the
end of the file. `scripts/build_audit_overrides.py` rebuilds this file with the non-audit
rows first. Its `--check` mode, and `tests/test_audit_overrides.py::test_committed_overrides_are_current`,
fail if the rows are at the end. The daily ingest workflow (`.github/workflows/ingest_works.yml`)
runs that rebuild too. The original lines are unchanged. The diff is two added lines.

## Effect on the published site

Two published works would be removed by the next export: W4391214784 and W4403000424.
The export has not been rebuilt, so `site/data/` still lists them. The report counts this
offline from index membership. There is no dry-run mode in `scripts/build_export_site.py`.

## Flags for owner review

None. Both carry-forward candidates have matching titles.

## Nothing was deleted

- The 63 `not_in_corpus` rows protect against re-ingest. If those works come back in a
  pull, they will be excluded. They are AT-1 audit labels from 2026-11-10 and 2026-11-11.
  Why they are missing from `data/interim/works_raw.parquet` cannot be checked offline.
- The duplicate-ID rows record the merge. They are the owner's rows and were kept.
- No row was edited. Only two rows were appended to `curation/overrides_works.csv`.

## Open items for the lead

- Rebuild `site/data/` through the normal export to drop the two works from the public site.
- `docs/BQ_1_6_COUNTS.md` section 4 bug 1 still says "at least 10". That file is not owned
  by this task and was not edited.
- The 63 `not_in_corpus` exclusions may come from an audit pull that was never stored in
  the raw table. This was not verified.
