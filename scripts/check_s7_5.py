"""Check the public monitoring export boundary and source citations offline."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from atlas.build.monitoring import (
    PRIVATE_SAMPLE_FIELDS,
    build_monitoring_payload,
    load_publication_clearances,
)
from atlas.ingest.monitoring.registry import load_registry


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-private-preview", action="store_true")
    parser.add_argument(
        "--samples", type=Path, default=Path("data/processed/normalized/sf_bay_5gyres/samples.json")
    )
    args = parser.parse_args()
    path = Path("site/data/monitoring.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    registry_payload = load_registry()
    assert payload["schema_version"] == "s7.5"
    mode = payload["publication_mode"]
    assert mode in {"public_catalogue", "public_cleared"}, mode
    assert payload["sample_count"] == len(payload["samples"])
    cleared = load_publication_clearances()
    if mode == "public_catalogue":
        assert payload["sample_count"] == 0
    else:
        assert payload["sample_count"] > 0
        assert {row["dataset_id"] for row in payload["samples"]} <= set(cleared)
        assert all(set(row) <= set(PRIVATE_SAMPLE_FIELDS) for row in payload["samples"])
        published = [
            row for row in payload["datasets"] if row["measurement_status"] != "catalogue_only"
        ]
        assert {row["id"] for row in published} <= set(cleared)
        assert all(
            row["measurement_status"] == "published_rights_cleared"
            and row["publication_license"]["id"] == cleared[row["id"]]["license"]
            for row in published
        )
    assert len(payload["datasets"]) == len(registry_payload["datasets"])
    assert all(row.get("url", "").startswith("https://") for row in payload["datasets"])
    assert all(row.get("provenance_url", "").startswith("https://") for row in payload["datasets"])
    assert all(row.get("citation") for row in payload["datasets"])
    serialized = json.dumps(payload)
    for private_key in ("source_sha256", "license_evidence", '"qc"', "particle_detail_rows"):
        assert private_key not in serialized, private_key
    if mode == "public_catalogue":
        assert "sample_id" not in serialized
    # Budget: catalogue < 100 KB; cleared rows add display fields only (C5 is 3 MB gzip).
    assert path.stat().st_size < (100_000 if mode == "public_catalogue" else 400_000)
    if args.check_private_preview:
        local_rows = json.loads(args.samples.read_text(encoding="utf-8"))
        private_payload = build_monitoring_payload(
            registry_payload, samples=local_rows, private_preview=True, generated_at="check"
        )
        assert len(local_rows) == 314
        assert private_payload["sample_count"] == 314
        assert private_payload["publication_mode"] == "private_preview"
        assert all(set(row) <= set(PRIVATE_SAMPLE_FIELDS) for row in private_payload["samples"])

        def has_coordinates(row: dict) -> bool:
            numeric_pair = all(
                isinstance(row.get(key), int | float)
                and not isinstance(row.get(key), bool)
                and math.isfinite(row[key])
                for key in ("lat", "lon")
            )
            return numeric_pair and -90 <= row["lat"] <= 90 and -180 <= row["lon"] <= 180

        assert sum(has_coordinates(row) for row in local_rows) == 277
        # Only the 8 samples without any Particle Data rows lack a matrix code (S7.3 mapping).
        assert sum(not str(row.get("matrix") or "").strip() for row in local_rows) == 8
    print(
        f"S7.5 public monitoring payload passed: {len(payload['datasets'])} sources, "
        f"{payload['sample_count']} public observations ({mode}), {path.stat().st_size} bytes"
    )


if __name__ == "__main__":
    main()
