"""Build data/processed/analytics/topic_series.json (BQ-4.1, schema bq4-series-v1).

Reads local files only. Writes two gitignored outputs under data/processed/analytics/:

- labels_snapshot_v1.parquet: the frozen per-work CA labels the series use (one row per work and
  label; ``content_sha256`` is a canonical hash, so later steps compare like with like).
- topic_series.json: CA counts per approved non-experimental tag by year (complete years, partial
  years flagged, share of plastic-related works, label-source sensitivity), global counts for the
  top 30 OpenAlex primary topics plus "other" (unscreened), and the lens block (empty until lens
  labels exist).

    py -3.14 scripts/build_topic_series.py                    # write both files
    py -3.14 scripts/build_topic_series.py --check            # fail when stale or missing
    py -3.14 scripts/build_topic_series.py --refresh-snapshot # accept changed labels

If the live labels differ from the frozen snapshot, a plain build stops: the series must stay on the
snapshot they were first built from. Use --refresh-snapshot only when the owner accepts the change.
--check exits 0 with SKIP when an input is absent (CI has no data/ tree).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import pyarrow.parquet as pq  # noqa: E402
import yaml  # noqa: E402

from atlas.analytics.topic_series import (  # noqa: E402
    SNAPSHOT_SCHEMA,
    SeriesInputs,
    build_series,
    ca_corpus,
    load_curation_inputs,
    load_relevance,
    read_snapshot,
    snapshot_rows,
    snapshot_sha256,
    works_from_snapshot,
    write_snapshot,
)
from atlas.query import load_query_config  # noqa: E402

INPUTS = {
    "work_labels": ROOT / "data" / "processed" / "work_labels.parquet",
    "works": ROOT / "data" / "processed" / "normalized" / "works.parquet",
    "global_works": ROOT / "data" / "processed" / "global" / "works.parquet",
    "taxonomy": ROOT / "config" / "taxonomy.yml",
    "queries": ROOT / "config" / "queries.yml",
    "work_overrides": ROOT / "curation" / "overrides_works.csv",
    "suppressions": ROOT / "curation" / "suppressions.csv",
    "work_relevance": ROOT / "curation" / "work_relevance.csv",
    "work_relevance_model": ROOT / "curation" / "work_relevance_model.csv",
}
# Optional inputs may be absent (the export reads no model labels until the owner accepts a model).
OPTIONAL_INPUTS = frozenset({"work_relevance_model"})
ABSENT = "absent"
SNAPSHOT = ROOT / "data" / "processed" / "analytics" / "labels_snapshot_v1.parquet"
OUTPUT = ROOT / "data" / "processed" / "analytics" / "topic_series.json"


def _relative(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _sha256_file(path: Path) -> str:
    if not path.exists():
        return ABSENT
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fingerprint(path: Path) -> dict[str, str]:
    return {"path": _relative(path), "sha256": _sha256_file(path)}


def _load_inputs() -> SeriesInputs:
    works = pq.read_table(
        INPUTS["works"], columns=["work_id", "year", "title", "abstract", "ca_any_author"]
    ).to_pylist()
    labels = pq.read_table(
        INPUTS["work_labels"],
        columns=["work_id", "plastic_related", "plastic_tier", "domain_tags", "facet_tags"],
    ).to_pylist()
    global_works = pq.read_table(
        INPUTS["global_works"],
        columns=["work_id", "publication_year", "primary_topic_id", "primary_topic_name"],
    ).to_pylist()
    taxonomy = yaml.safe_load(INPUTS["taxonomy"].read_text(encoding="utf-8")) or {}
    return SeriesInputs(
        works=works,
        labels=labels,
        global_works=global_works,
        taxonomy=taxonomy,
        query_config=load_query_config(INPUTS["queries"]),
        relevance=load_relevance(INPUTS["work_relevance"], INPUTS["work_relevance_model"]),
        curation=load_curation_inputs(INPUTS["suppressions"], INPUTS["work_overrides"]),
    )


def _missing_inputs() -> list[str]:
    return [
        _relative(path)
        for name, path in INPUTS.items()
        if not path.exists() and name not in OPTIONAL_INPUTS
    ]


def _snapshot_block(rows: list[dict[str, Any]], content_sha: str) -> dict[str, Any]:
    return {
        "path": _relative(SNAPSHOT),
        "schema": SNAPSHOT_SCHEMA,
        "content_sha256": content_sha,
        "file_sha256": _sha256_file(SNAPSHOT),
        "rows": len(rows),
        "works": len({row["work_id"] for row in rows}),
    }


def _headline(payload: dict[str, Any]) -> str:
    ca = payload["ca"]
    labelled = [t for t in ca["tags"] if t["status"] == "labelled"]
    empty = [t["tag"] for t in ca["tags"] if t["status"] != "labelled"]
    last = payload["last_complete_year"]
    top = payload["global"]["topics"][:3]
    lines = [
        f"CA works {ca['works']} (plastic-related {ca['plastic_related_works']}, "
        f"undated {ca['undated_works']}, removed {ca['removed_works']}); last complete year {last}",
        "tags with labels: "
        + ", ".join(f"{t['tag']}={t['total']}" for t in labelled)
        + f"; no labels yet: {', '.join(empty) or 'none'}",
        "sensitivity totals (all/owner+model/rule): "
        + "; ".join(
            f"{t['tag']} {t['sensitivity']['all_sources']['total']}/"
            f"{t['sensitivity']['owner_model_only']['total']}/"
            f"{t['sensitivity']['rule_only']['total']}"
            for t in labelled
        ),
        "global top topics (unscreened): "
        + "; ".join(f"{t['topic']} {t['total_complete_years']}" for t in top),
        f"lens: {payload['lens']['status']}",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="fail when output is missing or stale")
    parser.add_argument(
        "--refresh-snapshot",
        action="store_true",
        help="replace the frozen labels snapshot with the live labels",
    )
    parser.add_argument("--as-of", type=date.fromisoformat, default=None, help="YYYY-MM-DD")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--snapshot", type=Path, default=SNAPSHOT)
    args = parser.parse_args(argv)

    absent = _missing_inputs()
    if absent:
        if args.check:
            print(f"SKIP: inputs absent ({', '.join(absent)}); nothing checked")
            return 0
        print(f"error: missing inputs: {', '.join(absent)}", file=sys.stderr)
        return 1

    inputs = _load_inputs()
    corpus = ca_corpus(inputs)
    live_rows = snapshot_rows(corpus.works)
    live_sha = snapshot_sha256(live_rows)
    frozen_exists = args.snapshot.exists()
    frozen_rows = read_snapshot(args.snapshot) if frozen_exists else None
    frozen_sha = snapshot_sha256(frozen_rows) if frozen_rows is not None else None

    if args.check:
        if not args.output.exists() or not frozen_exists:
            print(f"FAIL: {_relative(args.output)} or the snapshot is missing; run without --check")
            return 1
        if frozen_sha != live_sha:
            print("FAIL: labels changed since the frozen snapshot; rerun with --refresh-snapshot")
            return 1
        current = json.loads(args.output.read_text(encoding="utf-8"))
        recorded = current.get("inputs", {})
        for name, path in INPUTS.items():
            if recorded.get(name, {}).get("sha256") != _sha256_file(path):
                print(f"FAIL: {_relative(args.output)} is stale ({name} changed); rerun")
                return 1
        if current.get("labels_snapshot", {}).get("content_sha256") != frozen_sha:
            print(f"FAIL: {_relative(args.output)} is stale (snapshot); rerun")
            return 1
        print(f"ok: {_relative(args.output)} is current")
        return 0

    if frozen_rows is None or args.refresh_snapshot:
        write_snapshot(args.snapshot, live_rows)
        rows_used, sha_used = live_rows, live_sha
    elif frozen_sha != live_sha:
        print(
            "error: labels changed since the frozen snapshot "
            f"({_relative(args.snapshot)}); rerun with --refresh-snapshot to accept them",
            file=sys.stderr,
        )
        return 1
    else:
        rows_used, sha_used = frozen_rows, frozen_sha

    as_of = args.as_of or datetime.now(UTC).date()
    payload = build_series(
        works=works_from_snapshot(rows_used),
        removed=corpus.removed,
        global_rows=inputs.global_works,
        taxonomy=inputs.taxonomy,
        as_of=as_of,
        snapshot=_snapshot_block(rows_used, sha_used),
        inputs={name: _fingerprint(path) for name, path in INPUTS.items()},
    )
    text = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    tmp = args.output.with_suffix(args.output.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(args.output)
    print(f"wrote {_relative(args.output)} and {_relative(args.snapshot)}")
    print(_headline(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
