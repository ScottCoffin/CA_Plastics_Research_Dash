"""Write site/data/california/search_index.json, the header search index (VD-19).

Usage: py -3.14 scripts/build_search_index.py [--check]
--check rebuilds in memory and fails when the committed file is stale.
Reads site/data/california (index, institutions, grants, linkouts), site/assets/topics.js,
framework/src/components/shared/labels.js, framework/observablehq.config.js and
framework/src/glossary.md. Stdlib only, so the daily ingest can run it on any Python 3.11.
"""

from __future__ import annotations

import argparse
import gzip
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from atlas.build.search_index import build_search_index, load_sources, serialize  # noqa: E402
from atlas.regions.registry import load_registry  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--region", default="california", help="registry region slug")
    parser.add_argument(
        "--out", help="output file (defaults to site/data/<region>/search_index.json)"
    )
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)

    root = Path(args.root)
    try:
        region = load_registry().get(args.region)
    except KeyError as error:
        parser.error(str(error.args[0]))
    index = build_search_index(**load_sources(root, args.region))
    text = serialize(index)
    out = Path(args.out) if args.out else root / region.site_data_dir / "search_index.json"
    if args.check:
        if not out.exists() or out.read_text(encoding="utf-8") != text:
            print(f"{out} is stale; rerun scripts/build_search_index.py", file=sys.stderr)
            return 1
        print(f"{out} is current")
        return 0
    out.write_bytes(text.encode("utf-8"))
    raw = len(text.encode("utf-8"))
    gzipped = len(gzip.compress(text.encode("utf-8"), compresslevel=9))
    counts = {
        name: sum(1 for item in index["items"] if item[0] == number)
        for number, name in enumerate(index["types"])
    }
    summary = ", ".join(f"{name} {count}" for name, count in counts.items())
    print(
        f"search index: {len(index['items'])} items ({summary}), "
        f"{raw} bytes raw, {gzipped} gzip -> {out}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
