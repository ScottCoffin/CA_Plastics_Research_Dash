# Handoff history (archived 2026-11-09, newest first)

Moved from `.agent/HANDOFF.md` per spec.md B2; HANDOFF.md keeps only the latest entry.

# Handoff - 2026-11-09 - S7.3 partial; S7.4 next

## Done
- Implemented local SF Bay / 5 Gyres workbook normalization in `src/atlas/ingest/monitoring/sfbay.py` and CLI `scripts/ingest_s7_3_sfbay.py`; synthetic fixture tests cover SampleID joins, canonical matrix/unit handling, polygon flags, duplicate conflicts, and deterministic output.
- Reviewed local private QC: 315 sample rows / 314 selected identities, 44,226 particle rows, 63 concentrations computed / 251 null, 15 invalid volume values on raw rows / 14 after unique selection, and one duplicate-conflict category. Full per-row diagnostics remain in ignored QC only; committed evidence contains aggregate counts/categories.
- Focused 10 tests and full offline 232-test suite, Ruff, and diff checks passed per local execution and independent tester review. `openpyxl` is declared as a dependency.
- Source rights remain unresolved: current package metadata reports ODC BY, resource-level license is empty, historical S7.2 recorded CC BY 4.0, and the official resource redirect returned HTTP 403. No source or normalized data is committed or published. S7.3 remains unchecked; see `docs/S7_3_VERIFICATION.md` and question S7.3-A.

## State of the repo
- S7.3 is partial and local-only. Do not treat public availability or package metadata as owner/legal approval to publish raw or normalized data. Other sources remain below Tier A or unresolved.
- The S7.3 workbook path/hash, ignored output contract, and command are recorded in `docs/S7_3_VERIFICATION.md`. Existing S7.2 offline checker remains `py -3.14 scripts/check_s7_2.py`; do not run `--smoke-urls` during offline verification.
- This handoff preserves the integrated L1-L9 history below; do not discard those changes while sealing this partial S7.3 checkpoint.

## Next task (suggested)
- S7.4: DataCite and full-text discovery with the 50-link precision spot check may proceed if current TODO dependencies allow. Do not start S7.5 from synthetic/fake monitoring outputs. Return to S7.3 only after the owner clarifies the conflicting license evidence and any remaining acceptance gaps.

---

# Integrated prior checkpoint notes

## L2 adoption annotations

### Done
- Added the owner-decision gate to the 8 L2 and 6 L3 SPK/AT roadmap entries; all 18 entries carry exactly one adoption level.
- Preserved IDs, titles, order, dependencies, acceptance text, base-task lines, and checkboxes.

### Files changed
- .agent/TODO.md, .agent/HANDOFF.md, and .agent/SESSION_LOG.md.

### Next
- Continue with the planned L3 conflict-register pass after this checkpoint is integrated.

### Open questions
- Section 4 mentions AT-8 data tables under L1 and the full AT-8 Maps task under L3; the roadmap classifies AT-8 as L3 per this pass's mapping.

## L1 add-on roadmap insertion

### Done
- Inserted SPK-1..SPK-7 and AT-1..AT-11 in the integrated sequence, then corrected dependencies against sections 5 and 8.
- SPK-7 has no direct section 9 row; its acceptance names `docs/api_notes/openalex_costs.md` and `config/budget.yml` as specified spike outputs.

### Files changed
- .agent/TODO.md, .agent/HANDOFF.md, and .agent/SESSION_LOG.md.

### Next
- Continue with the main agent's L2 adoption-annotation and consistency pass.

### Open questions
- Sections 5 and 8 state the AT-3 and AT-5 gates differently: section 5 lists AT-3 after S2.2 and AT-5 after SPK-3 plus AT-4; section 8 adds AT-2 to AT-3 but lists only SPK-3 for AT-5. The roadmap retains AT-2 for AT-3 and AT-4 for AT-5 as explicit gates; align the contract in the consistency pass.
- Section 9 has no direct cost-specific row for SPK-7, so its spike outputs are recorded explicitly.


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
## L3 conflict register

### Done
- Added 15 namespaced Add-on A1 conflict entries to .agent/DECISIONS.md. Conflict and rule text was copied verbatim from add-on section 6; every entry remains Open, and affected base-task mappings use section 2 only.
- L3 retry mapped C4 to S3.1, S11.2; C6 to S3.6; and C7 to S3.2-S3.6. All C1-C15 remain Open with concrete task IDs; copied conflict/rule text and prior ADR content are unchanged.

### Files changed
- .agent/DECISIONS.md, .agent/HANDOFF.md, and .agent/SESSION_LOG.md.

### Next
- Review the open register and decide whether any owner decisions are needed before L3 implementation.

### Open questions
- None; all 15 conflicts have concrete base-task mappings.


## L4 owner decision questions

### Done
- Added A1-D1..A1-D7 to the open questions table with question and default text copied verbatim from add-on section 11; each Owner answer is Pending and each status allows proceeding with its default while unanswered.

### Files changed
- .agent/QUESTIONS.md, .agent/HANDOFF.md, and .agent/SESSION_LOG.md.

### Next
- Integrate the L4 checkpoint, then continue with the next task in the add-on delegation plan.

### Open questions
- Owner answers remain pending for A1-D1..A1-D7; their stated defaults remain in use while unanswered.
## L5 query v2 transcription

### Done
- Added `config/query_v2.txt` as a byte-faithful copy of the Appendix A query expression (821 bytes) and `src/atlas/query_v2.py` with only `QUERY_VERSION = "plastic-v2"` plus its final newline.
- Appendix A has no code fences; the query expression is bounded by its closing parentheses before the following `Syntax [V]` explanatory text. No existing query implementation or active query configuration was changed, and no API/network call was made.

