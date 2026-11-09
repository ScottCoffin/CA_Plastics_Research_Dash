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


Older handoff entries: `.agent/archive/HANDOFF_history.md`.
