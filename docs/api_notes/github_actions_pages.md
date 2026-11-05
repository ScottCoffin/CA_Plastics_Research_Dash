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

Live workflow execution must be checked after the S0.2 commit reaches the default branch. A live
Pages URL cannot be verified until the owner changes the plan, visibility, or hosting choice.
