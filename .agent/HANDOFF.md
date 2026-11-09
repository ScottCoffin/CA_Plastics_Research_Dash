# Handoff - 2026-11-09 - S7.5 partial; S7.6 next

## S7.5 monitoring table, sample map, and gaps view

### Done
- Added the public monitoring catalogue and Monitoring tab registry, filters, schematic clustered sample map, and matrix/region/year sample coverage view. Source/provenance links and citations are displayed; public unknowns remain unknown.
- Public export contains 24 source records (15 verified seeds and 9 discovery records) and zero sample observations. Local private review used 314 observations; the acceptance browser run rendered 314 samples / 277 valid coordinate pairs, including 37 valid-coordinate unknown-matrix rows. The Unknown matrix filter returned 240 rows / 206 valid coordinates; zero particle counts and malformed-date unknown behavior are retained in runtime regressions.
- Executor recorded six focused tests, runtime CI wrapper, full 243-test suite, Ruff, and diff checks as passing. Tester accepted focused/runtime checks and browser results (desktop 314 ms / mobile 277 ms; 37 unknown-matrix rows with valid coordinates). See `docs/S7_5_VERIFICATION.md`.
- Public JSON is zero-observation and private preview output is constrained outside `site/`, including path aliases. The verification record discloses the initial transient private write and that whether the already-bound local server read it was not verified; the public payload was restored immediately. No external read or absence of external read is claimed.

### State and next
- S7.5 remains unchecked/partial because rights-cleared observations are unavailable; public sample map and measurement-based coverage acceptance remain unmet. Do not treat the ignored local preview as public data or statewide coverage.
- S7.6 is the next independent eligible task: implement the future-source watch list and weekly check updates to `docs/SOURCES.md`. S7.3 rights remain unresolved. Node.js 20+ is required by the focused pytest runtime wrapper; record environment pinning for S10 rather than expanding this checkpoint.

### Verification commands
- `py -3.14 scripts/build_monitoring_export.py`
- `py -3.14 scripts/check_s7_5.py --check-private-preview`
- `py -3.14 -m pytest tests/test_monitoring_s7_5.py tests/test_monitoring_view_runtime.py -q`
- `py -3.14 -m ruff check ...` and `py -3.14 -m ruff format --check ...` on task-owned modules
- `git diff --check`

---

# Handoff - 2026-11-09 - S7.3 partial; S7.4 next

## Done
- Implemented local SF Bay / 5 Gyres workbook normalization in `src/atlas/ingest/monitoring/sfbay.py` and CLI `scripts/ingest_s7_3_sfbay.py`; synthetic fixture tests cover SampleID joins, canonical matrix/unit handling, polygon flags, duplicate conflicts, and deterministic output.
- Reviewed local private QC: 315 sample rows / 314 selected identities, 44,226 particle rows, 63 concentrations computed / 251 null, 15 invalid volume values on raw rows / 14 after unique selection, and one duplicate-conflict category. Full per-row diagnostics remain in ignored QC only; committed evidence contains aggregate counts/categories.
- Focused 10 tests and full offline 232-test suite, Ruff, and diff checks passed per local execution and independent tester review. `openpyxl` is declared as a dependency.
- Source rights remain unresolved: current package metadata reports ODC BY, resource-level license is empty, historical S7.2 recorded CC BY 4.0, and the official resource redirect returned HTTP 403. No source or normalized data is committed or published. S7.3 remains unchecked; see `docs/S7_3_VERIFICATION.md` and question S7.3-A.

## State of the repo
- S7.3 is partial and local-only. Do not treat public availability or package metadata as owner/legal approval to publish raw or normalized data. Other sources remain below Tier A or unresolved.
- The S7.3 workbook path/hash, ignored output contract, and command are recorded in `docs/S7_3_VERIFICATION.md`. Existing S7.2 offline checker remains `py -3.14 scripts/check_s7_2.py`; do not run `--smoke-urls` during offline verification.

## Next task (suggested)
- S7.4: DataCite and full-text discovery with the 50-link precision spot check may proceed if current TODO dependencies allow. Do not start S7.5 from synthetic/fake monitoring outputs. Return to S7.3 only after the owner clarifies the conflicting license evidence and any remaining acceptance gaps.

---

## Prior handoff context

# Handoff - 2026-11-07 - S6.3 complete; S7.1 next

