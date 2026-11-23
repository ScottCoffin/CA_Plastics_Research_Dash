"""Freeze the label-blind design for the California evaluation block (BQ-G2).

Run from the repository root. The snapshot that curation/splits_v2.csv was drawn from is
recovered from git into scratch/gold_design_snapshot/, loaded with build_gold_sample's own
loader, and the selection is re-run with sampling.build_split_rows. The output,
curation/gold_design_v1.json, gives every splits_v2 row its stratum, N_h, n_h, inclusion
probability and weights, plus the pipeline state (labels, relevance, query version) at freeze
and at the first gold-label commit. Only pipeline outputs are read; the gold label sheet is
never opened.
"""

import argparse
import csv
import hashlib
import io
import json
import math
import subprocess
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_gold_sample import _load_records, _sha256  # noqa: E402
from check_s4_2 import (  # noqa: E402
    GUIDE_EXAMPLES,
    assert_guide_examples_excluded,
    load_doi_by_work,
)

from atlas.nlp.sampling import build_split_rows, sampling_strata  # noqa: E402

SCHEMA = "gold-design-v1"
OUT = Path("curation/gold_design_v1.json")
SPLITS = Path("curation/splits_v2.csv")
MANIFEST = Path("curation/splits_v2_manifest.json")
GAZETTEER_HITS = Path("curation/leak_gazetteer_hits_v1.csv")
SNAPSHOT_DIR = Path("scratch/gold_design_snapshot")
SNAPSHOT_TABLES = {
    "works": "data/processed/normalized/works.parquet",
    "authorships": "data/processed/normalized/authorships.parquet",
    "institutions": "data/processed/normalized/institutions.parquet",
}
LABELS = "data/processed/work_labels.parquet"
RELEVANCE = "curation/work_relevance.csv"
QUERIES = "config/queries.yml"
FIRST_LABELS_COMMIT = "bc3abefa"
DIMENSIONS = ("year_bin", "journal_type", "matrix", "oa_status", "institution_type")
LABEL_FIELDS = (
    "plastic_related",
    "plastic_tier",
    "domain_tags",
    "label_source",
    "model_version",
    "plastic_score",
    "confidence",
)
_YES_NO = {"true": True, "false": False, "": None}


def _git(*args: str) -> bytes:
    return subprocess.run(["git", *args], check=True, capture_output=True).stdout


def _blob(rev: str, path: str) -> bytes | None:
    """Committed bytes of ``path`` at ``rev``; None when the path is absent there."""
    try:
        return _git("show", f"{rev}:{path}")
    except subprocess.CalledProcessError:
        return None


def _rev_parse(rev: str) -> str:
    return _git("rev-parse", "--verify", f"{rev}^{{commit}}").decode().strip()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_or_none(data: bytes | None) -> str | None:
    return None if data is None else _sha256_bytes(data)


def recover_snapshot(expected: Mapping[str, str]) -> tuple[str, dict[str, Path]]:
    """Newest commit whose works, authorships and institutions match the manifest hashes."""
    for commit in _git("log", "--format=%H", "--", SNAPSHOT_TABLES["works"]).decode().split():
        blobs = {name: _blob(commit, path) for name, path in SNAPSHOT_TABLES.items()}
        if any(blob is None for blob in blobs.values()):
            continue
        if all(
            _sha256_bytes(blobs[name]) == expected[path] for name, path in SNAPSHOT_TABLES.items()
        ):
            SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
            paths = {}
            for name, path in SNAPSHOT_TABLES.items():
                target = SNAPSHOT_DIR / Path(path).name
                target.write_bytes(blobs[name])
                paths[name] = target
            return commit, paths
    raise AssertionError("no commit reproduces the splits_v2 source snapshot hashes")


def round_robin_plan(frame_sizes: Sequence[int], sample_size: int) -> tuple[int, int]:
    """Return (full rounds R, picks in the partial round) for build_split_rows' round-robin.

    Round r takes one work from every stratum that still has one, in the seeded stratum order,
    until the target is reached; the final round stops part-way through that order.
    """
    if not frame_sizes:
        raise ValueError("empty frame")
    target = min(sample_size, sum(frame_sizes))
    rounds = 0
    while rounds < max(frame_sizes) and sum(min(n, rounds + 1) for n in frame_sizes) <= target:
        rounds += 1
    return rounds, target - sum(min(n, rounds) for n in frame_sizes)


