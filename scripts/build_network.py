"""Write site/data/california/network.json, the expert collaboration network (S9.4).

Usage: py -3.14 scripts/build_network.py [--cap 400] [--fractional] [--check] [--region <slug>]
--region <slug> writes site/data/<slug>/network.json for a reference region from that region's
export (GP-3); it reads the region's index.json and institutions.json and leaves the California
metadata counts alone.
--check rebuilds in memory and fails when the committed file is stale.
Needs networkx (a declared project dependency).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from atlas.build.export_site import refresh_metadata_counts  # noqa: E402
from atlas.build.network import (  # noqa: E402
    DEFAULT_NODE_CAP,
    REGION_WORKS_METHOD,
    build_network,
    network_counts,
    unscreened_region_index,
)
from atlas.regions.scope import region_data_dir  # noqa: E402

REGION_SLUG_PATTERN = re.compile(r"^[a-z][a-z-]*[a-z]$")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--region", default="", help="reference region slug (default: California)")
    parser.add_argument("--index", default=None)
    parser.add_argument("--institutions", default=None)
    parser.add_argument("--out", default=None)
    parser.add_argument("--cap", type=int, default=DEFAULT_NODE_CAP)
    parser.add_argument("--fractional", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    if args.region and not REGION_SLUG_PATTERN.match(args.region):
        parser.error(f"--region {args.region!r} is not a region slug")

    data_dir = ROOT / "site" / "data" / args.region if args.region else region_data_dir()
    index_path = Path(args.index) if args.index else data_dir / "index.json"
    institutions_path = (
        Path(args.institutions) if args.institutions else data_dir / "institutions.json"
    )
    out = Path(args.out) if args.out else data_dir / "network.json"

    index = json.loads(index_path.read_text(encoding="utf-8"))
    institutions = []
    if institutions_path.exists():
        payload = json.loads(institutions_path.read_text(encoding="utf-8"))
        institutions = (
            payload.get("institutions", payload) if isinstance(payload, dict) else payload
        )
    if args.region:
        index = unscreened_region_index(index)
    network = build_network(index, institutions, cap=args.cap, fractional=args.fractional)
    if args.region:
        network["method"]["works"] = REGION_WORKS_METHOD
    text = json.dumps(network, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n"
    if args.check:
        if not out.exists() or out.read_text(encoding="utf-8") != text:
            print(f"{out} is stale; rerun scripts/build_network.py", file=sys.stderr)
            return 1
        print(f"{out} is current")
        return 0
    out.write_bytes(text.encode("utf-8"))
    # The Overview's network counts live in build_metadata.json, which the export wrote before
    # this script ran; refresh them so they match the file just written (VD-13). Only California
    # has those counts, so a region run leaves its folder's metadata alone.
    if not args.region:
        metadata_path = out.parent / "build_metadata.json"
        if not refresh_metadata_counts(metadata_path, network_counts(network)):
            print(
                f"network counts not refreshed: {metadata_path} is missing or unreadable",
                file=sys.stderr,
            )
    print(
        f"network: {len(network['nodes'])} nodes, {len(network['edges'])} edges, "
        f"{network['communities']} communities, {out.stat().st_size} bytes -> {out}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
