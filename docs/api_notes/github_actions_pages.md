# GitHub Actions and Pages verification

Verified 2026-11-05 for `ScottCoffin/CA_Plastics_Research_Dash`.

## Documentation checks

- Scheduled workflows run from the default branch and may be delayed or dropped at high-load
  times. GitHub documents UTC as the default schedule timezone and 60-day inactivity disabling
  for public repositories only.
- A manually dispatched workflow must contain `workflow_dispatch` on the default branch.
- A custom Pages workflow uploads a Pages artifact and deploys it with `pages: write` and
  `id-token: write`; the repository Pages source must be GitHub Actions.
- Workflow dispatch through the REST API requires Actions write permission.

Sources:

- <https://docs.github.com/actions/reference/workflows-and-actions/events-that-trigger-workflows>
- <https://docs.github.com/actions/how-tos/manage-workflow-runs/manually-run-a-workflow>
- <https://docs.github.com/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site>
- <https://docs.github.com/rest/actions/workflows>

## Live repository checks

- The default branch is `main`; the repository is private and the authenticated user has admin
  permission.
- Actions are enabled for all actions. The default `GITHUB_TOKEN` permission is read-only, so
  workflows request only their required write permissions explicitly.
- The Pages API returned HTTP 404 before S0.2, meaning Pages was not configured.
- Creating a Pages site with `build_type=workflow` returned HTTP 422: the current
  plan does not support GitHub Pages for this private repository. The repository
  must remain private until the owner resolves G-7 and the license decision.
- No repository Actions secrets or variables were configured before S0.2.
- GitHub release metadata showed current major releases `checkout@v7`, `setup-python@v7`,
  `configure-pages@v6`, `upload-pages-artifact@v5`, and `deploy-pages@v5`.

## Live workflow checks

Commit `3f5e832` was pushed to `main` on 2026-11-05.

- Push CI run `42088635662` succeeded.
- Manual CI run `42088690046` succeeded, including lint, tests, and build.
- Manual keepalive run `42088689050` succeeded and made no commit because
  `ENABLE_DATA_COMMITS` was not set to `true`.
- Manual watchdog run `42088690263` succeeded and correctly detected that the
  Pages workflow was already running.
- Push Pages run `42088635490` and manual Pages run `42088689403` both failed in
  `configure-pages` because the Pages site does not exist. This matches the prior
  HTTP 422 plan restriction; no deployment or live URL was created.

A live Pages URL cannot be verified until the owner changes the plan, visibility, or hosting
choice.
