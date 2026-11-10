# Handoff - 2026-11-09 - Add-on A2 integration; defaults accepted; EM-1 / SPK spikes next

## Add-on A2 (`docs/add_on_spec_2.md`) integrated into the plan

### Done
- `.agent/TODO.md`: EM-1..EM-18 scheduled by dependency (EM-1, EM-3 in S4; EM-2, EM-4, EM-15 in S5; the rest in the new "EM Evidence Map and Related Resources (Add-on A2)" section after S10). Each line carries the A2 level, dependencies, DoD, mapped EAT tests and size. S11.2 is marked superseded by EM-8; S7.5 notes A2-C4.
- `.agent/DECISIONS.md`: ADR-A2-OWNER (owner determinations from the A2 preamble) and the A2-C1..C15 register (verbatim resolutions, task mapping, all Open).
- `.agent/QUESTIONS.md`: A2-D1..D11 with spec defaults, plus A2-INT-1 (XLSX vs CSV ledger), A2-INT-2 (EM-2 "S5 geo" = S5.4; layer fetch may proceed as partial work), and A2-INT-3 (E0–E3 adopted).
- `spec.md`: change-log entry, A3.3a tab note, S4/S5 extension notes, S7.5/S11.2 row notes, and a Part G pointer. `docs/add_on_spec_2.md` has a reciprocal base-spec link.
- `docs/REUSE.md`: A2 source and licence ledger (25 rows; unstated terms recorded as `unknown`).
- Scaffold: `tests/acceptance/add_on_a2/` (12 EAT stubs, skipped), `tests/fixtures/add_on_a2/` placeholders, `scripts/check_a2_scaffold.py` (also validates EM/A2-D/A2-INT/A2-C IDs and EM dependency order in TODO), and a CI step.
- `CLAUDE.md`, `AGENTS.md`, `MEMORY.md` updated with A2 pointers and the `[E]` → lead/`sonnet-reviewer` mapping.

### State and next
- Owner accepted all pending defaults on 2026-11-09 (ADR-DEFAULTS-2026-11-09): SPK-1..SPK-4 are now eligible, and L3 stays gated. The clock-dependent budget test was fixed separately in `4b2154f`.
- Next eligible A2 task: EM-1 (depends on S4.1, done). Its keyword rules are `[E]`. EM-2 has a partial pre-S5.4 path (A2-INT-2). EM-5/EM-6 are blocked by owner-gated AT-4/AT-10.
- EAT-8's "no Minderoo anywhere" grep must exclude the governance docs that record the exclusion (A2 spec, `.agent/*`, `docs/REUSE.md`).
- Owner WIP in `src/atlas/source_watchlist.py` and `tests/test_source_watch_s7_6.py` was left untouched.

### Verification commands
- `py -3.14 scripts/check_doc_links.py`; `py -3.14 scripts/check_a1_scaffold.py`; `py -3.14 scripts/check_a2_scaffold.py`
- `/c/rtools45/usr/bin/make.exe PYTHON="py -3.14" APPDATA="$APPDATA" USERPROFILE="$USERPROFILE" lint test build` (all pass after `4b2154f`)
- `git diff --check`

Older handoff entries: `.agent/archive/HANDOFF_history.md`.
