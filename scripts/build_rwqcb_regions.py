"""Build the committed Regional Water Board GeoParquet from the raw feature-service export.

Reads the GeoJSON exported from the California Water Boards "Regional Board Boundary
Features" service (see docs/api_notes/rwqcb_regions.md), verifies its SHA-256, validates
the nine features, simplifies the geometry for a small committed asset, and writes
data/processed/geo/rwqcb_regions.parquet with provenance in the GeoParquet file metadata.
Offline: reads only the local raw file.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import geopandas as gpd
import pyarrow.parquet as pq
import shapely
from shapely.geometry import MultiPolygon, Polygon
from shapely.validation import make_valid

from atlas.geo.rwqcb import validate_region_frame

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RAW_PATH = ROOT / "data" / "raw" / "rwqcb" / "regional_board_boundaries.geojson"
OUTPUT_PATH = ROOT / "data" / "processed" / "geo" / "rwqcb_regions.parquet"

SERVICE_LAYER_URL = (
    "https://gispublic.waterboards.ca.gov/portalserver/rest/services/Hosted/"
    "Regional_Board_Boundary_Features/FeatureServer/1"
)
SOURCE_URL = f"{SERVICE_LAYER_URL}/query?where=1%3D1&outFields=*&outSR=4326&f=geojson"
RETRIEVED = "2026-11-09"
EXPECTED_SHA256 = "25576df6ee9551a35a3d424bd9956e31bd4859a8468a63a36582db676e70d490"
LICENCE = "Custom License (text not retrieved); owner-determined open use with mandatory disclaimer"
# 0.0002 degrees is about 22 m north-south and about 18 m east-west at 38 N.
DEFAULT_TOLERANCE_DEG = 0.0002
MAX_ASSET_BYTES = 1_500_000
# Holes left by per-feature simplification are slivers (about 1e-6 deg^2 at most); the raw
# union has no hole above 1e-8 deg^2. Larger holes fail the build.
SLIVER_MAX_DEG2 = 1e-5
PROVENANCE_KEY = b"atlas_provenance"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_sha256(path: Path, *, allow_sha_change: bool) -> str:
    actual = sha256_file(path)
    if actual != EXPECTED_SHA256 and not allow_sha_change:
        raise SystemExit(
            f"raw SHA-256 mismatch for {path.name}: expected {EXPECTED_SHA256}, got {actual}. "
            "Re-run with --allow-sha-change only after reviewing the new export."
        )
    return actual


def _repair(geometry):
    """Return a valid polygonal geometry, repairing with make_valid only when needed."""

    if geometry.is_valid:
        return geometry
    parts = [
        part for part in shapely.get_parts(make_valid(geometry)) if part.geom_type == "Polygon"
    ]
    if not parts:
        raise ValueError("make_valid produced no polygonal geometry")
    return parts[0] if len(parts) == 1 else MultiPolygon(parts)


def _close_slivers(geometries: list) -> list:
    """Merge simplification slivers (interior holes of the union) into the nearest region.

    Independent per-feature simplification can open thin gaps between neighbouring
    regions. A point in such a gap would otherwise fall through to an offshore value.
    """

    union = shapely.union_all(geometries)
    polygons = list(union.geoms) if union.geom_type == "MultiPolygon" else [union]
    holes = [Polygon(ring) for polygon in polygons for ring in polygon.interiors]
    for hole in holes:
        if hole.area > SLIVER_MAX_DEG2:
            raise ValueError(f"gap of {hole.area} deg^2 exceeds the sliver limit")
        point = hole.representative_point()
        target = min(
            range(len(geometries)),
            key=lambda index: (geometries[index].distance(point), index),
        )
        geometries[target] = _repair(shapely.union(geometries[target], hole))
    return geometries


def build(
    raw_path: Path = DEFAULT_RAW_PATH,
    output_path: Path = OUTPUT_PATH,
    *,
    allow_sha_change: bool = False,
    tolerance: float = DEFAULT_TOLERANCE_DEG,
) -> dict[str, object]:
    if not raw_path.is_file():
        raise SystemExit(f"raw regional layer not found: {raw_path}")
    digest = verify_sha256(raw_path, allow_sha_change=allow_sha_change)

    validated = validate_region_frame(gpd.read_file(raw_path))
    simplified = validated.copy()
    simplified["geometry"] = _close_slivers(
        [
            _repair(geometry.simplify(tolerance, preserve_topology=True))
            for geometry in validated.geometry
        ]
    )
    frame = validate_region_frame(simplified)
    raw_parts = len(shapely.get_parts(shapely.union_all(validated.geometry.values)))
    simplified_union = shapely.union_all(frame.geometry.values)
    if (
        len(shapely.get_parts(simplified_union)) != raw_parts
        or shapely.get_num_interior_rings(shapely.get_parts(simplified_union)).any()
    ):
        raise ValueError("simplified union changed its part count or left interior gaps")

    provenance = {
        "source_name": "California Water Boards 'Regional Board Boundary Features'",
        "service_layer_url": SERVICE_LAYER_URL,
        "source_url": SOURCE_URL,
        "retrieved": RETRIEVED,
        "raw_file": raw_path.name,
        "raw_sha256": digest,
        "expected_raw_sha256": EXPECTED_SHA256,
        "simplify_tolerance_deg": tolerance,
        "simplify_tolerance_m_approx": "about 22 m N-S, 18 m E-W at 38 N",
        "simplify_method": "shapely simplify(preserve_topology=True), make_valid if needed, "
        "then merge interior sliver holes (< 1e-5 deg^2) into the nearest region",
        "licence": LICENCE,
        "crs": "EPSG:4326",
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(output_path, index=False)
    # Keep the GeoParquet "geo" metadata written by geopandas and add provenance beside it.
    table = pq.read_table(output_path)
    metadata = dict(table.schema.metadata or {})
    metadata[PROVENANCE_KEY] = json.dumps(provenance, sort_keys=True).encode("utf-8")
    pq.write_table(table.replace_schema_metadata(metadata), output_path)
    size = output_path.stat().st_size
    if size > MAX_ASSET_BYTES:
        raise SystemExit(f"asset is {size} bytes, above the {MAX_ASSET_BYTES} byte limit")
    return {
        "features": len(frame),
        "vertices": int(shapely.get_num_coordinates(frame.geometry.values).sum()),
        "bytes": size,
        "tolerance_deg": tolerance,
        "raw_sha256": digest,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("raw", nargs="?", type=Path, default=DEFAULT_RAW_PATH)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--tolerance", type=float, default=DEFAULT_TOLERANCE_DEG)
    parser.add_argument(
        "--allow-sha-change",
        action="store_true",
        help="Accept a raw file whose SHA-256 differs from the pinned value",
    )
    args = parser.parse_args()
    summary = build(
        args.raw,
        args.output,
        allow_sha_change=args.allow_sha_change,
        tolerance=args.tolerance,
    )
    print(f"output={args.output}")
    for key, value in summary.items():
        print(f"{key}={value}")


if __name__ == "__main__":
    main()
