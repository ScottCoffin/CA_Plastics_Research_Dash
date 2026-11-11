"""Acceptance check for AT-2 institution type carry-forward (offline).

Confirms the committed outputs are current, complete for the site, consistent with the
owner override and old top-100 inputs, and that new entrants are queued for review.
"""

from __future__ import annotations

import csv
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from atlas.ingest.institutions import ATLAS_TYPES  # noqa: E402

TYPES_CSV = ROOT / "config/institution_types.csv"
REVIEW_CSV = ROOT / "data/processed/institution_review_needs_v31.csv"
OLD_TOP100 = ROOT / "data/processed/institution_review_top100.csv"
OVERRIDES = ROOT / "config/institution_overrides.csv"
SITE_JSON = ROOT / "site/data/institutions.json"
DOC = ROOT / "docs/AT_2_VERIFICATION.md"
BUILDER = ROOT / "scripts/build_institution_types.py"
TYPES_HEADER = [
    "inst_id",
    "display_name",
    "atlas_type",
    "type_source",
    "parent_id",
    "v31_work_count",
    "v31_rank",
    "needs_review",
]
REVIEW_HEADER = [
    "review_rank",
    "openalex_id",
    "display_name",
    "plastic_work_count",
    "proposed_atlas_type",
    "owner_atlas_type",
    "owner_reviewed_at",
    "owner_notes",
]
TOP_N = 100
SENTINEL_NEW_ENTRANT = "I4210111001"  # San Francisco Estuary Institute (SFEI)
SENTINEL_OLD_MEMBER = "I11006740"  # Southern California Coastal Water Research Project


class CheckError(AssertionError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckError(message)


def _rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    text = path.read_text(encoding="utf-8")
    reader = csv.DictReader(text.splitlines())
    return list(reader.fieldnames or []), list(reader)


def main() -> int:
    rebuilt = subprocess.run(
        [sys.executable, str(BUILDER), "--check"], cwd=ROOT, capture_output=True, text=True
    )
    _require(
        rebuilt.returncode == 0, "build_institution_types.py --check failed:\n" + rebuilt.stdout
    )

    header, types = _rows(TYPES_CSV)
    _require(header == TYPES_HEADER, f"config header mismatch: {header}")
    site = json.loads(SITE_JSON.read_text(encoding="utf-8"))["institutions"]
    site_ids = sorted(
        row["inst_id"] for row in site if row["ca_flag"] and int(row["work_count"]) >= 1
    )
    ids = [row["inst_id"] for row in types]
    _require(
        ids == site_ids, "config rows must be exactly the site institutions, sorted by inst_id"
    )

    overrides = {row["inst_id"]: row["value"] for row in _rows(OVERRIDES)[1]}
    old_header, old_rows = _rows(OLD_TOP100)
    old = {row["openalex_id"]: row for row in old_rows}
    review_header, review = _rows(REVIEW_CSV)
    _require(review_header == REVIEW_HEADER, f"review header mismatch: {review_header}")
    _require(old_header[:4] == REVIEW_HEADER[:4], "old top-100 header changed")

    new_top = {
        row["inst_id"]
        for row in types
        if row["v31_rank"] and int(row["v31_rank"]) <= TOP_N and row["inst_id"] not in old
    }
    review_ids = {row["openalex_id"] for row in review}
    _require(review_ids == new_top, "review CSV must hold exactly the new v3.1 top-100 entrants")
    _require(len(review) == len(new_top), "duplicate review rows")
    _require(SENTINEL_NEW_ENTRANT in review_ids, "SFEI should be a new top-100 entrant")
    # SCCWRP was not in the owner-reviewed 2026-11-05 top 100 (restored from 0cec765), so it
    # is a new v3.1 entrant, as the A1 AT-2 contract expects ("expect SCCWRP, SFEI ... to appear").
    _require(
        SENTINEL_OLD_MEMBER in ids and SENTINEL_OLD_MEMBER in review_ids,
        "SCCWRP should be a new top-100 entrant queued for review",
    )

    by_id = {row["inst_id"]: row for row in types}
    sources = {"owner_override", "owner_reviewed", "rule"}
    for row in types:
        _require(row["atlas_type"] in ATLAS_TYPES, f"{row['inst_id']}: invalid atlas_type")
        _require(row["type_source"] in sources, f"{row['inst_id']}: invalid type_source")
        _require(row["needs_review"] in {"true", "false"}, f"{row['inst_id']}: bad needs_review")
        _require(
            row["parent_id"] == "" or re.fullmatch(r"I\d+", row["parent_id"]) is not None,
            f"{row['inst_id']}: bad parent_id",
        )
        _require(row["parent_id"] != row["inst_id"], f"{row['inst_id']}: self parent")
        if row["type_source"] == "owner_override":
            _require(row["inst_id"] in overrides, f"{row['inst_id']}: override not in CSV")
            _require(
                row["atlas_type"] == overrides[row["inst_id"]],
                f"{row['inst_id']}: override mismatch",
            )
        elif row["type_source"] == "owner_reviewed":
            _require(row["inst_id"] in old, f"{row['inst_id']}: not in old top-100")
            _require(
                row["atlas_type"] == old[row["inst_id"]]["proposed_atlas_type"],
                f"{row['inst_id']}: owner_reviewed type mismatch",
            )
        expected_review = row["type_source"] == "rule" and row["inst_id"] in new_top
        _require(
            (row["needs_review"] == "true") == expected_review,
            f"{row['inst_id']}: needs_review inconsistent",
        )

    for row in review:
        _require(all(row[col] == "" for col in REVIEW_HEADER[5:]), "owner columns must be blank")
        _require(row["openalex_id"] not in old, "review row is an old top-100 member")
        config_row = by_id[row["openalex_id"]]
        _require(row["plastic_work_count"] == config_row["v31_work_count"], "work count mismatch")
        _require(row["review_rank"] == config_row["v31_rank"], "rank mismatch")

    for path in (TYPES_CSV, REVIEW_CSV, DOC):
        text = path.read_text(encoding="utf-8")
        _require("relevance check" not in text.lower(), f"stale note text in {path.name}")
    doc = DOC.read_text(encoding="utf-8")
    _require("Newly in the v3.1 top 100" in doc, "verification doc missing new-entrant section")

    counts = {
        "rows": len(types),
        "owner_override": sum(r["type_source"] == "owner_override" for r in types),
        "owner_reviewed": sum(r["type_source"] == "owner_reviewed" for r in types),
        "rule": sum(r["type_source"] == "rule" for r in types),
        "needs_review": sum(r["needs_review"] == "true" for r in types),
        "review_rows": len(review),
    }
    print("AT-2 checks passed: " + json.dumps(counts, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except CheckError as error:
        print(f"AT-2 check failed: {error}")
        sys.exit(1)
