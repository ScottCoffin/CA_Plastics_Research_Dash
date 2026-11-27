# Handoff — 2026-11-26 — CG-7b blind second tags, reviewer checks and export (local)

## Done

- CG-7b is implemented and tested locally (ADR-CG7B-QA-2026-11-26). Additive migration `worker/migrations/0008_group_qa.sql` adds five tables: `group_qa_blocks`, `group_tag_samples`, `group_tag_pairs`, `group_review_picks` and `group_tag_reviews`. The logic is in `worker/src/group_qa.ts`, with hooks in groups.ts, submissions.ts, export.ts and index.ts.
- Sampling: one random position in each block of 10 usable primary tags per region (10%). The sampled group is held for a different active member of the same region, at most 5 per batch, behind the same two-hour hold and inside the 25-group cap. First-wins and `second_tag_for` are unchanged. The first usable second tag forms the pair, labelled `sample` or `overlap` privately in D1. A cannot_determine second tag reopens the sample.
- Review: each ambassador's first 25 usable primary tags, then one random tag in each block of 5. Owners and leads use `GET/POST /groups/reviews` on approved tags that are not their own. All five Tier-1 facets are checked at once, and an edit stores the original value, the reviewed value and a `review_reason` code (new taxonomy list). The first complete review wins.
- Export: `/export/approved` now carries `group_pairs` and `group_reviews` with no ids, names or basis. `scripts/ambassador_export_pr.py` (Haiku) writes `curation/group_double_tags.csv` and `curation/group_reviews.csv`, and the export workflow rebuilds and stages them. `build_groups.py` ignores curated rows for groups that have since left the records. The 10-pair minimum is unchanged.

## State of the repo

- Worker: 239 tests passed, including 28 in `worker/test/group_qa.test.ts` (block draws, races, holds, lapsed holds, pairs, review validation and race, export privacy, retries); tsc clean. Python: the clean-worktree gate result is in SESSION_LOG.
- Production still runs Worker be02af19 with D1 0007. Migration 0008 has not been applied and nothing is deployed (H59).
- curation/group_merges.csv still holds the owner's uncommitted decisions and stays outside every commit.

## Next task

1. On "H59 approved": run `npx wrangler d1 migrations apply <db> --remote` for 0008 from `worker/`, then `npx wrangler deploy`. Check that the routes without a session return 401 (`/groups/reviews` GET and POST) and record the version id. Then mark CG-7b done.
2. Before or while waiting: CG-7c (offline). Add the reviewer screen on the Ambassadors page for `/groups/reviews`: one tag per screen, one click per facet, a reason picker on edit, auto-advance (owner rule: forms under a minute). Then apply approved reviewed values to the published record (status `reviewed`, `reviewed_at`). After that: AMB-ROSTER-QC, then FAVICON-MAIN.

## Gotchas

- `group_qa_blocks` has no foreign key. Clear it explicitly in tests (test/helpers.ts TABLES lists it).
- The SUBMIT_LIMIT of 30 per hour per account: bulk-tag tests clear `rate_limits` between submissions.
- Python edits on Windows: `Path.write_text` writes CRLF. The repo uses autocrlf with eol=lf attributes, so commits normalise.

## Needs owner input

- H59 (migration 0008 + Worker deploy). Other open items include H39, H28, H42, H2 and H9; H58 is optional.
