"""Export the curated OPC early actions to site/data/opc_actions.json (Add-on A2 §7 Part A, EM-17).

Every field from config/opc_early_actions.yml is written unchanged (deadlines are not reformatted).
The owner's review sheet (curation/opc_mapping_review.csv) is applied when it exists; a blank
sheet changes nothing. --check exits 1 when the committed file differs from a fresh build.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from atlas import opc_actions  # noqa: E402

SCHEMA_VERSION = "em17.v1"
SOURCE = "config/opc_early_actions.yml"
OUTPUT_PATH = ROOT / "site" / "data" / "opc_actions.json"


def _action_payload(action: dict[str, Any]) -> dict[str, Any]:
    return {key: action[key] for key in opc_actions.ACTION_KEYS}


def build_payload(
    data: dict[str, Any] | None = None, review: list[dict[str, str]] | None = None
) -> dict[str, Any]:
    curated = opc_actions.load_actions() if data is None else data
    if review is not None:
        curated = opc_actions.apply_review(curated, review)
    strategy = curated["source"]
    gpl = curated["gpl"]
    return {
        "schema_version": SCHEMA_VERSION,
        "source": SOURCE,
        "mapping_status": curated["mapping_status"],
        "strategy": {
            "label": strategy["label"],
            "url": strategy["url"],
            "adopted": strategy["adopted"],
        },
        "gpl": {
            "name": gpl["name"],
            "steward": gpl["steward"],
            "base_url": gpl["base_url"],
            "california_search_url": gpl["california_search_url"],
            "disclaimer": gpl["disclaimer"],
            "topics": dict(gpl["topics"]),
        },
        "objectives": [
            {"id": objective["id"], "name": objective["name"]}
            for objective in curated["objectives"]
        ],
        "actions": [_action_payload(action) for action in curated["actions"]],
    }


def render(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=1, ensure_ascii=False, sort_keys=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="fail if the committed JSON is stale")
    parser.add_argument(
        "--review",
        type=Path,
        default=opc_actions.REVIEW_PATH,
        help="owner review sheet, applied when the file exists",
    )
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        review = opc_actions.read_review(args.review) if args.review.exists() else None
        text = render(build_payload(review=review))
    except (OSError, ValueError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    if args.check:
        try:
            committed = args.output.read_bytes()
        except OSError:
            print(f"FAIL: {args.output} is missing; run without --check", file=sys.stderr)
            return 1
        if committed != text.encode("utf-8"):
            print(f"FAIL: {args.output} is stale; rerun without --check", file=sys.stderr)
            return 1
        print(f"OK: {args.output} is current")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