## Done
- Implemented GROBID TEI extraction and bounded pdfminer fallback/cache in `src/atlas/fulltext/grobid.py`, with focused acceptance and 30-PDF spot-check scripts.
- S6.3 spot check processed 30 selected Frontiers CC BY PDFs with per-copy license evidence and PDF hashes. Text review matched all 16 extracted target headings and evidence prefixes against source PDF text. This is a convenience sample; visual PDF layout was not assessed and it is not candidate-corpus performance.
- GROBID technical failure rate was 0/30. It returned no target sections for 21/30; pdfminer recovered targets for 6 of those, leaving 15 final no-target records (13 reviews, 2 editorials). Two PDFs were rejected before caching because their own copy lacked a CC BY statement.
- Focused acceptance, full 163-test suite, Ruff check/format, and `git diff --check` pass.

## State of the repo
- S6.2 is complete. S6.1 remains unchecked pending candidate-corpus XML/PDF/none coverage; its synthetic fixture is not corpus evidence.
- S4.2 representative split/leak evidence and S3.6 representative performance remain open. S4.1 guide approval is recorded.
- Preserve the unrelated README URL edit. The S6.2 `docs/REUSE.md` entry is part of this checkpoint.

## Next task
- S6.4 requires an abstract-vs-full-text evaluation delta and real gold subset; do not fabricate corpus metrics. Continue with independent S7.1 registry schema and at least 15 verified seed entries. First read its exact contract and preserve S6.3's sample-scope caveats.

## Gotchas
- Do not claim corpus-wide section recall from the ten selected articles.
- Check each selected-copy license before processing or caching full text; cache only in the ignored raw-data directory.
- Keep test data final-only for evaluation.

# Handoff - 2026-11-09 - SPK-7 complete; AT-1 next

## SPK-7 measured cost and budget checkpoint

### Done
- Closed SPK-7/G-COST against `79301e720d2e375c85b7f70774dc13856a274f50`; owner authorized free-only account use, and the 100-call benchmark completed successfully.
- The response metadata total is USD 0.026; the provider's post-run allowance decrement implies USD 0.028. The discrepancy remains explicit and the S2.1 budget guard accounts conservatively. Full and conservative totals are in `docs/api_notes/openalex_costs.md`.
- Final acceptance recorded 199 tests, Ruff, and a network-forbidden rerun. HTTP 500 without credit/accounting metadata stops before retry or output advancement; known-credit HTTP 500 bounded retry remains accepted.

### State and next
- AT-1 is still under review: query-v2 rendering/cache invalidation and precision/recall audit are unfinished. The independent candidate-promotion decision and S3.6 representative live-data performance evidence remain open.
- Continue with AT-1 after resolving its recorded review findings; do not activate/promote the candidate or claim S3.6 complete from the SPK-7 measurement.

### Files changed for this closure
- `.agent/TODO.md`, `.agent/QUESTIONS.md`, `.agent/MEMORY.md`, `.agent/SESSION_LOG.md`, `.agent/HANDOFF.md`, and `agent_docs/project_progress.md`.

## AT-1 partial checkpoint - 2026-11-09

### Done
- Kept the production ranking/cache on legacy `search=plastic`; added explicit audit-mode v2 counts with query/version/cache identity checks and alias rejection.
- Added a bounded, resumable sample runner with validated free-only status preflight and durable partial outputs. The accepted 20-stratum sample has 405 rows / 354 unique works, 51 repeated-ID rows, eight short strata and a 95-row gap; all four baseline counts are within 10%.
- Owner decision: retain the available 405 rows with blank labels, no supplements, no query or institution changes, and the 500-work gate still open. No candidate promotion.
- Network-blocked full suite: 222 passed; Ruff and format checks passed.

### Next
- S7.1 is the next independent unchecked roadmap task. AT-1 remains unchecked pending human labels, precision/noise-term review, repeat audit, and promotion decision.

## S7.1 monitoring registry reconciliation - 2026-11-09

### Done
- Reconciled the existing S7.1 implementation at `46e58e7`; no source work was repeated. The registry contains 24 records and 15 distinct eligible seed identities, with provenance, tier, URL, and `last_checked` evidence recorded in `docs/S7_1_VERIFICATION.md`.
- Registry source files are unchanged from the accepted implementation commit. Acceptance and verification are recorded there; this checkpoint closes the roadmap record only.

### Next
- S7.2 is the next dependency-satisfied task: source smoke tests and tier decisions, documenting access method, format, license, update frequency, and field maps. The earlier SPK-1..4 paths are gated on owner decisions; AT-2 remains blocked by incomplete AT-1.
