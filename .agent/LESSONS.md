# Lessons (newest first; append-only)

## 2026-11-05 - Institution coverage and resumable review
- An exact OpenAlex `geo.region:California` seed is necessary but not a
  sufficient coverage assertion. Compare against explicit official UC/CSU
  lists and supplement missing required records by bounded institution search.
- The shared anonymous OpenAlex budget can be exhausted by other users on the
  network. Validate the local key before a production pull; the builder accepts
  both `OPENALEX_API_KEY` and the owner's local `OPEN_ALEX_API_KEY` alias.
- Use the checksum-verified ROR dump for bulk joining. Resume interrupted
  Zenodo downloads with HTTP ranges rather than restarting a large transfer.
- A generated human-review CSV is state, not disposable output. Preserve owner
  columns by stable OpenAlex ID on rebuild and keep S1.2 unchecked until all
  100 rows contain both an owner type and review date.

## 2026-11-05 — OpenAlex and ROR live contracts
- OpenAlex's exact institution-region value is `California`, not `CA`.
  `institutions.id` and `authorships.institutions.id` matched the same works,
  but the shorter documented spelling is canonical for new code.
- OpenAlex rejects a 101-value institution OR filter even when its URL is far
  below the separate 8,190-byte GET limit; keep ID batches at 100 or fewer.
- Anonymous OpenAlex calls can initialize a cursor but need an API key to
  follow it. Basic paging is sufficient only for bounded result sets under the
  10,000-result ceiling.
- ROR v2 schema 2.1 uses `country_code=US` and
  `country_subdivision_code=CA`; do not expect the combined code `US-CA`.
- ROR emits no billing credits. Log its request count with zero cost so a run's
  cross-source accounting remains complete.

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
