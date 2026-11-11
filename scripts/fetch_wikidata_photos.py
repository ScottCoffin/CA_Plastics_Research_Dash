"""Fetch Wikidata and Commons photo metadata for Atlas experts (metadata only).

Usage:
    py -3.14 scripts/fetch_wikidata_photos.py [--limit N] [--offline]

``--limit N`` queries only the first N distinct ORCIDs in index order.
``--offline`` rebuilds the Parquet from ``data/raw/wikidata/`` without network.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from atlas.ingest.wikidata_photos import (  # noqa: E402
    build_expert_rows,
    summarize,
    write_expert_photos,
)

INDEX_PATH = ROOT / "site" / "data" / "index.json"
CACHE_DIR = ROOT / "data" / "raw" / "wikidata"
OUTPUT_PATH = ROOT / "data" / "processed" / "expert_photos.parquet"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--limit", type=int, default=None, help="max ORCIDs to query")
    parser.add_argument("--offline", action="store_true", help="rebuild from cached responses only")
    args = parser.parse_args(argv)
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be positive")

    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    rows = build_expert_rows(index["authors"], CACHE_DIR, offline=args.offline, limit=args.limit)
    write_expert_photos(rows, OUTPUT_PATH)
    print(json.dumps(summarize(rows), ensure_ascii=False, indent=2))
    print(f"wrote {len(rows)} rows to {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
