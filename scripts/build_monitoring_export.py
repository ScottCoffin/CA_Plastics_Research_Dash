"""Build public catalogue-only or an ignored local monitoring preview."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from atlas.build.monitoring import (
    build_monitoring_payload,
    load_registry,
    require_private_output_outside_site,
    write_monitoring_payload,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--private-preview",
        action="store_true",
        help="include ignored local samples and mark the payload private/rights-unresolved",
    )
    parser.add_argument(
        "--samples",
        type=Path,
        default=Path("data/processed/normalized/sf_bay_5gyres/samples.json"),
        help="local S7.3 sample JSON used only with --private-preview",
    )
    args = parser.parse_args()
    output = args.output or (
        Path("data/processed/normalized/sf_bay_5gyres/site_preview/data/monitoring.json")
        if args.private_preview
        else Path("site/data/monitoring.json")
    )
    if args.private_preview:
        output = require_private_output_outside_site(output)
    rows = json.loads(args.samples.read_text(encoding="utf-8")) if args.private_preview else None
    payload = build_monitoring_payload(
        load_registry(), samples=rows, private_preview=args.private_preview
    )
    target = write_monitoring_payload(payload, output)
    print(
        f"Wrote {target}: {len(payload['datasets'])} catalogue records, "
        f"{payload['sample_count']} samples ({payload['publication_mode']})"
    )


if __name__ == "__main__":
    main()
