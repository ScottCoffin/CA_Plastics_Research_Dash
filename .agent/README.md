# Agent Protocol

This repository is implemented one task per atomic checkpoint. A single chat
or Goal-mode run may complete multiple checkpoints without mixing their edits,
verification, documentation, or commits. The full mandatory rules are in
`spec.md` Part B; the roadmap and acceptance checks are in Part E.

## Enter a goal or start a task checkpoint
1. On goal/chat entry, read this file, `MEMORY.md`, `HANDOFF.md`, and `TODO.md`.
2. At later task boundaries, re-read `HANDOFF.md`, `TODO.md`, owner-answer
   changes in `QUESTIONS.md`, and `MEMORY.md` after compaction or outside edits.
3. Run `git log --oneline -15` and `git status --short` at every boundary.
4. Read only Part B, the selected Part E stage, and named Part D sources.
5. Take the first unchecked dependency-satisfied task. If an owner-gated task
   blocks, record it and take another eligible branch when one exists.

## Working rules
- Complete exactly one roadmap task per checkpoint; seal it before beginning
  another task.
- Keep large data and verbose output out of context and Git.
- Record unstated choices in `QUESTIONS.md`; use the documented default.
- Smoke-test every `[VERIFY]` dependency and add `docs/api_notes/` evidence.
- Make scripts idempotent, incremental, resumable, tested, and secret-free.
- Check licenses in `docs/REUSE.md` before copying third-party code.
- When delegation is authorized, use Luna task agents unless exceptional
  difficulty or risk justifies a documented higher-intelligence executor.
  Give each agent exact file ownership, contract sections, interfaces to
  preserve, and checks to run; require it to ingest only that bounded context.

## Browser smoke checks with Playwright

Use the repository's Playwright skill for real-browser work (UI flows,
keyboard checks, screenshots, and data-loading smoke tests). This checkout's
browser tooling runs in WSL, not the Windows PowerShell Node installation:

1. Start a WSL shell and confirm `node --version` is 20 or newer and
   `command -v npx` succeeds. The configured environment uses Node 20.20.2
   through `/home/scottoffin/.nvm`.
2. Serve the static site from WSL so the browser and server share a network
   namespace:

   ```bash
   cd /mnt/c/Users/Scott.Coffin/R_new/CA_Plastics_Research_Dash
   python3 -m http.server 8765 --directory site
   ```

3. In a second WSL shell, use the bundled wrapper. The installed browser is
   Playwright Chromium, so pass `--browser=chromium`; the default `chrome`
   channel expects a system install at `/opt/google/chrome/chrome`.
   The Windows-mounted wrapper currently has CRLF line endings, so normalize
   it in the pipeline:

   ```bash
   PWCLI=/mnt/c/Users/Scott.Coffin/.codex/skills/playwright/scripts/playwright_cli.sh
   sed 's/\r$//' "$PWCLI" | bash -s -- open --browser=chromium http://127.0.0.1:8765/
   sed 's/\r$//' "$PWCLI" | bash -s -- snapshot
   ```

   Always snapshot before using element refs, and snapshot again after tab
   changes or navigation. Use `screenshot` for visual checks and keep any
   deliberate artifacts under `output/playwright/`; do not commit CLI session
   logs or `.playwright-cli/` captures.

## Seal every task checkpoint
1. Run the task acceptance check and `make test`.
2. Update memory files in the order required by `spec.md` B4.
3. Overwrite `HANDOFF.md`; append one line to `SESSION_LOG.md`.
4. Commit as `S<stage>.<task>: <summary>`; push only if configured.
5. Confirm the worktree contains only known unrelated work, then report the
   checkpoint result and any owner actions.
6. If a continuous goal is active, return to the boundary checklist and begin
   the next eligible task. Otherwise provide a resumable continuation prompt.
7. Pause only for a blocking owner decision, required permission, genuine
   blocker, explicit user pause, or roadmap completion.
