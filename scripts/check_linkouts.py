"""Validate the link-out registry (EM-16) offline; with --live, run the weekly HTTP status check.

Offline mode makes no network requests. --live writes docs/api_notes/linkouts_check.json
and leaves config/linkouts.yml unchanged.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter

from atlas import linkouts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--live", action="store_true", help="run the HTTP status check")
    args = parser.parse_args(argv)
    try:
        registry = linkouts.load_registry()
        errors = linkouts.validate_registry(registry)
        timeline = linkouts.timeline_source_urls()
    except (OSError, ValueError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    if errors:
        for error in errors:
            print(f"FAIL: {error}", file=sys.stderr)
        return 1
    print(f"OK: {len(registry['entries'])} registry entries; {len(timeline)} timeline source URLs")
    if not args.live:
        return 0
    payload = linkouts.run_live()
    for eid, record in payload["entries"].items():
        detail = record.get("error") or ""
        print(
            f"{eid} status={record.get('status')} method={record.get('method')} {detail}".rstrip()
        )
    outcomes = Counter(
        record.get("outcome", "unchecked")
        for record in [*payload["entries"].values(), *payload["timeline"].values()]
    )
    summary = ", ".join(f"{name} {count}" for name, count in sorted(outcomes.items()))
    print(f"Live check: {summary}; wrote {linkouts.OUTPUT_PATH.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
