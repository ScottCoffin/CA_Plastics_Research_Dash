"""Machine acceptance check for S1.3 California geography assets."""

from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
from shapely import get_num_coordinates
from shapely.geometry import shape

from atlas.geo.ca_polygons import DEFAULT_LAND_PATH, DEFAULT_STATE_WATERS_PATH, in_ca

ROOT = Path(__file__).resolve().parents[1]
BROWSER_PATH = ROOT / "site" / "assets" / "ca_boundaries.geojson"
MAX_BROWSER_BYTES = 1_000_000


def _features(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as stream:
        payload = json.load(stream)
    assert payload["type"] == "FeatureCollection"
    assert payload["features"]
    return payload["features"]


def main() -> None:
    land = gpd.read_parquet(DEFAULT_LAND_PATH)
    waters = gpd.read_parquet(DEFAULT_STATE_WATERS_PATH)
    browser_features = _features(BROWSER_PATH)

    assert len(land) == 1 and land.iloc[0]["boundary"] == "land"
    assert len(waters) == 1 and waters.iloc[0]["boundary"] == "state_waters"
    assert BROWSER_PATH.stat().st_size < MAX_BROWSER_BYTES
    assert {feature["properties"]["boundary"] for feature in browser_features} == {
        "land",
        "state_waters",
    }
    full_coordinates = sum(get_num_coordinates(geometry) for geometry in land.geometry)
    full_coordinates += sum(get_num_coordinates(geometry) for geometry in waters.geometry)
    browser_coordinates = sum(
        get_num_coordinates(shape(feature["geometry"])) for feature in browser_features
    )
    assert browser_coordinates < full_coordinates

    known_points = {
        "Sacramento, CA": (38.5816, -121.4944, "land"),
        "about 1 nm west of San Francisco": (37.75, -122.53, "state_waters"),
        "about 10 nm west of San Francisco": (37.75, -122.75, "none"),
        "Eugene, OR": (44.0521, -123.0868, "none"),
    }
    for label, (lat, lon, expected) in known_points.items():
        actual = in_ca(lat, lon)
        assert actual == expected, f"{label}: expected {expected}, got {actual}"

    print(f"full_coordinates={full_coordinates}")
    print(f"browser_coordinates={browser_coordinates}")
    print(f"browser_bytes={BROWSER_PATH.stat().st_size} (<{MAX_BROWSER_BYTES})")
    print(f"known_points={len(known_points)} passed")


if __name__ == "__main__":
    main()
