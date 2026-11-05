from __future__ import annotations

import math

import pytest

from atlas.geo.ca_polygons import in_ca


@pytest.mark.parametrize(
    ("lat", "lon", "expected"),
    [
        (38.5816, -121.4944, "land"),
        (37.75, -122.53, "state_waters"),
        (37.75, -122.75, "none"),
        (44.0521, -123.0868, "none"),
    ],
)
def test_in_ca_known_points(lat: float, lon: float, expected: str) -> None:
    assert in_ca(lat, lon) == expected


@pytest.mark.parametrize(
    ("lat", "lon"),
    [(91, 0), (0, -181), (math.nan, 0), (None, 0), ("north", "west")],
)
def test_in_ca_rejects_invalid_coordinates(lat, lon) -> None:
    with pytest.raises(ValueError):
        in_ca(lat, lon)
