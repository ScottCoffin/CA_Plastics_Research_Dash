"""Add-on A2 acceptance test EAT-12: the regional feature service returns nine features and
the four point checks behave as recorded in section 4.

Owning EM task: EM-2.

Offline only: reads the committed processed asset (data/processed/geo/rwqcb_regions.parquet)
and makes no network calls.
"""

import geopandas as gpd
import pytest

from atlas.geo.rwqcb import (
    DEFAULT_REGIONS_PATH,
    EXPECTED_REGION_NAMES,
    OFFSHORE_OR_UNASSIGNED,
    assign_region,
    validate_region_frame,
)


def test_eat12_nine_regional_features_with_codes_one_to_nine() -> None:
    frame = validate_region_frame(gpd.read_parquet(DEFAULT_REGIONS_PATH))

    assert len(frame) == 9
    assert frame["rb"].tolist() == list(range(1, 10))
    assert frame["rb_name"].tolist() == [EXPECTED_REGION_NAMES[code] for code in range(1, 10)]


@pytest.mark.parametrize(
    ("name", "lat", "lon", "expected"),
    [
        ("Sacramento", 38.5816, -121.4944, "5"),
        ("San Francisco Bay", 37.80, -122.35, "2"),
        ("offshore about 60 km", 37.70, -123.20, OFFSHORE_OR_UNASSIGNED),
        ("offshore about 20 km", 37.70, -122.75, OFFSHORE_OR_UNASSIGNED),
    ],
)
def test_eat12_four_point_checks(name: str, lat: float, lon: float, expected: str) -> None:
    assert assign_region(lat, lon) == expected, name
