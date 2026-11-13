Resume the CA Plastics Research Atlas as lead orchestrator (CLAUDE.md role) from the latest commit on main
(session end 2026-11-12 overnight: UX remediation batch done, 15 UX tasks sealed; eScholarship evidence
complete; CI and deploy green).

Session entry only (CLAUDE.md "Session entry"): `git status --short && git log --oneline -15`, read
`.agent/MEMORY.md` in full, read `.agent/HANDOFF.md`, list open TODO lines, `git diff HEAD -- .agent/QUESTIONS.md`.

First remind the owner of the "Do now" items in `.agent/HUMAN_TASKS.md` (H17 UX answers, H16 switch,
H1 CORE key).

Then, by owner answer:
- UXD-3 answered -> UX-5 (scope toggle). UXD-9 "yes" -> UX-17 (CI axe/Lighthouse).
- H16 "switch" -> UX-13, then make the Framework build the site root (ADR-AT5-SHELL "Switch plan").
- CORE key renewed -> S2.5 CORE audit.
- UX-GLOSS / UX-LICENCE edits -> apply the owner's wording to glossary.md, monitoring_view.js, about.md.
Use Haiku workers for bounded pages (budget one "continue" per worker: they hit the 30-turn limit),
seal each checkpoint (gate, clean-worktree pytest, push ONLY if that pytest exits 0), and confirm CI.
Edit repo files as bytes or with newline="" (Python write_text on Windows doubles CRs).
Never commit `docs/SOURCES.md`, `docs/api_notes/source_watch_s7_6.json`, `data/processed/p{5,25,100}.parquet`,
`curation/annotations/` or `.agent/QUESTIONS.html` (owner work in progress).
