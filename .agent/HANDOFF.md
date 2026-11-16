# Handoff — 2026-11-15 — task VD-6a

## Done
- Completed VD-6a documentation in `.agent/TODO.md`, `.agent/MEMORY.md`, `.agent/SESSION_LOG.md`, `.agent/DELEGATION_LOG.md`, and `docs/VD_6A_VERIFICATION.md`.
- Accepted Experts adoption in `framework/src/experts.md`, `framework/src/components/experts.css`, and `framework/src/components/experts.js`; the focused test is `tests/test_vd6a_experts.py`.
- Worker verification: 33 focused tests passed; Node, Ruff, and diff checks passed. The consolidated suite reported 1,595 passed and 9 expected placeholder skips. Framework build: 13 pages, 76 links.
- Local assembled Playwright acceptance passed at 1440 x 900 and 390 x 844. Axe violations, horizontal overflow, console/page/request errors, and actionable targets below 24 px: zero (excluding the accepted inert Framework 1 x 1 sidebar checkbox). Exactly three full expert rows fit at desktop; row three ends at 897.375 px.
- One independent Luna browser auditor hit the account usage cap; the primary agent completed browser verification.
- Implementation and records are ready for the lead's narrow commit/push.

## State of the repo
- For the Framework build, run `npm run build` in `framework/`. Use an assembled site for browser checks so packaged assets resolve.
- Evidence is local to the assembled site and does not claim a live deployment.
- At task entry, unrelated concurrent worktree edits included `.agent/QUESTIONS.md` plus VD-5/VD-6b implementation and test files. This documentation checkpoint did not alter them; inspect current Git status before the next task.
- VD-5 remains open, including its LCP requirement. H25 owner review remains open under VD-12. VD-6b status is tracked separately.

## Next tasks (suggested)
- Re-read `.agent/TODO.md` and current Git status, then select the next dependency-satisfied task without assuming VD-5 or VD-6b acceptance from these records.

## Gotchas the next agent must know
- For visual browser QA, use the production-shaped assembly rather than `framework/dist` alone; the latter does not contain all packaged font assets.
- Framework's hidden 1 x 1 sidebar checkbox is inert and excluded from the actionable-target result. Do not count it as a visitor control.

## Needs owner input
- H25: owner side-by-side review for VD-12.

## Files that are large or unsafe to read whole
- `site/data/` — inspect schemas and counts, not all generated payloads.
