# Agent Protocol

This repository is implemented one task per session. The full mandatory rules
are in `spec.md` Part B; the roadmap and acceptance checks are in Part E.

## Start every session
1. Read this file, `MEMORY.md`, `HANDOFF.md`, and `TODO.md`.
2. Skim `QUESTIONS.md` for owner answers.
3. Run `git log --oneline -15` and `git status --short`.
4. Read only Part B, the selected Part E stage, and named Part D sources.
5. Take the first unchecked task whose dependencies are met.

## Working rules
- Complete exactly one roadmap task and stop.
- Keep large data and verbose output out of context and Git.
- Record unstated choices in `QUESTIONS.md`; use the documented default.
- Smoke-test every `[VERIFY]` dependency and add `docs/api_notes/` evidence.
- Make scripts idempotent, incremental, resumable, tested, and secret-free.
- Check licenses in `docs/REUSE.md` before copying third-party code.

## End every session
1. Run the task acceptance check and `make test`.
2. Update memory files in the order required by `spec.md` B4.
3. Overwrite `HANDOFF.md`; append one line to `SESSION_LOG.md`.
4. Commit as `S<stage>.<task>: <summary>`; push only if configured.
5. Report completed work, the next task, and owner actions, then stop.

