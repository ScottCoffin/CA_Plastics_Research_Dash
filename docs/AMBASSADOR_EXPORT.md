# Ambassador export pull request (AMB-1 step 4)

Approved ambassador contributions reach the repository through a daily pull request, so every change is
reviewed and versioned (docs/AMBASSADORS_SPEC.md section 5). Nothing merges by itself: the owner reviews every
pull request, and auto-merge is not enabled.

## What the job does

Workflow: `.github/workflows/ambassador_export.yml` (daily at 06:23 UTC, and on manual dispatch).
Script: `scripts/ambassador_export_pr.py`.

1. Reads `GET {api}/export/approved?since=<watermark>` from the ambassador Worker with
   `Authorization: Bearer <AMB_EXPORT_TOKEN>`. The watermark is `curation/ambassador_export_state.json`.
2. Applies each approved item to the repository files:

| Submission | Change |
| --- | --- |
| stream `confirm`, kind `confirm` | the item's `status` becomes `confirmed`; `Confirmed by <name>.` is appended to its note when the ambassador kept public credit |
| stream `confirm`, kind `correct` | the item's `name` and/or `url` are replaced and `status` becomes `confirmed` |
| stream `confirm`, kind `not_relevant` | the item's status becomes `not_relevant`; it stays in region.yml so item positions (the ids) never shift, and the region page leaves it out |
| stream `knowledge`, kinds funder, policy, dataset, research_network, institution, community_group, volunteer_group, community_knowledge | a new item with `status: draft` is appended to the matching section of `regions/<slug>/region.yml` |
| stream `knowledge`, kind `correction` | the named item's fields are replaced and its `status` becomes `draft` |
| consensus `case_answers` | a row in `curation/ambassador_labels.csv` with `source = ambassador_consensus`; one row per (region, case), newest answer wins |

Knowledge kinds map to sections as follows. `community_group`, `volunteer_group` and `community_knowledge`
go to `research_networks` with item kind `community`, because the region-v1 schema has no `community`
section (`scripts/build_region_pages.py` requires exactly six sections). Kinds with no section (`event`,
`media`, `researcher`) are skipped with a printed reason. Researcher entries are not published on region pages.

3. Validates every string again: length caps, `https://` URLs only, no angle brackets or control characters.
   An invalid or unmatched record is skipped and printed by its submission id.
4. Writes the files. Region files are edited line by line, so comments and untouched items keep their bytes.
   After a change to a region, the file is checked against the region-v1 rules and reverted if it would break them.
5. Advances the watermark last, and only after every write succeeds. A failed run leaves the watermark alone.
6. If any file changed, the job force-pushes branch `ambassador-export/<date>` and opens a pull request titled
   `Ambassador contributions <date>`. The body lists counts per region and kind. It carries no names, emails or
   ambassador ids. A same-day re-run updates the open pull request.

`--dry-run` prints the same report and writes nothing. `--input FILE` reads a saved export instead of calling the
API; the tests use it.

## Owner review step

1. Open the pull request from the notification. Check the counts in the body against the diff.
2. For each changed item, check the URL, the name and the wording. Draft items are not yet verified;
   confirm them or edit them in the same pull request.
3. Check `curation/ambassador_labels.csv`. The labels are not used by the pipeline yet (see below).
4. Merge, or close the pull request. A closed pull request does not move the watermark on the default branch, so
   the same contributions are offered again the next day.

## Secrets and settings the owner must set

- **`AMB_EXPORT_TOKEN`** (GitHub Actions repository secret). Its value must equal the Worker's `EXPORT_TOKEN`
  secret. Set it with `gh secret set AMB_EXPORT_TOKEN`. Without the secret the job prints a notice and exits.
- **Settings > Actions > General > Workflow permissions**: the job needs permission to open pull requests, so
  "Allow GitHub Actions to create and approve pull requests" must be enabled.
- The Worker must be deployed and `EXPORT_TOKEN` set with `wrangler secret put` (owner-approved step, see
  worker/README.md). Until then the export refuses every request.

## How labels feed the pipeline later (not wired yet)

`curation/ambassador_labels.csv` holds consensus answers for classifier cases. Columns: `region, case_id, answer,
correct_value, answered_at_iso, source`. Later, the pipeline will read them as labels with `source = ambassador`
and apply the usual override precedence: owner > ambassador consensus > model
(docs/AMBASSADORS_SPEC.md section 5). Nothing reads this file yet, so these answers change no public page.

## Known limits

- The region page payload `site/data/<slug>/region.json` is not rebuilt by this job, so a merged change shows on
  the page only after `scripts/build_region_pages.py` runs. Its inputs come from the data build, so the rebuild
  is a separate step for the owner or a later job.
- Ambassador free-text notes (the `note` field of confirm and knowledge submissions) are not published. Only the
  description of a knowledge item, the credit name, and the fixed draft wording appear in `region.yml`.
- An item's `item_id` is `<slug>:<section id or item kind>:<0-based index>`, for example `norway:funder:3`. The
  exact format is assumed from the Worker's test fixtures and is open for owner confirmation.
- Consensus answers are written newest-wins per (region, case). The Worker already filters to consensus answers.
- The job writes the watermark even when every record was skipped, so a bad record is reported once.
