"""Regional Water Board assignment for WGS84 points (Add-on A2 EM-2).

Rule (A2 section 4, A2-D11): a point inside a Regional Board polygon gets that
board's code; otherwise a point inside the S1.3 state-waters polygon gets
``offshore_state_waters``; otherwise ``offshore_or_unassigned``. The region wins
where both apply (for example San Francisco Bay).
"""

from __future__ import annotations

import math
from functools import lru_cache
from pathlib import Path
from typing import NamedTuple

import geopandas as gpd
from shapely import STRtree
from shapely.geometry import MultiPolygon, Point, Polygon
from shapely.prepared import prep

REGION_CODES: tuple[str, ...] = ("1", "2", "3", "4", "5", "6", "7", "8", "9")
OFFSHORE_STATE_WATERS = "offshore_state_waters"
OFFSHORE_OR_UNASSIGNED = "offshore_or_unassigned"
STATEWIDE_UNSPECIFIED = "statewide_unspecified"

EXPECTED_REGION_NAMES: dict[int, str] = {
    1: "North Coast",
    2: "San Francisco Bay",
    3: "Central Coast",
    4: "Los Angeles",
    5: "Central Valley",
    6: "Lahontan",
    7: "Colorado River",
    8: "Santa Ana",
    9: "San Diego",
}

_REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_REGIONS_PATH = _REPO_ROOT / "data" / "processed" / "geo" / "rwqcb_regions.parquet"
DEFAULT_STATE_WATERS_PATH = _REPO_ROOT / "data" / "processed" / "geo" / "ca_state_waters.parquet"

REGIONAL_DISCLAIMER = (
    "Regional Water Board boundaries come from the California Water Boards' 'Regional Board "
    "Boundary Features' feature service and are only as accurate as that source. The Water "
    "Boards describe the boundaries as generally based on watersheds, with official legal "
    "definitions in Water Code Section 13200. Region assignments for studies are derived from "
    "sampled coordinates and may be wrong near boundaries; points offshore are not assigned to "
    "a Regional Board by this layer. Geometry shown may be simplified for web display."
)
DISCLAIMER_LINKS: tuple[str, ...] = (
    "https://gispublic.waterboards.ca.gov/portalserver/rest/services/Hosted/"
    "Regional_Board_Boundary_Features/FeatureServer/1",
    "https://gis.data.ca.gov/datasets/waterboards::regional-board-boundaries",
)


class _RegionIndex(NamedTuple):
    codes: tuple[str, ...]
    tree: STRtree


def _polygonal(geometry) -> bool:
    return isinstance(geometry, (Polygon, MultiPolygon))


def validate_region_frame(frame: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Return ``frame`` reduced to rb (int), rb_name, geometry, sorted by rb.

    Raises ValueError unless there are exactly nine features with codes 1-9, the
    expected names, non-empty valid polygonal geometry, and CRS EPSG:4326.
    """

    missing = [column for column in ("rb", "rb_name", "geometry") if column not in frame]
    if missing:
        raise ValueError(f"regional layer is missing columns: {missing}")
    if frame.crs is None or frame.crs.to_epsg() != 4326:
        raise ValueError("regional layer must be in EPSG:4326")
    if len(frame) != 9:
        raise ValueError(f"regional layer must have exactly 9 features, found {len(frame)}")

    codes: list[int] = []
    for value in frame["rb"]:
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"rb code is not numeric: {value!r}") from exc
        if not number.is_integer():
            raise ValueError(f"rb code is not an integer: {value!r}")
        codes.append(int(number))
    if sorted(codes) != list(range(1, 10)):
        raise ValueError(f"rb codes must be exactly 1-9, found {sorted(codes)}")

    for code, name in zip(codes, frame["rb_name"], strict=True):
        if EXPECTED_REGION_NAMES[code] != name:
            raise ValueError(
                f"rb {code} must be named {EXPECTED_REGION_NAMES[code]!r}, found {name!r}"
            )

    for code, geometry in zip(codes, frame.geometry, strict=True):
        if geometry is None or geometry.is_empty or not _polygonal(geometry):
            raise ValueError(f"rb {code} geometry is missing, empty, or not polygonal")
        if not geometry.is_valid:
            raise ValueError(f"rb {code} geometry is not valid")

    result = gpd.GeoDataFrame(
        {
            "rb": codes,
            "rb_name": [str(name) for name in frame["rb_name"]],
            "geometry": list(frame.geometry),
        },
        geometry="geometry",
        crs="EPSG:4326",
    )
    return result.sort_values("rb", kind="stable").reset_index(drop=True)


def _coordinates(lat: float, lon: float) -> tuple[float, float]:
    try:
        latitude = float(lat)
        longitude = float(lon)
    except (TypeError, ValueError) as exc:
        raise ValueError("lat and lon must be finite numeric values") from exc
    if not math.isfinite(latitude) or not math.isfinite(longitude):
        raise ValueError("lat and lon must be finite numeric values")
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        raise ValueError("lat or lon is outside the WGS84 coordinate range")
    return latitude, longitude


@lru_cache(maxsize=4)
def _load_region_index(path: str) -> _RegionIndex:
    frame = validate_region_frame(gpd.read_parquet(path))
    codes = tuple(str(code) for code in frame["rb"])
    return _RegionIndex(codes=codes, tree=STRtree(list(frame.geometry)))


@lru_cache(maxsize=4)
def _load_state_waters(path: str):
    frame = gpd.read_parquet(path)
    if frame.empty or frame.crs is None:
        raise ValueError(f"Expected a non-empty CRS-tagged state-waters layer: {path}")
    if frame.crs.to_epsg() != 4326:
        frame = frame.to_crs(4326)
    return prep(frame.geometry.union_all())


def assign_region(
    lat: float,
    lon: float,
    *,
    regions_path: str | Path = DEFAULT_REGIONS_PATH,
    state_waters_path: str | Path = DEFAULT_STATE_WATERS_PATH,
) -> str:
    """Return the Regional Board code ("1"-"9") or an offshore value for a WGS84 point.

    Boundary points count as inside. When the region layer has overlapping
    polygons after simplification, the lowest rb code wins (deterministic).
    """

    latitude, longitude = _coordinates(lat, lon)
    point = Point(longitude, latitude)

    index = _load_region_index(str(regions_path))
    hits = index.tree.query(point, predicate="intersects")
    if len(hits):
        return index.codes[int(min(hits))]

    if _load_state_waters(str(state_waters_path)).covers(point):
        return OFFSHORE_STATE_WATERS
    return OFFSHORE_OR_UNASSIGNED
