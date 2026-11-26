"""Tier B country aggregates from the global partition: ``site/data/global/countries.json``.

Reads the ignored ``data/processed/global/works.parquet`` and ``work_regions.parquet`` and writes
one entry per country with at least one unscreened query hit (tier B at 50 or more works, else
tier C), plus the registry-region blocks. Country names come from ``explore.json``. Offline.

``--check`` validates the committed file (schema, labels, tier rule, totals, no person-level
keys). When the ignored inputs exist it also rebuilds the file and fails if the committed copy
is stale; without them it prints SKIP for the staleness check and exits 0.

Usage:
    py -3.14 scripts/build_tier_b.py          # write countries.json
    py -3.14 scripts/build_tier_b.py --check  # validate; exit 1 on problems or a stale file
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from atlas.build.tier_b import (  # noqa: E402
    build,
    encode,
    load_country_names,
    parse_generated_at,
    validate,
)

PARTITION = ROOT / "data" / "processed" / "global"
DEFAULT_WORKS = PARTITION / "works.parquet"
DEFAULT_REGIONS = PARTITION / "work_regions.parquet"
DEFAULT_NAMES = ROOT / "site" / "data" / "global" / "explore.json"
DEFAULT_OUTPUT = ROOT / "site" / "data" / "global" / "countries.json"


def _write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(text.encode("utf-8"))
    tmp.replace(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--works", type=Path, default=DEFAULT_WORKS)
    parser.add_argument("--regions", type=Path, default=DEFAULT_REGIONS)
    parser.add_argument("--names", type=Path, default=DEFAULT_NAMES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--check",
        action="store_true",
        help="validate the committed file; SKIP staleness without inputs",
    )
    args = parser.parse_args(argv)
    inputs_present = args.works.is_file() and args.regions.is_file()

    if args.check:
        if not args.output.is_file():
            print(f"FAIL: missing {args.output}")
            return 1
        committed = json.loads(args.output.read_text(encoding="utf-8"))
        problems = validate(committed)
        if problems:
            for problem in problems[:20]:
                print(f"FAIL: {problem}")
            return 1
        if not inputs_present:
            print(f"SKIP: staleness; no partition under {PARTITION}")
            print("PASS: countries.json schema, labels, tier rule and totals")
            return 0
        rebuilt = encode(
            build(
                args.works,
                args.regions,
                generated_at=parse_generated_at(committed),
                names=load_country_names(args.names),
            )
        )
        if args.output.read_text(encoding="utf-8") != rebuilt:
            print("FAIL: countries.json is stale; rerun scripts/build_tier_b.py")
            return 1
        print("PASS: countries.json schema, labels, tier rule, totals and freshness")
        return 0

    if not inputs_present:
        print(
            f"ERROR: missing partition under {PARTITION}; run scripts/partition_global.py",
            file=sys.stderr,
        )
        return 1
    payload = build(
        args.works,
        args.regions,
        generated_at=datetime.now(UTC),
        names=load_country_names(args.names),
    )
    problems = validate(payload)
    if problems:
        for problem in problems[:20]:
            print(f"ERROR: {problem}", file=sys.stderr)
        return 1
    text = encode(payload)
    _write_atomic(args.output, text)
    tiers = payload["tier_counts"]
    print(
        f"wrote {args.output.name}: {len(text.encode('utf-8')):,} bytes, "
        f"{len(payload['countries'])} countries (tier B {tiers['B']}, tier C {tiers['C']}), "
        f"{len(payload['registry_regions'])} registry regions"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
