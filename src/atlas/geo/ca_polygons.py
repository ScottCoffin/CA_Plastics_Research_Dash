"""Point-in-polygon classification for California land and state waters."""

from __future__ import annotations

import math
from functools import lru_cache
from pathlib import Path
from typing import Literal

import geopandas as gpd
from shapely.geometry import Point

Location = Literal["land", "state_waters", "none"]

_REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_LAND_PATH = _REPO_ROOT / "data" / "processed" / "geo" / "ca_land.parquet"
DEFAULT_STATE_WATERS_PATH = _REPO_ROOT / "data" / "processed" / "geo" / "ca_state_waters.parquet"


def _boundary_geometry(path: Path):
    frame = gpd.read_parquet(path)
    if frame.empty or "geometry" not in frame:
        raise ValueError(f"Expected a non-empty GeoParquet geometry: {path}")
    return frame.geometry.union_all()


@lru_cache(maxsize=8)
def _load_boundaries(land_path: str, state_waters_path: str):
    land = _boundary_geometry(Path(land_path))
    state_waters = _boundary_geometry(Path(state_waters_path))
    return land, state_waters


def in_ca(
    lat: float,
    lon: float,
    *,
    land_path: str | Path = DEFAULT_LAND_PATH,
    state_waters_path: str | Path = DEFAULT_STATE_WATERS_PATH,
) -> Location:
    """Classify a WGS84 point as California land, state waters, or neither.

    Boundary points count as inside. Land takes precedence if source polygons
    touch or overlap at the shoreline.
    """

    try:
        latitude = float(lat)
        longitude = float(lon)
    except (TypeError, ValueError) as exc:
        raise ValueError("lat and lon must be finite numeric values") from exc
    if not math.isfinite(latitude) or not math.isfinite(longitude):
        raise ValueError("lat and lon must be finite numeric values")
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        raise ValueError("lat or lon is outside the WGS84 coordinate range")

    land, state_waters = _load_boundaries(str(land_path), str(state_waters_path))
    point = Point(longitude, latitude)
    if land.covers(point):
        return "land"
    if state_waters.covers(point):
        return "state_waters"
    return "none"
