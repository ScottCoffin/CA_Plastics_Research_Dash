# S3.5 Verification — 2026-11-06

## Acceptance

- `py -3.14 scripts/check_s3_5.py` passes. It checks the public Methods,
  disclaimer, and correction path; confirms the committed
  `build_metadata.json` fixture sentinel and counts; and executes the actual
  About renderer in Node for fixture, live-timestamp, and missing-value cases.
- `py -3.14 scripts/check_s3_2.py`, `py -3.14 scripts/check_s3_3.py`, and
  `py -3.14 scripts/check_s3_4.py` pass, preserving the earlier tab, Experts,
  and Institutions contracts.
- `C:\rtools45\usr\bin\make.exe PYTHON="py -3.14" test` passes: 49 tests.
- `py -3.14 -m ruff check .` and `py -3.14 -m ruff format --check .` pass.
- `git diff --check` passes.

The fixture timestamp is intentionally `fixture`; it is shown as example data,
not a live refresh. Independent browser interaction and visual evidence is
recorded below.

## Independent verification — 2026-11-06

### Outcome

S3.5 acceptance passed for the fixture data and rendered About page. No S3.5
product failure was observed.

### Checks and browser evidence

- `py -3.14 scripts/check_s3_5.py` passed. Its Node runtime harness evaluates
  the production About view-model and renderer against the committed fixture,
  a live ISO timestamp (`2026-11-06T12:34:56+00:00`), and missing refresh/count
  values. It checks metadata counts (not index counts) and the unavailable
  fallbacks.
- `py -3.14 -m pytest tests/test_s3_5.py -q` passed: 2 tests.
- Playwright Chromium opened the static site in WSL using Node `v20.20.2` and
  `npx`. The browser loaded the fixture and showed the freshness label, all
  five counts (4 authors, 4 works, 3 institutions, 1 California institution,
  4 labeled works), schema `s3.1`, Methods content, correction route, and the
  exact disclaimer: “Independent project; not an official OEHHA or State
  product.”
- Regression path passed: Institutions → University of California, Davis
  “View experts” → Experts filtered by `I84218800` → Alice California drawer.
  The drawer showed its work and report-an-error link.
- At 390×844, the About cards stack and the document width remains 390 px.
  The tab strip is horizontally scrollable. Screenshot (local, gitignored): `output/playwright/s3_5_about_mobile.png`.

### Limitations and residual risk

- The live ISO and missing-value cases are covered by the Node renderer harness,
  not by browser fetch interception; the browser smoke used the committed
  fixture as intended.
- The browser logged two 404 requests for `/favicon.ico`; the app data loaded
  successfully and no warnings were reported. Raw console reference:
  `.playwright-cli/console-2026-11-07T03-13-24-086Z.log`.
- Snapshot references: initial
  `.playwright-cli/page-2026-11-07T03-13-24-212Z.yml`; About
  `.playwright-cli/page-2026-11-07T03-14-03-656Z.yml`; Institutions
  `.playwright-cli/page-2026-11-07T03-14-14-479Z.yml`; filtered Experts
  `.playwright-cli/page-2026-11-07T03-14-24-695Z.yml`; drawer
  `.playwright-cli/page-2026-11-07T03-14-36-066Z.yml`; mobile About
  `.playwright-cli/page-2026-11-07T03-15-15-762Z.yml`.
