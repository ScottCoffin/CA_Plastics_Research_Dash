# AT-3 verification: SQL analytics

Date: 2026-11-11. Engine: DuckDB 2.0.0 (ADR-DUCKDB-2-2026-11-11). Module:
`atlas.analytics` (`src/atlas/analytics/sql.py`). Build: `py -3.14 scripts/build_analytics.py`.
Acceptance: `py -3.14 scripts/check_at3.py`. Method text: `docs/METHODS.md`
("Institution counts and stability (AT-3)").

## What it does

The module reads the normalized tables (`works`, `authorships`, `institutions`) and
scopes them to the published work set (`site/data/index.json`, after curation). By
default it keeps plastic-related works only and excludes retracted works
(`works.is_retracted`, new in normalize). It writes zstd Parquet to
`data/processed/analytics/` (gitignored):

| Table | Content |
|---|---|
| `work_inst_weights` | Appendix B fractional weights per (work, institution), with an `unaffiliated` bucket; audit trail |
| `inst_counts` | `works_full`, `works_frac`, and competition ranks over California institutions only |
| `inst_stability` | Top 200 CA institutions: 95% bootstrap intervals for `works_frac` and rank, `widened`, `not_distinguishable` |
| `year_tag` | Works per year x domain tag (`_all` = all in-scope works) |
| `tag_cooccurrence`, `topic_cooccurrence` | Works per tag pair and per OpenAlex topic pair (topic pairs with at least 2 works) |
| `inst_cooccurrence` | Works shared by pairs of CA institutions (input for S9.4/AT-8) |
| `manifest.json` | Inputs, exclusions, seed, replicates, rows per table, runtime, DuckDB version |

## DoD checks

| Check | Result |
|---|---|
| Hand-checked 10-work fixture: weights sum to 1 (within 1e-9), exact `works_frac`/`works_full`, Leiden 2-of-5 → 0.4, multi-affiliation halves, no-authorship work → unaffiliated 1.0, retracted and non-plastic exclusions | `tests/test_analytics_at3.py`, 18 passed |
| Rank intervals contain the point rank | Fixture and real output: PASS (`check_at3.py`) |
| Same seed → identical stability output | Test passes (connection uses `SET threads = 1`, because parallel float sums differed in the last bit) |
| Under 5 min at 100k works | Synthetic 100,000 works, B = 1,000: 4.8 s build (7.9 s with generation) |
| Full gate | links, A1/A2 scaffolds, lint, 1,046 tests passed (9 skipped), build, `git diff --check` |

## Real-data run (2026-11-11)

Of 1,896 normalized works, 122 are not published, 344 are not plastic-related, and 1 is
retracted, which leaves **1,429 works**. That gives 1,836 institution rows, 161 of them
ranked CA institutions. The `unaffiliated` bucket holds 225.8 fractional works (449 works
have at least one author without an institution). Runtime 0.5 s.

| Rank | Institution | works_full | works_frac (95% CI) | Rank interval |
|---:|---|---:|---|---|
| 1 | UC Davis | 118 | 44.1 (33.9-55.2) | 1-5 |
| 2 | Stanford University | 147 | 41.4 (32.2-50.1) | 1-5 |
| 3 | UC Berkeley | 111 | 37.7 (28.6-47.2) | 1-6 |
| 4 | UC Riverside | 94 | 36.1 (27.6-46.0) | 1-6 |
| 5 | UC Santa Barbara | 75 | 31.2 (22.4-40.7) | 2-8 |
| 6 | UCLA | 61 | 30.2 (22.1-39.4) | 3-8 |
| 7 | USC | 42 | 24.8 (16.5-33.7) | 4-11 |
| 8 | UC San Diego | 79 | 21.0 (14.4-27.4) | 6-12 |
| 9 | San Diego State University | 40 | 20.5 (13.7-28.4) | 6-12 |
| 10 | Cal Poly | 28 | 17.4 (10.1-25.2) | 7-15 |

**Finding:** all 161 ranked CA institutions are "not distinguishable" from at least
one neighbour (20 intervals widened to include the point). At 1,429 works, single-rank
ordering is not meaningful, so a published leaderboard should show tiers or intervals
rather than a strict 1..N rank. Full and fractional orderings also differ: Stanford
leads on `works_full` and UC Davis on `works_frac`.

## Not done here

- No site integration. AT-4 decides which tables go public (no abstracts are present).
- Author merges (`curation/author_merges.csv`) are not applied before counting distinct
  authors. This matters only when two merged IDs share one work.
- `ingest_works.yml` does not run the build yet; AT-4 wires it into the export.
