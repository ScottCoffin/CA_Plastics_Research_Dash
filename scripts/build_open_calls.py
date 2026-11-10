"""Refresh ``site/data/open_calls.json`` from the California Grants Portal CSV (S8.9).

``--csv PATH`` reads a local copy instead of fetching the portal (offline runs).
A failed fetch or unusable CSV prints status ``deferred`` and exits 0 without
touching the existing JSON, following the S2.4 defer pattern.  Only counts are
printed.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import yaml

from atlas.ingest.grants.open_calls import refresh


def _load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected a YAML mapping in {path}")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--csv", type=Path, default=None, help="read a local CSV instead of fetching"
    )
    parser.add_argument("--config", type=Path, default=Path("config/queries.yml"))
    parser.add_argument("--output", type=Path, default=Path("site/data/open_calls.json"))
    args = parser.parse_args(argv)

    now = datetime.now(UTC)
    # Calendar day in California (UTC-8, standard time), so deadlines today stay open.
    today = now.astimezone(timezone(timedelta(hours=-8))).date()
    summary = refresh(
        output=args.output,
        query_config=_load_yaml(args.config),
        today=today,
        generated_at=now.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        csv_path=args.csv,
    )
    print(json.dumps(summary, sort_keys=True))
    if summary["status"] == "deferred":
        print("status: deferred; existing output left untouched")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
