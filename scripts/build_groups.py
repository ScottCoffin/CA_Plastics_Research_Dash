#!/usr/bin/env python3
"""Build groups.json (cg-v2) and the derived group files (Add-on A4, CG-9).

Usage:
  py -3.14 scripts/build_groups.py          # write the six files from the committed roster
  py -3.14 scripts/build_groups.py --check  # rebuild in memory; fail if a committed file differs

Reads site/data/global/groups/roster.json and writes into site/data/global/groups/. Exit codes:
0 ok, 1 validation failure or a committed file that differs from the rebuild.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from atlas.groups.build import OUTPUT_FILES, GroupsBuildError, build_groups  # noqa: E402

GROUPS_DIR = ROOT / "site" / "data" / "global" / "groups"
ROSTER_PATH = GROUPS_DIR / "roster.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="fail if committed files differ")
    args = parser.parse_args(argv)

    roster = json.loads(ROSTER_PATH.read_text(encoding="utf-8"))
    try:
        outputs = build_groups(roster)
    except GroupsBuildError as exc:
        print(f"FAIL: {exc}")
        return 1

    if args.check:
        stale = [
            name
            for name in OUTPUT_FILES
            if not (GROUPS_DIR / name).exists() or (GROUPS_DIR / name).read_bytes() != outputs[name]
        ]
        if stale:
            print(f"FAIL: out of date, rerun scripts/build_groups.py: {', '.join(stale)}")
            return 1
        print(f"OK: {len(outputs)} group files match the rebuild")
        return 0

    GROUPS_DIR.mkdir(parents=True, exist_ok=True)
    for name in OUTPUT_FILES:
        (GROUPS_DIR / name).write_bytes(outputs[name])
    print(f"OK: wrote {len(outputs)} files to {GROUPS_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
