# Handoff - 2026-11-12 (overnight) - UX remediation batch; eScholarship complete

## Done this session (all pushed; checks: full gate + clean-worktree pytest before every push)
- UX-4 Evidence honest state; UX-23 headings; UX-24 Monitoring CLS 0.52 -> 0.04 and grants.html
  aria (+ heat-map contrast: grants.html axe-clean); UX-6 institution-count definitions (211 any
  work vs 161 plastic-related; not a data bug); UX-8 Funding without headline sum; UX-9 Monitoring
  CSV download, ISO dates, licence glosses; UX-10 About (How to cite, licence, plain text);
  UX-11 Related resources badge + NCEI/Plastiverse stewards; UX-12 Policy dates and acronyms;
  UX-14 Overview; UX-7 `/app/glossary`; UX-25 mobile/meta (no 375 px overflow, SEO 100, favicon);
  UX-15/16 Experts list states + volume captions; UX-18 `scripts/ux_tasks.py` (6/6 pass);
  UX-20 materials (`docs/UX_20_SESSION_PLAN.md`). Evidence: `docs/UX_*_VERIFICATION.md`.
- `check_public_text.py` also rejects TODO-OWNER and "pending owner review".
- S2.5 eScholarship: last 72 items fetched (no 403); 265/265 with evidence; applied by
  normalization at the next daily export.
- Local audit, 10 /app/ routes, desktop + 375 px: axe only the Framework sidebar `list`/`region`;
  0 console/HTTP errors.

## Not verified / left
- Loading and failure panels on Experts not exercised in a browser (no-results was).
- The NIH amount-basis text on Funding shows a raw field name (`award_amount, reported as ...`): it
  comes from `site/data/grants.json` (pipeline), so a UX task did not change it. Fix in the grants
  export if wanted.
- Worker preview servers on ports 8778/8779 and gitignored `framework/dist-h` may still exist
  locally (the worker's kill was denied).

## Next eligible (each needs an owner answer first)
1. UX-5 after UXD-3; UX-17 after UXD-9; UX-13 after H16 ("switch"); then the Framework-at-root switch.
2. S2.5 CORE audit after H1 (key renewed 2026-11-13).
3. S5 chain after H9 gold labels; UX-19/UX-20 sessions are owner work.

## Owner actions (details in `.agent/HUMAN_TASKS.md`)
- H17: answer UXD-1..9 plus UX-LICENCE, UX-GLOSS, UX-13-H16 in QUESTIONS (blank = keep default);
  optional About contact address.
- H16: compare /app/ with the classic site; reply "switch" when ready.
- H1: renew the CORE key. H18 (optional): run the usability sessions. H2, H15, H8, H9 as before.
