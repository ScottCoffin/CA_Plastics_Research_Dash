"""Export the link-out registry to site/data/linkouts.json (Add-on A2 §8, EM-5a).

Only the public display fields from atlas.linkouts.strip_entries are written. --check
exits 1 when the committed file differs from a fresh build.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from atlas import linkouts

SCHEMA_VERSION = "em5.v1"
SOURCE = "config/linkouts.yml"
OUTPUT_PATH = linkouts.ROOT / "site" / "data" / "linkouts.json"


def build_payload(registry: dict[str, Any] | None = None) -> dict[str, Any]:
    data = linkouts.load_registry() if registry is None else registry
    return {
        "schema_version": SCHEMA_VERSION,
        "source": SOURCE,
        "entries": linkouts.strip_entries(data),
    }


def render(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=1, ensure_ascii=False, sort_keys=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="fail if the committed JSON is stale")
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        text = render(build_payload())
    except (OSError, ValueError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    if args.check:
        try:
            committed = args.output.read_bytes()
        except OSError:
            print(f"FAIL: {args.output} is missing; run without --check", file=sys.stderr)
            return 1
        if committed != text.encode("utf-8"):
            print(f"FAIL: {args.output} is stale; rerun without --check", file=sys.stderr)
            return 1
        print(f"OK: {args.output} is current")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
