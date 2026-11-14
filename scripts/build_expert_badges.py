"""Build site/data/expert_badges.json (S9.3 funding and data-stewardship badges).

Usage: py -3.14 scripts/build_expert_badges.py
Reads site/data/index.json and grants.json plus the committed link tables; offline.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from atlas.build.expert_badges import write_badges  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--index", default=str(ROOT / "site" / "data" / "index.json"))
    parser.add_argument("--grants", default=str(ROOT / "site" / "data" / "grants.json"))
    parser.add_argument(
        "--links", default=str(ROOT / "data" / "processed" / "work_grant_links.parquet")
    )
    parser.add_argument(
        "--datacite", default=str(ROOT / "data" / "processed" / "expert_datacite_outputs.parquet")
    )
    parser.add_argument("--out", default=str(ROOT / "site" / "data" / "expert_badges.json"))
    args = parser.parse_args(argv)
    counts = write_badges(
        index_path=Path(args.index),
        grants_path=Path(args.grants),
        out_path=Path(args.out),
        work_grant_links_path=Path(args.links),
        datacite_path=Path(args.datacite),
    )
    print(
        f"expert badges: {counts['experts']} experts "
        f"({counts['with_grants']} with grants, {counts['with_datasets']} with datasets)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
