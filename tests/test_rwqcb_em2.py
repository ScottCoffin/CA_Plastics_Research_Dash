"""Offline tests for the Add-on A2 EM-2 Regional Water Board layer and offshore rule.

Reads only the committed processed asset and synthetic fixtures built in tmp_path.
No network, no raw download, no dependency on the raw GeoJSON.
"""

from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path

import geopandas as gpd
import pyarrow.parquet as pq
import pytest
import shapely
from shapely.geometry import Point, Polygon, box

from atlas.geo import rwqcb
from atlas.geo.rwqcb import (
    DEFAULT_REGIONS_PATH,
    DEFAULT_STATE_WATERS_PATH,
    DISCLAIMER_LINKS,
    EXPECTED_REGION_NAMES,
    OFFSHORE_OR_UNASSIGNED,
    OFFSHORE_STATE_WATERS,
    REGION_CODES,
    REGIONAL_DISCLAIMER,
    STATEWIDE_UNSPECIFIED,
    assign_region,
    validate_region_frame,
)

ROOT = Path(__file__).resolve().parents[1]
BUILD_SCRIPT = ROOT / "scripts" / "build_rwqcb_regions.py"


def _load_build_script():
    spec = importlib.util.spec_from_file_location("build_rwqcb_regions", BUILD_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _synthetic_regions(codes: list[int] | None = None) -> gpd.GeoDataFrame:
    codes = list(range(1, 10)) if codes is None else codes
    rows = [
        {
            "rb": code,
            "rb_name": EXPECTED_REGION_NAMES[code],
            "geometry": box(index, 0, index + 1, 1),
        }
        for index, code in enumerate(codes)
    ]
    return gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:4326")


def test_committed_asset_has_nine_named_regions() -> None:
    frame = validate_region_frame(gpd.read_parquet(DEFAULT_REGIONS_PATH))

    assert len(frame) == 9
    assert frame["rb"].tolist() == list(range(1, 10))
    assert frame["rb_name"].tolist() == [EXPECTED_REGION_NAMES[n] for n in range(1, 10)]
    assert str(frame.crs.to_epsg()) == "4326"


def test_region_codes_are_strings_one_to_nine() -> None:
    assert REGION_CODES == ("1", "2", "3", "4", "5", "6", "7", "8", "9")


def test_committed_asset_provenance_and_size() -> None:
    metadata = pq.read_metadata(DEFAULT_REGIONS_PATH).metadata
    provenance = json.loads(metadata[b"atlas_provenance"].decode("utf-8"))

    assert provenance["retrieved"] == "2026-11-09"
    assert provenance["raw_sha256"] == (
        "25576df6ee9551a35a3d424bd9956e31bd4859a8468a63a36582db676e70d490"
    )
    assert provenance["source_url"].startswith(DISCLAIMER_LINKS[0])
    assert provenance["licence"] == (
        "Custom License (text not retrieved); owner-determined open use with mandatory disclaimer"
    )
    assert provenance["simplify_tolerance_deg"] > 0
    assert DEFAULT_REGIONS_PATH.stat().st_size <= 1_500_000


@pytest.mark.parametrize(
    ("lat", "lon", "expected"),
    [
        (38.5816, -121.4944, "5"),  # Sacramento, Central Valley
        (37.80, -122.35, "2"),  # San Francisco Bay
        (37.76, -122.545, OFFSHORE_STATE_WATERS),  # about 3 km off Ocean Beach
        (37.70, -123.00, OFFSHORE_STATE_WATERS),  # near the Farallones
        (37.70, -123.20, OFFSHORE_OR_UNASSIGNED),  # about 60 km offshore
        (37.70, -122.75, OFFSHORE_OR_UNASSIGNED),  # about 20 km offshore
    ],
)
def test_assign_region_known_points(lat: float, lon: float, expected: str) -> None:
    assert assign_region(lat, lon) == expected


@pytest.mark.parametrize(
    ("lat", "lon"),
    [
        (91, 0),
        (-91, 0),
        (0, 181),
        (0, -181),
        (math.nan, 0),
        (math.inf, 0),
        (0, -math.inf),
        (None, 0),
        ("north", "west"),
    ],
)
def test_assign_region_rejects_invalid_coordinates(lat: object, lon: object) -> None:
    with pytest.raises(ValueError):
        assign_region(lat, lon)


def test_region_wins_over_state_waters_and_offshore_values_apply(tmp_path: Path) -> None:
    regions_path = tmp_path / "regions.parquet"
    waters_path = tmp_path / "waters.parquet"
    _synthetic_regions().to_parquet(regions_path, index=False)
    # Covers region 3's footprint plus a strip at x 9..10, so a point can be in both.
    gpd.GeoDataFrame(
        {"boundary": ["state_waters"]},
        geometry=[box(2.5, 0, 3.5, 1).union(box(9, 0, 10, 1))],
        crs="EPSG:4326",
    ).to_parquet(waters_path, index=False)

    def classify(lat: float, lon: float) -> str:
        return assign_region(lat, lon, regions_path=regions_path, state_waters_path=waters_path)

    assert classify(0.5, 2.7) == "3"  # inside region 3 and state waters: region wins
    assert classify(0.5, 9.5) == OFFSHORE_STATE_WATERS
    assert classify(0.5, 20.0) == OFFSHORE_OR_UNASSIGNED


def test_disclaimer_text_and_links_are_exact() -> None:
    assert REGIONAL_DISCLAIMER == (
        "Regional Water Board boundaries come from the California Water Boards' 'Regional Board "
        "Boundary Features' feature service and are only as accurate as that source. The Water "
        "Boards describe the boundaries as generally based on watersheds, with official legal "
        "definitions in Water Code Section 13200. Region assignments for studies are derived from "
        "sampled coordinates and may be wrong near boundaries; points offshore are not assigned "
        "to a Regional Board by this layer. Geometry shown may be simplified for web display."
    )
    assert DISCLAIMER_LINKS == (
        "https://gispublic.waterboards.ca.gov/portalserver/rest/services/Hosted/"
        "Regional_Board_Boundary_Features/FeatureServer/1",
        "https://gis.data.ca.gov/datasets/waterboards::regional-board-boundaries",
    )


def test_statewide_value_is_distinct() -> None:
    assert STATEWIDE_UNSPECIFIED == "statewide_unspecified"
    assert len({OFFSHORE_STATE_WATERS, OFFSHORE_OR_UNASSIGNED, STATEWIDE_UNSPECIFIED}) == 3


def test_state_waters_default_path_points_at_s1_3_asset() -> None:
    assert DEFAULT_STATE_WATERS_PATH.name == "ca_state_waters.parquet"
    assert rwqcb.DEFAULT_REGIONS_PATH.name == "rwqcb_regions.parquet"


def test_validate_accepts_nine_named_features() -> None:
    frame = validate_region_frame(_synthetic_regions())

    assert list(frame.columns) == ["rb", "rb_name", "geometry"]
    assert frame["rb"].tolist() == list(range(1, 10))


def test_validate_accepts_string_codes() -> None:
    frame = _synthetic_regions()
    frame["rb"] = [str(code) for code in frame["rb"]]

    assert validate_region_frame(frame)["rb"].tolist() == list(range(1, 10))


def test_validate_rejects_wrong_feature_count() -> None:
    with pytest.raises(ValueError, match="exactly 9"):
        validate_region_frame(_synthetic_regions(codes=list(range(1, 9))))


def test_validate_rejects_missing_code() -> None:
    with pytest.raises(ValueError, match="exactly 1-9"):
        validate_region_frame(_synthetic_regions(codes=[1, 2, 3, 4, 5, 6, 7, 8, 8]))


def test_validate_rejects_wrong_name() -> None:
    frame = _synthetic_regions()
    frame.loc[frame["rb"] == 3, "rb_name"] = "Central Coast Basin"

    with pytest.raises(ValueError, match="must be named 'Central Coast'"):
        validate_region_frame(frame)


def test_validate_rejects_non_polygonal_geometry() -> None:
    frame = _synthetic_regions()
    frame.loc[frame.index[0], "geometry"] = Point(0, 0)

    with pytest.raises(ValueError, match="not polygonal"):
        validate_region_frame(frame)


def test_validate_rejects_invalid_geometry() -> None:
    frame = _synthetic_regions()
    bowtie = Polygon([(0, 0), (1, 1), (1, 0), (0, 1)])
    frame.loc[frame.index[0], "geometry"] = bowtie

    with pytest.raises(ValueError, match="not valid"):
        validate_region_frame(frame)


def test_validate_rejects_wrong_crs() -> None:
    frame = _synthetic_regions().to_crs(3310)

    with pytest.raises(ValueError, match="EPSG:4326"):
        validate_region_frame(frame)


def test_validate_rejects_missing_column() -> None:
    frame = _synthetic_regions().drop(columns=["rb_name"])

    with pytest.raises(ValueError, match="missing columns"):
        validate_region_frame(frame)


def test_close_slivers_fills_thin_interior_gap() -> None:
    build = _load_build_script()
    gap = 1e-6  # well under the 1e-5 deg^2 sliver limit
    pieces = [
        box(0, 0, 1, 3),
        box(2, 0, 3, 3),
        box(1, 0, 2, 1),
        box(1, 1 + gap, 2, 2),
    ]
    assert len(shapely.get_parts(shapely.union_all(pieces))) == 1
    union_before = shapely.union_all(pieces)
    assert shapely.get_num_interior_rings(shapely.get_parts(union_before)).sum() == 1

    closed = build._close_slivers(list(pieces))
    union_after = shapely.union_all(closed)

    assert shapely.get_num_interior_rings(shapely.get_parts(union_after)).sum() == 0
    assert all(geometry.is_valid for geometry in closed)


def test_close_slivers_rejects_large_gap() -> None:
    build = _load_build_script()
    pieces = [box(0, 0, 1, 3), box(2, 0, 3, 3), box(1, 0, 2, 1), box(1, 1.01, 2, 2)]

    with pytest.raises(ValueError, match="sliver limit"):
        build._close_slivers(list(pieces))


def test_verify_sha256_guards_mismatch(tmp_path: Path) -> None:
    build = _load_build_script()
    raw = tmp_path / "raw.geojson"
    raw.write_bytes(b"not the pinned export")

    with pytest.raises(SystemExit, match="SHA-256 mismatch"):
        build.verify_sha256(raw, allow_sha_change=False)
    assert build.verify_sha256(raw, allow_sha_change=True) == build.sha256_file(raw)


def test_build_rejects_wrong_feature_count_before_writing(tmp_path: Path) -> None:
    build = _load_build_script()
    raw = tmp_path / "raw.geojson"
    _synthetic_regions(codes=list(range(1, 9))).to_file(raw, driver="GeoJSON")
    output = tmp_path / "out" / "rwqcb_regions.parquet"

    with pytest.raises(ValueError, match="exactly 9"):
        build.build(raw, output, allow_sha_change=True)
    assert not output.exists()
