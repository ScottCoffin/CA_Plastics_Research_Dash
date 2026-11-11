"""Build the public monitoring payload or an ignored local preview.

Default: zero-observation public catalogue. ``--public-samples`` adds normalized
rows, but only for datasets cleared in ``config/monitoring_publication.yml``; any
row from an uncleared dataset stops the build. ``--private-preview`` writes all
local rows outside ``site/`` for review.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from atlas.build.monitoring import (
    build_monitoring_payload,
    load_publication_clearances,
    load_registry,
    require_private_output_outside_site,
    write_monitoring_payload,
)
from atlas.ingest.monitoring.literature import load_curated_samples

# S7.8 enriched rows (CEDEN concentrations, qa_sample flags) when present.
_NORMALIZED = Path("data/processed/normalized/sf_bay_5gyres")
DEFAULT_SAMPLES = (
    _NORMALIZED / "samples_enriched.json"
    if (_NORMALIZED / "samples_enriched.json").exists()
    else _NORMALIZED / "samples.json"
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--private-preview",
        action="store_true",
        help="include ignored local samples and mark the payload private/rights-unresolved",
    )
    mode.add_argument(
        "--public-samples",
        action="store_true",
        help="publish rows from rights-cleared datasets (config/monitoring_publication.yml)",
    )
    parser.add_argument(
        "--samples",
        type=Path,
        default=DEFAULT_SAMPLES,
        help="local S7.3 sample JSON used with --private-preview or --public-samples",
    )
    args = parser.parse_args()
    output = args.output or (
        Path("data/processed/normalized/sf_bay_5gyres/site_preview/data/monitoring.json")
        if args.private_preview
        else Path("site/data/monitoring.json")
    )
    if args.private_preview:
        output = require_private_output_outside_site(output)
    with_rows = args.private_preview or args.public_samples
    rows = None
    if with_rows:
        # Local normalized rows (S7.3) plus committed literature-derived rows.
        rows = json.loads(args.samples.read_text(encoding="utf-8")) + load_curated_samples()
    payload = build_monitoring_payload(
        load_registry(),
        samples=rows,
        private_preview=args.private_preview,
        clearances=load_publication_clearances() if args.public_samples else None,
    )
    target = write_monitoring_payload(payload, output)
    print(
        f"Wrote {target}: {len(payload['datasets'])} catalogue records, "
        f"{payload['sample_count']} samples ({payload['publication_mode']})"
    )


if __name__ == "__main__":
    main()
