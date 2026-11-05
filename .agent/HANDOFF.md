# Handoff — 2026-11-05 — task S0.2

## Done
- Confirmed the owner made the repository public and chose to keep it public.
- Enabled GitHub Pages with the GitHub Actions build type.
- Manually dispatched `build_deploy.yml`; run `42092058401` succeeded for
  commit `8a80fca`.
- Verified `https://scottcoff.in/CA_Plastics_Research_Dash/` returns HTTP 200
  with the expected title and placeholder content.
- Confirmed `OPENALEX_API_KEY` exists by name and normalized the repository
  variable `ENABLE_DATA_COMMITS` to the exact required value `true`.
- Completed the S0.2 acceptance records and marked the task complete.

## State of the repo
- Run local checks with `C:\rtools45\usr\bin\make.exe test`, `lint`, and `build`.
- Pages deploys `site/` on main-branch pushes, manual dispatches, and the daily
  schedule; the live placeholder is at the URL above.
- GitHub configuration and live-run evidence are recorded in
  `docs/api_notes/github_actions_pages.md`.
- S0.2 is complete; no S1 implementation was started.

## Next task (suggested)
- S1.1: verify OpenAlex and ROR API behavior and implement request-cost logging.
- First read Part B, the S1 stage entry, and the named Part D source rows.
- Create bounded smoke tests under `scripts/smoke/` and dated API notes.
- Implement and test `util/cost.py` only after the live contracts are recorded.

## Gotchas the next agent must know
- The Pages URL uses the account custom domain, not the default `github.io` URL.
- `ENABLE_DATA_COMMITS` is case-sensitive and must stay exactly `true`.
- `OPENALEX_API_KEY` was verified only by name; never print or commit its value.
- Upstream licenses still must be checked before publishing CC BY derived data.

## Needs owner input
- G-6 remains open: identify a machine-readable State Water Board awards source
  when S8.8 is reached.
- No owner action remains for S0.2.

## Files that are large or unsafe to read whole
- `spec.md` (~80 KB): read Part B, the selected Part E task, and named Part D rows.
- Future `data/raw/` and `data/interim/`: inspect with schemas and row limits.

## Prompt for the next fresh agent
You are a build agent for `C:\Users\Scott.Coffin\R_new\CA_Plastics_Research_Dash`.
Follow Part B of `spec.md` exactly. Read the required `.agent` files, inspect
`git log --oneline -15` and `git status`, and complete exactly the first unchecked
task, S1.1. Read only Part B, the S1 stage entry, and the Part D source rows named
by S1.1. Run the task acceptance check and `make test`, update all B4 records in
order, commit/push if configured, and stop without starting S1.2. End by
reporting owner actions and providing a copy-paste prompt for the next fresh
agent that explicitly repeats this successor-prompt requirement.
