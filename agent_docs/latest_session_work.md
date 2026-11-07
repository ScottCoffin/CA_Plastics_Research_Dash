# Latest Session Work

## Detailed Current State

S3.4 is complete and pushed. `site/index.html` now contains the qualifying
institution leaderboard, type chips, all-time/latest-five-year counts,
sparklines, a dependency-free clustered California map, and links into the
existing Experts filter. The authoritative task handoff is
`.agent/HANDOFF.md`; the next unchecked task is S3.5.

The repository protocol now uses one atomic roadmap checkpoint per task while
allowing a single chat or Goal-mode run to continue across checkpoints. Each
task must still be accepted, documented, committed, and pushed separately.

## Verification

- `py -3.14 scripts/check_s3_4.py` passes with three qualifying fixture
  institutions.
- `py -3.14 scripts/check_s3_3.py` and `scripts/check_s3_2.py` pass.
- The full suite passes with 47 tests; Ruff, compileall, and `git diff --check`
  pass.
- WSL Chromium verified the Institutions tab, type chip, map marker, Experts
  link, and the preserved S3.3 researcher drawer.

## Next Entry Point

Continue with S3.5 from `.agent/HANDOFF.md`: implement About/Methods content
and generated freshness metadata, run its acceptance and the full suite, update
the B4 records, and commit/push only S3.5. Then re-read `.agent/TODO.md` and
continue to the next eligible checkpoint unless a pause condition applies.
