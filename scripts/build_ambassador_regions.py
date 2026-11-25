"""Build site/data/global/ambassador_regions.json: the regions the ambassadors page shows (AMB-1).

Source of truth: regions/_registry.yml. A region is listed when its registry status is active or
planned and it has a page at framework/src/<slug>/index.md. Owner rule (2026-11-25): real data only,
so no proposed regions appear here. The eligible institution count comes from
site/data/<slug>/ambassador_institutions.json.

Every listed region is "open_to_ambassadors" for now. "ambassadors_active" is reserved for the time
the Worker reports a verified ambassador for that region; nothing reports one yet.

Usage:
    py -3.14 scripts/build_ambassador_regions.py          # write the file
    py -3.14 scripts/build_ambassador_regions.py --check  # exit 1 if the committed file is stale
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "regions" / "_registry.yml"
SITE_DATA = ROOT / "site" / "data"
FRAMEWORK_SRC = ROOT / "framework" / "src"
OUT = SITE_DATA / "global" / "ambassador_regions.json"

SCHEMA = "amb-regions-v1"
STATUS_OPEN = "open_to_ambassadors"
LISTED_STATUSES = ("active", "planned")


def build(registry: dict[str, Any]) -> dict[str, Any]:
    regions: list[dict[str, Any]] = []
    for entry in registry.get("regions", []):
        slug = entry.get("slug")
        if entry.get("status") not in LISTED_STATUSES or entry.get("tier") == "root":
            continue
        if not (FRAMEWORK_SRC / slug / "index.md").is_file():
            continue
        predicate = entry.get("predicate") or {}
        institutions = json.loads(
            (SITE_DATA / slug / "ambassador_institutions.json").read_text(encoding="utf-8")
        )
        regions.append(
            {
                "slug": slug,
                "name": entry["name"],
                "status": STATUS_OPEN,
                "country_codes": list(predicate.get("country_codes", [])),
                "subdivision_names": list(predicate.get("institution_region_names", [])),
                "eligible_institutions": len(institutions.get("institutions", [])),
                "page": f"./{slug}/",
            }
        )
    regions.sort(key=lambda r: r["name"])
    return {
        "schema": SCHEMA,
        "source": "regions/_registry.yml (status active or planned, with a page)",
        "statuses": {
            STATUS_OPEN: (
                "Open to ambassadors: the region can have verified ambassadors; "
                "none is reported yet."
            ),
        },
        "regions": regions,
    }


def render(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--check", action="store_true", help="fail when the committed file is stale"
    )
    args = parser.parse_args(argv)
    registry = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    text = render(build(registry))
    if args.check:
        current = OUT.read_text(encoding="utf-8") if OUT.is_file() else ""
        if current != text:
            print(
                f"{OUT.relative_to(ROOT).as_posix()} is stale; "
                "run scripts/build_ambassador_regions.py",
                file=sys.stderr,
            )
            return 1
        print(f"{OUT.relative_to(ROOT).as_posix()} is up to date")
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {OUT.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
