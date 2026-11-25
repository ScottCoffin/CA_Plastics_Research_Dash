"""Build data/processed/analytics/rising_share.json (BQ-4.2, schema bq4-rising-v1).

Reads the frozen labels snapshot written by build_topic_series.py (BQ-4.1), the taxonomy and the
authorship links. Writes one gitignored output: per reported tag, the rising-share flag with its
trend test, label-source sensitivity and leave-one-institution-out checks. Local files only.

    py -3.14 scripts/build_rising_share.py                    # write the output
    py -3.14 scripts/build_rising_share.py --check            # fail when missing or stale
    py -3.14 scripts/build_rising_share.py --as-of 2026-11-25 # pin the as-of date

Run scripts/build_topic_series.py first: this step reads only the frozen snapshot, never the live
labels. --check recomputes the payload from the current inputs and fails unless it matches the file.
--check exits 0 with SKIP when an input is absent (CI has no data/ tree).
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

import pyarrow.parquet as pq  # noqa: E402
import yaml  # noqa: E402

from atlas.analytics.rising_share import institutions_by_work, rising_payload  # noqa: E402
from atlas.analytics.topic_series import (  # noqa: E402
    SNAPSHOT_SCHEMA,
    read_snapshot,
    snapshot_sha256,
    works_from_snapshot,
)
from atlas.ingest.normalize import compact_id  # noqa: E402

INPUTS = {
    "taxonomy": ROOT / "config" / "taxonomy.yml",
    "authorships": ROOT / "data" / "processed" / "normalized" / "authorships.parquet",
}
SNAPSHOT = ROOT / "data" / "processed" / "analytics" / "labels_snapshot_v1.parquet"
OUTPUT = ROOT / "data" / "processed" / "analytics" / "rising_share.json"
ABSENT = "absent"


def _relative(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _sha256_file(path: Path) -> str:
    if not path.exists():
        return ABSENT
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fingerprint(path: Path) -> dict[str, str]:
    return {"path": _relative(path), "sha256": _sha256_file(path)}


def _headline(payload: dict[str, Any]) -> str:
    tags = payload["tags"]
    failed: dict[str, int] = {}
    for tag in tags:
        for reason in tag["reasons_failed"]:
            key = reason.split(":")[0]
            failed[key] = failed.get(key, 0) + 1
    not_testable = sum(
        1 for tag in tags for status in tag["sensitivity"].values() if status == "not_testable"
    )
    lines = [
        f"reported tags {len(tags)}; flagged {len(payload['flagged'])}; "
        f"experimental excluded {len(payload['tags_excluded'])}",
        f"window {payload['window_years'][0]}-{payload['window_years'][-1]}; "
        f"last complete year {payload['last_complete_year']}",
        "failed checks (tags, not exclusive): "
        + (", ".join(f"{k}={v}" for k, v in sorted(failed.items())) or "none"),
        f"sensitivity variants not_testable (tag x variant): {not_testable}",
    ]
    return "\n".join(lines)


def _load_institutions(work_ids: set[str]) -> dict[str, frozenset[str]]:
    table = pq.read_table(INPUTS["authorships"], columns=["work_id", "institution_ids"])
    rows = (
        (row["work_id"], row["institution_ids"])
        for row in table.to_pylist()
        if compact_id(row["work_id"]) in work_ids
    )
    return institutions_by_work(rows)


def _build(as_of: date, snapshot_path: Path) -> tuple[dict[str, Any], str]:
    """Return the payload and the snapshot content hash, read from the frozen snapshot."""

    rows = read_snapshot(snapshot_path)
    content_sha = snapshot_sha256(rows)
    works = works_from_snapshot(rows)
    taxonomy = yaml.safe_load(INPUTS["taxonomy"].read_text(encoding="utf-8")) or {}
    institutions = _load_institutions({w.work_id for w in works})
    payload = rising_payload(
        works=works,
        taxonomy=taxonomy,
        institutions=institutions,
        as_of=as_of,
        snapshot={
            "path": _relative(snapshot_path),
            "schema": SNAPSHOT_SCHEMA,
            "content_sha256": content_sha,
            "file_sha256": _sha256_file(snapshot_path),
            "rows": len(rows),
            "works": len(works),
        },
        inputs={name: _fingerprint(path) for name, path in INPUTS.items()},
    )
    return payload, content_sha


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="fail when output is missing or stale")
    parser.add_argument("--as-of", type=date.fromisoformat, default=None, help="YYYY-MM-DD")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--snapshot", type=Path, default=SNAPSHOT)
    args = parser.parse_args(argv)

    absent = [
        _relative(path) for path in [*INPUTS.values(), args.snapshot] if not Path(path).exists()
    ]
    if absent:
        if args.check:
            print(f"SKIP: inputs absent ({', '.join(absent)}); nothing checked")
            return 0
        print(f"error: missing inputs: {', '.join(absent)}", file=sys.stderr)
        return 1

    as_of = args.as_of or datetime.now(UTC).date()
    if args.check:
        if not args.output.exists():
            print(f"FAIL: {_relative(args.output)} is missing; run without --check")
            return 1
        current = json.loads(args.output.read_text(encoding="utf-8"))
        recorded_as_of = date.fromisoformat(current.get("as_of", "1970-01-01"))
        expected_year = (args.as_of or datetime.now(UTC).date()).year - 1
        if recorded_as_of.year - 1 != expected_year:
            print(f"FAIL: {_relative(args.output)} is stale (last complete year changed); rerun")
            return 1
        fresh, _ = _build(recorded_as_of, args.snapshot)
        if fresh != current:
            print(f"FAIL: {_relative(args.output)} is stale (inputs or snapshot changed); rerun")
            return 1
        print(f"ok: {_relative(args.output)} is current")
        return 0

    payload, _ = _build(as_of, args.snapshot)
    text = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    tmp = args.output.with_suffix(args.output.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(args.output)
    print(f"wrote {_relative(args.output)}")
    print(_headline(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
