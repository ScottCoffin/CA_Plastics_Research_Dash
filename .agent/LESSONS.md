# Lessons (newest first; append-only)

## 2026-11-05 — GitHub Pages live acceptance
- Changing the repository to public removed the plan restriction, but Pages
  still had to be created explicitly with `build_type=workflow` before the
  deployment could pass `configure-pages`.
- The Pages API reports the account custom-domain URL
  `https://scottcoff.in/CA_Plastics_Research_Dash/`; verify that URL's status
  and expected page content, not only the Actions conclusion.
- Manual run `42092058401` built and deployed the site successfully.

## 2026-11-05 — GitHub Actions and Pages scaffold
- GitHub Pages creation returned HTTP 422 because the current plan does not
  support Pages for this private repository. Resolving that requires an owner
  decision under G-7: change visibility after the license decision, upgrade the
  plan, or choose alternate hosting.
- GitHub documents the 60-day scheduled-workflow inactivity disablement for
  public repositories. Scheduled workflows run only from the default branch and
  may be delayed or dropped, so S0.2 uses off-peak minutes plus a watchdog.
- The Job_Scraper reference is AGPL-3.0 while this repository's license remains
  pending. Reuse its documented concepts, not its workflow code.
- Validate workflow syntax locally with `actionlint`; live execution still
  requires the files to be present on the default branch.

## 2026-11-05 — Bootstrap environment
- GNU Make is not on PATH, but Rtools provides
  `C:\rtools45\usr\bin\make.exe`; direct Python equivalents also work.
- Do not rely on an ambient `PYTHONPATH` in acceptance checks. Pytest now gets
  `src` from `pyproject.toml`, so a clean `make test` imports the package.
- `gh` 2.89.0 is installed, so S0.2 can inspect and trigger GitHub Actions after
  repository authentication and permissions are confirmed.
