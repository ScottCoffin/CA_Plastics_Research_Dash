# UX-0, UX-1 and UX-21 verification (2026-11-12)

Contract: `docs/EM_spec.md` (owner UX/UI remediation spec; browser audit in its Section 1A).

## UX-0 recon
- Stack: Observable Framework 1.13.4 app in `framework/` (config `framework/observablehq.config.js`,
  pages `framework/src/*.md`, theme `framework/src/style.css`), built by `npm run build` and
  deployed under `/app/` by `.github/workflows/build_deploy.yml`; the classic site is `site/`
  (`index.html`, `expert.html`, `grants.html`). Shared header and footer: the `header` and
  `footer` strings in the Framework config.
- Live audit, 2026-11-12: Playwright (Chromium) at 1366x900 and 375x812, axe-core 4.10.3, Tab walk,
  Lighthouse 12.8.2 on 12 routes. The results are in `docs/EM_spec.md` Section 1A. Tool:
  `~/tools/ux-audit/ux_audit.py` (machine-wide, outside the repo).

## UX-1: Classic-site link and new-version banner
- Cause: Framework rewrites the header's `href="../"` to `./`, which is the page the reader is
  already on. The live audit showed `./` on all nine /app/ pages.
- Fix: the header link now has `class="atlas-classic"`, and `framework/scripts/postbuild.mjs`
  (the npm `postbuild` hook) sets its href to `../index.html` in every built page.
  `site/index.html` shows "A newer version of this atlas is available." linking to `app/`.
- Local preview (`scripts/serve_framework_preview.py --port 8771`, Playwright):
  - On `/app/experts`, clicking "Classic site" opened `.../CA_Plastics_Research_Dash/index.html#experts`,
    the classic Experts browser.
  - On the classic page, clicking the banner link opened `.../app/` ("Overview | CA Plastics Research Atlas").
- Tests: `tests/test_ux_links.py` (config href, postbuild hook, banner href and text, and the
  `fixHtml` rewrite run under Node).

## UX-21: template accessibility
- The postbuild step adds `<html lang="en">` and removes `maximum-scale=1` from the viewport meta.
- axe (`html-has-lang`, `meta-viewport`) found no violations on the preview's `/app/`,
  `/app/experts`, `/app/evidence` and `/app/about`. The live site showed both violations on every
  /app/ page before the fix.

## Gate
- Links, A1 and A2 scaffolds; `make lint test build`: 1,353 passed, 9 skipped; `git diff --check`.
- `scripts/check_at5.py --dist dist` passed. `scripts/smoke_framework_pages.py` passed on all
  nine pages.

## Not verified
- The live deploy was not checked until CI ran. The other axe findings (contrast, headings,
  CLS) are open as UX-22..UX-25.
