#!/usr/bin/env python3
"""Build roster_qc.json (cg-roster-qc-v1): public roster QC candidates (AMB-ROSTER-QC).

Usage:
  py -3.14 scripts/build_roster_qc.py                       # write the file from curation/
  py -3.14 scripts/build_roster_qc.py --check               # fail if the committed file differs
  py -3.14 scripts/build_roster_qc.py --curation-dir DIR    # read merges and corrections from DIR

Reads site/data/global/groups/roster.json and DIR/group_merges.csv and
DIR/group_name_corrections.csv (a missing file means no rows). Pairs already decided in the
merges file are left out, and suspect names with an approved correction are left out. The output
holds group ids and reason codes only. Exit codes: 0 ok, 1 the committed file differs.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from atlas.groups import admission, roster_qc  # noqa: E402
from atlas.groups.build import to_bytes  # noqa: E402

GROUPS_DIR = ROOT / "site" / "data" / "global" / "groups"
ROSTER_PATH = GROUPS_DIR / "roster.json"
OUTPUT_PATH = GROUPS_DIR / "roster_qc.json"
CURATION_DIR = ROOT / "curation"


def render(curation_dir: Path, roster_path: Path | None = None) -> bytes:
    roster = json.loads((roster_path or ROSTER_PATH).read_text(encoding="utf-8"))
    merges = admission.read_merges(curation_dir / "group_merges.csv")
    corrections = admission.read_name_corrections(curation_dir / "group_name_corrections.csv")
    return to_bytes(roster_qc.build_roster_qc(roster, merges, corrections))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--check", action="store_true", help="fail if the committed file differs")
    parser.add_argument("--curation-dir", type=Path, default=CURATION_DIR)
    args = parser.parse_args(argv)

    data = render(args.curation_dir)
    if args.check:
        if not OUTPUT_PATH.exists() or OUTPUT_PATH.read_bytes() != data:
            print(f"{OUTPUT_PATH.name} differs from the rebuild; run scripts/build_roster_qc.py")
            return 1
        print(f"{OUTPUT_PATH.name} is up to date")
        return 0
    OUTPUT_PATH.write_bytes(data)
    print(f"wrote {OUTPUT_PATH.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
