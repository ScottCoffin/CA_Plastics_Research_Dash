"""Write site/data/global/graphs/exports/: GEXF and GraphML copies of the graph files (BQ-V.6).

Usage: py -3.14 scripts/build_graph_exports.py [--check] [--graphs-dir DIR] [--network FILE]
       [--out-dir DIR]
Reads only committed files (offline): the desktop global graphs and their manifest, and the
California expert network. Without --check it writes the exports and manifest.json. --check
rebuilds in memory and fails (exit 1) when a committed export is missing, stale or unexpected;
it does not write anything.
Needs networkx (a declared project dependency).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from atlas.build.graph_exports import build_exports, check_exports, write_exports  # noqa: E402

DEFAULT_GRAPHS_DIR = ROOT / "site" / "data" / "global" / "graphs"
DEFAULT_NETWORK = ROOT / "site" / "data" / "california" / "network.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graphs-dir", default=str(DEFAULT_GRAPHS_DIR))
    parser.add_argument("--network", default=str(DEFAULT_NETWORK))
    parser.add_argument("--out-dir", default=None)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    graphs_dir = Path(args.graphs_dir)
    out_dir = Path(args.out_dir) if args.out_dir else graphs_dir / "exports"
    network = Path(args.network) if args.network else None
    if network is not None and not network.exists():
        print(f"missing network file: {network}", file=sys.stderr)
        return 1

    files = build_exports(graphs_dir, network)
    if args.check:
        stale = check_exports(out_dir, files)
        if stale:
            print(f"stale exports in {out_dir}: {', '.join(stale)}", file=sys.stderr)
            print("rerun scripts/build_graph_exports.py", file=sys.stderr)
            return 1
        print(f"{out_dir}: {len(files)} files current")
        return 0

    write_exports(out_dir, files)
    for name in sorted(files):
        print(f"{name}: {len(files[name])} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
