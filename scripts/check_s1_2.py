"""Acceptance check for the S1.2 institution registry."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import pyarrow.parquet as pq

from atlas.ingest.institutions import (
    ATLAS_TYPES,
    CSU_CAMPUSES,
    MAJOR_PRIVATE_UNIVERSITIES,
    REQUIRED_NAME_ALIASES,
    UC_CAMPUSES,
)


def _normalize(value: str) -> str:
    return " ".join(value.casefold().replace("é", "e").split())


def _covered(expected: str, rows: list[dict[str, object]], atlas_type: str) -> bool:
    wanted = {_normalize(value) for value in (expected, *REQUIRED_NAME_ALIASES.get(expected, ()))}
    return any(
        row["atlas_type"] == atlas_type and _normalize(str(row["display_name"])) in wanted
        for row in rows
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--require-owner-review", action="store_true")
    args = parser.parse_args()
    parquet = Path("data/processed/institutions.parquet")
    review_path = Path("data/processed/institution_review_top100.csv")
    qc_path = Path("docs/institutions_qc.md")
    if not (parquet.exists() and review_path.exists() and qc_path.exists()):
        raise SystemExit("S1.2 outputs are missing")

    rows = pq.read_table(parquet).to_pylist()
    if len(rows) < 100:
        raise SystemExit("institution registry has fewer than 100 rows")
    missing_types = sorted(
        {row["atlas_type"] for row in rows}
        - {
            "UC",
            "CSU",
            "other-public",
            "private",
            "community-college",
            "nonprofit/NGO",
            "state-agency",
            "federal",
            "local-agency",
            "JPA",
            "company",
        }
    )
    if missing_types:
        raise SystemExit(f"unexpected atlas types: {missing_types}")
    for label, expected, atlas_type in (
        ("UC", UC_CAMPUSES, "UC"),
        ("CSU", CSU_CAMPUSES, "CSU"),
        ("major private", MAJOR_PRIVATE_UNIVERSITIES, "private"),
    ):
        absent = [name for name in expected if not _covered(name, rows, atlas_type)]
        if absent:
            raise SystemExit(f"missing {label} institutions: {absent}")

    with review_path.open(encoding="utf-8", newline="") as stream:
        review = list(csv.DictReader(stream))
    if len(review) != 100 or [int(row["review_rank"]) for row in review] != list(range(1, 101)):
        raise SystemExit("owner review CSV must contain ranks 1 through 100")
    reviewed = sum(
        bool(row["owner_atlas_type"].strip() and row["owner_reviewed_at"].strip()) for row in review
    )
    if reviewed not in {0, 100}:
        raise SystemExit(f"owner review is incomplete: {reviewed}/100 rows")
    invalid_owner_types = sorted(
        {
            row["owner_atlas_type"].strip()
            for row in review
            if row["owner_atlas_type"].strip()
            and row["owner_atlas_type"].strip() not in ATLAS_TYPES
        }
    )
    if invalid_owner_types:
        raise SystemExit(f"invalid owner atlas types: {invalid_owner_types}")
    if args.require_owner_review and reviewed != 100:
        raise SystemExit("OWNER_REVIEW_PENDING: 0/100 rows signed off")
    print(
        f"S1.2 machine acceptance passed: {len(rows)} institutions; "
        f"UC {len(UC_CAMPUSES)}/{len(UC_CAMPUSES)}; "
        f"CSU {len(CSU_CAMPUSES)}/{len(CSU_CAMPUSES)}; "
        f"major private {len(MAJOR_PRIVATE_UNIVERSITIES)}/{len(MAJOR_PRIVATE_UNIVERSITIES)}; "
        f"owner review {reviewed}/100."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
