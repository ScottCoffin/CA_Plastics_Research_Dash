"""Acceptance checks for AT-3 institution analytics (offline).

Builds the hand-checked 10-work fixture, checks weights, fractional counts and rank intervals,
then re-checks the real build output when data/processed/analytics/ exists.
"""

from __future__ import annotations

import sys
import tempfile
from fractions import Fraction
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

import duckdb  # noqa: E402

from atlas.analytics.sql import build_analytics, write_fixture  # noqa: E402

REAL_DIR = REPO / "data" / "processed" / "analytics"
TOL = 1e-9

# Hand-checked expectations for the fixture under plastic_only=True (8 in-scope works).
EXPECTED = {
    # inst_id: (works_full, works_frac exact)
    "I_A": (5, Fraction(119, 60)),
    "I_B": (4, Fraction(59, 24)),
    "I_C": (3, Fraction(29, 24)),
    "I_X": (1, Fraction(1, 2)),
    "unaffiliated": (3, Fraction(37, 20)),
}
EXPECTED_RANK_FRAC = {"I_B": 1, "I_A": 2, "I_C": 3}
EXPECTED_RANK_FULL = {"I_A": 1, "I_B": 2, "I_C": 3}


def _fail(message: str) -> None:
    raise AssertionError(message)


def check_weights(weights_path: Path) -> int:
    con = duckdb.connect()
    rows = con.execute(
        f"""SELECT work_id, sum(w) AS total FROM read_parquet('{weights_path.as_posix()}')
            GROUP BY 1"""
    ).fetchall()
    bad = [(wid, total) for wid, total in rows if abs(total - 1.0) > TOL]
    if bad:
        _fail(f"{len(bad)} works with weights not summing to 1, e.g. {bad[:3]}")
    return len(rows)


def check_intervals(stability_path: Path) -> int:
    con = duckdb.connect()
    rows = con.execute(
        f"""SELECT inst_id, works_frac, frac_lo, frac_hi, rank_frac, rank_lo, rank_hi
            FROM read_parquet('{stability_path.as_posix()}')"""
    ).fetchall()
    for inst_id, frac, flo, fhi, rank, rlo, rhi in rows:
        if not (rlo <= rank <= rhi):
            _fail(f"{inst_id}: rank {rank} outside [{rlo}, {rhi}]")
        if not (flo - TOL <= frac <= fhi + TOL):
            _fail(f"{inst_id}: works_frac {frac} outside [{flo}, {fhi}]")
    return len(rows)


def check_fixture(tmp: Path) -> None:
    paths = write_fixture(tmp / "fixture")
    result = build_analytics(
        works_path=paths["works"],
        authorships_path=paths["authorships"],
        institutions_path=paths["institutions"],
        scope_path=paths["scope"],
        output_dir=tmp / "out",
        bootstrap_replicates=200,
    )
    out = result.output_dir
    n_weighted = check_weights(out / "work_inst_weights.parquet")
    if n_weighted != 8:
        _fail(f"expected 8 weighted works, got {n_weighted}")
    con = duckdb.connect()
    counts = con.execute(
        f"""SELECT inst_id, works_full, works_frac, rank_frac, rank_full, ca_flag
            FROM read_parquet('{(out / "inst_counts.parquet").as_posix()}')"""
    ).fetchall()
    by_id = {row[0]: row for row in counts}
    for inst_id, (full, frac) in EXPECTED.items():
        if inst_id not in by_id:
            _fail(f"missing institution {inst_id}")
        got_full, got_frac = by_id[inst_id][1], by_id[inst_id][2]
        if got_full != full or abs(got_frac - float(frac)) > TOL:
            _fail(f"{inst_id}: expected ({full}, {float(frac):.6f}), got ({got_full}, {got_frac})")
    for inst_id, rank in EXPECTED_RANK_FRAC.items():
        if by_id[inst_id][3] != rank:
            _fail(f"{inst_id}: rank_frac expected {rank}, got {by_id[inst_id][3]}")
    for inst_id, rank in EXPECTED_RANK_FULL.items():
        if by_id[inst_id][4] != rank:
            _fail(f"{inst_id}: rank_full expected {rank}, got {by_id[inst_id][4]}")
    if by_id["I_X"][5] or by_id["unaffiliated"][3] is not None:
        _fail("non-CA institutions must not be ranked")
    n_intervals = check_intervals(out / "inst_stability.parquet")
    if n_intervals != 3:
        _fail(f"expected 3 stability rows for the fixture, got {n_intervals}")


def check_real(output_dir: Path) -> str:
    n_weighted = check_weights(output_dir / "work_inst_weights.parquet")
    n_intervals = check_intervals(output_dir / "inst_stability.parquet")
    return f"real output: {n_weighted} works weight-checked, {n_intervals} intervals checked"


def main() -> int:
    try:
        with tempfile.TemporaryDirectory(prefix="at3_check_") as tmp:
            check_fixture(Path(tmp))
        print("fixture: PASS (weights, fractional counts, ranks, rank intervals)")
        if (REAL_DIR / "manifest.json").exists():
            print(f"{check_real(REAL_DIR)}: PASS")
        else:
            print("real output: not built (data/processed/analytics/manifest.json absent), skipped")
    except AssertionError as exc:
        print(f"FAIL: {exc}")
        return 1
    print("PASS: AT-3 analytics checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
