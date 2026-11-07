"""Export, import, or summarize annotations after guide_v1 approval."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import pyarrow.parquet as pq

from atlas.nlp.annotation import (
    agreement_summary,
    export_templates,
    import_annotations,
    require_frozen_guide,
    sha256_file,
)


def _read_splits(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"work_id", "sample_role", "split"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError("split CSV needs work_id, sample_role, and split columns")
        return list(reader)


def _read_work_metadata(path: Path) -> dict[str, dict]:
    table = pq.read_table(path, columns=["work_id", "year", "title", "abstract"])
    return {str(row["work_id"]): row for row in table.to_pylist()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    export = subparsers.add_parser("export")
    export.add_argument("--splits", type=Path, default=Path("curation/splits_v1.csv"))
    export.add_argument("--annotators", required=True, help="comma-separated unique annotator IDs")
    export.add_argument("--output-dir", type=Path, required=True)
    export.add_argument("--include-test", action="store_true")
    export.add_argument(
        "--works", type=Path, default=Path("data/processed/normalized/works.parquet")
    )
    importer = subparsers.add_parser("import")
    importer.add_argument("--splits", type=Path, default=Path("curation/splits_v1.csv"))
    importer.add_argument("--inputs", nargs="+", type=Path, required=True)
    importer.add_argument("--output", type=Path, required=True)
    importer.add_argument("--include-test", action="store_true")
    importer.add_argument(
        "--works", type=Path, default=Path("data/processed/normalized/works.parquet")
    )
    agreement = subparsers.add_parser("agreement")
    agreement.add_argument("--annotations", type=Path, required=True)
    agreement.add_argument("--output", type=Path, required=True)
    agreement.add_argument("--split", choices=("train", "dev", "test"), required=True)
    for command in (export, importer, agreement):
        command.add_argument("--guide", type=Path, default=Path("docs/LABELING_GUIDE.md"))
        command.add_argument("--review", type=Path, default=Path("docs/LABELING_GUIDE_REVIEW.md"))
    args = parser.parse_args()
    guide_version = require_frozen_guide(args.guide, args.review)
    works_path = args.works if args.command in {"export", "import"} else None
    works = _read_work_metadata(works_path) if works_path else None
    if args.command == "export":
        annotators = [name.strip() for name in args.annotators.split(",")]
        paths = export_templates(
            _read_splits(args.splits),
            annotators,
            args.output_dir,
            guide_version=guide_version,
            include_test=args.include_test,
            works_by_id=works,
        )
        manifest = {
            "schema_version": "annotation_export_manifest_v1",
            "guide_version": guide_version,
            "guide_sha256": sha256_file(args.guide),
            "split_manifest_sha256": sha256_file(args.splits.with_name("splits_v1_manifest.json")),
            "split_csv_sha256": sha256_file(args.splits),
            "works_snapshot_sha256": sha256_file(args.works),
            "template_files": {path.name: sha256_file(path) for path in paths},
            "test_rows_included": args.include_test,
        }
        (args.output_dir / "annotation_export_manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(f"Wrote {len(paths)} blank annotation templates")
    elif args.command == "import":
        rows = import_annotations(
            args.inputs,
            _read_splits(args.splits),
            guide_version=guide_version,
            works_by_id=works,
            include_test=args.include_test,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(rows, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        manifest = {
            "schema_version": "annotation_import_manifest_v1",
            "guide_version": guide_version,
            "guide_sha256": sha256_file(args.guide),
            "split_manifest_sha256": sha256_file(args.splits.with_name("splits_v1_manifest.json")),
            "split_csv_sha256": sha256_file(args.splits),
            "works_snapshot_sha256": sha256_file(args.works),
            "input_csv_sha256": {path.as_posix(): sha256_file(path) for path in args.inputs},
            "annotation_rows": len(rows),
            "annotators": sorted({row["annotator"] for row in rows}),
            "test_rows_included": args.include_test,
        }
        args.output.with_suffix(".manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(f"Imported {len(rows)} validated annotation rows")
    else:
        rows = json.loads(args.annotations.read_text(encoding="utf-8"))
        if any(row.get("guide_version") != guide_version for row in rows):
            raise ValueError("annotation guide version does not match the frozen guide")
        report = agreement_summary(rows, split=args.split)
        report["input_sha256"] = sha256_file(args.annotations)
        report["guide_sha256"] = sha256_file(args.guide)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(f"Wrote agreement report with {len(report['labels'])} label summaries")


if __name__ == "__main__":
    main()
