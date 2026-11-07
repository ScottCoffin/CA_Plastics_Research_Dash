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

## End every session
1. Run the task acceptance check and `make test`.
2. Update memory files in the order required by `spec.md` B4.
3. Overwrite `HANDOFF.md`; append one line to `SESSION_LOG.md`.
4. Commit as `S<stage>.<task>: <summary>`; push only if configured.
5. Report completed work, the next task, owner actions, and a copy-paste prompt
   for the next fresh agent that asks that agent to provide its successor prompt.
   Then stop.
