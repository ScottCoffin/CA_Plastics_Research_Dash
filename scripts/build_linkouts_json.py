"""Export the link-out registry to site/data/california/linkouts.json (Add-on A2 §8, EM-5a).

Only the public display fields from atlas.linkouts.strip_entries are written, plus each card's
icon and initials (config/linkout_icons.yml; VD-32) and its Atlas steward_inst_id
(config/linkouts.yml). --check exits 1 when the committed file differs from a fresh build.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml

from atlas import linkouts
from atlas.regions.scope import region_data_dir

SCHEMA_VERSION = "em5.v1"
SOURCE = "config/linkouts.yml"
OUTPUT_PATH = region_data_dir() / "linkouts.json"
ICONS_PATH = linkouts.ROOT / "config" / "linkout_icons.yml"
ICON_DIR = "assets/linkouts/"
INITIALS_PATTERN = re.compile(r"^[A-Z0-9]{1,3}$")
INST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


def load_icons(path: Path = ICONS_PATH) -> dict[str, dict[str, Any]]:
    """Icon records keyed by card ID. Each needs initials; a stored icon must exist on disk."""
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"{path}: {exc}") from exc
    rows = data.get("icons") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        raise ValueError(f"{path}: icons must be a list")
    icons: dict[str, dict[str, Any]] = {}
    for row in rows:
        eid = row.get("id") if isinstance(row, dict) else None
        if not isinstance(eid, str):
            raise ValueError(f"{path}: every icon record needs an id")
        if eid in icons:
            raise ValueError(f"{path}: duplicate icon record {eid}")
        if not isinstance(row.get("initials"), str) or not INITIALS_PATTERN.match(row["initials"]):
            raise ValueError(f"{path}: {eid} initials must be 1 to 3 capital letters or digits")
        icon = row.get("path")
        if icon is not None:
            valid = (
                isinstance(icon, str)
                and icon.startswith(ICON_DIR)
                and icon.endswith((".png", ".svg"))
                and ".." not in icon
            )
            if not valid:
                raise ValueError(f"{path}: {eid} path must be {ICON_DIR}<file>.png or .svg")
            if not (linkouts.ROOT / "site" / icon).is_file():
                raise ValueError(f"{path}: {eid} icon file is missing: site/{icon}")
        icons[eid] = row
    return icons


def _display_fields(
    entry: dict[str, Any], icon: str | None, initials: str, steward_inst_id: str | None
) -> dict[str, Any]:
    """Insert icon and initials after the name and steward_inst_id after the steward source."""
    out: dict[str, Any] = {}
    for key, value in entry.items():
        out[key] = value
        if key == "name":
            out["icon"] = icon
            out["initials"] = initials
        if key == "steward_source":
            out["steward_inst_id"] = steward_inst_id
    return out


def build_payload(
    registry: dict[str, Any] | None = None, icons: dict[str, dict[str, Any]] | None = None
) -> dict[str, Any]:
    data = linkouts.load_registry() if registry is None else registry
    icon_records = load_icons() if icons is None else icons
    entries: list[dict[str, Any]] = []
    for public, source in zip(linkouts.strip_entries(data), data["entries"], strict=True):
        eid = public["id"]
        if eid not in icon_records:
            raise ValueError(f"{eid}: no icon record in {ICONS_PATH.name}")
        inst_id = source.get("steward_inst_id")
        if inst_id is not None and not (
            isinstance(inst_id, str) and INST_ID_PATTERN.match(inst_id)
        ):
            raise ValueError(f"{eid}: steward_inst_id must be an institution id, not {inst_id!r}")
        record = icon_records[eid]
        entries.append(_display_fields(public, record.get("path"), record["initials"], inst_id))
    return {
        "schema_version": SCHEMA_VERSION,
        "source": SOURCE,
        "entries": entries,
    }


def render(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=1, ensure_ascii=False, sort_keys=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="fail if the committed JSON is stale")
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        text = render(build_payload())
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
