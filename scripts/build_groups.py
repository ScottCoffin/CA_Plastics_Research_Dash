#!/usr/bin/env python3
"""Build groups.json (cg-v2) and the derived group files (Add-on A4, CG-9, CG-6b).

Usage:
  py -3.14 scripts/build_groups.py          # write the six files from the committed roster
  py -3.14 scripts/build_groups.py --check  # rebuild in memory; fail if a committed file differs

Reads site/data/global/groups/roster.json and writes into site/data/global/groups/. Exit codes:
0 ok, 1 validation failure or a committed file that differs from the rebuild.

Curated submissions (CG-6b, written by scripts/ambassador_export_pr.py) are read from
curation/group_tags.csv and curation/group_affiliations.csv when present. Corrected display names
come from curation/group_name_corrections.csv (the group_id never changes). Blind second tags
(curation/group_double_tags.csv) and reviewer checks (curation/group_reviews.csv) feed the
precision card; a missing file means no rows. A tagged group with all five Tier-1 review rows is
published as status reviewed with the reviewed values (partial reviews change nothing). A row whose
group_id is not on the roster is skipped with a printed reason. A tag with not_an_organisation true
removes the group from the roster used for every output (spec section 4.4, rule 5). Status
reviewed is set only by reviews in curation/group_reviews.csv, never by a submission.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from atlas.groups.build import (  # noqa: E402
    OUTPUT_FILES,
    TIER1_FACETS,
    GroupsBuildError,
    build_groups,
)

GROUPS_DIR = ROOT / "site" / "data" / "global" / "groups"
ROSTER_PATH = GROUPS_DIR / "roster.json"
CURATION_DIR = ROOT / "curation"
TAGS_FILE = "group_tags.csv"
AFFILIATIONS_FILE = "group_affiliations.csv"
NAME_CORRECTIONS_FILE = "group_name_corrections.csv"
DOUBLE_TAGS_FILE = "group_double_tags.csv"
REVIEWS_FILE = "group_reviews.csv"
REVIEW_OUTCOMES = ("agree", "edit")
# Facets with evidence columns in group_tags.csv (section 8.3), in column order.
TAG_FACETS = (
    "entity_type",
    "sector",
    "plastics_centrality",
    "primary_activities",
    "geographic_scope",
    "legal_form",
    "participation_in_science",
    "website_languages",
)
TAG_SINGLE_FIELDS = (
    "cannot_determine_reason",
    "entity_type",
    "sector",
    "plastics_centrality",
    "geographic_scope",
    "legal_form",
    "legal_form_note",
    "participation_in_science",
    "tagged_at",
)
TAG_LIST_FIELDS = ("primary_activities", "places", "website_languages", "themes", "constituency")


def _rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return [{k: v or "" for k, v in row.items() if k} for row in csv.DictReader(handle)]


def _flag(value: str, where: str) -> bool | None:
    """'' -> None, 'true' -> True, 'false' -> False; anything else is a malformed file."""
    if value in ("", "true", "false"):
        return None if value == "" else value == "true"
    raise GroupsBuildError(f"{where}: expected true, false or blank, got {value!r}")


def tag_submission(row: dict[str, str]) -> dict[str, Any]:
    """The cg-v2 fields one group_tags.csv row sets. Blank cells keep the roster defaults."""
    submission: dict[str, Any] = {"group_id": row["group_id"], "status": row["status"]}
    for key in TAG_SINGLE_FIELDS:
        if row.get(key):
            submission[key] = row[key]
    for key in TAG_LIST_FIELDS:
        if row.get(key):
            submission[key] = row[key].split(";")
    evidence = []
    for facet in TAG_FACETS:
        url = row.get(f"evidence_{facet}_url", "")
        if not url:
            continue
        not_stated = _flag(row.get(f"evidence_{facet}_not_stated", ""), facet) is True
        evidence.append(
            {
                "facet": facet,
                "url": url,
                "accessed_at": row.get(f"evidence_{facet}_accessed_at", ""),
                "quote": None if not_stated else row.get(f"evidence_{facet}_quote") or None,
                "not_stated": not_stated,
                "note": row.get(f"evidence_{facet}_note") or None,
            }
        )
    if evidence:
        submission["evidence"] = evidence
    return submission


def affiliation_entry(row: dict[str, str]) -> dict[str, Any]:
    return {
        "target_name": row["target_name"],
        "relation": row["relation"],
        "evidence": {
            "url": row["evidence_url"],
            "accessed_at": row["evidence_accessed_at"],
            "quote": row["evidence_quote"],
            "not_stated": False,
        },
    }


def load_curated_submissions(
    curation_dir: Path, roster_ids: set[str]
) -> tuple[list[dict[str, Any]], set[str]]:
    """Return (submissions, group ids not counted as organisations) from the curation CSVs."""
    submissions: dict[str, dict[str, Any]] = {}
    excluded: set[str] = set()
    seen: set[str] = set()
    for row in _rows(curation_dir / TAGS_FILE):
        group_id = row.get("group_id", "")
        if group_id in seen:
            raise GroupsBuildError(f"{TAGS_FILE} has duplicate group rows")
        seen.add(group_id)
        is_not_organisation = _flag(row.get("not_an_organisation", ""), TAGS_FILE) is True
        if is_not_organisation:
            # Remember even when the roster was already filtered, so offline export logs stay quiet.
            excluded.add(group_id)
            continue
        if group_id not in roster_ids:
            print(f"skip group_tags row: group_id {group_id!r} is not on the roster")
            continue
        submissions[group_id] = tag_submission(row)
    for row in _rows(curation_dir / AFFILIATIONS_FILE):
        group_id = row.get("group_id", "")
        if group_id in excluded:
            continue
        elif group_id not in submissions:
            print(f"skip group_affiliations row: group_id {group_id!r} has no tag row")
        else:
            submissions[group_id].setdefault("stated_affiliations", []).append(
                affiliation_entry(row)
            )
    return list(submissions.values()), excluded


def load_name_corrections(curation_dir: Path, roster_ids: set[str]) -> dict[str, str]:
    """group_id -> corrected name from group_name_corrections.csv; the last row per group_id wins.

    Rows for ids not on the roster are ignored; only their count is reported. A header-only or
    missing file gives no corrections.
    """
    corrections: dict[str, str] = {}
    unknown = 0
    for row in _rows(curation_dir / NAME_CORRECTIONS_FILE):
        name = row.get("name", "").strip()
        if not name:
            raise GroupsBuildError(f"{NAME_CORRECTIONS_FILE} has a row with no name")
        group_id = row.get("group_id", "")
        if group_id not in roster_ids:
            unknown += 1
            continue
        corrections[group_id] = name
    if unknown:
        print(
            f"skip {NAME_CORRECTIONS_FILE} rows: {unknown} row(s) not on the roster",
            file=sys.stderr,
        )
    return corrections


def load_double_tags(curation_dir: Path) -> list[dict[str, str]]:
    """Blind second-tag rows (CG-7a): group_id, facet, value_a, value_b. Missing file = no rows."""
    rows = _rows(curation_dir / DOUBLE_TAGS_FILE)
    for row in rows:
        if row.get("facet", "") not in TIER1_FACETS:
            raise GroupsBuildError(
                f"{DOUBLE_TAGS_FILE}: facet {row.get('facet')!r} is not a Tier-1 facet"
            )
    return rows


def load_reviews(curation_dir: Path) -> list[dict[str, str]]:
    """Reviewer checks (CG-7a, CG-GRP-REVIEW-APPLY): group_id, facet, outcome, reason_code,
    reviewed_at and reviewed_value (blank in files written before the column existed)."""
    rows = _rows(curation_dir / REVIEWS_FILE)
    for row in rows:
        if row.get("facet", "") not in TIER1_FACETS:
            raise GroupsBuildError(
                f"{REVIEWS_FILE}: facet {row.get('facet')!r} is not a Tier-1 facet"
            )
        if row.get("outcome", "") not in REVIEW_OUTCOMES:
            raise GroupsBuildError(
                f"{REVIEWS_FILE}: outcome {row.get('outcome')!r} must be agree or edit"
            )
    return rows


def build_outputs(roster: dict[str, Any], curation_dir: Path) -> dict[str, bytes]:
    """Return file name -> bytes for the six group files, with curated submissions applied."""
    roster_ids = {record.get("group_id") for record in roster["records"]}
    submissions, excluded = load_curated_submissions(curation_dir, roster_ids)
    names = load_name_corrections(curation_dir, roster_ids)
    kept = [record for record in roster["records"] if record.get("group_id") not in excluded]
    # A group removed from the roster after it was paired or reviewed keeps its curated rows
    # (the audit trail) but no longer counts toward the precision card (CG-7b).
    kept_ids = {record.get("group_id") for record in kept}
    return build_groups(
        {**roster, "records": kept},
        submissions,
        name_corrections=names,
        double_tags=[r for r in load_double_tags(curation_dir) if r.get("group_id") in kept_ids],
        reviews=[r for r in load_reviews(curation_dir) if r.get("group_id") in kept_ids],
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="fail if committed files differ")
    parser.add_argument(
        "--curation-dir", type=Path, default=CURATION_DIR, help="folder with the CG-6b CSVs"
    )
    args = parser.parse_args(argv)

    roster = json.loads(ROSTER_PATH.read_text(encoding="utf-8"))
    try:
        outputs = build_outputs(roster, args.curation_dir)
    except GroupsBuildError as exc:
        print(f"FAIL: {exc}")
        return 1

    if args.check:
        stale = [
            name
            for name in OUTPUT_FILES
            if not (GROUPS_DIR / name).exists() or (GROUPS_DIR / name).read_bytes() != outputs[name]
        ]
        if stale:
            print(f"FAIL: out of date, rerun scripts/build_groups.py: {', '.join(stale)}")
            return 1
        print(f"OK: {len(outputs)} group files match the rebuild")
        return 0

    GROUPS_DIR.mkdir(parents=True, exist_ok=True)
    for name in OUTPUT_FILES:
        (GROUPS_DIR / name).write_bytes(outputs[name])
    print(f"OK: wrote {len(outputs)} files to {GROUPS_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
