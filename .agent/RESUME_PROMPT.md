Resume the CA Plastics Research Atlas as lead orchestrator (CLAUDE.md role) from the latest commit on main
(session end 2026-11-14: Framework app is the live site root; Evidence map selection feedback,
institution page, sigma.js network, expert badges, auxiliary chemicals topic, AI crawlers allowed,
UX-19 failure table, daily-ingest date-cap fix; CI and deploy green; worktree clean).

Session entry only (CLAUDE.md "Session entry"): `git status --short && git log --oneline -15`, read
`.agent/MEMORY.md` in full, read `.agent/HANDOFF.md`, list open TODO lines, `git diff HEAD -- .agent/QUESTIONS.md`.
Also run `gh run list --workflow ingest_works.yml -L 3`: the first scheduled run after the
2026-11-14 fix must succeed (it now also builds network.json and expert_badges.json).

First remind the owner of the "Do now" items in `.agent/HUMAN_TASKS.md` (H1 CORE key, H2 relevance
review, H21 network, H23 institution pages + 10 expert profiles).

Then, in order:
- UX-32: fix the UX-19 failure rows (`docs/UX_19_ACCESSIBILITY_PASS.md`); rerun
  `scripts/ux19_a11y_pass.py` on an assembled copy (`scripts/assemble_site.py`, then
  `scripts/serve_framework_preview.py --assembled <dir>`).
- UX-13 remainder: expert.html in the app shell; URL-saved state on Funding and Monitoring.
- By owner answer: H21 "network OK" -> close S9.4; H23 "profiles OK" -> close S9.3; H20b -> run
  Lighthouse SEO and close S3.8; S9.3-NAMES / H16-STUBS / REL-TITLE -> apply.
Use Haiku workers for bounded pages (budget one "continue" per worker: they hit the 30-turn limit),
seal each checkpoint (gate, clean-worktree pytest, push ONLY if that pytest exits 0), and confirm CI.
Edit repo files as bytes or with newline="" (Python write_text on Windows doubles CRs).
`curation/annotations/annotations_SC.csv` (owner gold labels) is versioned since 2026-11-14: commit it
when it changes. `docs/SOURCES.md` and the source-watch JSON belong to the weekly CI job; never run
`scripts/check_source_watch_s7_6.py` locally.
