# Handoff — 2026-11-05 — task S0.1

## Done
- Created the C2 repository directory skeleton and Python `src/atlas` package.
- Added `pyproject.toml`, `Makefile`, pre-commit/Ruff config, ignore rules,
  README, license placeholder, config/curation schemas, docs, and a smoke test.
- Created all Part B memory files and the complete 60-task Part E roadmap.
- Passed `make test`, `make lint`, `make build`, and `git diff --check`.

## State of the repo
- Bootstrap package version is `0.0.0`; no external sources or UI are active.
- Run checks using `C:\rtools45\usr\bin\make.exe test` (or direct Python
  equivalents from `README.md`) because Make is not on PATH.
- No known failing tests or warnings.

## Next task (suggested)
- S0.2: add CI and Pages scaffolding. First create lint/test CI, then a
  placeholder site and Pages workflow, then keepalive/watchdog workflows.

## Gotchas the next agent must know
- Do not implement S1 work during S0.2; config and data files are placeholders.
- `spec.md` was supplied untracked and is now the committed canonical contract.
- Raw/interim/log contents, full-text PDFs, scratch files, and models are ignored.

## Needs owner input
- G-7: confirm repository name/hosting and replace the license placeholder.
- S0.2: add `OPENALEX_API_KEY` only after the workflow documents its secret name.

## Files that are large or unsafe to read whole
- `spec.md` (~80 KB): read only Part B and the selected stage/source sections.
- Future `data/raw/` and `data/interim/`: inspect with schemas and row limits.
