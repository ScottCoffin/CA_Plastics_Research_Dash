"""Export the curated DTSC timeline to site/data/dtsc_timeline.json (Add-on A2 §7 Part B, EM-18).

Every entry field from config/dtsc_timeline.yml is written unchanged (dates are never reformatted).
--check exits 1 when the committed file differs from a fresh build.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from atlas import dtsc_timeline  # noqa: E402

SCHEMA_VERSION = "em18.v1"
SOURCE = "config/dtsc_timeline.yml"
OUTPUT_PATH = ROOT / "site" / "data" / "dtsc_timeline.json"


def build_payload(data: dict[str, Any] | None = None) -> dict[str, Any]:
    timeline = dtsc_timeline.load_timeline() if data is None else data
    return {
        "schema_version": SCHEMA_VERSION,
        "source": SOURCE,
        "caveat": timeline["caveat"],
        "caveat_detail": timeline["caveat_detail"],
        "order": timeline["order"],
        "entries": list(timeline["entries"]),
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
