"""Write site/data/network.json, the expert collaboration network (S9.4).

Usage: py -3.14 scripts/build_network.py [--cap 400] [--fractional] [--check]
--check rebuilds in memory and fails when the committed file is stale.
Needs networkx (not yet a declared dependency; QUESTIONS S9.4-DEP).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from atlas.build.network import DEFAULT_NODE_CAP, build_network  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", default=str(ROOT / "site" / "data" / "index.json"))
    parser.add_argument("--institutions", default=str(ROOT / "site" / "data" / "institutions.json"))
    parser.add_argument("--out", default=str(ROOT / "site" / "data" / "network.json"))
    parser.add_argument("--cap", type=int, default=DEFAULT_NODE_CAP)
    parser.add_argument("--fractional", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)

    index = json.loads(Path(args.index).read_text(encoding="utf-8"))
    institutions_path = Path(args.institutions)
    institutions = []
    if institutions_path.exists():
        payload = json.loads(institutions_path.read_text(encoding="utf-8"))
        institutions = (
            payload.get("institutions", payload) if isinstance(payload, dict) else payload
        )
    network = build_network(index, institutions, cap=args.cap, fractional=args.fractional)
    text = json.dumps(network, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n"
    out = Path(args.out)
    if args.check:
        if not out.exists() or out.read_text(encoding="utf-8") != text:
            print(f"{out} is stale; rerun scripts/build_network.py", file=sys.stderr)
            return 1
        print(f"{out} is current")
        return 0
    out.write_bytes(text.encode("utf-8"))
    print(
        f"network: {len(network['nodes'])} nodes, {len(network['edges'])} edges, "
        f"{network['communities']} communities, {out.stat().st_size} bytes -> {out}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
