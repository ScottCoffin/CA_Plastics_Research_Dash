"""Write site/data/global/graphs/: the global institutions graph set (BQ-V.1 slice 1).

Usage: py -3.14 scripts/build_global_graphs.py [--check] [--raw-dir DIR] [--out-dir DIR]
--check validates the committed files (schema, caps, sizes, manifest). When the ignored raw
store is present it also rebuilds in memory and fails if a committed file is stale; when the raw
store is absent the staleness check is skipped (SKIP) and only the validation runs.
Needs networkx (a declared project dependency). Runtime is dominated by ForceAtlas2 per community.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from atlas.build.global_graphs import FILE_NAMES, build_graphs, check_outputs  # noqa: E402
from atlas.ingest.global_partition import NoRawStoreError  # noqa: E402

DEFAULT_RAW_DIR = ROOT / "data" / "raw" / "openalex_global"
DEFAULT_OUT_DIR = ROOT / "site" / "data" / "global" / "graphs"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", default=str(DEFAULT_RAW_DIR))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    out_dir = Path(args.out_dir)

    if args.check:
        problems = check_outputs(out_dir)
        for problem in problems:
            print(f"FAIL: {problem}", file=sys.stderr)
        if problems:
            return 1
        print(f"{out_dir}: schema and caps OK")
        try:
            build = build_graphs(args.raw_dir)
        except NoRawStoreError:
            print("SKIP staleness: raw store absent (data/raw/openalex_global/pages)")
            return 0
        stale = [
            name
            for key, name in FILE_NAMES.items()
            if not (out_dir / name).exists() or (out_dir / name).read_bytes() != build.files[key]
        ]
        if stale:
            print(
                f"stale: {', '.join(stale)}; rerun scripts/build_global_graphs.py", file=sys.stderr
            )
            return 1
        print(f"{out_dir}: current with the raw store")
        return 0

    try:
        build = build_graphs(args.raw_dir)
    except NoRawStoreError as error:
        print(f"no raw store: {error}", file=sys.stderr)
        return 1
    out_dir.mkdir(parents=True, exist_ok=True)
    for key, name in FILE_NAMES.items():
        (out_dir / name).write_bytes(build.files[key])
    for key, name in FILE_NAMES.items():
        print(f"{name}: {len(build.files[key])} bytes")
    graphs = build.manifest["graphs"]
    for graph_key, entry in graphs.items():
        print(f"{graph_key}: {entry['nodes']} nodes, {entry['edges']} edges")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
