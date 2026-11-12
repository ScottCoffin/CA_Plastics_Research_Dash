Resume the CA Plastics Research Atlas as lead orchestrator (CLAUDE.md role) from the latest commit on main
(session end 2026-11-12: AT-5 Framework app live at https://plastiverse.live/app/ beside the classic site;
EM-5, EM-6, EM-7, EM-16, EM-18 done as Framework pages; CI and deploy green).

Session entry only (CLAUDE.md "Session entry"): `git status --short && git log --oneline -15`, read
`.agent/MEMORY.md` in full, read `.agent/HANDOFF.md`, list open TODO lines, `git diff HEAD -- .agent/QUESTIONS.md`.

First remind the owner of the "Do now" items in `.agent/HUMAN_TASKS.md`, especially H16 (compare
https://plastiverse.live/app/ with the classic site; answer EM5-STRIP) and H1 (CORE key).

Then:
- If the owner replied "Framework pages OK, switch" (H16): make the Framework build the site root
  (ADR-AT5-SHELL "Switch plan"): build Framework at `/`, keep classic-only pages and `data/`/`assets/`
  alongside, redirect `index.html#<tab>?...` hashes to the matching page hashes; run
  `scripts/check_at5.py --dist dist` and `scripts/smoke_framework_pages.py` on every page before pushing.
- Otherwise continue "Next eligible" in HANDOFF.md (CORE audit once the key is renewed; eScholarship
  resume, 72 items).
Use Haiku workers for bounded pages (budget one "continue" per large port: they hit the 30-turn limit),
seal each checkpoint (gate, clean-worktree pytest, and push ONLY if that pytest exits 0), and confirm CI.
Never commit `docs/SOURCES.md`, `docs/api_notes/source_watch_s7_6.json`, `data/processed/p{5,25,100}.parquet`,
`curation/annotations/` or `.agent/QUESTIONS.html` (owner work in progress). Write patch scripts with the
Write tool or Python (shell heredocs containing `${...}` are blocked by the safety parser).
