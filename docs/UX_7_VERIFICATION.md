# UX-7 verification (2026-11-12)

Contract: `docs/EM_spec.md` UX-7 (keyboard-reachable definitions for the listed terms; /app/glossary
linked from every page footer; unknown terms TODO-OWNER).

## Changes
- New page `framework/src/glossary.md` (/app/glossary): a definition list with anchors for access
  tiers A–D, tier, fractional works, bootstrap interval, rank range, rising percentile and its
  population, m-quotient, CA-led, CA-sampled, California state waters, matrix, plastic-related and
  licences. Each entry names its source in plain words (no file paths).
- `framework/observablehq.config.js`: Glossary in the sidebar after About and a Glossary link in the
  footer of every page. (The same file carries UX-25's favicon `head` line.)
- Institutions and Experts pages link their terms (tier, rank range, bootstrap interval, fractional
  works, m-quotient, rising percentile, CA-led, plastic-related) to the glossary anchors, so every
  definition is reachable by keyboard (links, not `title` tooltips).
- Lead edit: removed repo paths, "pending owner review" and TODO markers from the public text; gave
  "Matrix" its standard monitoring meaning.
- Tests: `tests/test_ux7_glossary.py`; `tests/test_framework_shell.py` page list.

## Sources of the wording
- Methods (institution counts and stability): tier, fractional works, bootstrap interval, rank range.
- About, Definitions: CA-led, CA-sampled, state waters, plastic-related.
- Monitoring source-registry rules (`docs/S7_1_VERIFICATION.md`): access tiers.
- `src/atlas/build/expert_metrics.py` docstring: m-quotient, rising percentile (population = experts
  with at least 10 plastics citations in the 5-year window).

## TODO-OWNER
- Confirm the m-quotient and rising-percentile wording and add them to `docs/METHODS.md`.
- Confirm the matrix wording and the licence glosses (shared with UX-9).

## Evidence
- Local audit of 10 routes (desktop and 375 px): no new axe violations, no console or HTTP errors.