def inclusion_probabilities(frame: Mapping[Any, int], sample_size: int) -> dict[Any, float]:
    """Probability that a given work in each stratum is selected by build_split_rows.

    Within a stratum every work is equally likely, because the within-stratum order is a seeded
    hash. A stratum with N_h <= R is taken whole. A stratum with N_h > R is in the partial round
    with probability rem / (number of strata with N_h > R), and then its (R+1)-th work is taken
    with probability 1 / N_h, so each work has probability (R + rem / E) / N_h.
    """
    rounds, rem = round_robin_plan(list(frame.values()), sample_size)
    eligible = sum(size > rounds for size in frame.values())
    partial = rem / eligible if rem else 0.0
    return {
        key: 1.0 if size <= rounds else (rounds + partial) / size for key, size in frame.items()
    }


def _check_plan(frame: Mapping[Any, int], counts: Mapping[Any, int], rounds: int, rem: int) -> None:
    """Realized stratum counts must follow the plan: full rounds, then rem extra picks."""
    extra = 0
    for key, size in frame.items():
        taken = counts.get(key, 0)
        base = min(size, rounds)
        ok = taken == size if size <= rounds else taken - base in (0, 1)
        if not ok:
            raise AssertionError("realized stratum counts do not follow the round-robin plan")
        extra += taken - base
    if extra != rem:
        raise AssertionError(f"partial-round picks {extra} differ from plan {rem}")


def _check_selection(
    rebuilt: Sequence[Mapping[str, Any]], split_rows: Sequence[Mapping[str, str]]
) -> None:
    selected = {row["work_id"]: row for row in rebuilt if row["sample_role"] == "pool"}
    frozen = {row["work_id"]: row for row in split_rows if row["sample_role"] == "pool"}
    missing = len(frozen.keys() - selected.keys())
    extra = len(selected.keys() - frozen.keys())
    if missing or extra:
        raise AssertionError(
            f"rebuilt pool selection differs from splits_v2: {extra} extra, {missing} missing"
        )
    for field in DIMENSIONS:
        differing = sum(selected[work_id][field] != frozen[work_id][field] for work_id in frozen)
        if differing:
            raise AssertionError(f"rebuilt {field} differs from splits_v2 for {differing} works")


def _check_splits(
    rebuilt: Sequence[Mapping[str, Any]], split_rows: Sequence[Mapping[str, str]]
) -> None:
    selected = {row["work_id"]: row for row in rebuilt if row["sample_role"] == "pool"}
    for row in split_rows:
        if row["sample_role"] != "pool":
            continue
        mine = selected[row["work_id"]]
        if mine["split"] != row["split"] or mine["author_group"] != row["author_group"]:
            raise AssertionError("rebuilt split or author_group differs from splits_v2")


def _stratum_key(values: Sequence[str]) -> str:
    if any("|" in value for value in values):
        raise ValueError("stratum value contains the key separator")
    return "|".join(values)


def _index_labels(blob: bytes | None) -> dict[str, dict[str, Any]]:
    if blob is None:
        return {}
    rows = pq.read_table(io.BytesIO(blob), columns=["work_id", *LABEL_FIELDS]).to_pylist()
    index = {row["work_id"]: row for row in rows}
    if len(index) != len(rows):
        raise ValueError("work_labels.parquet has duplicate work_id values")
    return index


def _yes_no(text: str) -> bool | None:
    key = text.strip().lower()
    if key not in _YES_NO:
        raise ValueError("unexpected true/false value in work_relevance.csv")
    return _YES_NO[key]


def _index_relevance(blob: bytes | None) -> dict[str, dict[str, Any]]:
    if blob is None:
        return {}
    index: dict[str, dict[str, Any]] = {}
    for row in csv.DictReader(io.StringIO(blob.decode("utf-8-sig"), newline="")):
        work_id = row["work_id"].strip()
        if work_id in index:
            raise ValueError("work_relevance.csv has duplicate work_id values")
        index[work_id] = {
            "plastic_related": _yes_no(row["plastic_related"]),
            "assist_plastic_related": _yes_no(row["assist_plastic_related"]),
            "confidence": row["confidence"] or None,
            "reviewer": row["reviewer"] or None,
            "owner_review": row["owner_review"] or None,
        }
    return index


