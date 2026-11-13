# UX-10 verification (2026-11-12)

Contract: `docs/EM_spec.md` UX-10 (How to cite with the current release DOI; licence statement per
UXD-8; non-GitHub contact; plain-language rewrite of developer sentences; link definitions).

## Changes (`framework/src/about.md`)
- **How to cite** card, built from `site/data/release.json`: "Coffin, S. (2026). CA Plastics
  Research Atlas (v2026.11.11) [Data set and software]. Zenodo. https://doi.org/10.5281/zenodo.24124017",
  plus the concept DOI 10.5281/zenodo.24124016 for all versions. Release 2026-11-11 confirmed in
  `config/release.yml`.
- **Licence** card: states the licences already committed in `LICENSE` (MIT, code) and
  `LICENSE-DATA.md` (CC BY 4.0, derived data; third-party terms kept; OpenAlex CC0). UXD-8's default
  was a placeholder, but these files already exist (ADR-002), so the page restates them; the
  owner can still change the wording.
- Developer sentences rewritten: the inactive-query and `search=plastic` sentence, the
  `build_metadata.json` refresh sentence, and the "S3.1 site data contract" link text.
- Definitions card links to the Glossary (UX-7).
- Contact: "If you cannot use GitHub, a contact address will be listed here soon." (TODO-OWNER.)
- Test: `tests/test_ux10_about.py`.

## Evidence
- Local build: rendered How to cite and Licence text checked with Playwright; axe on /app/about
  shows only the Framework sidebar `list`/`region`; `check_public_text.py` OK.

## TODO-OWNER
- A non-GitHub contact address (email or form) for About.
- Confirm the licence wording (UXD-8).
