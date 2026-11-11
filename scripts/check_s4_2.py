"""Acceptance checks for deterministic S4.2 sample and split preparation."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_gold_sample import _load_records, _sha256  # noqa: E402

from atlas.nlp.sampling import build_split_rows  # noqa: E402

WORKS = Path("data/processed/normalized/works.parquet")
AUTHORSHIPS = Path("data/processed/normalized/authorships.parquet")
INSTITUTIONS = Path("data/processed/normalized/institutions.parquet")
SPLITS = Path("curation/splits_v1.csv")
MANIFEST = Path("curation/splits_v1_manifest.json")
SPLITS_V2 = Path("curation/splits_v2.csv")
MANIFEST_V2 = Path("curation/splits_v2_manifest.json")
LEAK_HITS = Path("curation/leak_gazetteer_hits_v1.csv")
LEAK_RAW = Path("data/interim/leak_candidates.parquet")
V2_SEED = 42042
V2_POOL = 500
V2_LEAK = 80


def validate_v2(rows: list[dict], manifest: dict, hit_ids: set[str]) -> None:
    """Structural checks on the real-corpus splits; independent of any ignored data."""
    assert manifest["version"] == "splits_v2"
    assert manifest["snapshot_status"] == "v3.1_corpus"
    ids = [row["work_id"] for row in rows]
    assert len(ids) == len(set(ids)), "duplicate work_id in splits_v2"
    pool = [row for row in rows if row["sample_role"] == "pool"]
    leak = [row for row in rows if row["sample_role"] == "leak_test"]
    assert len(pool) + len(leak) == len(rows)
    assert 400 <= len(pool) <= 600, f"pool size {len(pool)} outside 400-600"
    assert leak and all(row["split"] == "test" for row in leak), "leak_test rows must be test"
    assert {row["work_id"] for row in leak} <= hit_ids, "leak rows must be gazetteer-hit works"
    assert {row["split"] for row in pool} == {"train", "dev", "test"}
    groups: dict[str, set[str]] = {}
    for row in rows:
        groups.setdefault(row["author_group"], set()).add(row["split"])
    assert all(len(v) == 1 for v in groups.values()), "an author_group spans splits"
    assert manifest["author_group_overlap_across_splits"] == 0
    assert manifest["pool_rows"] == len(pool) and manifest["leak_test_rows"] == len(leak)
    assert manifest["split_counts"] == {
        name: sum(row["split"] == name for row in pool) for name in ("train", "dev", "test")
    }
    assert manifest["split_counts_all_roles"] == {
        name: sum(row["split"] == name for row in rows) for name in ("train", "dev", "test")
    }
    for dim, counts in manifest["stratum_counts"].items():
        observed: dict[str, int] = {}
        for row in pool:
            observed[row[dim]] = observed.get(row[dim], 0) + 1
        assert counts == dict(sorted(observed.items())), f"stratum counts differ for {dim}"
    test_pool = {row["work_id"] for row in pool if row["split"] == "test"}
    dev_train = {row["work_id"] for row in rows if row["split"] != "test"}
    assert not test_pool & dev_train, "test isolation violated"


def check_v2() -> str:
    with SPLITS_V2.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    manifest = json.loads(MANIFEST_V2.read_text(encoding="utf-8"))
    with LEAK_HITS.open(encoding="utf-8-sig", newline="") as stream:
        hit_ids = {row["work_id"] for row in csv.DictReader(stream)}
    validate_v2(rows, manifest, hit_ids)
    assert manifest["split_file_sha256"] == _sha256(SPLITS_V2), "splits_v2.csv hash drifted"
    sources = {s["path"]: s["sha256"] for s in manifest["source_snapshot"]}
    assert sources[LEAK_HITS.as_posix()] == _sha256(LEAK_HITS), "leak hit CSV hash drifted"
    notes = []
    local = [p for p in (WORKS, AUTHORSHIPS, INSTITUTIONS) if p.exists()]
    # The split is frozen: when the corpus has grown since the freeze, verify the frozen
    # files against the manifest instead of rebuilding from different inputs.
    changed = [p for p in local if sources[p.as_posix()] != _sha256(p)]
    if changed:
        notes.append(
            "corpus changed since freeze (" + ", ".join(p.name for p in changed) + "); "
            "frozen splits verified against the manifest"
        )
        return "; ".join(notes)
    if len(local) == 3 and LEAK_RAW.exists():
        assert manifest["leak_candidates_sha256"] == _sha256(LEAK_RAW)
        records = _load_records(WORKS, AUTHORSHIPS, INSTITUTIONS, LEAK_HITS, LEAK_RAW)
        rebuilt = build_split_rows(
            records, seed=V2_SEED, sample_size=V2_POOL, leak_test_size=V2_LEAK
        )
        assert rebuilt == rows, "splits_v2.csv does not match deterministic rebuild"
        notes.append("rebuild matched")
    else:
        notes.append("ignored inputs absent: manifest hashes and structure only")
    return "; ".join(notes)


def check_v1() -> str:
    """Fixture splits: rebuild when the fixture inputs are local, else check the manifest."""
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    with SPLITS.open(encoding="utf-8-sig", newline="") as stream:
        persisted = list(csv.DictReader(stream))
    assert manifest["version"] == "splits_v1"
    assert manifest["snapshot_status"] == "fixture_only"
    assert manifest["pool_rows"] == 2
    assert manifest["leak_test_rows"] == 0
    assert manifest["split_file_sha256"] == _sha256(SPLITS)
    source_hashes = {source["path"]: source["sha256"] for source in manifest["source_snapshot"]}
    local = {p.as_posix(): _sha256(p) for p in (WORKS, AUTHORSHIPS, INSTITUTIONS) if p.exists()}
    fixture_inputs_local = len(local) == 3 and local == source_hashes
    if fixture_inputs_local:
        records = _load_records(WORKS, AUTHORSHIPS, INSTITUTIONS, None)
        rows = build_split_rows(records)
        assert len(records) == 4
        assert rows == persisted, "committed fixture splits do not match deterministic rebuild"
        assert build_split_rows(records) == rows
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
        split_by_author_group.setdefault(row["author_group"], set()).add(row["split"])
    assert all(len(splits) == 1 for splits in split_by_author_group.values())
    assert all(row["matrix"] != "" for row in pool)
    return "fixture rebuild matched" if fixture_inputs_local else "fixture inputs superseded"


def main() -> None:
    v1_note = check_v1()
    v2_note = check_v2()
    print(f"S4.2 v1 (fixture) passed: {v1_note}")
    print(f"S4.2 v2 (v3.1 corpus) passed: {v2_note}")


if __name__ == "__main__":
    main()
