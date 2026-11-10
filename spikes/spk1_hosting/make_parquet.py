"""SPK-1: write synthetic Parquet files of roughly 5, 25 and 100 MB for hosting tests.

Run only inside the opt-in deploy job (or locally into scratch/). Files are never
committed. Columns mix compressible facets with incompressible payload so the
on-disk size tracks the target.
"""

from __future__ import annotations

import argparse
import os
import random
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

TARGETS_MB = {"p5": 5, "p25": 25, "p100": 100}
ROW_BYTES = 256  # incompressible payload per row
ROW_GROUP = 20_000


def make_table(target_mb: int, seed: int) -> pa.Table:
    rows = target_mb * 1024 * 1024 // (ROW_BYTES + 24)
    rng = random.Random(seed)
    return pa.table(
        {
            "work_id": pa.array([f"W{seed:02d}{i:09d}" for i in range(rows)]),
            "year": pa.array([1990 + rng.randrange(37) for _ in range(rows)], pa.int16()),
            "tag": pa.array([rng.randrange(8) for _ in range(rows)], pa.int8()),
            "payload": pa.array([os.urandom(ROW_BYTES) for _ in range(rows)], pa.binary()),
        }
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("out_dir", type=Path)
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    for seed, (name, mb) in enumerate(TARGETS_MB.items(), start=1):
        path = args.out_dir / f"{name}.parquet"
        pq.write_table(make_table(mb, seed), path, compression="zstd", row_group_size=ROW_GROUP)
        print(f"{path.name}: {path.stat().st_size} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
