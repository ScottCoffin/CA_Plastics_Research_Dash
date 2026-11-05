# Handoff — 2026-11-05 — task S0.2

## Done
- Added `.github/workflows/ci.yml` for lint, tests, and build checks.
- Added the placeholder `site/index.html` and `build_deploy.yml` Pages workflow.
- Added guarded monthly `keepalive.yml` and the stale-run `watchdog.yml`.
- Added `docs/SECRETS.md`, GitHub verification notes, and reuse attribution.
- Passed test, lint, build, HTML parsing, YAML parsing, actionlint, and diff checks.

## State of the repo
- Run local checks with `C:\rtools45\usr\bin\make.exe test`, `lint`, and `build`.
- The automation implementation is complete, but S0.2 remains unchecked because
  live Pages acceptance is blocked by the private repository's current plan.
- Inspect external status with `gh run list --limit 20` and
  `gh api repos/ScottCoffin/CA_Plastics_Research_Dash/pages`.

## Next task (suggested)
- S0.2 live acceptance closeout after the owner resolves hosting: enable Pages
  with GitHub Actions, manually dispatch `build_deploy.yml`, and verify the URL.
- After S0.2 is checked off, S1.1 is the next roadmap task: create OpenAlex/ROR
  smoke tests, record exact filters and response shapes, then add cost logging.

## Gotchas the next agent must know
- Do not implement S1 while S0.2 is still the first unchecked task.
- Do not make the repository public while the G-7 license decision is pending.
- `ENABLE_DATA_COMMITS` must be exactly `true` before keepalive can push.
- Local workflow validation does not prove a successful Actions run or deploy.

## Needs owner input
- G-7 and S0.2-A: choose public visibility after licensing, a Pages-capable plan,
  or alternate hosting.
- S0.2-B: approve and set `ENABLE_DATA_COMMITS=true` when repository writes are
  wanted.
- S0.2-C: add `OPENALEX_API_KEY` as an Actions secret; never commit its value.

## Files that are large or unsafe to read whole
- `spec.md` (~80 KB): read Part B, the selected Part E task, and named Part D rows.
- Future `data/raw/` and `data/interim/`: inspect with schemas and row limits.

## Prompt for the next fresh agent
Follow Part B of `spec.md`. Read the required `.agent` files, inspect Git state,
and complete exactly the first unchecked task. S0.2 code is implemented, but its
live Pages acceptance is blocked by S0.2-A/G-7. If the owner has resolved hosting,
enable Pages with GitHub Actions, manually dispatch and verify the deploy, update
all B4 records, commit/push, and stop. Do not start S1 until S0.2 is checked off.
End by reporting owner actions and providing a copy-paste prompt for the next
fresh agent that repeats this successor-prompt requirement.
