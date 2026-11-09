"""Check the public monitoring export boundary and source citations offline."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from atlas.build.monitoring import PRIVATE_SAMPLE_FIELDS, build_monitoring_payload
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
    assert payload["publication_mode"] == "public_catalogue"
    assert payload["sample_count"] == 0 and payload["samples"] == []
    assert len(payload["datasets"]) == len(registry_payload["datasets"])
    assert all(row.get("url", "").startswith("https://") for row in payload["datasets"])
    assert all(row.get("provenance_url", "").startswith("https://") for row in payload["datasets"])
    assert all(row.get("citation") for row in payload["datasets"])
    serialized = json.dumps(payload)
    assert "sample_id" not in serialized and "source_sha256" not in serialized
    assert path.stat().st_size < 100_000
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
        assert sum(not str(row.get("matrix") or "").strip() for row in local_rows) == 240
    print(
        f"S7.5 public monitoring payload passed: {len(payload['datasets'])} sources, "
        f"0 public observations, {path.stat().st_size} bytes"
    )


if __name__ == "__main__":
    main()
