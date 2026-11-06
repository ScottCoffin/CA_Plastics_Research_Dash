"""Create deterministic provisional S2.3 labels from normalized and raw works."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from atlas.ingest.normalize import normalize_fixture
from atlas.nlp.labels import label_records, read_normalized_works, read_raw_parquet


def _read_fixture(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or len(payload) > 200:
        raise ValueError("S2.3 fixture must be a JSON list of at most 200 works")
    return [dict(row) for row in payload if isinstance(row, dict)]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--normalized",
        type=Path,
        default=Path("data/processed/normalized/works.parquet"),
        help="normalized C3 works table",
    )
    parser.add_argument(
        "--raw",
        type=Path,
        default=Path("data/interim/works_raw.parquet"),
        help="S2.1 raw works Parquet",
    )
    parser.add_argument(
        "--fixture",
        type=Path,
        default=Path("tests/fixtures/s2_2_openalex_works.json"),
        help="fallback JSON fixture when live outputs are absent",
    )
    parser.add_argument(
        "--institution",
        type=Path,
        default=Path("data/processed/institutions.parquet"),
    )
    parser.add_argument("--output", type=Path, default=Path("data/processed/work_labels.parquet"))
    parser.add_argument("--qc", type=Path, default=Path("docs/labels_qc.md"))
    args = parser.parse_args()

    if args.normalized.exists():
        normalized = read_normalized_works(args.normalized)
        raw = read_raw_parquet(args.raw) if args.raw.exists() else []
        source = f"normalized={args.normalized}; raw={args.raw if args.raw.exists() else 'missing'}"
    else:
        fixture = _read_fixture(args.fixture)
        with tempfile.TemporaryDirectory(prefix="s2-3-normalized-") as directory:
            root = Path(directory)
            result = normalize_fixture(
                args.fixture,
                institution_path=args.institution,
                output_dir=root / "processed",
                qc_path=root / "normalization_qc.md",
                generated_at="fixture",
            )
            normalized = read_normalized_works(result.output_dir / "works.parquet")
        raw = fixture
        source = str(args.fixture)

    result = label_records(
        normalized,
        raw,
        output_path=args.output,
        qc_path=args.qc,
        source=source,
    )
    print(
        f"S2.3 labeled {result.metrics['label_rows']} works; "
        f"plastic-related={result.metrics['plastic_related_rows']}; QC: {result.qc_path}"
    )


if __name__ == "__main__":
    main()
