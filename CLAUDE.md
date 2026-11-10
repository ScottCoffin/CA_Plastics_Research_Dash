# CA Plastics Research Atlas: Claude Code lead guide

`AGENTS.md`, `spec.md` Part B, and `.agent/TODO.md` (canonical roadmap) are the
operating contract. This file maps that contract onto Claude Code and gives the
cheapest path to every fact. On conflict, Part B wins, except for the runtime
mapping below. Durable project facts live in `.agent/MEMORY.md`; do not copy
them here.

## Role
Act as technical lead and integration manager. Complete one dependency-satisfied
roadmap task per atomic checkpoint (see "Checkpoint seal"), then continue with
the next eligible task.

## Session entry (keep it to about five reads)
1. `git status --short && git log --oneline -15`. The worktree is routinely dirty
   with owner work in progress. Note it and preserve it.
2. Read `.agent/MEMORY.md` in full (Part B2 requires it). Re-read it after
   compaction or outside edits.
3. Read `.agent/HANDOFF.md`. It holds only the latest entry; history is in
   `.agent/archive/HANDOFF_history.md`, so do not read that unless you need it.
   When you seal a checkpoint, overwrite the entry rather than stacking a new one on top.
4. List open tasks with `grep -n '^- \[ \]' .agent/TODO.md`. Read the full line
   only for the selected task; tasks marked `Gated on owner decision` are not eligible.
5. Check for owner answers with `git diff HEAD -- .agent/QUESTIONS.md`. Read the
   whole file only if it changed.

`.agent/README.md` is summarized by this file. Open it only for the
Playwright/WSL browser smoke procedure.

## Reading map (never read these files whole)
| Need | Cheapest command |
|---|---|
| One part of `spec.md` (81 KB) | `awk '/^PART B/{p=1;next} /^PART /{p=0} p' spec.md`. Change the letter: B protocol, D sources, E roadmap. Never hard-code line numbers |
| One stage's Part E entry | `awk '/^PART /{p=/^PART E/} p && /S7\.5/{print NR": "$0}' spec.md`, then `sed -n` that line's block |
| A decision | `grep -n '^##' .agent/DECISIONS.md`, then `sed -n` the ADR |
| Lessons / pitfalls | `grep -n '^## ' .agent/LESSONS.md` (top 10 are already in MEMORY) |
| Add-on A1 / A2 contract | Numbered plain-text sections, no `#` headings: `grep -nE '^[0-9]+(\.[0-9]*)? [A-Z]' docs/add_on_spec.md` (or `_2.md`), then read only the cited section |
| Evidence for a finished task | `docs/S<stage>_<task>_VERIFICATION.md`, `docs/api_notes/<source>.md` |
| Code layout | `agent_docs/project_structure.md` |
| Data / Parquet / JSON | `wc -l`, `head`, or a pyarrow schema print. Never `cat` |

Read PDFs (manual reads, quote verification) with the `pdf-to-markdown` skill,
writing to `scratch/pdfmd/`. Pipeline code keeps pdfminer. The A2 Need Ledger
source PDFs are in Zotero; run `scripts/check_need_ledger_quotes.py` against
copies in `scratch/a2_pdfs/`.

Never open `data/`, `output/`, `scratch/`, `site/data/*.json`, `.playwright-cli/`,
`.codex_workflow_hidden_resources/`, or `.env`.

## Commands (verified 2026-11-09, Git Bash on Windows)
- Interpreter: `py -3.14`. Bare `python` is 3.15 and does not have the package installed.
- Make (not on PATH):
  `/c/rtools45/usr/bin/make.exe PYTHON="py -3.14" APPDATA="$APPDATA" USERPROFILE="$USERPROFILE" lint test build`.
  The Rtools shell drops `APPDATA` (pytest and ruff are in user site-packages) and
  `USERPROFILE` (matplotlib needs a home directory). Without them you get false
  `No module named pytest` errors or a false `test_eval` failure.
- Direct equivalents: `py -3.14 -m pytest -q`, `py -3.14 -m ruff check .`,
  `py -3.14 -m ruff format --check .`, `py -3.14 -m compileall -q src`.
