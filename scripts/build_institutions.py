"""Build the S1.2 California institution registry."""

from __future__ import annotations

import argparse
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path

from atlas.ingest.institutions import BuildPaths, build_registry
from atlas.util.cost import ApiCostLogger


def load_openalex_key(path: Path = Path(".env")) -> None:
    """Load only OPENALEX_API_KEY from an ignored local dotenv file."""

    if os.environ.get("OPENALEX_API_KEY") or not path.exists():
        return
    active_lines = [
        line.strip()
        for line in path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    assignments = 0
    for line in active_lines:
        if "=" not in line:
            continue
        name, value = line.split("=", 1)
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name.strip()):
            continue
        assignments += 1
        if name.strip() in {"OPENALEX_API_KEY", "OPEN_ALEX_API_KEY"}:
            os.environ["OPENALEX_API_KEY"] = value.strip().strip('"').strip("'")
            return
    # The owner's existing file contains one bare credential rather than a
    # KEY=value pair. Supporting that shape avoids rewriting or exposing it.
    if len(active_lines) == 1 and assignments == 0:
        os.environ["OPENALEX_API_KEY"] = active_lines[0].strip('"').strip("'")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh-openalex", action="store_true")
    parser.add_argument("--refresh-counts", action="store_true")
    parser.add_argument(
        "--supplement-government",
        action="store_true",
        help="add California type:government institutions missing from the cached seed",
    )
    parser.add_argument(
        "--reuse-ror-dump",
        action="store_true",
        help="use the ROR dump on disk and the existing registry's provenance (no Zenodo call)",
    )
    parser.add_argument("--usage-log", type=Path, default=Path("data/logs/api_usage.jsonl"))
    args = parser.parse_args()
    load_openalex_key()
    from atlas.ingest.openalex import load_openalex_key as load_all_keys

    load_all_keys()
    run_id = f"institutions-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}"
    with ApiCostLogger(run_id, args.usage_log) as logger:
        summary = build_registry(
            BuildPaths(),
            logger,
            refresh_openalex=args.refresh_openalex,
            refresh_counts=args.refresh_counts,
            supplement_government=args.supplement_government,
            reuse_ror_dump=args.reuse_ror_dump,
        )
    if not summary["openalex_authenticated"]:
        print(
            "WARNING: configured OpenAlex key was unavailable or rejected; "
            "used bounded anonymous access"
        )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
