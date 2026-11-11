"""Build a versioned, label-independent stratified sample and frozen splits."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

import pyarrow.parquet as pq

from atlas.nlp.sampling import build_split_rows


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_gazetteer_hit_ids(path: Path) -> set[str]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or "work_id" not in reader.fieldnames:
            raise ValueError("gazetteer-hit CSV must include a work_id header")
        return {
            row["work_id"].strip()
            for row in reader
            if row.get("work_id") and row["work_id"].strip()
        }


def _leak_records(path: Path, hit_ids: set[str], taken: set[str]) -> list[dict]:
    """Minimal leak-candidate records: not CA-affiliated, gazetteer hit from the hit CSV."""
    records = []
    for row in pq.read_table(path).to_pylist():
        work_id = row["work_id"]
        if work_id not in hit_ids or work_id in taken:
            continue
        records.append(
            {
                "work_id": work_id,
                "title": row.get("title") or "",
                "abstract": row.get("abstract") or "",
                "year": row.get("year"),
                "type": row.get("type") or "",
                "oa_status": row.get("oa_status") or "",
                "institution_type": "unknown",
                "author_ids": sorted(row.get("author_ids") or []),
                "ca_any_author": False,
                "gazetteer_hit": True,
            }
        )
    return records


def _load_records(
    works_path: Path,
    authorships_path: Path,
    institutions_path: Path,
    gazetteer_hits_path: Path | None,
    leak_candidates_path: Path | None = None,
) -> list[dict]:
    works = pq.read_table(works_path).to_pylist()
    authorships = pq.read_table(authorships_path).to_pylist()
    institutions = pq.read_table(institutions_path).to_pylist()
    authors_by_work: dict[str, set[str]] = defaultdict(set)
    institution_by_work: dict[str, set[str]] = defaultdict(set)
    for row in authorships:
        if row.get("author_id"):
            authors_by_work[row["work_id"]].add(row["author_id"])
        institution_by_work[row["work_id"]].update(row.get("institution_ids") or [])
    type_by_id = {row["inst_id"]: row.get("atlas_type") or "unknown" for row in institutions}
    hit_ids: set[str] = set()
    if gazetteer_hits_path:
        hit_ids = _load_gazetteer_hit_ids(gazetteer_hits_path)
    records = []
    for row in works:
        types = sorted(
            {type_by_id.get(item, "unknown") for item in institution_by_work[row["work_id"]]}
        )
        record = dict(row)
        record.update(
            {
                "author_ids": sorted(authors_by_work[row["work_id"]]),
                "institution_type": "+".join(types) if types else "unknown",
                "gazetteer_hit": row["work_id"] in hit_ids,
            }
        )
        records.append(record)
    if leak_candidates_path:
        records.extend(
            _leak_records(leak_candidates_path, hit_ids, {row["work_id"] for row in records})
        )
    unknown_hits = hit_ids - {row["work_id"] for row in records}
    if unknown_hits:
        raise ValueError(
            f"gazetteer-hit input contains {len(unknown_hits)} work IDs absent from works snapshot"
        )
    return records


def _v2_details(rows: list[dict], args: argparse.Namespace) -> dict:
    pool = [row for row in rows if row["sample_role"] == "pool"]
    split_by_group: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        split_by_group[row["author_group"]].add(row["split"])
    dimensions = ("year_bin", "journal_type", "matrix", "oa_status", "institution_type")
    return {
        "author_group_overlap_across_splits": sum(len(v) > 1 for v in split_by_group.values()),
        "split_counts_all_roles": {
            name: sum(row["split"] == name for row in rows) for name in ("train", "dev", "test")
        },
        "stratum_counts": {
            dim: dict(sorted(Counter(row[dim] for row in pool).items())) for dim in dimensions
        },
        "leak_candidates_sha256": (
            _sha256(args.leak_candidates)
            if args.leak_candidates and args.leak_candidates.exists()
            else None
        ),
        "leak_candidates_note": (
            "ignored parquet (data/interim); not re-hashable from a clean checkout; "
            "leak_test IDs are verifiable against the committed gazetteer-hit CSV"
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--works", type=Path, default=Path("data/processed/normalized/works.parquet")
    )
    parser.add_argument(
        "--authorships", type=Path, default=Path("data/processed/normalized/authorships.parquet")
    )
    parser.add_argument(
        "--institutions", type=Path, default=Path("data/processed/normalized/institutions.parquet")
    )
    parser.add_argument(
        "--gazetteer-hits", type=Path, help="CSV with work_id values from a versioned hit pass"
    )
    parser.add_argument("--sample-size", type=int, default=500)
    parser.add_argument("--leak-test-size", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42042)
    parser.add_argument(
        "--snapshot-status",
        choices=("fixture_only", "production_snapshot", "v3.1_corpus"),
        default="fixture_only",
    )
    parser.add_argument(
        "--leak-candidates",
        type=Path,
        help="ignored parquet from scripts/fetch_leak_candidates.py (non-CA works)",
    )
    parser.add_argument("--out", type=Path, default=Path("curation/splits_v1.csv"))
    args = parser.parse_args()
    source_paths = [args.works, args.authorships, args.institutions]
    if args.gazetteer_hits:
        source_paths.append(args.gazetteer_hits)
    records = _load_records(
        args.works, args.authorships, args.institutions, args.gazetteer_hits, args.leak_candidates
    )
    rows = build_split_rows(
        records, seed=args.seed, sample_size=args.sample_size, leak_test_size=args.leak_test_size
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    columns = [
        "work_id",
        "sample_role",
        "split",
        "year_bin",
        "journal_type",
        "matrix",
        "oa_status",
        "institution_type",
        "author_group",
    ]
    with args.out.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    manifest = {
        "version": args.out.stem,
        "snapshot_status": args.snapshot_status,
        "seed": args.seed,
        "requested_pool_sample_size": args.sample_size,
        "requested_leak_test_size": args.leak_test_size,
        "pool_rows": sum(row["sample_role"] == "pool" for row in rows),
        "leak_test_rows": sum(row["sample_role"] == "leak_test" for row in rows),
        "split_counts": {
            name: sum(row["split"] == name and row["sample_role"] == "pool" for row in rows)
            for name in ("train", "dev", "test")
        },
        "source_snapshot": [
            {"path": path.as_posix(), "sha256": _sha256(path)} for path in source_paths
        ],
        "gazetteer_hit_source": args.gazetteer_hits.as_posix() if args.gazetteer_hits else None,
        "selection_contract": "label-independent; no provisional/model labels read",
        "limitations": (
            "Counts reflect the supplied local snapshot only; no claim of representative "
            "corpus coverage."
        ),
        "split_file_sha256": _sha256(args.out),
    }
    if args.snapshot_status == "v3.1_corpus":
        manifest.update(_v2_details(rows, args))
    manifest_path = args.out.with_name(f"{args.out.stem}_manifest.json")
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {len(rows)} split IDs to {args.out}; manifest: {manifest_path}")


if __name__ == "__main__":
    main()