def _plain(value: Any) -> Any:
    """Parquet scalars as JSON-safe values (NaN becomes null)."""
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def _pipeline_state(rev: str) -> dict[str, Any]:
    labels_blob = _blob(rev, LABELS)
    relevance_blob = _blob(rev, RELEVANCE)
    queries_blob = _blob(rev, QUERIES)
    return {
        "commit": rev,
        "labels": _index_labels(labels_blob),
        "relevance": _index_relevance(relevance_blob),
        "query_version": str(yaml.safe_load(queries_blob)["version"]) if queries_blob else None,
        "hashes": {
            "work_labels_parquet_sha256": _sha256_or_none(labels_blob),
            "work_relevance_csv_sha256": _sha256_or_none(relevance_blob),
            "queries_yml_sha256": _sha256_or_none(queries_blob),
        },
    }


def _pipeline_fields(state: Mapping[str, Any], work_id: str) -> dict[str, Any]:
    label = state["labels"].get(work_id)
    relevance = state["relevance"].get(work_id)
    fields: dict[str, Any] = {
        name: _plain(label[name]) if label is not None else None for name in LABEL_FIELDS
    }
    fields["relevance_assist"] = dict(relevance) if relevance is not None else None
    fields["query_version"] = state["query_version"]
    return fields


def _state_summary(state: Mapping[str, Any]) -> dict[str, Any]:
    return {"commit": state["commit"], **state["hashes"], "query_version": state["query_version"]}