### Files changed
- `config/query_v2.txt`, `src/atlas/query_v2.py`, `.agent/HANDOFF.md`, and `.agent/SESSION_LOG.md`.

### Verification
- Query payload bytes match Appendix A exactly: 821 bytes, SHA-256 `3b6d707346262437f6d5eb2f14dae814fd6d24a890782002e350ec1e2c842de1`.
- Module is exactly the single constant assignment plus final newline: 29 bytes, SHA-256 `334c2798f81da267179fc00057ade956bb9cd9ae4c2135e03b2db84c9b760c3b`.
- Python compile and exact unique assignment check passed; `git diff --check` passed.

### Next
- Integrate this checkpoint and continue with the next assigned add-on task.

### Open questions
- None. The Appendix A query boundary was clear despite the absence of code fences.
## L6 Add-on A1 licence ledger

### Done
- Appended a licence ledger to `docs/REUSE.md` covering the named external tools and projects in add-on §§0 and 7. Unstated licences are marked `UNKNOWN - needs SPK-n`; no licence research or inference was done.
- Recorded the §0 copy/vendor limits, the GPL/AGPL copying prohibition, the bibliometrix GPL-3 separate-process rule, and the DESTINY concepts-only rule.

### Files changed
- `docs/REUSE.md`, `.agent/HANDOFF.md`, and `.agent/SESSION_LOG.md`.

### Verification
- The prior `docs/REUSE.md` content remains byte-for-byte intact before the appended section.
- `git diff --check` passed.
- No network/API call or experiment was made.

### Next
- Integrate the L6 checkpoint, then continue with the next assigned task.

### Open questions
- Unstated licences remain marked against their relevant SPK entries for later verification; none blocks the L6 documentation checkpoint.

## L7 Offline documentation links

### Done
- Added a dated base-spec change-log entry linking to `docs/add_on_spec.md` and a reciprocal base-spec link in the add-on introduction.
- Added a dependency-free Markdown local-target checker and an offline CI step before dependency installation.

### Files changed
- `spec.md`, `docs/add_on_spec.md`, `.github/workflows/ci.yml`, `scripts/check_doc_links.py`, `.agent/HANDOFF.md`, and `.agent/SESSION_LOG.md`.

### Verification
- The repository-wide Markdown scan passed; an isolated file with a missing local target failed as expected.
- Python compilation and `git diff --check` passed. The existing `make lint`, `make test`, and `make build` CI steps remain present.
- No network/API call was made.

### Next
- Integrate L7, then continue with the next assigned add-on task.

### Open questions
- None.

## L8 Add-on A1 scaffold

### Done
- Added the 11 empty acceptance stubs named by section 9 and zero-row placeholders for query, analytics, serving, and release fixtures.
- Added an offline standard-library scaffold checker for the exact stub set, empty stubs and placeholders, fixture row limits, and Parquet/release ignore behavior. Added the checker to CI without changing the existing link, lint, test, or build steps.

### Files changed
- `tests/acceptance/add_on_a1/`, `tests/fixtures/add_on_a1/`, `scripts/check_a1_scaffold.py`, `.gitignore`, `.github/workflows/ci.yml`, `.agent/HANDOFF.md`, and `.agent/SESSION_LOG.md`.

### Verification
- The 11 section 9 acceptance rows match the assigned stub filenames exactly. The scaffold checker passed; a temporary 201-row fixture and nonempty acceptance stub each failed as expected.
- Python 3.14 compilation and `git diff --check` passed. The existing Markdown-link, lint, test, and build CI steps remain present; no network/API call was made.

### Next
- Integrate L8, then continue with the next assigned task.

### Open questions
- None.

## L9 Final add-on integration

### Done
- Added readable blank-line spacing around the reciprocal base/add-on specification links and formatted the delegation log as one contiguous table, preserving all 10 L1-L8 outcome rows.
- Verified unique SPK/AT IDs, dependency resolution and TODO order, all 18 adoption flags, 14 L2/L3 owner-decision gates, C1-C15 open and mapped, A1-D1..D7 defaults active, and unchanged L5 query/constant hashes.
- Corrected Ruff import formatting in the two new offline checkers. No network calls or commit were made.
- Corrected the session-log table to one contiguous table; the retry row records the passing `git diff --check`.

### Files changed
- `spec.md`, `docs/add_on_spec.md`, `.agent/DELEGATION_LOG.md`, `scripts/check_doc_links.py`, `scripts/check_a1_scaffold.py`, `.agent/HANDOFF.md`, and `.agent/SESSION_LOG.md`.

### Verification
- `py -3.14 scripts/check_doc_links.py` passed (62 Markdown files).
- `py -3.14 scripts/check_a1_scaffold.py` passed.
- Full Ruff rule and format checks passed for all 169 Python files.
- The full test suite passed: 178 tests. `make build` and `git diff --check` passed.
- `git diff --check` passed.

### Next
- Add-on A1 integration is locally verified and ready for owner review. Resolve the noted AT-3/AT-5 gate wording before implementing those tasks.

### Open questions
- A1-D1..D7 remain unanswered, with recorded defaults active; none blocks this integration.
- Before AT-3/AT-5 implementation, confirm the section 5/section 8 gate mismatch. The roadmap currently keeps AT-2 as an AT-3 gate and AT-4 as an AT-5 gate; L9 preserved those dependencies.
- L9 resume completed: both checkers are Ruff-formatted, and `scripts/check_a1_scaffold.py` exempts only a real, non-symlink `__pycache__` directory while continuing to reject other entries and nonempty stubs.
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
