"""Acceptance checks for deterministic S4.2 sample and split preparation."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from build_gold_sample import _load_records, _sha256

from atlas.nlp.sampling import build_split_rows

WORKS = Path("data/processed/normalized/works.parquet")
AUTHORSHIPS = Path("data/processed/normalized/authorships.parquet")
INSTITUTIONS = Path("data/processed/normalized/institutions.parquet")
SPLITS = Path("curation/splits_v1.csv")
MANIFEST = Path("curation/splits_v1_manifest.json")


def main() -> None:
    records = _load_records(WORKS, AUTHORSHIPS, INSTITUTIONS, None)
    rows = build_split_rows(records)
    with SPLITS.open(encoding="utf-8-sig", newline="") as stream:
        persisted = list(csv.DictReader(stream))
    assert rows == persisted, "committed fixture splits do not match deterministic rebuild"
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["version"] == "splits_v1"
    assert manifest["snapshot_status"] == "fixture_only"
    assert len(records) == 4
    assert manifest["pool_rows"] == 2
    assert manifest["leak_test_rows"] == 0
    assert manifest["split_file_sha256"] == _sha256(SPLITS)
    source_hashes = {source["path"]: source["sha256"] for source in manifest["source_snapshot"]}
    expected_sources = {
        path.as_posix(): _sha256(path) for path in (WORKS, AUTHORSHIPS, INSTITUTIONS)
    }
    assert source_hashes == expected_sources
    ids = [row["work_id"] for row in persisted]
    assert len(ids) == len(set(ids)) == 2
    assert all(row["sample_role"] == "pool" for row in persisted)
    assert all(row["split"] in {"train", "dev", "test"} for row in persisted)
    pool = [row for row in persisted if row["sample_role"] == "pool"]
    assert {row["split"] for row in pool} == {"train", "test"}
    assert manifest["split_counts"] == {
        split: sum(row["sample_role"] == "pool" and row["split"] == split for row in persisted)
        for split in ("train", "dev", "test")
    }
    assert all(row["author_group"] for row in pool)
    split_by_author_group: dict[str, set[str]] = {}
    for row in persisted:
        if row["author_group"]:
            split_by_author_group.setdefault(row["author_group"], set()).add(row["split"])
    assert all(len(splits) == 1 for splits in split_by_author_group.values())
    assert all(row["matrix"] != "" for row in pool)
    assert build_split_rows(records) == rows
    print("S4.2 acceptance passed: deterministic fixture splits and isolation metadata verified")


if __name__ == "__main__":
    main()