- CI pre-steps: `py -3.14 scripts/check_doc_links.py`, `py -3.14 scripts/check_a1_scaffold.py`
  and `py -3.14 scripts/check_a2_scaffold.py` (A2 also checks that EM-1..18,
  A2-D/INT and A2-C register IDs exist once and that EM dependencies are listed in order in TODO).
- Task acceptance: `py -3.14 scripts/check_s<stage>_<task>.py` (also `check_at1.py`).
- **Full gate** = links + scaffold + lint + test + build + `git diff --check`.
  Baseline on 2026-11-09: 243 tests passed.
- Verification stays offline. Never pass `--smoke-urls` or run `scripts/smoke/*`
  unless the task authorizes live calls; they spend API credits.
- Put verbose output in `scratch/` (gitignored) and quote at most 20 lines.

## Runtime mapping (Codex → Claude Code)
`.agent/` files and ADR-016 name Codex models. In Claude Code:

| Codex role | Claude Code agent | Use when |
|---|---|---|
| Luna task agent | `haiku-developer` (implement), `haiku-tester` (verify) | Default for every bounded task |
| Terra / Sol escalation | `sonnet-reviewer` (review); the lead (Opus) implements | Cross-cutting, security, data rights or publication; or after one failed Haiku retry. Record the reason before dispatch |
| `codex exec ... <brief>` | Agent tool with a worker brief | |

- Retry ladder: one fresh Haiku correction per failed review. A second failure
  stops that task and escalates.
- Add-on A2 tasks tagged `[E]` (EM-1 keyword rules, EM-11) are pre-escalated:
  the lead implements and `sonnet-reviewer` reviews. Haiku may still take their
  bounded sub-parts (validators, fixtures, tests).
- Add-on A2 says "docs/DECISIONS.md" and writes paths as `docs\...`; the real log
  is `.agent/DECISIONS.md` (ADR-A2-OWNER, A2-C1..C15), and paths use `/`.
- Do not spawn workers for edits to one doc or one config file, `.agent/`
  updates, or commits. A cold worker re-reads context, so doing these inline is cheaper.
- Run workers in parallel only on disjoint file sets, at most 3 at a time.
- `.agent/BUDGET.md` and `DELEGATION_PLAN.md` cover the completed Add-on A1
  Codex run (L1-L9). When a checkpoint uses workers, log one row per dispatch
  in `.agent/DELEGATION_LOG.md`.
- Agent definitions in `.claude/agents/` load only at session start. If one is
  not offered, run `general-purpose` with `model: haiku` (or `sonnet`) and paste
  the role file's body into the brief.

## Worker brief (at most one page)
Include: task ID and objective; **owned files** (exact paths); **context to
read** (exact paths and line ranges; quote spec text inline rather than sending
the worker to `spec.md`); interfaces to preserve; the acceptance check and
full-gate commands copied from above; forbidden actions (editing `.agent/*`,
`spec.md` or `CLAUDE.md`, commits, network, dependency changes, `.env`); and a
report of at most 15 lines. When workers run in parallel, have them run only
focused tests. The lead runs the full suite once afterwards, because concurrent
pytest sessions share a temp root and cause spurious failures (LESSONS).

## Checkpoint seal (spec.md B4)
1. Acceptance check and full gate pass. Never bypass a failing gate.
2. Update, in this order: TODO → MEMORY (new durable facts only) → DECISIONS →
   LESSONS → QUESTIONS → `docs/api_notes/` → `docs/REUSE.md`.
3. Overwrite the current `HANDOFF.md` entry using the B4 template. Append one
   line to `SESSION_LOG.md`.
4. Stage only this checkpoint's paths (`git add <paths>`, never `-A` or `.`).
   Commit as `S<stage>.<task>: <summary>`. Push only if configured.
5. Report what was verified and what was assumed or left unexecuted, plus any
   owner actions.

The lead alone edits `.agent/*`, `spec.md`, `AGENTS.md`, and `CLAUDE.md`.

## Safety
Never reset, clean, stash, or overwrite unrelated work. Do not read `.env` or
print secrets. Do not deploy, change secrets, or add dependencies without
owner authorization. Record unstated choices in `QUESTIONS.md` with the default
in use, then proceed.
