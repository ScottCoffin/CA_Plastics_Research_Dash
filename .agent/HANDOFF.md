# Handoff — 2026-11-26 — CG-7b sealed, CG-7c reviewer screen

## Done

- CG-7b (18d04522; CI and Pages green): migration 0008 (local only), `worker/src/group_qa.ts` (10% block-random blind second tags per region, reviews of each ambassador's first 25 tags then 20%, `/groups/reviews` with first-review-wins), export keys `group_pairs`/`group_reviews` written to the CG-7a CSVs by `scripts/ambassador_export_pr.py`. ADR-CG7B-QA-2026-11-26 and QUESTIONS CG-7B-* hold the defaults.
- CG-7c (this commit): a "Group tag checks" section on the unlisted Moderation page (`framework/src/components/ambassador_group_review.js` and `.css`). One tag per screen with the group name and website from the roster. Every field starts as Agree, so an all-agree check is one click. Edit opens a value picker (activities kept in ticking order) and a reason with a tip. The screen auto-advances, and a 409 advances with a plain sentence. Evidence is written with textContent, and links are http(s) only.

## State of the repo

- CG-7c checks: node runtime 18 checks; pytest for review, moderation and groups 32 passed; design tokens 0 hex; public-text check OK on the built page; Framework build passes with the 4 existing feed-link warnings. Mocked-API Chromium smoke (`scratch/cg7c/smoke.py framework/dist <port>`) covers the all-agree body, an edit with value and reason, auto-advance, the 409 path, no HTML from quotes, and a 390 px width with no horizontal scroll. The clean-worktree gate result is in SESSION_LOG.
- Production is still Worker be02af19 with D1 0007. The new section shows an error until H59 is deployed: `/groups/reviews` returns 404 on the old Worker.
- curation/group_merges.csv holds the owner's uncommitted work and stays outside every commit.

## Next task

1. On "H59 approved": from `worker/`, run `npx wrangler d1 migrations apply <db> --remote` (0008), then `npx wrangler deploy`. Confirm `/groups/reviews` GET and POST return 401 without a session and record the version id. Mark CG-7b done in TODO and update MEMORY.
2. Offline meanwhile: GRP-REVIEW-APPLY. Apply approved reviewed edits to the published record: the export writes the reviewed values to curation, and the build sets status `reviewed` and `reviewed_at`. Then AMB-ROSTER-QC, then FAVICON-MAIN.

## Gotchas

- `ambassador_signup.js` `api()` drops the Worker's `field` on a 400, so an invalid check shows a generic sentence. The screen validates first, so this is rare.
- A Python `http.server` preview of `framework/dist` needs the `.html` suffix in page paths.
- Python `Path.write_text` on Windows writes CRLF. Commits are normalised by autocrlf and the eol=lf attributes.

## Needs owner input

- H59 (migration 0008 + Worker deploy). Open reviews: H39, H28, H42, H2, H9; H58 is optional.
