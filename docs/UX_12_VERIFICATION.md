# UX-12 verification (2026-11-12)

Contract: `docs/EM_spec.md` UX-12 (UXD-7 dates; acronyms expanded on first use; Nov 2025 entry to
the Background Document if a stable URL exists).

## Changes
- `framework/src/components/policy.js`: exported `formatDate(dateIso)`; timeline dates render as
  `<time datetime="...">` with prose text: `2026-10-01` -> "1 Oct 2026", `2025-11` -> "Nov 2025",
  `2025` -> "2025"; an unusable value falls back to DTSC's `date_as_stated`.
- `framework/src/policy.md`: an intro paragraph expands DTSC, Candidate Chemicals list, Priority
  Product, Work Plan and OPC with `<abbr title>` at first use. OEHHA does not appear on the page.
- The page has no tables, so the YYYY-MM-DD table rule does not apply. Data files unchanged.
- Test: `tests/test_ux12_policy.py`.

## Evidence
- Local axe on /app/policy: one h1, no heading skips; only the Framework sidebar `list`/`region`.

## Not done
- The Nov 2025 entry (`dtsc-06`) still links to the DTSC research page: no stable Background
  Document URL is known (owner action H17, already in HUMAN_TASKS).