def _design_rows(
    split_rows: Sequence[Mapping[str, str]],
    frame: Mapping[tuple[str, ...], int],
    counts: Mapping[tuple[str, ...], int],
    probs: Mapping[tuple[str, ...], float],
    freeze: Mapping[str, Any],
    first: Mapping[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in split_rows:
        work_id = row["work_id"]
        out: dict[str, Any] = {
            "work_id": work_id,
            "sample_role": row["sample_role"],
            "split": row["split"],
            "author_group": row["author_group"],
            "pipeline_at_freeze": _pipeline_fields(freeze, work_id),
            "pipeline_at_first_labels": _pipeline_fields(first, work_id),
        }
        if row["sample_role"] == "leak_test":
            out.update(
                {
                    "design": "purposive",
                    "stratum": {"key": "leak_test", "values": None},
                    "N_h": None,
                    "n_h": None,
                    "incl_prob": None,
                    "design_weight": None,
                    "incl_prob_within_stratum": None,
                    "weight_within_stratum": None,
                }
            )
        elif row["sample_role"] == "pool":
            values = tuple(row[name] for name in DIMENSIONS)
            size, taken, prob = frame[values], counts[values], probs[values]
            out.update(
                {
                    "design": "stratum_round_robin",
                    "stratum": {"key": _stratum_key(values), "values": list(values)},
                    "N_h": size,
                    "n_h": taken,
                    "incl_prob": prob,
                    "design_weight": 1.0 / prob,
                    "incl_prob_within_stratum": taken / size,
                    "weight_within_stratum": size / taken,
                }
            )
        else:
            raise ValueError("unexpected sample_role in splits_v2")
        rows.append(out)
    return rows


def build_payload() -> dict[str, Any]:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    split_bytes = SPLITS.read_bytes()
    if _sha256_bytes(split_bytes) != manifest["split_file_sha256"]:
        raise AssertionError("curation/splits_v2.csv does not match its manifest hash")
    split_rows = list(csv.DictReader(io.StringIO(split_bytes.decode("utf-8-sig"), newline="")))
    expected = {source["path"]: source["sha256"] for source in manifest["source_snapshot"]}
    hits_sha = _sha256(GAZETTEER_HITS)
    if hits_sha != expected[GAZETTEER_HITS.as_posix()]:
        raise AssertionError("leak gazetteer-hit CSV does not match the manifest hash")
    with GAZETTEER_HITS.open(encoding="utf-8-sig", newline="") as stream:
        hit_ids = {row["work_id"] for row in csv.DictReader(stream)}
    leak_ids = {row["work_id"] for row in split_rows if row["sample_role"] == "leak_test"}
    if not leak_ids <= hit_ids:
        raise AssertionError("leak_test rows are not all gazetteer-hit works")

    commit, paths = recover_snapshot(expected)
    sample_size = int(manifest["requested_pool_sample_size"])
    records = _load_records(paths["works"], paths["authorships"], paths["institutions"], None)
    frame_records = [row for row in records if row.get("ca_any_author")]
    frame = Counter(sampling_strata(row) for row in frame_records)
    rebuilt = build_split_rows(
        records,
        seed=int(manifest["seed"]),
        sample_size=sample_size,
        leak_test_size=int(manifest["requested_leak_test_size"]),
    )
    _check_selection(rebuilt, split_rows)
    _check_splits(rebuilt, split_rows)

    frozen_pool = [row for row in split_rows if row["sample_role"] == "pool"]
    counts = Counter(tuple(row[name] for name in DIMENSIONS) for row in frozen_pool)
    rounds, rem = round_robin_plan(list(frame.values()), sample_size)
    _check_plan(frame, counts, rounds, rem)
    probs = inclusion_probabilities(frame, sample_size)

    with GUIDE_EXAMPLES.open(encoding="utf-8-sig", newline="") as stream:
        guides = list(csv.DictReader(stream))
    guides_in_frame = assert_guide_examples_excluded(guides, {"stratum_frame": frame_records}, {})
    guides_in_splits = assert_guide_examples_excluded(
        guides, {"splits_v2": split_rows}, load_doi_by_work()
    )

    head = _rev_parse("HEAD")
    first = _rev_parse(FIRST_LABELS_COMMIT)
    freeze_state = _pipeline_state(head)
    first_state = _pipeline_state(first)
    rows = _design_rows(split_rows, frame, counts, probs, freeze_state, first_state)
    expected_size = sum(frame[key] * probs[key] for key in frame)
    return {
        "schema": SCHEMA,
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "frozen_at_commit": head,
        "label_blind": True,
        "selection_reproduced": True,
        "splits_reproduced": True,
        "splits_file": {"path": SPLITS.as_posix(), "sha256": _sha256_bytes(split_bytes)},
        "manifest": {
            "path": MANIFEST.as_posix(),
            "sha256": _sha256(MANIFEST),
            "version": manifest["version"],
            "seed": manifest["seed"],
            "requested_pool_sample_size": sample_size,
            "requested_leak_test_size": manifest["requested_leak_test_size"],
        },
        "source_snapshot": {
            "commit": commit,
            "hashes_verified": True,
            "tables": [
                {"path": path, "sha256": expected[path]} for path in SNAPSHOT_TABLES.values()
            ],
        },
        "gazetteer_hits": {
            "path": GAZETTEER_HITS.as_posix(),
            "sha256": hits_sha,
            "hashes_verified": True,
        },
        "pipeline_snapshots": {
            "at_freeze": _state_summary(freeze_state),
            "at_first_labels": _state_summary(first_state),
        },
        "pool_population": sum(frame.values()),
        "strata_count": len(frame),
        "sampled_strata_count": len(counts),
        "expected_sample_size": round(expected_size, 9),
        "guide_examples": {
            "rows": len(guides),
            "with_identifier": guides_in_splits,
            "checked_against_pool_frame": guides_in_frame,
        },
        "weighting": {
            "unit": "work",
            "rule": (
                "sampling.build_split_rows round-robin: one work per stratum per round, in a "
                "seeded stratum order; the final round stops part-way through that order"
            ),
            "full_rounds": rounds,
            "partial_round_picks": rem,
            "incl_prob": (
                "probability that a given work in a stratum is selected under the rule above; "
                "equal within a stratum"
            ),
            "design_weight": (
                "1 / incl_prob (Horvitz-Thompson). Its expectation over seeds sums to "
                "pool_population; in a single sample it does not sum to it exactly"
            ),
            "within_stratum_fields": (
                "incl_prob_within_stratum = n_h / N_h and weight_within_stratum = N_h / n_h are "
                "conditional on the stratum being sampled; they sum to pool_population only when "
                f"every stratum is sampled ({len(counts)} of {len(frame)} are in this freeze)"
            ),
        },
        "gold_labels_note": (
            "Gold labels were never merged into exports; only scripts/report_gold_status.py and "
            "the review app read the gold label sheet. This file was built without opening it "
            "(label_blind: true), so it records the design and pipeline state only."
        ),
        "estimator_note": (
            "Weights apply within the California evaluation block only: design_weight expands "
            "the CA-pool frame of the frozen snapshot (pool_population works) and nothing "
            "outside it. The leak_test rows are purposive and carry no weight. Guide examples "
            "are excluded from every frame and split."
        ),
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--force", action="store_true", help="overwrite an existing design file")
    args = parser.parse_args()
    if args.out.exists() and not args.force:
        raise SystemExit(f"{args.out} exists; rerun with --force to overwrite it")
    payload = build_payload()
    text = json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n"
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(text.encode("utf-8"))
    pool = sum(row["sample_role"] == "pool" for row in payload["rows"])
    print(
        f"wrote {len(payload['rows'])} rows ({pool} pool) over {payload['strata_count']} strata "
        f"({payload['sampled_strata_count']} sampled), N={payload['pool_population']}: {args.out}"
    )


if __name__ == "__main__":
    main()
