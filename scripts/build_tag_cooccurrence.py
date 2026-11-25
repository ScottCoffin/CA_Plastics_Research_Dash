"""Build data/processed/analytics/tag_cooccurrence.json (BQ-4.3, schema bq4-cooc-v1).

Reads the frozen labels snapshot written by ``scripts/build_topic_series.py`` (not the live labels)
and the taxonomy. Writes one gitignored output.

    py -3.14 scripts/build_tag_cooccurrence.py                       # write the output
    py -3.14 scripts/build_tag_cooccurrence.py --check               # fail when missing or stale
    py -3.14 scripts/build_tag_cooccurrence.py --as-of 2026-11-25 --split-year 2021

--check regenerates the payload with the recorded as-of date (or --as-of) and fails unless it is
byte-identical to the file. It exits 0 with SKIP when an input is absent (CI has no data/ tree).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import yaml  # noqa: E402

from atlas.analytics.tag_cooccurrence import build_cooccurrence  # noqa: E402
from atlas.analytics.topic_series import (  # noqa: E402
    read_snapshot,
    snapshot_sha256,
    works_from_snapshot,
)

SNAPSHOT = ROOT / "data" / "processed" / "analytics" / "labels_snapshot_v1.parquet"
TAXONOMY = ROOT / "config" / "taxonomy.yml"
OUTPUT = ROOT / "data" / "processed" / "analytics" / "tag_cooccurrence.json"


def _relative(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _render(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _headline(payload: dict[str, Any]) -> str:
    tags = payload["tags"]
    all_sources = payload["variants"]["all_sources"]
    complete = (
        all_sources["windows"]["complete_years"]["pairs"]
        if all_sources["status"] == "testable"
        else []
    )
    sufficient = sum(1 for pair in complete if pair["status"] == "sufficient")
    testable = [name for name, v in payload["variants"].items() if v["status"] == "testable"]
    return (
        f"tags {len(tags)}; pairs {len(complete)}; pairs with sufficient data "
        f"(all_sources, complete years, n_ab >= {payload['min_pair_n']}) {sufficient}; "
        f"testable variants: {', '.join(testable) or 'none'}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="fail when output is missing or stale")
    parser.add_argument("--as-of", type=date.fromisoformat, default=None, help="YYYY-MM-DD")
    parser.add_argument(
        "--split-year",
        type=int,
        default=None,
        help="first year of the recent period (default: last 5 complete years)",
    )
    parser.add_argument("--snapshot", type=Path, default=SNAPSHOT)
    parser.add_argument("--taxonomy", type=Path, default=TAXONOMY)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args(argv)

    absent = [_relative(p) for p in (args.snapshot, args.taxonomy) if not p.exists()]
    if absent:
        if args.check:
            print(f"SKIP: inputs absent ({', '.join(absent)}); nothing checked")
            return 0
        print(f"error: missing inputs: {', '.join(absent)}", file=sys.stderr)
        return 1

    rows = read_snapshot(args.snapshot)
    works = works_from_snapshot(rows)
    content_sha = snapshot_sha256(rows)
    taxonomy_bytes = args.taxonomy.read_bytes()
    taxonomy = yaml.safe_load(taxonomy_bytes.decode("utf-8")) or {}

    recorded: dict[str, Any] = {}
    if args.check:
        if not args.output.exists():
            print(f"FAIL: {_relative(args.output)} is missing; run without --check")
            return 1
        recorded = json.loads(args.output.read_text(encoding="utf-8"))

    as_of = args.as_of or (
        date.fromisoformat(recorded["as_of"]) if args.check else datetime.now(UTC).date()
    )
    split_year = args.split_year
    if split_year is None and args.check:
        split_year = recorded.get("split_year")
    payload = build_cooccurrence(
        works=works,
        taxonomy=taxonomy,
        as_of=as_of,
        snapshot_path=_relative(args.snapshot),
        snapshot_sha256=content_sha,
        taxonomy_path=_relative(args.taxonomy),
        taxonomy_sha256=hashlib.sha256(taxonomy_bytes).hexdigest(),
        split_year=split_year,
    )
    text = _render(payload)

    if args.check:
        if args.output.read_text(encoding="utf-8") != text:
            print(
                f"FAIL: {_relative(args.output)} is stale (labels snapshot, taxonomy or "
                "settings changed); rerun without --check"
            )
            return 1
        print(f"ok: {_relative(args.output)} is current")
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    tmp = args.output.with_suffix(args.output.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(args.output)
    print(f"wrote {_relative(args.output)}")
    print(_headline(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
