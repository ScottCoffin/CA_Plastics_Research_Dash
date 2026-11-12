"""Export the V-3 pipeline flow to site/data/methods_flow.json (Add-on A2 §5, EM-6).

Counts are copied from the newest release/<YYYY-MM-DD>/methods_card.json (AT-10), so the flow
numbers match the methods card (EAT-4). The ROSES flow template is credited under CC BY 4.0.
--check exits 1 when the committed file differs from a fresh build.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "em6.v1"
RELEASE_DIR = ROOT / "release"
RELEASE_JSON = ROOT / "site" / "data" / "release.json"
OUTPUT_PATH = ROOT / "site" / "data" / "methods_flow.json"
TEMPLATE = {"name": "ROSES flow diagram for systematic maps", "licence": "CC BY 4.0"}
PERFORMED = "performed"
NOT_PERFORMED = "not performed"
CODING_NOTE = "Provisional rule-based topic labels; not validated against a gold set."
APPRAISAL_NOTE = "The Atlas does not grade study quality."
SYNTHESIS_NOTE = "Descriptive evidence map (counts), no meta-analysis."
_DATE_DIR = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def newest_card_path(release_dir: Path = RELEASE_DIR) -> Path:
    """Return the methods card in the newest dated release folder."""
    folders = sorted(
        path
        for path in release_dir.iterdir()
        if path.is_dir() and _DATE_DIR.match(path.name) and (path / "methods_card.json").is_file()
    )
    if not folders:
        raise ValueError(f"no release/<YYYY-MM-DD>/methods_card.json under {release_dir}")
    return folders[-1] / "methods_card.json"


def _flow_entry(flow: dict[str, Any], key: str) -> dict[str, Any]:
    entry = flow.get(key)
    if not isinstance(entry, dict):
        raise ValueError(f"methods card flow.{key} is missing")
    value = entry.get("value")
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"methods card flow.{key}.value is not an integer")
    if not isinstance(entry.get("source"), str):
        raise ValueError(f"methods card flow.{key}.source is missing")
    return entry


def _step(flow: dict[str, Any], key: str, label: str) -> dict[str, Any]:
    entry = _flow_entry(flow, key)
    return {"label": label, "value": entry["value"], "source": entry["source"]}


def release_version(release_date: str, path: Path = RELEASE_JSON) -> str | None:
    """Return the release version when site/data/release.json is for the same date."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if isinstance(data, dict) and data.get("date") == release_date:
        version = data.get("version")
        if isinstance(version, str) and version:
            return version
    return None


def build_payload(card: dict[str, Any], version: str | None = None) -> dict[str, Any]:
    flow = card.get("flow")
    if not isinstance(flow, dict):
        raise ValueError("methods card has no flow object")
    query = card.get("query")
    query_version = query.get("version") if isinstance(query, dict) else None
    if not isinstance(query_version, str) or not query_version:
        raise ValueError("methods card query.version is missing")
    release_date = card.get("release_date")
    if not isinstance(release_date, str) or not release_date:
        raise ValueError("methods card release_date is missing")
    stages = [
        {
            "stage": "Searching",
            "status": PERFORMED,
            "steps": [
                _step(
                    flow,
                    "raw_records",
                    f"Records retrieved from OpenAlex (query {query_version})",
                )
            ],
            "note": None,
        },
        {
            "stage": "Screening",
            "status": PERFORMED,
            "steps": [
                _step(flow, "after_near_duplicate_collapse", "After near-duplicate collapse"),
                _step(flow, "california_authorship", "With a California authorship"),
                _step(flow, "published_after_curation", "Published after curation"),
                _step(flow, "plastic_related_published", "Plastic-related"),
            ],
            "note": None,
        },
        {
            "stage": "Coding / meta-data extraction",
            "status": PERFORMED,
            "steps": [],
            "note": CODING_NOTE,
        },
        {"stage": "Data extraction", "status": NOT_PERFORMED, "steps": [], "note": None},
        {
            "stage": "Critical appraisal",
            "status": NOT_PERFORMED,
            "steps": [],
            "note": APPRAISAL_NOTE,
        },
        {
            "stage": "Synthesis",
            "status": PERFORMED,
            "steps": [
                _step(
                    flow,
                    "analysed_excluding_retracted",
                    "Analysed (retracted works excluded)",
                )
            ],
            "note": SYNTHESIS_NOTE,
        },
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "release_date": release_date,
        "release_version": version,
        "query_version": query_version,
        "template": dict(TEMPLATE),
        "stages": stages,
    }


def render(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=1, ensure_ascii=False, sort_keys=False) + "\n"


def build_from_disk() -> str:
    card_path = newest_card_path()
    card = json.loads(card_path.read_text(encoding="utf-8"))
    if not isinstance(card, dict):
        raise ValueError(f"{card_path} is not a JSON object")
    release_date = card.get("release_date")
    version = release_version(release_date) if isinstance(release_date, str) else None
    return render(build_payload(card, version))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="fail if the committed JSON is stale")
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        text = build_from_disk()
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
