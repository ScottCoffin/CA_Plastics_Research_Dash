Resume the CA Plastics Research Atlas roadmap as lead orchestrator from checkpoint 26b71a2
(query v3.1 promoted; grants relevance, monitoring basemap and CI experts export pushed).
Follow CLAUDE.md "Session entry" only (git status/log, .agent/MEMORY.md, .agent/HANDOFF.md,
open TODO lines, `git diff HEAD -- .agent/QUESTIONS.md`).
First task: S2.1-B. Check the latest `ingest_works` run (`gh run list --workflow ingest_works.yml`):
it should report a query-version backfill from 1950, commit site/data and dispatch the deploy.
If it succeeded, verify the live Experts tab has real CA authors, record counts and payload sizes
in docs/S3_6_VERIFICATION.md, and check off S2.1-B. If it failed or deferred, diagnose from the log.
Then apply any owner answers (GRANT-REL, EM18-DATES) and continue with AT-2 in dependency order,
using Haiku workers per CLAUDE.md, sealing each checkpoint (clean-worktree check, CI after push).
