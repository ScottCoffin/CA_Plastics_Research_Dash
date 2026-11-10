"""Build ``site/data/grants.json`` for the Funding tab (S8.10).

Reads the S8.6 merged grants table, the S2.2 institutions table, and the S8.6
dedupe map from local Parquet and CSV files. Runs offline and prints only counts.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from atlas.build.grants_export import build_from_paths

GRANTS_DIR = Path("data/interim/grants")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--merged", type=Path, default=GRANTS_DIR / "grants_merged.parquet")
    parser.add_argument("--dedupe-map", type=Path, default=GRANTS_DIR / "grants_dedupe_map.csv")
    parser.add_argument(
        "--institutions", type=Path, default=Path("data/processed/institutions.parquet")
    )
    parser.add_argument("--output", type=Path, default=Path("site/data/grants.json"))
    args = parser.parse_args(argv)

    summary = build_from_paths(
        merged=args.merged,
        institutions=args.institutions,
        dedupe_map=args.dedupe_map,
        output=args.output,
        generated_at=datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    )
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
