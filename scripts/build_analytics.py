"""Build DuckDB institution leaderboard analytics from the normalized tables.

Examples:
  py -3.14 scripts/build_analytics.py
  py -3.14 scripts/build_analytics.py --all-published --replicates 200
  py -3.14 scripts/build_analytics.py --synthetic 100000
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from atlas.analytics.sql import build_analytics  # noqa: E402

WORKS = Path("data/processed/normalized/works.parquet")
AUTHORSHIPS = Path("data/processed/normalized/authorships.parquet")
INSTITUTIONS = Path("data/processed/normalized/institutions.parquet")
SCOPE = Path("site/data/index.json")
OUTPUT_DIR = Path("data/processed/analytics")
N_INSTITUTIONS = 2000
N_CA_INSTITUTIONS = 300
N_TAGS = 10
N_TOPICS = 50


def write_synthetic(directory: Path, n_works: int, seed: int = 1) -> dict[str, Path]:
    """Write synthetic works, authorships, institutions and scope tables into directory."""
    rng = np.random.default_rng(seed)
    directory.mkdir(parents=True, exist_ok=True)
    work_ids = [f"W{i:07d}" for i in range(n_works)]
    years = rng.integers(1990, 2027, size=n_works)
    retracted = rng.random(n_works) < 0.02
    n_topics = rng.integers(0, 6, size=n_works)
    topics = [
        [f"T{t:03d}" for t in rng.choice(N_TOPICS, size=int(k), replace=False)] for k in n_topics
    ]
    n_tags = rng.integers(0, 4, size=n_works)
    tags = [[f"tag{t}" for t in rng.choice(N_TAGS, size=int(k), replace=False)] for k in n_tags]
    plastic_draw = rng.random(n_works)
    plastic = [True if d < 0.90 else (None if d < 0.95 else False) for d in plastic_draw]

    n_authors = rng.poisson(6, size=n_works)
    n_auth_total = int(n_authors.sum())
    author_pool = 200_000
    author_ids = [
        "" if rng.random() < 0.05 else f"A{a:06d}"
        for a in rng.integers(0, author_pool, size=n_auth_total)
    ]
    auth_work = np.repeat(np.arange(n_works), n_authors)
    n_insts = rng.integers(0, 3, size=n_auth_total)
    inst_draw = rng.integers(0, N_INSTITUTIONS, size=int(n_insts.sum()))
    inst_lists: list[list[str]] = []
    cursor = 0
    for k in n_insts:
        inst_lists.append([f"I{x:04d}" for x in inst_draw[cursor : cursor + int(k)]])
        cursor += int(k)

    works_table = pa.table(
        {
            "work_id": pa.array(work_ids, pa.string()),
            "year": pa.array(years.astype(np.int64), pa.int64()),
            "is_retracted": pa.array(retracted.tolist(), pa.bool_()),
            "openalex_topics": pa.array(topics, pa.list_(pa.string())),
        }
    )
    works_path = directory / "works.parquet"
    pq.write_table(works_table, works_path)

    auth_path = directory / "authorships.parquet"
    pq.write_table(
        pa.table(
            {
                "work_id": pa.array([work_ids[i] for i in auth_work], pa.string()),
                "author_id": pa.array(author_ids, pa.string()),
                "position": pa.array(["additional"] * n_auth_total, pa.string()),
                "institution_ids": pa.array(inst_lists, pa.list_(pa.string())),
            }
        ),
        auth_path,
    )

    inst_path = directory / "institutions.parquet"
    inst_ids = [f"I{x:04d}" for x in range(N_INSTITUTIONS)]
    pq.write_table(
        pa.table(
            {
                "inst_id": pa.array(inst_ids, pa.string()),
                "name": pa.array([f"Institution {x}" for x in inst_ids], pa.string()),
                "atlas_type": pa.array(["university"] * N_INSTITUTIONS, pa.string()),
                "parent_system": pa.array([None] * N_INSTITUTIONS, pa.string()),
                "ca_flag": pa.array(
                    [x < N_CA_INSTITUTIONS for x in range(N_INSTITUTIONS)], pa.bool_()
                ),
            }
        ),
        inst_path,
    )

    scope_path = directory / "scope.json"
    scope_path.write_text(
        json.dumps(
            {
                "works": [
                    {"work_id": w, "plastic_related": p, "domain_tags": t}
                    for w, p, t in zip(work_ids, plastic, tags, strict=True)
                ]
            }
        ),
        encoding="utf-8",
    )
    return {
        "works": works_path,
        "authorships": auth_path,
        "institutions": inst_path,
        "scope": scope_path,
    }


def print_summary(result) -> None:
    manifest = result.manifest
    exc = manifest["exclusions"]
    print(f"output: {result.output_dir}")
    print(
        f"n_works={manifest['n_works']} total_in_table={exc['total_works_in_table']} "
        f"excluded: retracted={exc['retracted']} not_in_scope={exc['not_in_scope']} "
        f"not_plastic_related={exc['not_plastic_related']}"
    )
    print(f"rows: {result.row_counts}")
    print(f"runtime_s={manifest['runtime_s']}")


def print_top(output_dir: Path, limit: int = 5) -> None:
    import duckdb

    con = duckdb.connect()
    path = (output_dir / "inst_stability.parquet").as_posix()
    rows = con.execute(
        f"""SELECT s.inst_id, i.name, s.works_frac, s.frac_lo, s.frac_hi, s.rank_frac,
                   s.not_distinguishable
            FROM read_parquet('{path}') s
            LEFT JOIN read_parquet('{(output_dir / "inst_counts.parquet").as_posix()}') i
              USING (inst_id)
            ORDER BY s.rank_frac LIMIT {int(limit)}"""
    ).fetchall()
    print("top CA institutions by works_frac (95% bootstrap interval):")
    for inst_id, name, frac, lo, hi, rank, nd in rows:
        print(
            f"  {rank}. {name or inst_id} [{inst_id}] {frac:.2f} ({lo:.2f}-{hi:.2f})"
            f"{' not_distinguishable' if nd else ''}"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--works", type=Path, default=WORKS)
    parser.add_argument("--authorships", type=Path, default=AUTHORSHIPS)
    parser.add_argument("--institutions", type=Path, default=INSTITUTIONS)
    parser.add_argument("--scope", type=Path, default=SCOPE)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument(
        "--all-published",
        action="store_true",
        help="skip the plastic_related filter (plastic_only=False)",
    )
    parser.add_argument("--replicates", type=int, default=1000)
    parser.add_argument("--top-n", type=int, default=200)
    parser.add_argument("--seed", type=int, default=20261111)
    parser.add_argument(
        "--synthetic",
        type=int,
        metavar="N",
        help="generate N synthetic works in a temp dir and time the build there",
    )
    args = parser.parse_args(argv)

    if args.synthetic is not None:
        with tempfile.TemporaryDirectory(prefix="atlas_analytics_") as tmp:
            tmp_dir = Path(tmp)
            t0 = time.perf_counter()
            paths = write_synthetic(tmp_dir / "in", args.synthetic)
            print(f"generated {args.synthetic} synthetic works in {time.perf_counter() - t0:.1f}s")
            t1 = time.perf_counter()
            result = build_analytics(
                works_path=paths["works"],
                authorships_path=paths["authorships"],
                institutions_path=paths["institutions"],
                scope_path=paths["scope"],
                output_dir=tmp_dir / "analytics",
                plastic_only=not args.all_published,
                bootstrap_replicates=args.replicates,
                top_n=args.top_n,
                seed=args.seed,
            )
            wall = time.perf_counter() - t1
            print_summary(result)
            print(f"synthetic build wall time: {wall:.1f}s (B={args.replicates})")
        return 0

    for path in (args.works, args.authorships, args.institutions):
        if not path.exists():
            print(f"missing input: {path}", file=sys.stderr)
            return 1
    scope = args.scope if args.scope and args.scope.exists() else None
    if scope is None:
        print(f"scope file not found ({args.scope}); plastic filter not applied", file=sys.stderr)
    result = build_analytics(
        works_path=args.works,
        authorships_path=args.authorships,
        institutions_path=args.institutions,
        scope_path=scope,
        output_dir=args.output_dir,
        plastic_only=not args.all_published,
        bootstrap_replicates=args.replicates,
        top_n=args.top_n,
        seed=args.seed,
    )
    print_summary(result)
    print_top(result.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
