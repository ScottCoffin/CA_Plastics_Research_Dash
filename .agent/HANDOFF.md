# Handoff - 2026-11-13 - owner batch: relevance audit, Evidence map, funding merge, SEO, network

## Done this session (checks: full gate 1,529 passed / 9 skipped, ruff, AT-4, AT-5 build + check, public text, doc links, git diff --check; clean-worktree pytest before push)
- REL-1: the Neolithic pottery paper came from an OpenAlex match on a withheld abstract
  ("microfibers"); rules and Haiku already said "not plastic". The Evidence map ignored that
  label, so 432 non-plastic works were shown. New title-only patterns, tier-2 policy and a Haiku
  screen of 28 never-screened works take plastic-related works from 1,477 to 1,573. Details are in
  `docs/RELEVANCE_AUDIT_2026-11-13.md`.
- UX-27: Evidence map is plastic-only; heatmap cells/topic rows multi-select and narrow the table;
  works popup and table topic dropdown removed (Playwright: 1,573 -> 293 -> 451, no errors, 375 px ok).
- UX-28: Sankey and the other grants.html views ported into /app/funding.
- UX-29: "Current affiliation" filter + "Now outside California" badge (Rochman: last CA 2019).
- S9.4 (partial): `site/data/network.json` + /app/network page.
- S3.8 (partial): deploy-built expert/institution pages with JSON-LD, sitemaps, robots, llms.txt.
- H19 closed: Spring photo credit "Monterey Bay Aquarium", used with permission.

## Not verified / left
- SEO pages and the network page are only checked locally; Lighthouse SEO and the 3 s network
  load are unmeasured until after deploy.
- `network.json` is rebuilt by hand (`py -3.14 scripts/build_network.py`) after each export until
  S9.4-DEP; the daily ingest does not refresh it.
- `.agent/TODO.md` in the worktree had lost the UX-26 line and an S11.2 note (likely a stale editor
  save). It was left unstaged; the committed TODO keeps them. Owner: discard or keep the worktree diff.
- Funding: chart click-to-filter not ported; the classic grants.html remains for the classic root.
- EM-8..EM-13 remain blocked: all depend on EM-4 (A2 field classifiers), which needs S5 and the H9
  gold labels. S9.3 stays `owner: review` (H15).

## Next eligible
1. After H20/H21 answers: finish S3.8/S9.4 acceptance. After H16 "switch": Framework at root, UX-13.
2. S5 chain (then EM-4 -> EM-8..13) after H9.

## Owner actions (details in `.agent/HUMAN_TASKS.md`)
- H20 Search Console + sitemap; H21 network review; H2 now includes 28 new pending Haiku rows.
- QUESTIONS: REL-TIER2, REL-TITLE, S3.8-AI, S3.8-RENDER, S9.4-DEP; H16 "switch" (lead recommends it).
