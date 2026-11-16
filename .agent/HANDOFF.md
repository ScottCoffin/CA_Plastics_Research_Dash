# Handoff — 2026-11-15 — task S2.6

## Done
- S2.6: OpenAlex authorships with a null `author.id` are repaired at normalization by `src/atlas/ingest/author_repair.py` (order: `curation/author_attach.csv`, then ORCID via the committed `curation/orcid_author_ids.csv` or the raw index, then a unique same name + institution match; a repair never repeats an author already on the work). Authorships gain `author_id_source`; counts are in `docs/normalization_qc.md`.
- Live ORCID lookup (`scripts/fetch_orcid_author_ids.py`): 70 ORCIDs, 53 resolved, 17 not found (stored blank), 700 OpenAlex credits.
- Full local rebuild in the daily-workflow order: 131 of 792 null IDs filled (72 ORCID, 59 name/institution); experts 2,614 -> 2,635 with none removed; exported works 1,909 -> 1,915. Jeff Wagner (A5072641519, CDPH) is exported with 7 works. Most author-file diffs are routine citation refreshes from `fetch_author_metrics.py`.
- Gate: links, A1/A2 scaffolds, Ruff check/format, compileall, 1,655 passed / 9 expected skips; CI guards OK.
- Owner change: HUMAN_TASKS H1 (CORE key) moved to Later, because no code uses CORE.

## State of the repo
- At entry, concurrent owner edits were in progress (`framework/src/**`, `tests/test_vd*.py`, `tests/framework_monitoring_runtime.mjs`, `.agent/QUESTIONS.md`); they were preserved and left out of this commit.

## Next tasks (suggested)
- Follow-up (not yet in TODO): run `fetch_orcid_author_ids.py` in `ingest_works.yml` before normalization, so new orphan ORCIDs get resolved.
- Expert metrics for repaired authors still come from their OpenAlex profiles (Wagner shows 0 `plastic_works_count`); consider computing those counts from corpus authorships.

## Gotchas the next agent must know
- Rerun `scripts/fetch_orcid_author_ids.py` and then renormalize after big ingests; the ORCID map is committed so CI normalization can read it.
- 661 null-ID authorships stay out of Experts by owner decision (no provisional IDs); fix individual people in `curation/author_attach.csv`.

## Needs owner input
- H25: owner side-by-side design review for VD-12. Optional: report the split Jeff Wagner profile to OpenAlex.
